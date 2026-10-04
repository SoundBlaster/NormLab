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

test('versioned upgrades preserve data and failed future migrations roll back atomically', () => {
  const db = new DatabaseSync(':memory:');
  const versionOne = [
    {
      version: 1,
      name: 'initial',
      sql: "CREATE TABLE records (id TEXT PRIMARY KEY, value TEXT NOT NULL); INSERT INTO records VALUES ('kept', 'original');",
    },
  ];
  const versionTwo = [
    ...versionOne,
    {
      version: 2,
      name: 'add-status',
      sql: "ALTER TABLE records ADD COLUMN status TEXT NOT NULL DEFAULT 'active';",
    },
  ];
  const failedVersionThree = [
    ...versionTwo,
    {
      version: 3,
      name: 'broken-index',
      sql: 'CREATE TABLE transient_upgrade (id TEXT); INVALID SQL;',
    },
  ];
  const versionThree = [
    ...versionTwo,
    {
      version: 3,
      name: 'record-index',
      sql: 'CREATE INDEX records_status_idx ON records(status);',
    },
  ];

  try {
    applyTestMigration(db, versionOne);
    applyTestMigration(db, versionTwo);

    assertPreservedRecord(db);
    assert.throws(() => applyTestMigration(db, failedVersionThree), /syntax error/i);
    assert.equal(
      db
        .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='transient_upgrade'")
        .get(),
      undefined,
    );
    assert.deepEqual(
      db
        .prepare('SELECT version FROM normlab_schema_migrations WHERE component=? ORDER BY version')
        .all('legacy')
        .map((row) => Number((row as { version: number }).version)),
      [1, 2],
    );

    applyTestMigration(db, versionThree);
    applyTestMigration(db, versionThree);

    assert.deepEqual(
      db
        .prepare(
          'SELECT version, name FROM normlab_schema_migrations WHERE component=? ORDER BY version',
        )
        .all('legacy')
        .map((row) => ({
          version: Number((row as { version: number }).version),
          name: String((row as { name: string }).name),
        })),
      [
        { version: 1, name: 'initial' },
        { version: 2, name: 'add-status' },
        { version: 3, name: 'record-index' },
      ],
    );
    assertPreservedRecord(db);
    assert.ok(
      db
        .prepare("SELECT name FROM sqlite_master WHERE type='index' AND name='records_status_idx'")
        .get(),
    );
    assert.equal(String(db.prepare('PRAGMA integrity_check').get()?.integrity_check), 'ok');
  } finally {
    db.close();
  }
});

function applyTestMigration(
  db: DatabaseSync,
  migrations: { version: number; name: string; sql: string }[],
): void {
  applyDatabaseMigrations(db, 'legacy', migrations);
}

function assertPreservedRecord(db: DatabaseSync): void {
  const record = db.prepare('SELECT id, value, status FROM records').get();
  assert.equal(record?.id, 'kept');
  assert.equal(record?.value, 'original');
  assert.equal(record?.status, 'active');
}
