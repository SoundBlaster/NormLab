import { createHash, randomBytes, randomUUID, timingSafeEqual } from 'node:crypto';
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import { mkdirSync, readFileSync, existsSync, statSync } from 'node:fs';
import { extname, join, resolve } from 'node:path';
import { z } from 'zod';
import {
  bundleIdSchema,
  snapshotInputSchema,
  type Analysis,
  type Bootstrap,
} from '../shared/domain.js';
import { bundles, getBundle } from './bundles.js';
import { compare, propose } from './interpreter.js';
import { ReceiptSigner, verifyReceipt } from './receipts.js';
import { Conflict, Store } from './store.js';
import { discoverLean, verifyCertificate } from './verifier.js';
import { isCurrentAnalysis } from '../shared/current.js';
import { LabHttpError, ReformLab } from './reform-lab.js';
import { isWithinDirectory } from './path-containment.js';
import { MAX_EXPERIMENT_BYTES } from '../shared/reform-transfer.js';
import { ParkingReview, ParkingReviewError } from './parking-review.js';
import { ParkingJobError } from './parking-jobs.js';
import type { ParkingExtractor } from './inference-client.js';

class HttpError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}
async function readBody(req: IncomingMessage, limit = 32768): Promise<unknown> {
  if (!req.headers['content-type']?.startsWith('application/json'))
    throw new HttpError(415, 'Ожидается application/json.');
  const chunks: Buffer[] = [];
  let bytes = 0;
  for await (const chunk of req) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    bytes += buffer.length;
    if (bytes > limit) throw new HttpError(413, 'Слишком большой запрос.');
    chunks.push(buffer);
  }
  try {
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(chunks)));
  } catch {
    throw new HttpError(400, 'Некорректный JSON.');
  }
}
function send(res: ServerResponse, status: number, body: unknown): void {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  res.end(JSON.stringify(body));
}
function matchesSecret(candidate: string, expected: string): boolean {
  const candidateDigest = createHash('sha256').update(candidate).digest();
  const expectedDigest = createHash('sha256').update(expected).digest();
  return timingSafeEqual(candidateDigest, expectedDigest);
}
function hasOperatorCredentials(
  header: string | undefined,
  username: string,
  password: string,
): boolean {
  if (!header?.startsWith('Basic ') || header.length > 8192) return false;
  let credentials: string;
  try {
    credentials = Buffer.from(header.slice(6), 'base64').toString('utf8');
  } catch {
    return false;
  }
  const separator = credentials.indexOf(':');
  if (separator < 0) return false;
  return (
    matchesSecret(credentials.slice(0, separator), username) &&
    matchesSecret(credentials.slice(separator + 1), password)
  );
}
const analysisInput = z
  .object({ snapshotId: z.string().uuid(), bundleId: bundleIdSchema })
  .strict();
const snapshotRequest = z
  .object({ input: snapshotInputSchema, expectedSnapshotId: z.string().uuid() })
  .strict();

