import type { DatabaseSync } from 'node:sqlite';

export type DatabaseMigration = {
  version: number;
  name: string;
  sql: string;
};

export type DatabaseComponent = 'legacy' | 'reform';

export function applyDatabaseMigrations(
  db: DatabaseSync,
  component: DatabaseComponent,
  migrations: DatabaseMigration[],
): void {
  migrations.forEach((migration, index) => {
    if (migration.version !== index + 1)
      throw new Error(`Invalid ${component} migration sequence at version ${migration.version}`);
  });
  db.exec(`
    CREATE TABLE IF NOT EXISTS normlab_schema_migrations (
      component TEXT NOT NULL,
      version INTEGER NOT NULL,
      name TEXT NOT NULL,
      applied_at TEXT NOT NULL,
      PRIMARY KEY (component, version)
    );
  `);
  const applied = db
    .prepare('SELECT version FROM normlab_schema_migrations WHERE component=? ORDER BY version')
    .all(component)
    .map((row) => Number((row as { version: number }).version));
  let current = 0;
  for (const version of applied) {
    if (version !== current + 1)
      throw new Error(`Gapped ${component} database migration history at version ${version}`);
    current = version;
  }
  if (current > migrations.length)
    throw new Error(`Database ${component} schema is newer than this NormLab build`);

  for (const migration of migrations) {
    if (migration.version <= current) continue;
    if (!Number.isInteger(migration.version) || migration.version !== current + 1)
      throw new Error(`Invalid ${component} migration sequence at version ${migration.version}`);
    db.exec('BEGIN IMMEDIATE');
    try {
      db.exec(migration.sql);
      db.prepare(
        'INSERT INTO normlab_schema_migrations (component, version, name, applied_at) VALUES (?, ?, ?, ?)',
      ).run(component, migration.version, migration.name, new Date().toISOString());
      db.exec('COMMIT');
      current = migration.version;
    } catch (error) {
      db.exec('ROLLBACK');
      throw error;
    }
  }
}
