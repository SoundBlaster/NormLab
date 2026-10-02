import { randomUUID } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { z } from 'zod';
import { labQueries, type LabAnalysis, type LabWorkspace } from '../shared/reform-lab.js';
import {
  reformBundleSchema,
  reformCertificateSchema,
  reformQuerySchema,
  reformReceiptSchema,
  reformSnapshotSchema,
  reformSnapshotInputSchema,
  type ReformSnapshot,
} from '../shared/reform-contracts.js';
import { reformMetricAnnotationsSchema } from '../shared/reform-metrics.js';
import { digestSchema } from '../shared/domain.js';
import {
  validateReformCertificateBindings,
  validateReformReceiptBindings,
  validateReformSnapshot,
} from './reform-bindings.js';
import { canonical, digest } from './hash.js';
import { Conflict } from './store.js';
import {
  importedExperimentSchema,
  validatePortableExperiment,
  type ImportedExperiment,
} from './reform-transfer.js';
import type { ImportedExperimentSummary } from '../shared/reform-transfer.js';

export const labSnapshotInputSchema = reformSnapshotInputSchema
  .transform((input) => ({
    narrative: input.narrative.trim(),
    group: input.group,
    findings: Object.fromEntries(
      Object.entries(input.findings).map(([p, f]) => [
        p,
        { state: f.state, rationale: f.rationale.trim() },
      ]),
    ) as typeof input.findings,
  }))
  .superRefine((input, ctx) => {
    if (!input.narrative.length)
      ctx.addIssue({
        code: 'custom',
        path: ['narrative'],
        message: 'Добавьте описание учебного сценария.',
      });
    for (const p of ['M', 'N', 'E'] as const)
      if (input.findings[p].state !== 'unreviewed' && [...input.findings[p].rationale].length < 3)
        ctx.addIssue({
          code: 'custom',
          path: ['findings', p, 'rationale'],
          message: `Добавьте основание для ${p} (от 3 символов).`,
        });
  });