export async function createApp(options: {
  dataDir: string;
  production?: boolean;
  web?: boolean;
  publicOrigin?: string;
  operatorAuth?: { username: string; password: string };
  parkingExtractor?: ParkingExtractor | null;
}) {
  const publicOrigin = options.publicOrigin ? new URL(options.publicOrigin).origin : undefined;
  if (options.publicOrigin && publicOrigin !== options.publicOrigin)
    throw new Error('NORMLAB_PUBLIC_ORIGIN must contain only an origin, without a path.');
  if (
    options.operatorAuth &&
    (!publicOrigin?.startsWith('https://') ||
      !options.operatorAuth.username ||
      !options.operatorAuth.password)
  )
    throw new Error('Protected deployment requires HTTPS origin and operator credentials.');
  mkdirSync(options.dataDir, { recursive: true, mode: 0o700 });
  const store = new Store(join(options.dataDir, 'normlab.sqlite'));
  const signer = new ReceiptSigner(options.dataDir);
  const csrfToken = randomBytes(32).toString('hex');
  const running = new Map<string, Promise<Analysis>>();
  const lab = new ReformLab(options.dataDir, () => running.size);
  const parking = new ParkingReview(options.dataDir, options.parkingExtractor);
  const vite =
    options.web !== false && !options.production
      ? await (
          await import('vite')
        ).createServer({ server: { middlewareMode: true }, appType: 'spa' })
      : null;

  const server = createServer(async (req, res) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Referrer-Policy', 'no-referrer');
    res.setHeader('X-Frame-Options', 'DENY');
    try {
      const requestUrl = new URL(req.url ?? '/', 'http://normlab.local');
      if (requestUrl.pathname === '/health' && req.method === 'GET') {
        send(res, 200, { ok: true });
        return;
      }
      if (
        options.operatorAuth &&
        !hasOperatorCredentials(
          req.headers.authorization,
          options.operatorAuth.username,
          options.operatorAuth.password,
        )
      ) {
        res.writeHead(401, {
          'WWW-Authenticate': 'Basic realm="NormLab private", charset="UTF-8"',
          'Cache-Control': 'no-store',
          'Content-Type': 'text/plain; charset=utf-8',
        });
        res.end('Authentication required.');
        return;
      }
      const host = req.headers.host;
      const allowedHosts = publicOrigin
        ? [new URL(publicOrigin).host]
        : [`127.0.0.1:${req.socket.localPort}`, `localhost:${req.socket.localPort}`];
      if (!host || !allowedHosts.includes(host)) throw new HttpError(403, 'Недопустимый Host.');
      if (
        (req.headers.origin && req.headers.origin !== (publicOrigin ?? `http://${host}`)) ||
        (options.operatorAuth && req.method === 'POST' && req.headers.origin !== publicOrigin)
      )
        throw new HttpError(403, 'Недопустимый Origin.');
      const url = new URL(req.url ?? '/', `http://${host}`);
      const path = url.pathname;
      if (path.startsWith('/api/')) {
        if (req.method === 'POST' && req.headers['x-normlab-token'] !== csrfToken)
          throw new HttpError(403, 'Обновите страницу: локальная сессия изменилась.');
        if (path.startsWith('/api/parking/')) {
          const result = await parking.handle(
            req.method ?? 'GET',
            path,
            req.method === 'POST' ? await readBody(req, 2 * 1024 * 1024) : undefined,
          );
          if (result === undefined) throw new HttpError(404, 'Parking route не найден.');
          send(res, 200, result);
          return;
        }
        if (path.startsWith('/api/reform/')) {
          if (req.method === 'GET' && path === '/api/reform/experiments/download') {
            const result = await lab.handle(
              'POST',
              '/api/reform/experiments/export',
              { analysisIds: url.searchParams.getAll('analysisId') },
              csrfToken,
            );
            if (!result) throw new HttpError(404, 'Экспорт не найден.');
            if (result.filename)
              res.setHeader('Content-Disposition', `attachment; filename="${result.filename}"`);
            send(res, result.status, result.body);
            return;
          }
          const result = await lab.handle(
            req.method ?? 'GET',
            path,
            req.method === 'POST'
              ? await readBody(
                  req,
                  path === '/api/reform/imports' ? MAX_EXPERIMENT_BYTES + 32768 : 65536,
                )
              : undefined,
            csrfToken,
          );
          if (!result) throw new HttpError(404, 'API route A/B/C не найден.');
          if (result.filename)
            res.setHeader('Content-Disposition', `attachment; filename="${result.filename}"`);
          send(res, result.status, result.body);
          return;
        }
        if (req.method === 'GET' && path === '/api/bootstrap') {
          const lean = await discoverLean();
          const data: Bootstrap = {
            csrfToken,
            workspace: store.workspace(),
            bundles,
            verifier: {
              available: lean.available,
              version: lean.version,
              toolchainDigest: lean.digest,
            },
            comparison: compare(getBundle('reduction-v1'), getBundle('reduction-v2')),
          };
          send(res, 200, data);
          return;
        }
        if (req.method === 'POST' && path === '/api/snapshots') {
          const input = snapshotRequest.parse(await readBody(req));
          const snapshot = store.createSnapshot(input.input, input.expectedSnapshotId);
          send(res, 201, { snapshot, workspace: store.workspace() });
          return;
        }
        if (req.method === 'POST' && path === '/api/analyze') {
          const input = analysisInput.parse(await readBody(req));
          const snapshot = store.snapshot(input.snapshotId);
          if (!snapshot) throw new HttpError(404, 'Снимок не найден.');
          const bundle = getBundle(input.bundleId);
          const toolchain = await discoverLean();
          const prior = store
            .workspace()
            .analyses.find(
              (a) =>
                isCurrentAnalysis(a, snapshot, bundle, toolchain.digest) &&
                a.receipt.payload.verification.status === 'verified' &&
                verifyReceipt(a.receipt, signer.publicKey),
            );
          if (prior) {
            send(res, 200, prior);
            return;
          }
          const key = `${snapshot.digest}:${bundle.semanticDigest}:${bundle.provenanceDigest}`;
          let job = running.get(key);
          if (!job) {
            if (running.size + lab.activeJobs >= 2)
              throw new HttpError(
                429,
                'Две проверки уже выполняются. Повторите через несколько секунд.',
              );
            job = (async () => {
              const certificate = propose(snapshot, bundle);
              const verification = await verifyCertificate(snapshot, bundle, certificate);
              const analysis: Analysis = {
                id: randomUUID(),
                snapshotId: snapshot.id,
                bundleId: bundle.id,
                bundle,
                certificate,
                receipt: signer.issue(snapshot, bundle, certificate, verification),
              };
              store.saveAnalysis(analysis);
              return analysis;
            })();
            running.set(key, job);
          }
          try {
            send(res, 200, await job);
          } finally {
            running.delete(key);
          }
          return;
        }
        const artifact = /^\/api\/analyses\/([a-f0-9-]{36})\/(export|signature)$/.exec(path);
        if (artifact) {
          const analysis = store.analysis(artifact[1]);
          if (!analysis) throw new HttpError(404, 'Результат не найден.');
          if (req.method === 'GET' && artifact[2] === 'export') {
            const lockedBundle = analysis.bundle ?? getBundle(analysis.bundleId);
            if (
              lockedBundle.semanticDigest !== analysis.receipt.payload.bundleSemanticDigest ||
              lockedBundle.provenanceDigest !== analysis.receipt.payload.bundleProvenanceDigest
            ) {
              throw new HttpError(409, 'Исторический пакет недоступен для полного экспорта.');
            }
            res.setHeader(
              'Content-Disposition',
              `attachment; filename="normlab-${analysis.id}.json"`,
            );
            send(res, 200, {
              schema: 'normlab.export/v1',
              snapshot: store.snapshot(analysis.snapshotId),
              bundle: lockedBundle,
              certificate: analysis.certificate,
              receipt: analysis.receipt,
            });
            return;
          }
          if (req.method === 'POST' && artifact[2] === 'signature') {
            send(res, 200, {
              valid: verifyReceipt(analysis.receipt, signer.publicKey),
              issuer: analysis.receipt.payload.issuer,
              scope: 'signature-and-payload-integrity',
            });
            return;
          }
        }
        throw new HttpError(404, 'API route не найден.');
      }
      if (req.method !== 'GET' && req.method !== 'HEAD')
        throw new HttpError(405, 'Метод не поддерживается.');
      if (vite) {
        vite.middlewares(req, res);
        return;
      }
      const directory = resolve('dist');
      const relative = decodeURIComponent(path).replace(/^\/+/, '');
      let file = resolve(directory, relative || 'index.html');
      if (!isWithinDirectory(directory, file)) throw new HttpError(404, 'Файл не найден.');
      if (!existsSync(file) || !statSync(file).isFile()) {
        if (extname(file)) throw new HttpError(404, 'Файл не найден.');
        file = join(directory, 'index.html');
      }
      if (!existsSync(file)) throw new HttpError(503, 'Сначала выполните npm run build.');
      const mime: Record<string, string> = {
        '.html': 'text/html; charset=utf-8',
        '.js': 'text/javascript',
        '.css': 'text/css',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
      };
      res.setHeader(
        'Content-Security-Policy',
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'",
      );
      res.writeHead(200, {
        'Content-Type': mime[extname(file)] ?? 'application/octet-stream',
        'Cache-Control': 'no-cache',
      });
      res.end(req.method === 'HEAD' ? undefined : readFileSync(file));
    } catch (error) {
      if (res.headersSent) {
        res.end();
        return;
      }
      if (error instanceof z.ZodError)
        send(res, 400, { error: error.issues[0]?.message ?? 'Некорректные данные.' });
      else if (error instanceof Conflict) send(res, 409, { error: error.message });
      else if (
        error instanceof HttpError ||
        error instanceof LabHttpError ||
        error instanceof ParkingReviewError ||
        error instanceof ParkingJobError
      )
        send(res, error.status, { error: error.message });
      else {
        console.error(error instanceof Error ? error.message : 'Server error');
        send(res, 500, {
          error:
            'Не удалось выполнить операцию. Сохранённые снимки доступны после обновления страницы.',
        });
      }
    }
  });
  return {
    server,
    store,
    lab,
    async close() {
      await Promise.allSettled(running.values());
      await lab.close();
      await vite?.close();
      if (server.listening)
        await new Promise<void>((resolveClose, reject) =>
          server.close((error) => (error ? reject(error) : resolveClose())),
        );
      store.close();
    },
  };
}
