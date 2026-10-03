import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { applyDatabaseMigrations } from '../server/database-migrations.js';
import { ReformStore } from '../server/reform-store.js';
import { Store } from '../server/store.js';
import { test } from 'node:test';

test('unversioned SQLite databases migrate in place and record each component exactly once', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'normlab-migrations-'));
  const path = join(directory, 'normlab.sqlite');
  const prior = new DatabaseSync(path);
  prior.exec(`
    CREATE TABLE cases (id TEXT PRIMARY KEY, title TEXT NOT NULL);
    CREATE TABLE snapshots (
      id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
      revision INTEGER NOT NULL, body TEXT NOT NULL, UNIQUE(case_id, revision)
    );
    CREATE TABLE analyses (
      id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
      bundle_id TEXT NOT NULL, body TEXT NOT NULL
    );
    INSERT INTO cases VALUES ('synthetic-case', 'Existing case');
    INSERT INTO snapshots VALUES (
      'pre-migration-snapshot', 'synthetic-case', 1,
      '{"id":"pre-migration-snapshot"}'
    );
  `);
  prior.close();

  try {
    const store = new Store(path);
    const reformStore = new ReformStore(path);
    assert.equal(store.snapshot('pre-migration-snapshot')?.id, 'pre-migration-snapshot');
    const reformSnapshot = reformStore.workspace().snapshots[0];
    assert.ok(reformSnapshot);

    store.close();
    reformStore.close();

    const migrated = new DatabaseSync(path, { readOnly: true });
    const versions = migrated
      .prepare('SELECT component, version, name FROM normlab_schema_migrations ORDER BY component')
      .all()
      .map((row) => ({
        component: String(row.component),
        version: Number(row.version),
        name: String(row.name),
      }));
    assert.deepEqual(versions, [
      { component: 'legacy', version: 1, name: 'initial-schema' },
      { component: 'reform', version: 1, name: 'initial-schema' },
    ]);
    assert.equal(migrated.prepare('SELECT COUNT(*) AS count FROM snapshots').get()?.count, 1);
    assert.equal(
      migrated.prepare('SELECT COUNT(*) AS count FROM reform_snapshots').get()?.count,
      1,
    );
    assert.equal(String(migrated.prepare('PRAGMA integrity_check').get()?.integrity_check), 'ok');
    migrated.close();

    const reopened = new Store(path);
    const reopenedReform = new ReformStore(path);
    assert.equal(reopened.snapshot('pre-migration-snapshot')?.id, 'pre-migration-snapshot');
    assert.equal(reopenedReform.workspace().snapshots.length, 1);
    reopened.close();
    reopenedReform.close();
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test('failed migration rolls back schema changes and can be retried', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'normlab-migration-rollback-'));
  const path = join(directory, 'normlab.sqlite');
  const db = new DatabaseSync(path);
  try {
    db.exec(`
      CREATE TABLE normlab_schema_migrations (
        component TEXT NOT NULL, version INTEGER NOT NULL, name TEXT NOT NULL,
        applied_at TEXT NOT NULL, PRIMARY KEY(component, version)
      );
    `);
    assert.throws(() =>
      applyTestMigration(db, [
        { version: 1, name: 'broken', sql: 'CREATE TABLE rolled_back (id TEXT); INVALID SQL;' },
      ]),
    );
    assert.equal(
      db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='rolled_back'").get(),
      undefined,
    );
    applyTestMigration(db, [
      { version: 1, name: 'recovered', sql: 'CREATE TABLE recovered (id TEXT);' },
    ]);
    assert.equal(db.prepare('SELECT version FROM normlab_schema_migrations').get()?.version, 1);
    assert.ok(
      db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='recovered'").get(),
    );
  } finally {
    db.close();
    await rm(directory, { recursive: true, force: true });
  }
});

function applyTestMigration(
  db: DatabaseSync,
  migrations: { version: number; name: string; sql: string }[],
): void {
  applyDatabaseMigrations(db, 'legacy', migrations);
}
