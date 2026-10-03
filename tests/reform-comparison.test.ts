import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { randomUUID } from 'node:crypto';
import type { ReformCertificate, ReformReceipt } from '../shared/reform-contracts.js';
import {
  validateReformCertificateBindings,
  validateReformQuery,
  validateReformReceiptBindings,
} from '../server/reform-bindings.js';
import { digest } from '../server/hash.js';
import { getReformBundle, lockReformPackage } from '../server/reform-models.js';
import {
  comparisonQuery,
  getReformCounterexampleBundle,
  mitigationQuery,
  proposeReformQuery,
  queryInputs,
  relationHolds,
} from '../server/reform-queries.js';
import {
  exportReformArtifacts,
  reformExportSchema,
  verifyReformReceiptSignature,
} from '../server/reform-receipts.js';

const a = getReformBundle('A'),
  b = getReformBundle('B'),
  c = getReformBundle('C');
const expected = JSON.parse(
  readFileSync(new URL('../fixtures/reform-v1/fixture.json', import.meta.url), 'utf8'),
).expected as {
  input: { group: 'K1' | 'K2'; M: boolean; N: boolean; E: boolean };
  prisonMonths: Record<'A' | 'B' | 'C', number>;
  fineAmount: number;
}[];

function unsignedCorpusReceipt(
  query: ReturnType<typeof comparisonQuery>,
  certificate: ReformCertificate,
): ReformReceipt {
  assert.equal(query.kind, 'comparison');
  assert.equal(certificate.kind, 'comparison');
  return {
    payload: {
      schema: 'normlab.receipt/v2',
      id: randomUUID(),
      createdAt: '2026-10-02T14:00:00.000Z',
      queryKind: query.kind,
      bindings: {
        queryDigest: digest(query),
        certificateDigest: digest(certificate),
        resultDigest: digest(certificate.result),
        statementDigest: '0'.repeat(64),
        assumptionsDigest: digest(query.assumptions),
        models: [
          { role: 'baseline', bundle: query.baseline },
          { role: 'candidate', bundle: query.candidate },
        ],
      },
      coverage: {
        domainDigest: digest(query.domain),
        kind: 'corpus',
        status: 'partial',
        declaredCardinality: 16,
        coveredCardinality: certificate.result.rows.length,
      },
      verification: {
        status: 'inconclusive',
        engine: 'lean-kernel',
        version: null,
        method: null,
        toolchainDigest: null,
        axioms: [],
        reason: 'Unsigned structural fixture',
      },
      issuer: '0'.repeat(64),
    },
    signature: Buffer.alloc(64).toString('base64'),
    publicKey: 'Untrusted structural fixture',
  };
}

test('comparison and property producers preserve exact scopes and all manual A/B/C outcomes', () => {
  let rows = 0,
    pairs = 0;
  for (const property of [
    'equivalence',
    'component-no-increase',
    'strict-reduction',
    'preserved-outside',
  ] as const) {
    const candidate = property === 'equivalence' ? b : c;
    const role = property === 'equivalence' ? 'B' : 'C';
    const query = comparisonQuery(a, candidate, property);
    const certificate = proposeReformQuery(query, [a, candidate]);
    assert.equal(certificate.kind, 'comparison');
    assert.equal(certificate.result.verdict, 'holds');
    for (const row of certificate.result.rows) {
      const manual = expected.find((r) => digest(r.input) === digest(row.input))!;
      assert.equal(row.baseline.prisonMonths, manual.prisonMonths.A);
      assert.equal(row.candidate.prisonMonths, manual.prisonMonths[role]);
      assert.equal(row.baseline.fineAmount, manual.fineAmount);
      assert.deepEqual(row.baseline.qualification, row.candidate.qualification);
      rows++;
    }
  }
  for (const [role, bundle] of [
    ['A', a],
    ['B', b],
    ['C', c],
  ] as const) {
    const certificate = proposeReformQuery(mitigationQuery(bundle), [bundle]);
    assert.equal(certificate.kind, 'property');
    assert.equal(certificate.result.verdict, 'holds');
    for (const pair of certificate.result.pairs) {
      assert.deepEqual(pair.after, { ...pair.before, M: true });
      assert.equal(
        pair.baseline.prisonMonths,
        expected.find((r) => digest(r.input) === digest(pair.before))!.prisonMonths[role],
      );
      assert.equal(
        pair.candidate.prisonMonths,
        expected.find((r) => digest(r.input) === digest(pair.after))!.prisonMonths[role],
      );
      pairs++;
    }
  }
  assert.equal(rows, 48);
  assert.equal(pairs, 24);
});

