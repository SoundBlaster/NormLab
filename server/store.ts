import { randomUUID } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import type { Analysis, Snapshot, SnapshotInput, Workspace } from '../shared/domain.js';
import { canonical, digest } from './hash.js';

export class Conflict extends Error {}
export class Store {
  private db: DatabaseSync;
  constructor(path: string) {
    this.db = new DatabaseSync(path);
    this.db.exec(`
      PRAGMA journal_mode=WAL;
      PRAGMA foreign_keys=ON;
      CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, title TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS snapshots (
        id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
        revision INTEGER NOT NULL, body TEXT NOT NULL, UNIQUE(case_id, revision)
      );
      CREATE TABLE IF NOT EXISTS analyses (
        id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
        bundle_id TEXT NOT NULL, body TEXT NOT NULL
      );
      CREATE TRIGGER IF NOT EXISTS snapshots_immutable_update BEFORE UPDATE ON snapshots BEGIN SELECT RAISE(ABORT, 'immutable snapshot'); END;
      CREATE TRIGGER IF NOT EXISTS snapshots_immutable_delete BEFORE DELETE ON snapshots BEGIN SELECT RAISE(ABORT, 'immutable snapshot'); END;
    `);
    this.db
      .prepare('INSERT OR IGNORE INTO cases VALUES (?, ?)')
      .run('synthetic-case', 'Условие A · учебный сценарий');
    if (!this.db.prepare('SELECT id FROM snapshots LIMIT 1').get()) {
      this.createSnapshot(
        {
          narrative:
            'В учебной модели базовое решение включает 120 месяцев и штраф 200 000 DEMO. Требуется установить условие A: если оно подтверждено, срок обязательно уменьшается на треть. Штраф сохраняется.',
          finding: 'unreviewed',
          rationale: '',
        },
        null,
      );
    }
  }

  workspace(): Workspace {
    const snapshots = this.db
      .prepare('SELECT body FROM snapshots ORDER BY revision DESC')
      .all()
      .map((row) => JSON.parse(String(row.body)) as Snapshot);
    const analyses = this.db
      .prepare('SELECT body FROM analyses ORDER BY rowid DESC')
      .all()
      .map((row) => JSON.parse(String(row.body)) as Analysis);
    return { caseId: 'synthetic-case', title: 'Условие A · учебный сценарий', snapshots, analyses };
  }

  snapshot(id: string): Snapshot | null {
    const row = this.db.prepare('SELECT body FROM snapshots WHERE id = ?').get(id);
    return row ? (JSON.parse(String(row.body)) as Snapshot) : null;
  }

  createSnapshot(input: SnapshotInput, expectedSnapshotId: string | null): Snapshot {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const row = this.db
        .prepare('SELECT id, revision FROM snapshots ORDER BY revision DESC LIMIT 1')
        .get();
      const latestId = row ? String(row.id) : null;
      if (latestId !== expectedSnapshotId)
        throw new Conflict('Сценарий уже изменён. Обновите страницу и повторите действие.');
      const body = {
        ...input,
        id: randomUUID(),
        caseId: 'synthetic-case',
        revision: row ? Number(row.revision) + 1 : 1,
        createdAt: new Date().toISOString(),
        supersedes: latestId,
        authority: 'simulated-reviewer' as const,
      };
      const snapshot: Snapshot = { ...body, digest: digest(body) };
      this.db
        .prepare('INSERT INTO snapshots VALUES (?, ?, ?, ?)')
        .run(snapshot.id, snapshot.caseId, snapshot.revision, canonical(snapshot));
      this.db.exec('COMMIT');
      return snapshot;
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }

  saveAnalysis(analysis: Analysis): void {
    this.db
      .prepare('INSERT INTO analyses VALUES (?, ?, ?, ?)')
      .run(analysis.id, analysis.snapshotId, analysis.bundleId, canonical(analysis));
  }

  analysis(id: string): Analysis | null {
    const row = this.db.prepare('SELECT body FROM analyses WHERE id = ?').get(id);
    return row ? (JSON.parse(String(row.body)) as Analysis) : null;
  }
  close(): void {
    this.db.close();
  }
}