const analysisSchema = z.strictObject({
  schema: z.literal('normlab.lab-analysis/v1'),
  id: z.uuid(),
  createdAt: z.iso.datetime({ precision: 3 }),
  snapshotId: z.uuid().nullable(),
  modelRole: z.enum(['A', 'B', 'C']).nullable(),
  queryId: z.enum(labQueries.map((q) => q.id)).nullable(),
  title: z.string().min(1).max(200),
  query: reformQuerySchema,
  bundles: z.array(reformBundleSchema).min(1).max(2),
  snapshot: reformSnapshotSchema.nullable(),
  certificate: reformCertificateSchema,
  receipt: reformReceiptSchema.nullable(),
  verification: reformReceiptSchema.shape.payload.shape.verification.extend({
    queryDigest: digestSchema,
    certificateDigest: digestSchema.nullable(),
    statementDigest: digestSchema,
    durationMs: z.number().int().min(0).max(3600000),
  }),
  annotations: reformMetricAnnotationsSchema.nullable(),
});
function parseAnalysis(value: unknown): LabAnalysis {
  const analysis = analysisSchema.parse(value);
  const snapshot = analysis.snapshot ? validateReformSnapshot(analysis.snapshot) : undefined;
  if (
    analysis.snapshotId !== (snapshot?.id ?? null) ||
    (analysis.query.kind === 'decision'
      ? analysis.modelRole === null || analysis.queryId !== null
      : analysis.modelRole !== null || analysis.queryId === null)
  )
    throw new Error('Invalid laboratory analysis context');
  validateReformCertificateBindings(
    analysis.certificate,
    analysis.query,
    analysis.bundles,
    snapshot,
  );
  if (analysis.receipt)
    validateReformReceiptBindings(
      analysis.receipt,
      analysis.query,
      analysis.certificate,
      analysis.bundles,
      snapshot,
    );
  return analysis;
}
export class ReformStore {
  private readonly db: DatabaseSync;
  constructor(path: string) {
    this.db = new DatabaseSync(path);
    this.db.exec(`
      PRAGMA journal_mode=WAL;
      PRAGMA foreign_keys=ON;
      CREATE TABLE IF NOT EXISTS reform_snapshots (
        id TEXT PRIMARY KEY, revision INTEGER NOT NULL UNIQUE, body TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS reform_analyses (
        id TEXT PRIMARY KEY, snapshot_id TEXT REFERENCES reform_snapshots(id), body TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS reform_analysis_snapshot ON reform_analyses(snapshot_id);
      CREATE TABLE IF NOT EXISTS reform_imports (
        id TEXT PRIMARY KEY, body TEXT NOT NULL
      );
      CREATE TRIGGER IF NOT EXISTS reform_imports_no_update BEFORE UPDATE ON reform_imports BEGIN SELECT RAISE(ABORT, 'immutable reform import'); END;
      CREATE TRIGGER IF NOT EXISTS reform_imports_no_delete BEFORE DELETE ON reform_imports BEGIN SELECT RAISE(ABORT, 'immutable reform import'); END;
      CREATE TRIGGER IF NOT EXISTS reform_snapshots_no_update BEFORE UPDATE ON reform_snapshots BEGIN SELECT RAISE(ABORT, 'immutable reform snapshot'); END;
      CREATE TRIGGER IF NOT EXISTS reform_snapshots_no_delete BEFORE DELETE ON reform_snapshots BEGIN SELECT RAISE(ABORT, 'immutable reform snapshot'); END;
      CREATE TRIGGER IF NOT EXISTS reform_analyses_no_update BEFORE UPDATE ON reform_analyses BEGIN SELECT RAISE(ABORT, 'immutable reform analysis'); END;
      CREATE TRIGGER IF NOT EXISTS reform_analyses_no_delete BEFORE DELETE ON reform_analyses BEGIN SELECT RAISE(ABORT, 'immutable reform analysis'); END;
    `);
    if (!this.db.prepare('SELECT id FROM reform_snapshots LIMIT 1').get())
      this.createSnapshot(
        {
          narrative:
            'Учебный эпизод группы K1. Исследуем обязательное уменьшение срока при возмещении M, сообщении N и исключении E. Это синтетические правила, не реальное дело.',
          group: 'K1',
          findings: {
            M: { state: 'established', rationale: 'В учебном примере ущерб полностью возмещён.' },
            N: { state: 'refuted', rationale: 'В учебном примере самостоятельного сообщения нет.' },
            E: { state: 'refuted', rationale: 'В учебном примере повторность отсутствует.' },
          },
        },
        null,
      );
  }
  workspace(): LabWorkspace {
    const snapshots = this.db
      .prepare('SELECT body FROM reform_snapshots ORDER BY revision DESC')
      .all()
      .map((row) => validateReformSnapshot(JSON.parse(String(row.body))));
    const analyses = this.db
      .prepare('SELECT body FROM reform_analyses ORDER BY rowid DESC')
      .all()
      .map((row) => {
        const a = parseAnalysis(JSON.parse(String(row.body)));
        return {
          id: a.id,
          createdAt: a.createdAt,
          snapshotId: a.snapshotId,
          modelRole: a.modelRole,
          queryId: a.queryId,
          title: a.title,
          proofStatus: a.verification.status,
          resultStatus:
            a.certificate.kind === 'decision'
              ? a.certificate.result.status
              : a.certificate.result.verdict,
        };
      });
    return { snapshots, analyses };
  }
  snapshot(id: string): ReformSnapshot | null {
    const row = this.db.prepare('SELECT body FROM reform_snapshots WHERE id=?').get(id);
    return row ? validateReformSnapshot(JSON.parse(String(row.body))) : null;
  }
  createSnapshot(value: unknown, expectedId: string | null): ReformSnapshot {
    const input = labSnapshotInputSchema.parse(value);
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const latest = this.db
        .prepare('SELECT id, revision FROM reform_snapshots ORDER BY revision DESC LIMIT 1')
        .get();
      if ((latest ? String(latest.id) : null) !== expectedId)
        throw new Conflict('Снимок A/B/C уже изменён. Обновите рабочую область перед сохранением.');
      const content = {
        ...input,
        schema: 'normlab.snapshot/v2' as const,
        id: randomUUID(),
        caseId: 'reform-lab-case',
        revision: latest ? Number(latest.revision) + 1 : 1,
        createdAt: new Date().toISOString(),
        supersedes: latest ? String(latest.id) : null,
        authority: 'simulated-reviewer' as const,
      };
      const snapshot = validateReformSnapshot({ ...content, digest: digest(content) });
      this.db
        .prepare('INSERT INTO reform_snapshots VALUES (?, ?, ?)')
        .run(snapshot.id, snapshot.revision, canonical(snapshot));
      this.db.exec('COMMIT');
      return snapshot;
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }
  saveAnalysis(value: LabAnalysis): void {
    const analysis = parseAnalysis(value);
    if (
      analysis.snapshot &&
      digest(this.snapshot(analysis.snapshot.id)) !== digest(analysis.snapshot)
    )
      throw new Error('Analysis snapshot differs from stored immutable snapshot');
    this.db
      .prepare('INSERT INTO reform_analyses VALUES (?, ?, ?)')
      .run(analysis.id, analysis.snapshotId, canonical(analysis));
  }
  analysis(id: string): LabAnalysis | null {
    const row = this.db.prepare('SELECT body FROM reform_analyses WHERE id=?').get(id);
    return row ? parseAnalysis(JSON.parse(String(row.body))) : null;
  }
  imports(): ImportedExperimentSummary[] {
    return this.db
      .prepare('SELECT body FROM reform_imports ORDER BY rowid DESC')
      .all()
      .map((row) => {
        const record = importedExperimentSchema.parse(JSON.parse(String(row.body)));
        return {
          id: record.id,
          importedAt: record.importedAt,
          exportedAt: record.experiment.createdAt,
          issuer: record.experiment.issuer,
          itemCount: record.experiment.items.length,
        };
      });
  }
  imported(id: string): ImportedExperiment | null {
    const row = this.db.prepare('SELECT body FROM reform_imports WHERE id=?').get(id);
    return row ? importedExperimentSchema.parse(JSON.parse(String(row.body))) : null;
  }
  saveImport(input: ImportedExperiment): ImportedExperiment {
    const record = importedExperimentSchema.parse(input);
    validatePortableExperiment(record.experiment, record.trustedPublicKey);
    if (record.id !== digest(record.experiment)) throw new Error('Invalid import identity');
    const prior = this.imported(record.id);
    if (prior) {
      if (prior.trustedPublicKey !== record.trustedPublicKey)
        throw new Error('Stored import has a different trusted issuer');
      return prior;
    }
    this.db.prepare('INSERT INTO reform_imports VALUES (?, ?)').run(record.id, canonical(record));
    return record;
  }
  close(): void {
    this.db.close();
  }
}
