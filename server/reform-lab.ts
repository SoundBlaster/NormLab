import { randomUUID } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { z } from 'zod';
import {
  labModelRoles,
  labQueries,
  type LabAnalysis,
  type LabAnalysisView,
  type LabBootstrap,
  type LabModelRole,
  type LabQueryId,
} from '../shared/reform-lab.js';
import { reformExplanationReportSchema } from '../shared/reform-explanations.js';
import { reformMetricAnnotationsSchema } from '../shared/reform-metrics.js';
import type { ReformBundle, ReformQuery, ReformSnapshot } from '../shared/reform-contracts.js';
import { decisionQuery, reformBundleRef } from './reform-bindings.js';
import { projectReformExplanation } from './reform-explanations.js';
import { measureReformExport, projectReformMetrics } from './reform-metrics.js';
import { getReformBundle } from './reform-models.js';
import {
  comparisonQuery,
  getReformCounterexampleBundle,
  mitigationQuery,
  proposeReformQuery,
} from './reform-queries.js';
import { exportReformArtifacts, ReformReceiptSigner } from './reform-receipts.js';
import { verifyReformCertificate } from './reform-verifier.js';
import { ReformStore, labSnapshotInputSchema } from './reform-store.js';
import { discoverLean } from './verifier.js';
import { digest } from './hash.js';

export class LabHttpError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}
type Response = { status: number; body: unknown; filename?: string };
const annotations = reformMetricAnnotationsSchema.parse(
  JSON.parse(
    readFileSync(new URL('../fixtures/reform-v1/metric-annotations.json', import.meta.url), 'utf8'),
  ),
);
const models = labModelRoles.map((role) => ({
  role,
  bundle: getReformBundle(role),
  title: { A: 'Исходная модель', B: 'Структурное упрощение', C: 'Усиленное смягчение' }[role],
  description: {
    A: 'Отдельные правила M/N для каждой группы.',
    B: 'Общие M/N; полные последствия сохраняются.',
    C: 'Общее M меняется с 2/3 на 1/2.',
  }[role],
}));
const allBundles = [...models.map((m) => m.bundle), getReformCounterexampleBundle()];
const queryIds = z.enum(labQueries.map((q) => q.id));
const snapshotRequest = z.strictObject({
  input: labSnapshotInputSchema,
  expectedSnapshotId: z.uuid(),
});
const analysisRequest = z.strictObject({ snapshotId: z.uuid() });
const queryRequest = z.strictObject({ queryId: queryIds });

