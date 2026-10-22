import assert from 'node:assert/strict';
import test from 'node:test';
import { randomUUID } from 'node:crypto';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { ParkingLegal } from '../server/parking-legal.js';
import { constructParkingStatement, parkingProfileDigest } from '../server/parking-verifier.js';
import { evaluateParkingFragment } from '../shared/parking-legal.js';
import { parkingFixture, inconclusiveParkingProof } from './parking-legal-fixture.js';

test('parking Lean serializer excludes free text and rejects unknown keys or result extensions', () => {
  const { input } = parkingFixture();
  input.findings[0].rationale = 'axiom injected : False';
  const result = evaluateParkingFragment(input);
  const statement = constructParkingStatement(input, result);
  assert.ok(!statement.includes('injected'));
  assert.throws(() => constructParkingStatement(input, { ...result, missing: ['injected'] }));
  assert.throws(() => constructParkingStatement(input, { ...result, arbitrary: 'Lean code' }));
  assert.throws(() =>
    constructParkingStatement({ ...input, packageDigest: '0'.repeat(64) }, result),
  );
});

test('inconclusive verification preserves calculation and idempotent retry; save never invokes Lean', async () => {
  const folder = mkdtempSync(join(tmpdir(), 'parking-proof-unit-'));
  try {
    let calls = 0;
    const api = new ParkingLegal(async (i, r) => {
      calls++;
      return inconclusiveParkingProof(i, r);
    });
    const { input, draft } = parkingFixture();
    const record = await api.submit(folder, () => draft, input);
    assert.equal(record.verification?.status, 'inconclusive');
    assert.equal(record.result?.outcome, 'fragment-matched');
    assert.deepEqual(await api.submit(folder, () => draft, input), record);
    assert.equal(calls, 1);
    const saved = await api.submit(folder, () => draft, {
      ...input,
      action: 'save',
      requestId: randomUUID(),
      expectedAssessmentId: record.id,
    });
    assert.equal(saved.result, null);
    assert.equal(saved.verification, null);
    assert.equal(calls, 1);
    assert.equal(api.history(folder).length, 2);
    const path = join(folder, 'legal', `${record.id}.json`);
    const old = JSON.parse(readFileSync(path, 'utf8'));
    old.schema = 'normlab.parking-legal-assessment/v1';
    delete old.verification;
    writeFileSync(path, JSON.stringify(old));
    assert.equal(api.history(folder).find((r) => r.id === record.id)?.verification, undefined);
    old.verification = { ...record.verification, inputDigest: '0'.repeat(64) };
    writeFileSync(path, JSON.stringify(old));
    assert.throws(() => api.history(folder), /сохранённый расчёт/);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test('edits and concurrent saves during Lean cannot publish a stale assessment', async () => {
  for (const change of ['draft', 'assessment'] as const) {
    const folder = mkdtempSync(join(tmpdir(), 'parking-proof-race-'));
    try {
      let release!: () => void;
      const gate = new Promise<void>((resolve) => {
        release = resolve;
      });
      const api = new ParkingLegal(async (i, r) => {
        await gate;
        return inconclusiveParkingProof(i, r);
      });
      const { input, draft } = parkingFixture();
      let current = draft;
      const pending = api.submit(folder, () => current, input);
      if (change === 'draft') current = { ...draft, revisionId: randomUUID(), revision: 2 };
      else
        await api.submit(folder, () => current, {
          ...input,
          action: 'save',
          requestId: randomUUID(),
        });
      release();
      await assert.rejects(pending, /измени/);
      assert.equal(api.history(folder).length, change === 'draft' ? 0 : 1);
    } finally {
      rmSync(folder, { recursive: true, force: true });
    }
  }
});

test('history marks previous verified profiles without changing immutable receipts or retries', async () => {
  for (const previous of [false, true]) {
    const folder = mkdtempSync(join(tmpdir(), 'parking-proof-profile-'));
    try {
      let calls = 0;
      const api = new ParkingLegal(async (i, r) => {
        calls++;
        return {
          ...inconclusiveParkingProof(i, r),
          status: 'verified',
          version: 'Lean (version 4.30.0, mocked)',
          profileDigest: previous ? 'f'.repeat(64) : parkingProfileDigest,
          toolchainDigest: '2'.repeat(64),
          axioms: ['propext'],
        };
      });
      const { input, draft } = parkingFixture();
      const record = await api.submit(folder, () => draft, input);
      const path = join(folder, 'legal', `${record.id}.json`);
      const original = readFileSync(path, 'utf8');
      assert.equal(record.verifiedByPreviousProfile, previous ? true : undefined);
      assert.equal(record.verification?.status, 'verified');
      assert.ok(!Object.hasOwn(JSON.parse(original), 'verifiedByPreviousProfile'));
      assert.deepEqual(api.history(folder), [record]);
      assert.deepEqual(await api.submit(folder, () => draft, input), record);
      assert.equal(calls, 1);
      assert.equal(readFileSync(path, 'utf8'), original);
    } finally {
      rmSync(folder, { recursive: true, force: true });
    }
  }
});

test('concurrent identical requests retain one immutable receipt', async () => {
  const folder = mkdtempSync(join(tmpdir(), 'parking-proof-retry-'));
  try {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const api = new ParkingLegal(async (i, r) => {
      await gate;
      return inconclusiveParkingProof(i, r);
    });
    const { input, draft } = parkingFixture();
    const a = api.submit(folder, () => draft, input);
    const b = api.submit(folder, () => draft, input);
    release();
    assert.deepEqual(await a, await b);
    assert.equal(api.history(folder).length, 1);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});
