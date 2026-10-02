import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { Certificate, FindingState, Snapshot, Verification } from '../shared/domain.js';
import { legalIrSchema, snapshotInputSchema } from '../shared/domain.js';
import { getBundle } from '../server/bundles.js';
import { canonical, digest } from '../server/hash.js';
import { compare, propose } from '../server/interpreter.js';
import { ReceiptSigner, verifyReceipt } from '../server/receipts.js';
import { Conflict, Store } from '../server/store.js';
import { checkCertificate } from '../server/verifier.js';
import { isCurrentAnalysis } from '../shared/current.js';

export function snapshot(finding: FindingState): Snapshot {
  const value = {
    id: '00000000-0000-4000-8000-000000000001',
    caseId: 'synthetic-case',
    revision: 1,
    createdAt: '2026-10-02T10:00:00.000Z',
    supersedes: null,
    authority: 'simulated-reviewer' as const,
    narrative: 'Synthetic example',
    finding,
    rationale: finding === 'unreviewed' ? '' : 'Synthetic finding rationale',
  };
  return { ...value, digest: digest(value) };
}

test('all finding states preserve declared scope and uncertainty in both bundles', () => {
  for (const id of ['reduction-v1', 'reduction-v2'] as const) {
    const bundle = getBundle(id);
    for (const state of ['established', 'refuted', 'unreviewed', 'not-established'] as const) {
      const input = snapshot(state);
      const cert = propose(input, bundle);
      assert.deepEqual(checkCertificate(input, bundle, cert), cert);
      const expected =
        state === 'established'
          ? [id === 'reduction-v1' ? 80 : 60]
          : state === 'refuted'
            ? [120]
            : [id === 'reduction-v1' ? 80 : 60, 120];
      assert.deepEqual(
        cert.result.outcomes.map((o) => o.prisonMonths),
        expected,
      );
      assert.equal(
        cert.result.outcomes.every((o) => o.fineAmount === 200000),
        true,
      );
    }
  }
});

test('checker rejects omitted mandatory adjustment, tampered fine, ledger and unknown fields', () => {
  const input = snapshot('established');
  const bundle = getBundle('reduction-v1');
  const changes: ((cert: Certificate) => void)[] = [
    (cert) => {
      cert.result.outcomes[0].prisonMonths = 120;
    },
    (cert) => {
      cert.result.outcomes[0].fineAmount = 199999;
    },
    (cert) => {
      cert.result.ledger[0].status = 'inapplicable';
    },
    (cert) => {
      cert.result.outcomes[0].ruleStatus = 'inapplicable';
    },
    (cert) => {
      Object.assign(cert, { leanSource: 'malicious source' });
    },
  ];
  for (const change of changes) {
    const cert = propose(input, bundle);
    change(cert);
    assert.throws(() => checkCertificate(input, bundle, cert));
  }
});

test('open questions cannot lose a branch, duplicate one, or become complete', () => {
  for (const state of ['unreviewed', 'not-established'] as const) {
    const input = snapshot(state);
    const bundle = getBundle('reduction-v1');
    const cert = propose(input, bundle);
    cert.result.outcomes.pop();
    assert.throws(() => checkCertificate(input, bundle, cert), /branch coverage/);
    const duplicate = propose(input, bundle);
    duplicate.result.outcomes[1] = duplicate.result.outcomes[0];
    assert.throws(() => checkCertificate(input, bundle, duplicate), /branch coverage/);
    const final = propose(input, bundle);
    final.result.status = 'complete';
    assert.throws(() => checkCertificate(input, bundle, final), /branch coverage/);
  }
});

test('certificates bind provenance, snapshot and trusted model content', () => {
  const input = snapshot('established');
  const bundle = getBundle('reduction-v1');
  const cert = propose(input, bundle);
  assert.throws(() => checkCertificate(snapshot('refuted'), bundle, cert), /binding/);
  assert.throws(
    () => checkCertificate({ ...input, narrative: 'Changed input' }, bundle, cert),
    /integrity/,
  );
  assert.throws(
    () => checkCertificate(input, bundle, { ...cert, bundleProvenanceDigest: '0'.repeat(64) }),
    /binding/,
  );
  const altered = getBundle('reduction-v1');
  altered.ir.adjustment.numerator = 1;
  assert.throws(() => checkCertificate(input, altered, cert), /trusted registry/);
});

