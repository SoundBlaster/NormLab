import assert from 'node:assert/strict';
import { createPrivateKey, sign } from 'node:crypto';
import { once } from 'node:events';
import { readFileSync } from 'node:fs';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { AddressInfo } from 'node:net';
import { test } from 'node:test';
import { createApp } from '../server/app.js';
import { canonical } from '../server/hash.js';
import { lockReformPackage } from '../server/reform-models.js';
import { portableExperimentLocks } from '../server/reform-transfer.js';
import type { LabAnalysisView, LabBootstrap } from '../shared/reform-lab.js';
import type { PortableExperiment } from '../server/reform-transfer.js';

test('portable import rejects untrusted and tampered sets without partial writes, then persists fresh read-only replay', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'normlab-transfer-'));
  let app = await createApp({ dataDir: directory, web: false });
  try {
    app.server.listen(0, '127.0.0.1');
    await once(app.server, 'listening');
    let base = `http://127.0.0.1:${(app.server.address() as AddressInfo).port}`;
    const bootstrap = (await (await fetch(`${base}/api/reform/bootstrap`)).json()) as LabBootstrap;
    let headers = {
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
    const secondResponse = await fetch(`${base}/api/reform/queries`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ queryId: 'AC-strict-reduction' }),
    });
    assert.equal(secondResponse.status, 200);
    const { view: secondView } = (await secondResponse.json()) as { view: LabAnalysisView };
    const beforeImport = structuredClone(app.lab.store.workspace());
    const exported = await fetch(`${base}/api/reform/experiments/export`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ analysisIds: [view.analysis.id] }),
    });
    assert.equal(exported.status, 200);
    const experiment = (await exported.json()) as PortableExperiment;
    assert.equal(experiment.schema, 'normlab.experiment/v1');
    const download = await fetch(
      `${base}/api/reform/experiments/download?analysisId=${encodeURIComponent(view.analysis.id)}`,
    );
    assert.equal(download.status, 200);
    assert.match(
      download.headers.get('content-disposition') ?? '',
      /attachment; filename="normlab-experiment\.json"/,
    );
    assert.equal(((await download.json()) as PortableExperiment).schema, 'normlab.experiment/v1');
    const postImport = (value: unknown, key = bootstrap.issuerPublicKey) =>
      fetch(`${base}/api/reform/imports`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ experiment: value, trustedPublicKey: key }),
      });

    const multiExportResponse = await fetch(`${base}/api/reform/experiments/export`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ analysisIds: [view.analysis.id, secondView.analysis.id] }),
    });
    assert.equal(multiExportResponse.status, 200);
    const multiExperiment = (await multiExportResponse.json()) as PortableExperiment;
    assert.equal(multiExperiment.items.length, 2);
    assert.deepEqual(multiExperiment.items[0], experiment.items[0]);
    const partiallyTamperedMultiExperiment = structuredClone(multiExperiment) as PortableExperiment;
    const secondSignature = partiallyTamperedMultiExperiment.items[1].artifact.receipt.signature;
    partiallyTamperedMultiExperiment.items[1].artifact.receipt.signature = `${secondSignature[0] === 'A' ? 'B' : 'A'}${secondSignature.slice(1)}`;
    partiallyTamperedMultiExperiment.manifest.locks = portableExperimentLocks(
      partiallyTamperedMultiExperiment.items,
    );

    const rejectedCases: {
      name: string;
      value: PortableExperiment;
      status: number;
      message?: RegExp;
    }[] = [];

    rejectedCases.push({
      name: 'wrong trusted issuer',
      value: experiment,
      status: 400,
    });

    const wrongRuntime = structuredClone(experiment) as PortableExperiment;
    wrongRuntime.manifest.runtime.dependencyLockDigest = '0'.repeat(64);
    rejectedCases.push({
      name: 'runtime lock drift',
      value: wrongRuntime,
      status: 400,
      message: /runtime\/dependency locks differ/,
    });

    const wrongBindings = structuredClone(experiment) as PortableExperiment;
    (wrongBindings.items[0].artifact.query as { property?: string }).property = 'strict-reduction';
    wrongBindings.manifest.locks = portableExperimentLocks(wrongBindings.items);
    rejectedCases.push({
      name: 'query/certificate mismatch',
      value: wrongBindings,
      status: 400,
    });

    const tampered = structuredClone(experiment) as PortableExperiment;
    tampered.items[0].artifact.receipt.signature = `${tampered.items[0].artifact.receipt.signature[0] === 'A' ? 'B' : 'A'}${tampered.items[0].artifact.receipt.signature.slice(1)}`;
    tampered.manifest.locks = portableExperimentLocks(tampered.items);
    rejectedCases.push({
      name: 'tampered receipt signature',
      value: tampered,
      status: 400,
      message: /invalid artifact signature/i,
    });

    rejectedCases.push({
      name: 'second item tampering leaves no partial multi-item import',
      value: partiallyTamperedMultiExperiment,
      status: 400,
      message: /invalid artifact signature/i,
    });

    const tamperedManifest = structuredClone(experiment) as PortableExperiment;
    tamperedManifest.manifest.locks[0].artifactDigest = '0'.repeat(64);
    rejectedCases.push({
      name: 'tampered manifest',
      value: tamperedManifest,
      status: 400,
      message: /manifest does not match/,
    });

    const unknownVersion = structuredClone(experiment) as PortableExperiment;
    unknownVersion.items[0].artifact.bundles[0] = lockReformPackage({
      ...unknownVersion.items[0].artifact.bundles[0].package,
      version: '99.0.0',
    });
    unknownVersion.manifest.locks = portableExperimentLocks(unknownVersion.items);
    rejectedCases.push({
      name: 'unknown model version',
      value: unknownVersion,
      status: 400,
      message: /Unknown model\/version/,
    });

    const unknownModel = structuredClone(experiment) as PortableExperiment;
    unknownModel.items[0].artifact.bundles[0] = lockReformPackage({
      ...unknownModel.items[0].artifact.bundles[0].package,
      id: 'foreign-reform',
    });
    unknownModel.manifest.locks = portableExperimentLocks(unknownModel.items);
    rejectedCases.push({
      name: 'unknown model identity',
      value: unknownModel,
      status: 400,
      message: /Unknown model\/version/,
    });

    const unknownRole = structuredClone(experiment) as PortableExperiment;
    (
      unknownRole.items[0].artifact.receipt.payload.bindings.models[0] as unknown as {
        role: string;
      }
    ).role = 'origin';
    unknownRole.manifest.locks = portableExperimentLocks(unknownRole.items);
    rejectedCases.push({
      name: 'unknown receipt role',
      value: unknownRole,
      status: 400,
    });

    const tamperedAnnotations = structuredClone(experiment) as PortableExperiment;
    assert.ok(tamperedAnnotations.items[0].annotations);
    tamperedAnnotations.items[0].annotations.models[0].reviewer += ' (changed)';
    tamperedAnnotations.manifest.locks = portableExperimentLocks(tamperedAnnotations.items);
    rejectedCases.push({
      name: 'tampered reviewed annotations',
      value: tamperedAnnotations,
      status: 400,
      message: /Unknown or altered reviewed source annotations/,
    });

    const unsupportedClaim = structuredClone(experiment) as PortableExperiment;
    const unsupportedReceipt = unsupportedClaim.items[0].artifact.receipt;
    unsupportedReceipt.payload.verification.status = 'unsupported';
    const issuerPrivateKey = createPrivateKey(
      readFileSync(join(directory, 'reform-issuer-private.pem')),
    );
    unsupportedReceipt.signature = sign(
      null,
      Buffer.from(canonical(unsupportedReceipt.payload)),
      issuerPrivateKey,
    ).toString('base64');
    unsupportedClaim.manifest.locks = portableExperimentLocks(unsupportedClaim.items);
    rejectedCases.push({
      name: 'signed unsupported proof claim',
      value: unsupportedClaim,
      status: 409,
      message: /fresh verification не подтверждает/,
    });

    for (const rejected of rejectedCases) {
      const response = await postImport(
        rejected.value,
        rejected.name === 'wrong trusted issuer' ? 'wrong trusted key' : bootstrap.issuerPublicKey,
      );
      assert.equal(response.status, rejected.status, rejected.name);
      const body = (await response.json()) as { error?: string };
      if (rejected.message) assert.match(body.error ?? '', rejected.message, rejected.name);
      assert.deepEqual(await (await fetch(`${base}/api/reform/imports`)).json(), [], rejected.name);
    }

    const imported = await postImport(experiment);
    assert.equal(imported.status, 201);
    const result = (await imported.json()) as {
      experiment: { id: string; importedAt: string };
      views: LabAnalysisView[];
    };
    assert.equal(result.views.length, 1);
    assert.equal(result.views[0].metricsReport?.evidence.current, true);
    assert.deepEqual(app.lab.store.workspace(), beforeImport);

    const duplicateImport = await postImport(experiment);
    assert.equal(duplicateImport.status, 201);
    const duplicateResult = (await duplicateImport.json()) as {
      experiment: { importedAt: string };
    };
    assert.equal(duplicateResult.experiment.importedAt, result.experiment.importedAt);
    assert.equal(
      ((await (await fetch(`${base}/api/reform/imports`)).json()) as unknown[]).length,
      1,
    );

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

    await app.close();
    app = await createApp({ dataDir: directory, web: false });
    app.server.listen(0, '127.0.0.1');
    await once(app.server, 'listening');
    base = `http://127.0.0.1:${(app.server.address() as AddressInfo).port}`;
    const restartedBootstrap = (await (
      await fetch(`${base}/api/reform/bootstrap`)
    ).json()) as LabBootstrap;
    headers = {
      'content-type': 'application/json',
      'x-normlab-token': restartedBootstrap.csrfToken,
    };
    assert.deepEqual(app.lab.store.workspace(), beforeImport);
    const persistedImports = (await (await fetch(`${base}/api/reform/imports`)).json()) as {
      id: string;
      importedAt: string;
    }[];
    assert.equal(persistedImports.length, 1);
    assert.equal(persistedImports[0].id, result.experiment.id);
    assert.equal(persistedImports[0].importedAt, result.experiment.importedAt);

    const replayAfterRestart = await fetch(
      `${base}/api/reform/imports/${result.experiment.id}/replay`,
      {
        method: 'POST',
        headers,
        body: '{}',
      },
    );
    assert.equal(replayAfterRestart.status, 200);
    const replayedAfterRestart = (await replayAfterRestart.json()) as {
      views: LabAnalysisView[];
    };
    assert.equal(replayedAfterRestart.views[0].metricsReport?.evidence.current, true);

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