test('supported erroneous amendment has two outside-M counterexamples while missing exclusion remains inadmissible', () => {
  const d = getReformCounterexampleBundle();
  const query = comparisonQuery(a, d, 'preserved-outside');
  assert.equal(query.kind, 'comparison');
  const certificate = proposeReformQuery(query, [a, d]);
  assert.equal(certificate.kind, 'comparison');
  assert.equal(certificate.result.verdict, 'counterexample');
  assert.deepEqual(
    certificate.result.rows
      .filter((r) => !relationHolds(query, r.baseline, r.candidate))
      .map((r) => [
        r.input.group,
        r.input.M,
        r.input.N,
        r.input.E,
        r.baseline.prisonMonths,
        r.candidate.prisonMonths,
      ]),
    [
      ['K1', false, true, false, 90, 80],
      ['K2', false, true, false, 180, 160],
    ],
  );
  const noExclusion = structuredClone(c.package);
  noExclusion.ir.rules = noExclusion.ir.rules.filter((r) => r.operation.kind !== 'exclude');
  assert.throws(() => lockReformPackage(noExclusion), /exactly one exclude/);
});

test('partial evidence cannot silently become finite coverage and witnesses must bind actual rows', () => {
  const query = comparisonQuery(a, b, 'equivalence');
  assert.throws(
    () => proposeReformQuery(query, [a, b], { inputs: queryInputs(query).slice(0, 1) }),
    /coverage/,
  );
  const corpus = proposeReformQuery(query, [a, b], {
    method: 'corpus',
    inputs: queryInputs(query).slice(0, 1),
  });
  assert.equal(corpus.kind, 'comparison');
  assert.equal(corpus.result.rows.length, 1);
  const promoted = structuredClone(corpus);
  promoted.result.method = 'exhaustive-finite-domain';
  assert.throws(() => validateReformCertificateBindings(promoted, query, [a, b]), /coverage/);
  const repeated = structuredClone(corpus);
  repeated.result.rows.push(repeated.result.rows[0]);
  assert.throws(() => validateReformCertificateBindings(repeated, query, [a, b]), /coverage/);
  const d = getReformCounterexampleBundle();
  const badQuery = comparisonQuery(a, d, 'preserved-outside');
  const bad = proposeReformQuery(badQuery, [a, d]);
  assert.equal(bad.kind, 'comparison');
  bad.result.counterexample!.candidate.prisonMonths++;
  assert.throws(() => validateReformCertificateBindings(bad, badQuery, [a, d]), /Counterexample/);
});

test('query roles, conditions, profile digests and duplicate registry IDs are authenticated', () => {
  const query = comparisonQuery(a, c, 'strict-reduction');
  assert.equal(query.kind, 'comparison');
  const cert = proposeReformQuery(query, [a, c]);
  assert.throws(
    () =>
      validateReformCertificateBindings(
        cert,
        { ...query, baseline: query.candidate, candidate: query.baseline },
        [a, c],
      ),
    /query binding/,
  );
  assert.throws(() => validateReformQuery({ ...query, condition: null }, [a, c]), /scope/);
  assert.throws(
    () =>
      validateReformQuery(
        { ...query, candidate: { ...query.candidate, profileDigest: '0'.repeat(64) } },
        [a, c],
      ),
    /bundle binding/,
  );
  assert.throws(() => validateReformQuery(query, [a, c, c]), /duplicate bundle/);
});

test('corpus receipt coverage stays partial even with all rows and cannot claim a finite-domain method', () => {
  const query = comparisonQuery(a, b, 'equivalence');
  const certificate = proposeReformQuery(query, [a, b], { method: 'corpus' });
  const receipt = unsignedCorpusReceipt(query, certificate);
  validateReformReceiptBindings(receipt, query, certificate, [a, b]);
  const complete = structuredClone(receipt);
  complete.payload.coverage.status = 'declared-complete';
  assert.throws(
    () => validateReformReceiptBindings(complete, query, certificate, [a, b]),
    /promoted/,
  );
  const wrongMethod = structuredClone(receipt);
  wrongMethod.payload.verification = {
    status: 'verified',
    engine: 'lean-kernel',
    version: 'Synthetic version',
    method: 'finite-domain-theorem',
    toolchainDigest: '1'.repeat(64),
    axioms: ['propext'],
    reason: 'False finite claim',
  };
  assert.throws(
    () => validateReformReceiptBindings(wrongMethod, query, certificate, [a, b]),
    /proof metadata/,
  );
});

test('export envelope is strict and a structural receipt never establishes issuer trust', () => {
  const query = comparisonQuery(a, b, 'equivalence');
  const certificate = proposeReformQuery(query, [a, b], {
    method: 'corpus',
    inputs: queryInputs(query).slice(0, 1),
  });
  const receipt = unsignedCorpusReceipt(query, certificate);
  const artifact = exportReformArtifacts(query, [a, b], certificate, receipt);
  assert.equal(reformExportSchema.safeParse(artifact).success, true);
  assert.equal(
    reformExportSchema.safeParse({ ...artifact, leanSource: 'axiom falseClaim : False' }).success,
    false,
  );
  assert.equal(verifyReformReceiptSignature(receipt, receipt.publicKey), false);
  assert.equal(artifact.snapshot, null);
});
