import assert from 'node:assert/strict';
import { once } from 'node:events';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { AddressInfo } from 'node:net';
import { test } from 'node:test';
import { createApp } from '../server/app.js';
import { portableExperimentLocks } from '../server/reform-transfer.js';
import type { LabAnalysisView, LabBootstrap } from '../shared/reform-lab.js';
import type { PortableExperiment } from '../server/reform-transfer.js';

test('portable import rejects untrusted and tampered sets without partial writes, then persists fresh read-only replay', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'normlab-transfer-'));
  const app = await createApp({ dataDir: directory, web: false });
  try {
    app.server.listen(0, '127.0.0.1');
    await once(app.server, 'listening');
    const base = `http://127.0.0.1:${(app.server.address() as AddressInfo).port}`;
    const bootstrap = (await (await fetch(`${base}/api/reform/bootstrap`)).json()) as LabBootstrap;
    const headers = {
      'content-type': 'application/json',
      'x-normlab-token': bootstrap.csrfToken,
    };
    const response = await fetch(`${base}/api/reform/queries`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ queryId: 'AB-equivalence' }),
    });
    assert.equal(response.status, 200);
    const { view } = (await response.json()) as { view: LabAnalysisView };
    const beforeImport = structuredClone(app.lab.store.workspace());
    const exported = await fetch(`${base}/api/reform/experiments/export`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ analysisIds: [view.analysis.id] }),
    });
    assert.equal(exported.status, 200);
    const experiment = (await exported.json()) as PortableExperiment;
    assert.equal(experiment.schema, 'normlab.experiment/v1');
    const postImport = (value: unknown, key = bootstrap.issuerPublicKey) =>
      fetch(`${base}/api/reform/imports`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ experiment: value, trustedPublicKey: key }),
      });

    assert.equal((await postImport(experiment, 'wrong trusted key')).status, 400);

    const wrongRuntime = structuredClone(experiment) as PortableExperiment;
    wrongRuntime.manifest.runtime.dependencyLockDigest = '0'.repeat(64);
    assert.equal((await postImport(wrongRuntime)).status, 400);

    const wrongBindings = structuredClone(experiment) as PortableExperiment;
    (wrongBindings.items[0].artifact.query as { property?: string }).property = 'strict-reduction';
    wrongBindings.manifest.locks = portableExperimentLocks(wrongBindings.items);
    assert.equal((await postImport(wrongBindings)).status, 400);

    const tampered = structuredClone(experiment) as PortableExperiment;
    tampered.items[0].artifact.receipt.signature = `${tampered.items[0].artifact.receipt.signature[0] === 'A' ? 'B' : 'A'}${tampered.items[0].artifact.receipt.signature.slice(1)}`;
    tampered.manifest.locks = portableExperimentLocks(tampered.items);
    assert.equal((await postImport(tampered)).status, 400);
    assert.deepEqual(await (await fetch(`${base}/api/reform/imports`)).json(), []);

    const imported = await postImport(experiment);
    assert.equal(imported.status, 201);
    const result = (await imported.json()) as {
      experiment: { id: string };
      views: LabAnalysisView[];
    };
    assert.equal(result.views.length, 1);
    assert.equal(result.views[0].metricsReport?.evidence.current, true);
    assert.deepEqual(app.lab.store.workspace(), beforeImport);

    const reopened = await fetch(`${base}/api/reform/imports/${result.experiment.id}/replay`, {
      method: 'POST',
      headers,
      body: '{}',
    });
    assert.equal(reopened.status, 200);
    const replay = (await reopened.json()) as { views: LabAnalysisView[] };
    assert.equal(replay.views[0].metricsReport?.evidence.current, true);
    assert.equal(
      ((await (await fetch(`${base}/api/reform/imports`)).json()) as unknown[]).length,
      1,
    );
    assert.equal(
      (await (await fetch(`${base}/api/reform/imports/${result.experiment.id}/export`)).json())
        .schema,
      'normlab.experiment/v1',
    );
  } finally {
    await app.close();
    await rm(directory, { recursive: true, force: true });
  }
});
