import assert from 'node:assert/strict';
import { once } from 'node:events';
import { mkdtemp, rm } from 'node:fs/promises';
import { get } from 'node:http';
import type { AddressInfo } from 'node:net';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { test } from 'node:test';
import { z } from 'zod';
import { createApp } from '../server/app.js';
import { validateReformSnapshot } from '../server/reform-bindings.js';
import { ReformStore } from '../server/reform-store.js';
import { Conflict } from '../server/store.js';
import type { ReformSnapshot, ReformSnapshotInput } from '../shared/reform-contracts.js';
import type { LabBootstrap, LabWorkspace } from '../shared/reform-lab.js';

function input(): ReformSnapshotInput {
  return {
    narrative: '  Синтетический сценарий K2  ',
    group: 'K2',
    findings: {
      M: { state: 'established', rationale: '  Ущерб возмещён  ' },
      N: { state: 'not-established', rationale: '  Недостаточно учебных сведений  ' },
      E: { state: 'unreviewed', rationale: '  ' },
    },
  };
}

async function withStore(action: (store: ReformStore, path: string) => void) {
  const directory = await mkdtemp(join(tmpdir(), 'normlab-reform-store-'));
  const path = join(directory, 'normlab.sqlite');
  const store = new ReformStore(path);
  try {
    action(store, path);
  } finally {
    store.close();
    await rm(directory, { recursive: true, force: true });
  }
}

async function withHttp(action: (base: string, bootstrap: LabBootstrap) => Promise<void>) {
  const directory = await mkdtemp(join(tmpdir(), 'normlab-reform-api-'));
  const app = await createApp({ dataDir: directory, web: false });
  try {
    app.server.listen(0, '127.0.0.1');
    await once(app.server, 'listening');
    const base = `http://127.0.0.1:${(app.server.address() as AddressInfo).port}`;
    const response = await fetch(`${base}/api/reform/bootstrap`);
    assert.equal(response.status, 200);
    await action(base, (await response.json()) as LabBootstrap);
  } finally {
    await app.close();
    await rm(directory, { recursive: true, force: true });
  }
}