export class ReformLab {
  readonly store: ReformStore;
  private readonly signer: ReformReceiptSigner;
  private readonly running = new Map<string, Promise<unknown>>();
  constructor(
    dataDir: string,
    private readonly otherJobs: () => number,
  ) {
    this.store = new ReformStore(join(dataDir, 'normlab.sqlite'));
    this.signer = new ReformReceiptSigner(dataDir);
  }
  get activeJobs(): number {
    return this.running.size;
  }
  private async job<T>(key: string, action: () => Promise<T>): Promise<T> {
    const prior = this.running.get(key);
    if (prior) return (await prior) as T;
    if (this.running.size + this.otherJobs() >= 2)
      throw new LabHttpError(
        429,
        'Две проверки уже выполняются. Повторите через несколько секунд.',
      );
    const promise = action();
    this.running.set(key, promise);
    try {
      return await promise;
    } finally {
      this.running.delete(key);
    }
  }
  private bootstrap(token: string): Promise<LabBootstrap> {
    return discoverLean().then((lean) => {
      const a = models[0].bundle,
        b = models[1].bundle,
        c = models[2].bundle;
      const ab = comparisonQuery(a, b, 'equivalence'),
        ac = comparisonQuery(a, c, 'component-no-increase');
      return {
        csrfToken: token,
        workspace: this.store.workspace(),
        models,
        modelMetrics: [
          ...projectReformMetrics(
            ab,
            [a, b],
            proposeReformQuery(ab, [a, b]),
            undefined,
            annotations,
          ).models,
          projectReformMetrics(ac, [a, c], proposeReformQuery(ac, [a, c]), undefined, annotations)
            .models[1],
        ],
        issuerPublicKey: this.signer.publicKey,
        verifier: { available: lean.available, version: lean.version },
      };
    });
  }
  private async produce(
    query: ReformQuery,
    bundles: ReformBundle[],
    title: string,
    snapshot: ReformSnapshot | null,
    modelRole: LabModelRole | null,
    queryId: LabQueryId | null,
  ): Promise<LabAnalysisView> {
    const certificate = proposeReformQuery(query, bundles, {}, snapshot ?? undefined);
    const started = Date.now();
    let receipt = null;
    let verification;
    try {
      receipt = await this.signer.issue(query, bundles, certificate, snapshot ?? undefined);
      verification = {
        ...receipt.payload.verification,
        queryDigest: digest(query),
        certificateDigest: digest(certificate),
        statementDigest: receipt.payload.bindings.statementDigest,
        durationMs: Date.now() - started,
      };
    } catch {
      verification = await verifyReformCertificate(
        query,
        bundles,
        certificate,
        snapshot ?? undefined,
      );
    }
    const analysis: LabAnalysis = {
      schema: 'normlab.lab-analysis/v1',
      id: randomUUID(),
      createdAt: new Date().toISOString(),
      snapshotId: snapshot?.id ?? null,
      snapshot,
      modelRole,
      queryId,
      title,
      query,
      bundles,
      certificate,
      receipt,
      verification,
      annotations,
    };
    this.store.saveAnalysis(analysis);
    return this.view(analysis);
  }
  private async view(analysis: LabAnalysis): Promise<LabAnalysisView> {
    const snapshot = analysis.snapshot ?? undefined;
    const explanation = projectReformExplanation(
      analysis.query,
      analysis.bundles,
      analysis.certificate,
      snapshot,
    );
    const metrics = projectReformMetrics(
      analysis.query,
      analysis.bundles,
      analysis.certificate,
      snapshot,
      analysis.annotations,
    );
    const metricsReport = analysis.receipt
      ? await measureReformExport(
          exportReformArtifacts(
            analysis.query,
            analysis.bundles,
            analysis.certificate,
            analysis.receipt,
            snapshot,
          ),
          this.signer.publicKey,
          analysis.annotations,
        )
      : null;
    const explanationReport = metricsReport
      ? reformExplanationReportSchema.parse({
          schema: 'normlab.explanation-report/v1',
          artifactDigest: metricsReport.artifactDigest,
          explanationDigest: metricsReport.evidence.current ? digest(explanation) : null,
          explanation: metricsReport.evidence.current ? explanation : null,
          evidence: metricsReport.evidence,
        })
      : null;
    const registryCurrent = explanation.bindings.models.every(({ bundle }) => {
      const current = allBundles.find((b) => b.id === bundle.id);
      return current !== undefined && digest(bundle) === digest(reformBundleRef(current));
    });
    return { analysis, registryCurrent, explanation, metrics, metricsReport, explanationReport };
  }
  private queryPlan(id: LabQueryId): { query: ReformQuery; bundles: ReformBundle[] } {
    const [a, b, c] = models.map((m) => m.bundle);
    if (id.endsWith('strict-M-mitigation')) {
      const bundle = models.find((m) => m.role === id[0])!.bundle;
      return { query: mitigationQuery(bundle), bundles: [bundle] };
    }
    const candidate = id.startsWith('AB-') ? b : id.startsWith('AD-') ? allBundles[3] : c;
    const property =
      id === 'AB-equivalence'
        ? 'equivalence'
        : id === 'AC-component-no-increase'
          ? 'component-no-increase'
          : id === 'AC-strict-reduction'
            ? 'strict-reduction'
            : 'preserved-outside';
    return { query: comparisonQuery(a, candidate, property), bundles: [a, candidate] };
  }
  async handle(
    method: string,
    path: string,
    body: unknown,
    token: string,
  ): Promise<Response | null> {
    if (method === 'GET' && path === '/api/reform/bootstrap')
      return { status: 200, body: await this.bootstrap(token) };
    if (method === 'POST' && path === '/api/reform/snapshots') {
      const request = snapshotRequest.parse(body);
      const snapshot = this.store.createSnapshot(request.input, request.expectedSnapshotId);
      return { status: 201, body: { snapshot, workspace: this.store.workspace() } };
    }
    if (method === 'POST' && path === '/api/reform/analyze') {
      const request = analysisRequest.parse(body);
      const snapshot = this.store.snapshot(request.snapshotId);
      if (!snapshot) throw new LabHttpError(404, 'Снимок A/B/C не найден.');
      const views = await this.job(`decision:${snapshot.digest}`, async () => {
        const result = [];
        for (const model of models)
          result.push(
            await this.produce(
              decisionQuery(snapshot, model.bundle),
              [model.bundle],
              model.title,
              snapshot,
              model.role,
              null,
            ),
          );
        return result;
      });
      return { status: 200, body: { views, workspace: this.store.workspace() } };
    }
    if (method === 'POST' && path === '/api/reform/queries') {
      const request = queryRequest.parse(body);
      const plan = this.queryPlan(request.queryId);
      const view = await this.job(`query:${digest(plan.query)}`, () =>
        this.produce(
          plan.query,
          plan.bundles,
          labQueries.find((q) => q.id === request.queryId)!.title,
          null,
          null,
          request.queryId,
        ),
      );
      return { status: 200, body: { view, workspace: this.store.workspace() } };
    }
    const match = /^\/api\/reform\/analyses\/([a-f0-9-]{36})\/(replay|export)$/.exec(path);
    if (match) {
      const analysis = this.store.analysis(z.uuid().parse(match[1]));
      if (!analysis) throw new LabHttpError(404, 'Результат A/B/C не найден.');
      if (method === 'POST' && match[2] === 'replay') {
        z.strictObject({}).parse(body);
        return {
          status: 200,
          body: await this.job(`replay:${analysis.id}`, () => this.view(analysis)),
        };
      }
      if (method === 'GET' && match[2] === 'export') {
        if (!analysis.receipt)
          throw new LabHttpError(409, 'Подписанный export недоступен: проверка не завершена.');
        return {
          status: 200,
          filename: `normlab-reform-${analysis.id}.json`,
          body: exportReformArtifacts(
            analysis.query,
            analysis.bundles,
            analysis.certificate,
            analysis.receipt,
            analysis.snapshot ?? undefined,
          ),
        };
      }
    }
    return null;
  }
  async close(): Promise<void> {
    await Promise.allSettled([...this.running.values()]);
    this.store.close();
  }
}