test('strict domain rejects fractional reductions, unsupported IR and missing rationale', () => {
  const ir = getBundle('reduction-v1').ir;
  assert.equal(
    legalIrSchema.safeParse({ ...ir, adjustment: { ...ir.adjustment, denominator: 7 } }).success,
    false,
  );
  assert.equal(legalIrSchema.safeParse({ ...ir, executable: 'plugin.js' }).success, false);
  assert.equal(
    snapshotInputSchema.safeParse({ narrative: 'Synthetic', finding: 'refuted', rationale: '' })
      .success,
    false,
  );
  assert.equal(
    snapshotInputSchema.safeParse({ narrative: 'Synthetic', finding: 'unreviewed', rationale: '' })
      .success,
    true,
  );
});

test('comparison uses an explicit baseline and exhibits the non-equivalence witness', () => {
  const diff = compare(getBundle('reduction-v1'), getBundle('reduction-v2'));
  assert.equal(diff.equivalent, false);
  assert.deepEqual(
    diff.rows.map((row) => row.prisonDelta),
    [-20, 0],
  );
  assert.deepEqual(
    compare(getBundle('reduction-v2'), getBundle('reduction-v1')).rows.map(
      (row) => row.prisonDelta,
    ),
    [20, 0],
  );
  assert.equal(compare(getBundle('reduction-v1'), getBundle('reduction-v1')).equivalent, true);
});

test('canonical hashes ignore object order, preserve array order and reject unsafe numbers', () => {
  assert.equal(digest({ b: 2, a: 1 }), digest({ a: 1, b: 2 }));
  assert.notEqual(digest([1, 2]), digest([2, 1]));
  assert.throws(() => canonical(NaN));
  assert.throws(() => canonical(Number.MAX_SAFE_INTEGER + 1));
});

test('snapshots survive restart and reject lost updates', () => {
  const directory = mkdtempSync(join(tmpdir(), 'normlab-store-test-'));
  try {
    const path = join(directory, 'store.sqlite');
    const store = new Store(path);
    const first = store.workspace().snapshots[0];
    const next = store.createSnapshot(
      { narrative: 'Synthetic', finding: 'established', rationale: 'Given by fixture' },
      first.id,
    );
    assert.equal(next.supersedes, first.id);
    assert.throws(
      () =>
        store.createSnapshot(
          { narrative: 'Stale', finding: 'unreviewed', rationale: '' },
          first.id,
        ),
      Conflict,
    );
    assert.deepEqual(store.snapshot(first.id), first);
    store.close();
    const reopened = new Store(path);
    assert.equal(reopened.workspace().snapshots.length, 2);
    assert.deepEqual(reopened.workspace().snapshots[0], next);
    reopened.close();
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('Ed25519 receipt detects tampering and does not trust a substituted issuer', () => {
  const input = snapshot('established');
  const bundle = getBundle('reduction-v1');
  const cert = propose(input, bundle);
  const verification: Verification = {
    status: 'inconclusive',
    engine: 'lean-kernel',
    version: null,
    statementDigest: digest('test'),
    toolchainDigest: null,
    axioms: [],
    reason: 'No proof in this unit test',
    durationMs: 0,
  };
  const signer = new ReceiptSigner();
  const receipt = signer.issue(input, bundle, cert, verification);
  assert.equal(verifyReceipt(receipt, signer.publicKey), true);
  const altered = structuredClone(receipt);
  altered.payload.verification.status = 'verified';
  assert.equal(verifyReceipt(altered, signer.publicKey), false);
  const other = new ReceiptSigner();
  assert.equal(
    verifyReceipt(other.issue(input, bundle, cert, verification), signer.publicKey),
    false,
  );
});

test('current-result checks invalidate old tools, snapshots and bundle provenance', () => {
  const input = snapshot('established');
  const bundle = getBundle('reduction-v1');
  const cert = propose(input, bundle);
  const toolchain = digest('toolchain-v1');
  const signer = new ReceiptSigner();
  const receipt = signer.issue(input, bundle, cert, {
    status: 'verified',
    engine: 'lean-kernel',
    version: 'test-only',
    statementDigest: digest('statement'),
    toolchainDigest: toolchain,
    axioms: [],
    reason: 'Unit fixture only',
    durationMs: 0,
  });
  const analysis = {
    id: 'test',
    snapshotId: input.id,
    bundleId: bundle.id,
    certificate: cert,
    receipt,
  };
  assert.equal(isCurrentAnalysis(analysis, input, bundle, toolchain), true);
  assert.equal(isCurrentAnalysis(analysis, input, bundle, digest('toolchain-v2')), false);
  assert.equal(isCurrentAnalysis(analysis, input, bundle, null), false);
  assert.equal(isCurrentAnalysis(analysis, snapshot('refuted'), bundle, toolchain), false);
  assert.equal(
    isCurrentAnalysis(
      analysis,
      input,
      { ...bundle, provenanceDigest: digest('revised-source') },
      toolchain,
    ),
    false,
  );
});