function post(base: string, path: string, body: unknown, token: string, headers = {}) {
  return fetch(`${base}${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-normlab-token': token, ...headers },
    body: JSON.stringify(body),
  });
}

test('reform store normalizes findings once and preserves exact revision history on reopen', async () => {
  await withStore((store, path) => {
    const first = store.workspace().snapshots[0];
    const supplied = input();
    const snapshot = store.createSnapshot(supplied, first.id);
    assert.equal(snapshot.narrative, 'Синтетический сценарий K2');
    assert.equal(snapshot.findings.M.rationale, 'Ущерб возмещён');
    assert.equal(snapshot.findings.N.state, 'not-established');
    assert.equal(snapshot.findings.E.rationale, '');
    assert.equal(snapshot.revision, first.revision + 1);
    assert.equal(snapshot.supersedes, first.id);
    assert.deepEqual(validateReformSnapshot(snapshot), snapshot);
    supplied.findings.M.rationale = 'Later caller mutation';
    assert.deepEqual(store.snapshot(first.id), first);
    assert.deepEqual(store.snapshot(snapshot.id), snapshot);
    const reopened = new ReformStore(path);
    try {
      assert.deepEqual(reopened.workspace().snapshots, [snapshot, first]);
    } finally {
      reopened.close();
    }
  });
});

test('reform store rejects blank narratives and missing reviewed rationale without adding revisions', async () => {
  await withStore((store) => {
    const first = store.workspace().snapshots[0];
    assert.throws(
      () => store.createSnapshot({ ...input(), narrative: ' \n\t ' }, first.id),
      z.ZodError,
    );
    for (const state of ['established', 'refuted', 'not-established'] as const) {
      const value = input();
      value.findings.N = { state, rationale: '  ' };
      assert.throws(() => store.createSnapshot(value, first.id), z.ZodError);
    }
    const short = input();
    short.findings.M.rationale = '😀😀';
    assert.throws(() => store.createSnapshot(short, first.id), z.ZodError);
    assert.deepEqual(store.workspace().snapshots, [first]);
  });
});

test('reform store rejects a stale editor and SQL mutation of saved snapshots', async () => {
  await withStore((store, path) => {
    const first = store.workspace().snapshots[0];
    const second = store.createSnapshot(input(), first.id);
    assert.throws(() => store.createSnapshot(input(), first.id), Conflict);
    const connection = new DatabaseSync(path);
    try {
      assert.throws(
        () =>
          connection.prepare('UPDATE reform_snapshots SET body=? WHERE id=?').run('{}', first.id),
        /immutable reform snapshot/,
      );
      assert.throws(
        () => connection.prepare('DELETE FROM reform_snapshots WHERE id=?').run(first.id),
        /immutable reform snapshot/,
      );
    } finally {
      connection.close();
    }
    assert.deepEqual(store.workspace().snapshots, [second, first]);
  });
});

test('reform HTTP routes expose A/B/C and enforce request guards before saving a new revision', async () => {
  await withHttp(async (base, bootstrap) => {
    assert.deepEqual(
      bootstrap.models.map((model) => model.role),
      ['A', 'B', 'C'],
    );
    assert.equal(bootstrap.modelMetrics.length, 3);
    assert.deepEqual(bootstrap.workspace.analyses, []);
    assert.match(bootstrap.issuerPublicKey, /BEGIN PUBLIC KEY/);
    const first = bootstrap.workspace.snapshots[0];
    const request = { input: input(), expectedSnapshotId: first.id };
    const route = '/api/reform/snapshots';
    assert.equal((await post(base, route, request, '')).status, 403);
    assert.equal(
      (
        await post(base, route, request, bootstrap.csrfToken, {
          origin: 'https://untrusted.example',
        })
      ).status,
      403,
    );
    const wrongHost = await new Promise<number | undefined>((resolve, reject) => {
      get(`${base}/api/reform/bootstrap`, { headers: { host: 'attacker.example' } }, (response) => {
        response.resume();
        resolve(response.statusCode);
      }).on('error', reject);
    });
    assert.equal(wrongHost, 403);
    const response = await post(base, route, request, bootstrap.csrfToken);
    assert.equal(response.status, 201);
    const saved = (await response.json()) as { snapshot: ReformSnapshot; workspace: LabWorkspace };
    assert.deepEqual(validateReformSnapshot(saved.snapshot), saved.snapshot);
    assert.equal(saved.snapshot.supersedes, first.id);
    assert.equal(saved.snapshot.findings.N.state, 'not-established');
    assert.deepEqual(saved.workspace.snapshots, [saved.snapshot, first]);
    assert.equal((await post(base, route, request, bootstrap.csrfToken)).status, 409);
    const legacy = await fetch(`${base}/api/bootstrap`);
    assert.equal(legacy.status, 200);
    assert.equal((await legacy.json()).workspace.snapshots.length, 1);
  });
});

test('reform HTTP rejects unknown queries, invalid findings and malformed UTF-8 before creating artifacts', async () => {
  await withHttp(async (base, bootstrap) => {
    assert.equal(
      (await post(base, '/api/reform/queries', { queryId: 'arbitrary-code' }, bootstrap.csrfToken))
        .status,
      400,
    );
    assert.equal(
      (
        await post(
          base,
          '/api/reform/queries',
          { queryId: 'AB-equivalence', snapshotId: bootstrap.workspace.snapshots[0].id },
          bootstrap.csrfToken,
        )
      ).status,
      400,
    );
    const value = input();
    value.findings.N.rationale = '';
    assert.equal(
      (
        await post(
          base,
          '/api/reform/snapshots',
          { input: value, expectedSnapshotId: bootstrap.workspace.snapshots[0].id },
          bootstrap.csrfToken,
        )
      ).status,
      400,
    );
    const encoded = Buffer.from(
      JSON.stringify({
        input: { ...input(), narrative: 'INVALID_UTF8' },
        expectedSnapshotId: bootstrap.workspace.snapshots[0].id,
      }),
    );
    const offset = encoded.indexOf('INVALID_UTF8');
    const malformed = await fetch(`${base}/api/reform/snapshots`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-normlab-token': bootstrap.csrfToken },
      body: Buffer.concat([
        encoded.subarray(0, offset),
        Buffer.from([0xff]),
        encoded.subarray(offset + 'INVALID_UTF8'.length),
      ]),
    });
    assert.equal(malformed.status, 400);
    const fresh = (await (await fetch(`${base}/api/reform/bootstrap`)).json()) as LabBootstrap;
    assert.deepEqual(fresh.workspace, bootstrap.workspace);
  });
});
