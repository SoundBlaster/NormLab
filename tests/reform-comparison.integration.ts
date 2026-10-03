import assert from 'node:assert/strict';
import { test } from 'node:test';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, rm, writeFile, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { createPublicKey, generateKeyPairSync, sign } from 'node:crypto';
import type {
  ReformCertificate,
  ReformQuery,
  ReformReceipt,
  ReformSnapshot,
} from '../shared/reform-contracts.js';
import { canonical, digest } from '../server/hash.js';
import { getReformBundle } from '../server/reform-models.js';
import {
  comparisonQuery,
  getReformCounterexampleBundle,
  mitigationQuery,
  proposeReformQuery,
  queryInputs,
} from '../server/reform-queries.js';
import {
  constructReformStatement,
  reformLeanCore,
  verifyReformCertificate,
} from '../server/reform-verifier.js';
import { discoverLean } from '../server/verifier.js';
import {
  exportReformArtifacts,
  ReformReceiptSigner,
  replayReformExport,
  replayReformReceipt,
  verifyReformReceiptSignature,
} from '../server/reform-receipts.js';
import { decisionQuery } from '../server/reform-bindings.js';
import { leanMemoryArgument } from './lean-resources.js';

const a = getReformBundle('A'),
  b = getReformBundle('B'),
  c = getReformBundle('C'),
  d = getReformCounterexampleBundle();
const execute = promisify(execFile);

