import assert from 'node:assert/strict';
import { test } from 'node:test';
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { promisify } from 'node:util';
import type { Snapshot } from '../shared/domain.js';
import { getBundle } from '../server/bundles.js';
import { digest } from '../server/hash.js';
import { propose } from '../server/interpreter.js';
import { constructStatement, discoverLean, verifyCertificate } from '../server/verifier.js';

function snapshot(finding: Snapshot['finding']): Snapshot {
  const body = {
    id: '00000000-0000-4000-8000-000000000001',
    caseId: 'synthetic-case',
    revision: 1,
    createdAt: '2026-10-02T10:00:00.000Z',
    supersedes: null,
    authority: 'simulated-reviewer' as const,
    narrative: 'Synthetic Lean integration',
    finding,
    rationale: 'Test fixture',
  };
  return { ...body, digest: digest(body) };
}

test('Lean kernel verifies all four states against both exact bundles with audited axioms', async () => {
  const lean = await discoverLean();
  assert.equal(
    lean.available,
    true,
    'Install the exact lean-toolchain before running integration checks',
  );
  for (const id of ['reduction-v1', 'reduction-v2'] as const) {
    for (const state of ['established', 'refuted', 'unreviewed', 'not-established'] as const) {
      const input = snapshot(state);
      const bundle = getBundle(id);
      const result = await verifyCertificate(input, bundle, propose(input, bundle));
      assert.equal(result.status, 'verified', `${id}/${state}: ${result.reason}`);
      assert.ok(result.axioms.every((axiom) => axiom === 'propext'));
      assert.match(result.statementDigest, /^[a-f0-9]{64}$/);
      assert.match(result.toolchainDigest!, /^[a-f0-9]{64}$/);
    }
  }
});

test('Lean independently rejects a missing reduction even when the TypeScript guard is bypassed', async () => {
  const lean = await discoverLean();
  assert.ok(lean.binary);
  const input = snapshot('established');
  const bundle = getBundle('reduction-v1');
  const forged = propose(input, bundle);
  forged.result.outcomes[0].prisonMonths = 120;
  const core = await readFile('lean/NormLab.lean', 'utf8');
  const directory = await mkdtemp(join(tmpdir(), 'normlab-negative-'));
  try {
    const path = join(directory, 'Forged.lean');
    await writeFile(path, `${core}\n${constructStatement(input, bundle, forged)}`);
    await assert.rejects(promisify(execFile)(lean.binary, [path], { timeout: 20000 }), (error) => {
      const result = error as Error & { stdout?: string };
      return !!result.stdout?.includes('false');
    });
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
