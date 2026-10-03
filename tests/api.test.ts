import assert from 'node:assert/strict';
import { once } from 'node:events';
import { get, request as httpRequest } from 'node:http';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import type { AddressInfo } from 'node:net';
import type { Analysis, Bootstrap, Snapshot } from '../shared/domain.js';
import { createApp } from '../server/app.js';

test('HTTP workflow preserves snapshots, validates input and exports bound receipts', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'normlab-api-'));
  const app = await createApp({ dataDir: directory, web: false });
  try {
    app.server.listen(0, '127.0.0.1');
    await once(app.server, 'listening');
    const base = `http://127.0.0.1:${(app.server.address() as AddressInfo).port}`;
    const bootstrap = (await (await fetch(`${base}/api/bootstrap`)).json()) as Bootstrap;
    const post = (path: string, body: unknown, token = bootstrap.csrfToken, headers = {}) =>
      fetch(`${base}${path}`, {
        method: 'POST',
        headers: { 'content-type': 'application/json', 'x-normlab-token': token, ...headers },
        body: JSON.stringify(body),
      });
    const first = bootstrap.workspace.snapshots[0];
    const valid = {
      input: {
        narrative: 'Synthetic HTTP scenario',
        finding: 'established',
        rationale: 'Explicit synthetic finding',
      },
      expectedSnapshotId: first.id,
    };
    assert.equal((await post('/api/snapshots', valid, '')).status, 403);
    assert.equal(
      (
        await post('/api/snapshots', valid, bootstrap.csrfToken, {
          origin: 'https://untrusted.example',
        })
      ).status,
      403,
    );
    assert.equal(
      (await post('/api/snapshots', { ...valid, input: { ...valid.input, rationale: '' } })).status,
      400,
    );
    const save = await post('/api/snapshots', valid);
    assert.equal(save.status, 201);
    const { snapshot } = (await save.json()) as { snapshot: Snapshot };
    assert.equal((await post('/api/snapshots', valid)).status, 409);
    assert.equal(
      (await post('/api/analyze', { snapshotId: snapshot.id, bundleId: 'untrusted-plugin' }))
        .status,
      400,
    );
    const outcome = await post('/api/analyze', {
      snapshotId: snapshot.id,
      bundleId: 'reduction-v1',
    });
    assert.equal(outcome.status, 200);
    const analysis = (await outcome.json()) as Analysis;
    assert.equal(analysis.certificate.result.outcomes[0].prisonMonths, 80);
    assert.equal(analysis.receipt.payload.snapshotDigest, snapshot.digest);
    assert.equal(
      analysis.receipt.payload.verification.status,
      bootstrap.verifier.available ? 'verified' : 'inconclusive',
    );
    if (bootstrap.verifier.available) {
      const again = (await (
        await post('/api/analyze', { snapshotId: snapshot.id, bundleId: 'reduction-v1' })
      ).json()) as Analysis;
      assert.equal(again.id, analysis.id, 'Repeated verified jobs reuse the stored result');
    }
    const signature = (await (await post(`/api/analyses/${analysis.id}/signature`, {})).json()) as {
      valid: boolean;
    };
    assert.equal(signature.valid, true);
    const exported = await fetch(`${base}/api/analyses/${analysis.id}/export`);
    assert.match(exported.headers.get('content-disposition')!, /attachment/);
    const artifact = (await exported.json()) as {
      snapshot: Snapshot;
      certificate: unknown;
      receipt: unknown;
    };
    assert.equal(artifact.snapshot.digest, snapshot.digest);
    assert.deepEqual(artifact.receipt, analysis.receipt);
    const fresh = (await (await fetch(`${base}/api/bootstrap`)).json()) as Bootstrap;
    assert.equal(fresh.workspace.snapshots.length, 2);
    assert.equal(fresh.workspace.snapshots[1].finding, 'unreviewed');
    const rebindingStatus = await new Promise<number | undefined>((resolveStatus, reject) => {
      get(`${base}/api/bootstrap`, { headers: { host: 'attacker.example' } }, (response) => {
        response.resume();
        resolveStatus(response.statusCode);
      }).on('error', reject);
    });
    assert.equal(rebindingStatus, 403);
    const unicodeBody = Buffer.from(
      JSON.stringify({
        input: {
          narrative: 'Русский синтетический сценарий',
          finding: 'unreviewed',
          rationale: '',
        },
        expectedSnapshotId: snapshot.id,
      }),
    );
    const split = unicodeBody.indexOf(Buffer.from('Р')) + 1;
    const chunked = await new Promise<{ status?: number; body: string }>(
      (resolveResponse, reject) => {
        const req = httpRequest(
          `${base}/api/snapshots`,
          {
            method: 'POST',
            headers: { 'content-type': 'application/json', 'x-normlab-token': bootstrap.csrfToken },
          },
          (response) => {
            response.setEncoding('utf8');
            let body = '';
            response.on('data', (chunk) => {
              body += chunk;
            });
            response.on('end', () => resolveResponse({ status: response.statusCode, body }));
            response.on('error', reject);
          },
        );
        req.on('error', reject);
        req.write(unicodeBody.subarray(0, split));
        setTimeout(() => req.end(unicodeBody.subarray(split)), 20);
      },
    );
    assert.equal(chunked.status, 201);
    assert.equal(JSON.parse(chunked.body).snapshot.narrative, 'Русский синтетический сценарий');
  } finally {
    await app.close();
    await rm(directory, { recursive: true, force: true });
  }
});