test('Lean proves equivalence A/B, all A/C properties, all unary properties and audits four general scope theorems', async () => {
  const cases = [
    [comparisonQuery(a, b, 'equivalence'), [a, b]],
    ...(['component-no-increase', 'strict-reduction', 'preserved-outside'] as const).map(
      (p) => [comparisonQuery(a, c, p), [a, c]] as const,
    ),
    ...[a, b, c].map((model) => [mitigationQuery(model), [model]] as const),
  ] as const;
  for (const [query, bundles] of cases) {
    const certificate = proposeReformQuery(query, [...bundles]);
    const verification = await verifyReformCertificate(query, [...bundles], certificate);
    assert.equal(verification.status, 'verified', `${query.kind}: ${verification.reason}`);
    assert.equal(verification.method, 'finite-domain-theorem');
    assert.ok(verification.axioms.every((x) => x === 'propext'));
  }
  const lean = await discoverLean();
  assert.ok(lean.binary);
  const dir = await mkdtemp(join(tmpdir(), 'normlab-scope-axioms-'));
  try {
    const path = join(dir, 'Scopes.lean');
    await writeFile(
      path,
      reformLeanCore +
        '\n' +
        [
          'comparison_scope_sound',
          'comparison_counterexample',
          'property_scope_sound',
          'property_counterexample',
        ]
          .map((name) => `#print axioms NormLabReform.${name}`)
          .join('\n'),
    );
    const { stdout, stderr } = await execute(lean.binary, [leanMemoryArgument, path], {
      timeout: 20000,
    });
    assert.equal(stderr, '');
    const reports = [...stdout.matchAll(/depends on axioms: \[([^\]]*)\]/g)];
    assert.equal(reports.length, 4, stdout);
    for (const report of reports)
      assert.ok(
        report[1].split(',').every((x) => x.trim() === 'propext'),
        stdout,
      );
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test('Lean verifies a genuine counterexample and corpus holds do not become a universal claim', async () => {
  const query = comparisonQuery(a, d, 'preserved-outside');
  const certificate = proposeReformQuery(query, [a, d]);
  assert.equal(certificate.kind, 'comparison');
  assert.equal(certificate.result.counterexample!.baseline.prisonMonths, 90);
  assert.equal(certificate.result.counterexample!.candidate.prisonMonths, 80);
  assert.equal((await verifyReformCertificate(query, [a, d], certificate)).status, 'verified');
  const corpus = proposeReformQuery(query, [a, d], {
    method: 'corpus',
    inputs: queryInputs(query).slice(0, 1),
  });
  assert.equal(corpus.kind, 'comparison');
  assert.equal(corpus.result.verdict, 'holds');
  const proof = await verifyReformCertificate(query, [a, d], corpus);
  assert.equal(proof.status, 'verified');
  assert.equal(proof.method, 'case-theorem');
  assert.match(proof.reason, /no universal coverage/);
});

async function expectKernelRejection(
  query: ReformQuery,
  bundles: (typeof a)[],
  certificate: ReformCertificate,
) {
  const lean = await discoverLean();
  assert.ok(lean.binary);
  const dir = await mkdtemp(join(tmpdir(), 'normlab-comparison-negative-'));
  try {
    const path = join(dir, 'False.lean');
    await writeFile(
      path,
      reformLeanCore + '\n' + constructReformStatement(query, bundles, certificate),
    );
    await assert.rejects(
      execute(lean.binary, [leanMemoryArgument, '-T200000', path], { timeout: 30000 }),
      (error) =>
        /proved that the proposition[\s\S]*is false/.test(
          (error as { stdout?: string }).stdout ?? '',
        ),
    );
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

test('kernel rejects forged comparison/property evidence even with contextual guards bypassed', async () => {
  const query = comparisonQuery(a, b, 'equivalence');
  const full = proposeReformQuery(query, [a, b]);
  assert.equal(full.kind, 'comparison');
  const lost = structuredClone(full);
  lost.result.rows.pop();
  const duplicate = structuredClone(full);
  duplicate.result.rows[1] = duplicate.result.rows[0];
  const reordered = structuredClone(full);
  reordered.result.rows.reverse();
  for (const certificate of [lost, duplicate, reordered])
    await expectKernelRejection(query, [a, b], certificate);
  const corpus = proposeReformQuery(query, [a, b], {
    method: 'corpus',
    inputs: queryInputs(query).slice(0, 1),
  });
  assert.equal(corpus.kind, 'comparison');
  for (const field of ['prisonMonths', 'fineAmount'] as const) {
    const wrong = structuredClone(corpus);
    wrong.result.rows[0].candidate[field]++;
    await expectKernelRejection(query, [a, b], wrong);
  }
  const wrongQualification = structuredClone(corpus);
  wrongQualification.result.rows[0].candidate.qualification = 'K2';
  await expectKernelRejection(query, [a, b], wrongQualification);
  const falseWitness = structuredClone(corpus);
  falseWitness.result.verdict = 'counterexample';
  falseWitness.result.counterexample = falseWitness.result.rows[0];
  await expectKernelRejection(query, [a, b], falseWitness);
  const badQuery = comparisonQuery(a, d, 'preserved-outside');
  const refuted = proposeReformQuery(badQuery, [a, d], {
    method: 'corpus',
    inputs: [queryInputs(badQuery)[2]],
  });
  assert.equal(refuted.kind, 'comparison');
  const falseHolds = structuredClone(refuted);
  falseHolds.result.verdict = 'holds';
  falseHolds.result.counterexample = null;
  await expectKernelRejection(badQuery, [a, d], falseHolds);
  const unboundWitness = structuredClone(refuted);
  unboundWitness.result.counterexample!.candidate.prisonMonths++;
  await expectKernelRejection(badQuery, [a, d], unboundWitness);
  const outside = structuredClone(corpus);
  outside.queryDigest = digest(badQuery);
  outside.result.rows[0].input.M = true;
  await expectKernelRejection(badQuery, [a, d], outside);
  const unaryQuery = mitigationQuery(c);
  const unary = proposeReformQuery(unaryQuery, [c]);
  assert.equal(unary.kind, 'property');
  const lostPair = structuredClone(unary);
  lostPair.result.pairs.pop();
  await expectKernelRejection(unaryQuery, [c], lostPair);
  const changedPair = structuredClone(unary);
  changedPair.result.pairs[0].after.E = !changedPair.result.pairs[0].before.E;
  await expectKernelRejection(unaryQuery, [c], changedPair);
  const unaryFalseWitness = structuredClone(unary);
  unaryFalseWitness.result.verdict = 'counterexample';
  unaryFalseWitness.result.counterexample = unaryFalseWitness.result.pairs[0];
  await expectKernelRejection(unaryQuery, [c], unaryFalseWitness);
});

test('signed receipts replay for decision, comparison, property, counterexample and corpus with separate issuer trust', async () => {
  const signer = new ReformReceiptSigner();
  const content = {
    schema: 'normlab.snapshot/v2' as const,
    id: '00000000-0000-4000-8000-000000000301',
    caseId: 'receipt-case',
    revision: 1,
    createdAt: '2026-10-02T14:00:00.000Z',
    supersedes: null,
    authority: 'simulated-reviewer' as const,
    narrative: 'Receipt case',
    group: 'K1' as const,
    findings: {
      M: { state: 'established' as const, rationale: 'Test M' },
      N: { state: 'refuted' as const, rationale: 'Test N' },
      E: { state: 'refuted' as const, rationale: 'Test E' },
    },
  };
  const snapshot: ReformSnapshot = { ...content, digest: digest(content) };
  const decision = decisionQuery(snapshot, c);
  const cases: {
    query: ReformQuery;
    bundles: (typeof a)[];
    certificate: ReformCertificate;
    snapshot?: ReformSnapshot;
  }[] = [
    {
      query: decision,
      bundles: [c],
      certificate: proposeReformQuery(decision, [c], {}, snapshot),
      snapshot,
    },
    ...[
      [comparisonQuery(a, b, 'equivalence'), [a, b]],
      [mitigationQuery(c), [c]],
      [comparisonQuery(a, d, 'preserved-outside'), [a, d]],
    ].map(([q, models]) => {
      const query = q as ReformQuery,
        bundles = models as (typeof a)[];
      return { query, bundles, certificate: proposeReformQuery(query, bundles) };
    }),
  ];
  const corpusQuery = comparisonQuery(a, b, 'equivalence');
  cases.push({
    query: corpusQuery,
    bundles: [a, b],
    certificate: proposeReformQuery(corpusQuery, [a, b], {
      method: 'corpus',
      inputs: queryInputs(corpusQuery).slice(0, 1),
    }),
  });
  for (const item of cases) {
    const receipt = await signer.issue(item.query, item.bundles, item.certificate, item.snapshot);
    assert.equal(verifyReformReceiptSignature(receipt, signer.publicKey), true);
    assert.equal(verifyReformReceiptSignature(receipt, new ReformReceiptSigner().publicKey), false);
    const artifact = exportReformArtifacts(
      item.query,
      item.bundles,
      item.certificate,
      receipt,
      item.snapshot,
    );
    const replay = await replayReformExport(JSON.stringify(artifact), signer.publicKey);
    assert.equal(replay.current, true, replay.reason);
    const tampered = structuredClone(receipt);
    tampered.payload.bindings.statementDigest = '0'.repeat(64);
    assert.equal(verifyReformReceiptSignature(tampered, signer.publicKey), false);
    assert.equal(
      (
        await replayReformReceipt(
          receipt,
          signer.publicKey,
          { ...item.query, assumptions: [...item.query.assumptions, 'Changed'] },
          item.bundles,
          item.certificate,
          item.snapshot,
        )
      ).bindingsValid,
      false,
    );
    if (item.certificate.kind !== 'decision' && item.certificate.result.method === 'corpus') {
      assert.equal(receipt.payload.coverage.status, 'partial');
      assert.equal(receipt.payload.coverage.kind, 'corpus');
      assert.equal(receipt.payload.verification.method, 'case-theorem');
    }
  }
});

test('a trusted signed claim still needs fresh proof and current toolchain; signer never signs refuted results', async () => {
  const query = mitigationQuery(c);
  const certificate = proposeReformQuery(query, [c], {
    method: 'corpus',
    inputs: queryInputs(query).slice(0, 1),
  });
  assert.equal(certificate.kind, 'property');
  const receipt = await new ReformReceiptSigner().issue(query, [c], certificate);
  const key = generateKeyPairSync('ed25519');
  const publicKey = createPublicKey(key.privateKey)
    .export({ format: 'pem', type: 'spki' })
    .toString();
  const signed = (payload: ReformReceipt['payload']): ReformReceipt => ({
    payload: { ...payload, issuer: digest(publicKey) },
    publicKey,
    signature: sign(
      null,
      Buffer.from(canonical({ ...payload, issuer: digest(publicKey) })),
      key.privateKey,
    ).toString('base64'),
  });
  const historical = structuredClone(receipt.payload);
  historical.verification.toolchainDigest = '0'.repeat(64);
  const historicalReplay = await replayReformReceipt(
    signed(historical),
    publicKey,
    query,
    [c],
    certificate,
  );
  assert.equal(historicalReplay.signatureValid, true);
  assert.equal(historicalReplay.bindingsValid, true);
  assert.equal(historicalReplay.current, false);
  assert.equal(historicalReplay.verification!.status, 'verified');
  const wrong = structuredClone(certificate);
  wrong.result.pairs[0].candidate.prisonMonths++;
  const falsePayload = structuredClone(receipt.payload);
  falsePayload.bindings.certificateDigest = digest(wrong);
  falsePayload.bindings.resultDigest = digest(wrong.result);
  const falseReplay = await replayReformReceipt(signed(falsePayload), publicKey, query, [c], wrong);
  assert.equal(falseReplay.signatureValid, true);
  assert.equal(falseReplay.bindingsValid, true);
  assert.equal(falseReplay.current, false);
  assert.equal(falseReplay.verification!.status, 'rejected');
  await assert.rejects(new ReformReceiptSigner().issue(query, [c], wrong), /rejected/);
  const dir = await mkdtemp(join(tmpdir(), 'normlab-issuer-test-'));
  try {
    const first = new ReformReceiptSigner(dir),
      second = new ReformReceiptSigner(dir);
    assert.equal(first.publicKey, second.publicKey);
    assert.equal((await stat(join(dir, 'reform-issuer-private.pem'))).mode & 0o777, 0o600);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
