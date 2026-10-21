import { createHash, timingSafeEqual } from 'node:crypto';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { ProxyAgent, fetch as undiciFetch } from 'undici';
import { inferenceGatewayConfig, type InferenceGatewayConfig } from './inference-config.js';
import { InferenceProviders } from './inference-providers.js';
import { MAX_INFERENCE_RESPONSE_BYTES } from './inference-http.js';
import { InferenceAccessError } from './inference-errors.js';
import { extractionInput, runHostedExtraction } from './hosted-extraction.js';
import { checkedHostedStage, hostedProfile, runHostedStage } from './hosted-stages.js';

/** Explicit route: no reliance on Node's bundled fetch sharing undici's global dispatcher. */
export function proxiedFetch(proxy: string): typeof fetch {
  const dispatcher = new ProxyAgent(proxy);
  return ((url: Parameters<typeof undiciFetch>[0], init?: Parameters<typeof undiciFetch>[1]) =>
    undiciFetch(url, { ...init, dispatcher })) as unknown as typeof fetch;
}

export function createInferenceGateway(
  config: InferenceGatewayConfig,
  fetcher: typeof fetch = fetch,
) {
  const providers = new InferenceProviders(config, fetcher);
  const secretHash = createHash('sha256').update(`Bearer ${config.token}`).digest();
  let active = false;
  let windowStart = Date.now();
  let requests = 0;
  const server = createServer(async (req, res) => {
    const send = (status: number, body: unknown) => {
      res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
      res.end(JSON.stringify(body));
    };
    if (req.url === '/health' && req.method === 'GET') {
      send(200, { ok: true });
      return;
    }
    const authorization = req.headers.authorization ?? '';
    if (
      authorization.length > 8199 ||
      !timingSafeEqual(createHash('sha256').update(authorization).digest(), secretHash)
    ) {
      send(401, { error: 'Authentication required.' });
      return;
    }
    // Exact RPC routes. No URL, model, schema, headers or tools accepted from the caller.
    if (
      req.method !== 'POST' ||
      !['/v1/extract', '/v1/profile', '/v1/stage'].includes(req.url ?? '')
    ) {
      send(404, { error: 'Unknown inference route.' });
      return;
    }
    if (active) {
      send(429, { error: 'Inference busy.' });
      return;
    }
    if (Date.now() - windowStart >= 3600000) {
      windowStart = Date.now();
      requests = 0;
    }
    if (req.url !== '/v1/profile' && requests >= config.requestsPerHour) {
      send(429, { error: 'Inference hourly limit reached.' });
      return;
    }
    if (!req.headers['content-type']?.startsWith('application/json')) {
      send(415, { error: 'Expected JSON.' });
      return;
    }
    active = true;
    const controller = new AbortController();
    const disconnected = () => {
      if (!res.writableEnded) controller.abort();
    };
    res.on('close', disconnected);
    try {
      const chunks: Buffer[] = [];
      let bytes = 0;
      for await (const chunk of req) {
        const buffer = Buffer.from(chunk as Uint8Array);
        bytes += buffer.length;
        if (bytes > 140000) {
          send(413, { error: 'Input exceeded its limit.' });
          return;
        }
        chunks.push(buffer);
      }
      let input: unknown;
      try {
        input = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(chunks)));
        if (req.url === '/v1/profile') {
          if (
            !input ||
            Array.isArray(input) ||
            typeof input !== 'object' ||
            Object.keys(input).length
          )
            throw new Error('Expected empty profile input.');
          send(200, hostedProfile(config));
          return;
        }
        input = req.url === '/v1/stage' ? checkedHostedStage(input) : extractionInput.parse(input);
      } catch {
        send(400, { error: 'Invalid extraction input.' });
        return;
      }
      if (
        req.url === '/v1/stage' &&
        checkedHostedStage(input).configDigest !== hostedProfile(config).configDigest
      ) {
        send(409, { error: 'Inference configuration changed. Start a new job.' });
        return;
      }
      requests++;
      const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(300000)]);
      const result =
        req.url === '/v1/stage'
          ? await runHostedStage(checkedHostedStage(input), providers, config, signal)
          : await runHostedExtraction(input, providers, config.classifier, signal);
      if (Buffer.byteLength(JSON.stringify(result)) > MAX_INFERENCE_RESPONSE_BYTES)
        throw new Error('Result too large.');
      send(200, result);
    } catch (error) {
      // Never log provider bodies, keys, narratives, authorization, or exception strings.
      if (!res.destroyed)
        send(503, {
          error: 'Inference failed; manual review remains available.',
          ...(error instanceof InferenceAccessError ? { inferenceFailure: error.failure } : {}),
        });
    } finally {
      active = false;
      res.off('close', disconnected);
    }
  });
  server.requestTimeout = 15000;
  server.headersTimeout = 10000;
  return server;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const proxy =
    process.env.NORMLAB_INFERENCE_EGRESS_PROXY ?? 'http://normlab-inference-egress:4319';
  if (!['http://normlab-inference-egress:4319', 'http://127.0.0.1:4319'].includes(proxy))
    throw new Error('Invalid inference egress proxy.');
  const server = createInferenceGateway(inferenceGatewayConfig(process.env), proxiedFetch(proxy));
  server.listen(4318, '0.0.0.0', () =>
    console.log('NormLab inference gateway listening on port 4318.'),
  );
  for (const signal of ['SIGINT', 'SIGTERM'] as const)
    process.once(signal, () => {
      server.close();
    });
}