test('multi-revision transfer preserves source history without mutating the receiving workspace', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'normlab-transfer-revisions-'));
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
    const post = (path: string, body: unknown) =>
      fetch(`${base}${path}`, { method: 'POST', headers, body: JSON.stringify(body) });
    const makeInput = (mState: 'established' | 'refuted') => ({
      narrative: 'Синтетический эпизод для проверки переноса ревизий.',
      group: 'K1',
      findings: {
        M: { state: mState, rationale: `Синтетическое основание M: ${mState}.` },
        N: { state: 'not-established', rationale: 'Нет достаточных учебных сведений.' },
        E: { state: 'refuted', rationale: 'Исключение не подтверждено.' },
      },
    });

    const firstSnapshotResponse = await post('/api/reform/snapshots', {
      input: makeInput('established'),
      expectedSnapshotId: bootstrap.workspace.snapshots[0].id,
    });
    assert.equal(firstSnapshotResponse.status, 201);
    const firstSnapshot = (await firstSnapshotResponse.json()).snapshot;
    const firstAnalysisResponse = await post('/api/reform/analyze', {
      snapshotId: firstSnapshot.id,
    });
    assert.equal(firstAnalysisResponse.status, 200);
    const firstViews = (await firstAnalysisResponse.json()).views as LabAnalysisView[];

    const secondSnapshotResponse = await post('/api/reform/snapshots', {
      input: makeInput('refuted'),
      expectedSnapshotId: firstSnapshot.id,
    });
    assert.equal(secondSnapshotResponse.status, 201);
    const secondSnapshot = (await secondSnapshotResponse.json()).snapshot;
    assert.equal(secondSnapshot.supersedes, firstSnapshot.id);
    const secondAnalysisResponse = await post('/api/reform/analyze', {
      snapshotId: secondSnapshot.id,
    });
    assert.equal(secondAnalysisResponse.status, 200);
    const secondViews = (await secondAnalysisResponse.json()).views as LabAnalysisView[];
    const beforeImport = structuredClone(app.lab.store.workspace());

    const exportResponse = await post('/api/reform/experiments/export', {
      analysisIds: [firstViews[0].analysis.id, secondViews[0].analysis.id],
    });
    assert.equal(exportResponse.status, 200);
    const experiment = (await exportResponse.json()) as PortableExperiment;
    assert.equal(experiment.items.length, 2);
    const [firstExport, secondExport] = experiment.items.map((item) => item.artifact.snapshot!);
    assert.equal(firstExport.id, firstSnapshot.id);
    assert.equal(firstExport.revision + 1, secondExport.revision);
    assert.equal(secondExport.id, secondSnapshot.id);
    assert.equal(secondExport.supersedes, firstExport.id);

    const imported = await post('/api/reform/imports', {
      experiment,
      trustedPublicKey: bootstrap.issuerPublicKey,
    });
    assert.equal(imported.status, 201);
    const importedResult = (await imported.json()) as { views: LabAnalysisView[] };
    assert.equal(importedResult.views.length, 2);
    assert.ok(importedResult.views.every((view) => view.metricsReport?.evidence.current));
    assert.deepEqual(app.lab.store.workspace(), beforeImport);
    const history = (await (await fetch(`${base}/api/reform/imports`)).json()) as {
      itemCount: number;
    }[];
    assert.equal(history.length, 1);
    assert.equal(history[0].itemCount, 2);
  } finally {
    await app.close();
    await rm(directory, { recursive: true, force: true });
  }
});
