import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import {
  exportedReformSchemas,
  reformContractSchemas,
  type ReformCertificate,
  type ReformCompletedInput,
  type ReformQuery,
  type ReformReceipt,
  type ReformSnapshot,
  type ReformSnapshotInput,
} from '../shared/reform-contracts.js';
import {
  interpretReform,
  parseReformInput,
  parseReformJson,
  parseSupportedReformIR,
  validateReformResultContext,
  ReformContractError,
} from '../shared/reform-semantics.js';
import {
  getReformBundle,
  lockReformPackage,
  validateReformBundle,
  reformProfile,
} from '../server/reform-models.js';
import {
  decisionQuery,
  reformAssumptions,
  reformBundleRef,
  reformDomain,
  validateReformCertificateBindings,
  validateReformQuery,
  validateReformReceiptBindings,
  validateReformSnapshot,
} from '../server/reform-bindings.js';
import { digest } from '../server/hash.js';

const fixture = JSON.parse(
  readFileSync(new URL('../fixtures/reform-v1/fixture.json', import.meta.url), 'utf8'),
) as {
  expected: {
    input: ReformCompletedInput;
    prisonMonths: Record<'A' | 'B' | 'C', number>;
    fineAmount: number;
  }[];
};
const roles = ['A', 'B', 'C'] as const;
const states = ['unreviewed', 'established', 'refuted', 'not-established'] as const;

function input(
  group: 'K1' | 'K2',
  M: (typeof states)[number],
  N: (typeof states)[number],
  E: (typeof states)[number],
): ReformSnapshotInput {
  const finding = (state: (typeof states)[number]) => ({
    state,
    rationale: state === 'unreviewed' ? '' : 'Synthetic rationale',
  });
  return {
    narrative: 'Synthetic reform fixture',
    group,
    findings: { M: finding(M), N: finding(N), E: finding(E) },
  };
}
function snapshot(value = input('K1', 'established', 'established', 'refuted')): ReformSnapshot {
  const content = {
    schema: 'normlab.snapshot/v2' as const,
    id: '00000000-0000-4000-8000-000000000101',
    caseId: 'reform-case',
    revision: 1,
    createdAt: '2026-10-02T11:00:00.000Z',
    supersedes: null,
    authority: 'simulated-reviewer' as const,
    ...value,
  };
  return { ...content, digest: digest(content) };
}
function decision() {
  const bundle = getReformBundle('B');
  const snap = snapshot();
  const query = decisionQuery(snap, bundle);
  const result = interpretReform(
    { narrative: snap.narrative, group: snap.group, findings: snap.findings },
    bundle.package.ir,
  );
  const certificate: ReformCertificate = {
    schema: 'normlab.certificate/v2',
    kind: 'decision',
    queryDigest: digest(query),
    result,
  };
  return { bundle, snap, query, certificate };
}
function receiptFixture(query: ReformQuery, certificate: ReformCertificate): ReformReceipt {
  assert.equal(query.kind, 'decision');
  assert.equal(certificate.kind, 'decision');
  return {
    payload: {
      schema: 'normlab.receipt/v2',
      id: '00000000-0000-4000-8000-000000000102',
      createdAt: '2026-10-02T11:00:00.000Z',
      queryKind: 'decision',
      bindings: {
        queryDigest: digest(query),
        certificateDigest: digest(certificate),
        resultDigest: digest(certificate.result),
        statementDigest: digest('Unproved contract-test statement'),
        assumptionsDigest: digest(query.assumptions),
        models: [{ role: 'model', bundle: query.model }],
      },
      coverage: {
        domainDigest: digest(query.domain),
        kind: 'snapshot-completions',
        status: 'declared-complete',
        declaredCardinality: 1,
        coveredCardinality: 1,
      },
      verification: {
        status: 'inconclusive',
        engine: 'lean-kernel',
        version: null,
        method: null,
        toolchainDigest: null,
        axioms: [],
        reason: 'Contract test only; no proof or signature evidence',
      },
      issuer: digest('TEST-ONLY'),
    },
    signature: Buffer.alloc(64).toString('base64'),
    publicKey: 'TEST-ONLY',
  };
}

test('all v2 JSON schemas compile and enforce the same strict wire examples as Zod', () => {
  const ajv = new Ajv2020({ strict: true, allErrors: true });
  addFormats(ajv);
  const { bundle, snap, query, certificate } = decision();
  const examples = {
    'semantic-profile': reformProfile,
    'legal-ir': bundle.package.ir,
    'norm-package': bundle.package,
    'norm-bundle': bundle,
    'snapshot-input': input('K1', 'established', 'established', 'refuted'),
    snapshot: snap,
    'decision-result': certificate.result,
    query,
    certificate,
    receipt: receiptFixture(query, certificate),
  };
  const schemas = exportedReformSchemas();
  for (const name of Object.keys(reformContractSchemas) as (keyof typeof reformContractSchemas)[]) {
    const validate = ajv.compile(schemas[name]);
    assert.equal(validate(examples[name]), true, `${name}: ${JSON.stringify(validate.errors)}`);
    assert.equal(reformContractSchemas[name].safeParse(examples[name]).success, true, name);
    const unknownField = { ...examples[name], leanSource: 'Untrusted executable input' };
    assert.equal(validate(unknownField), false, name);
    assert.equal(reformContractSchemas[name].safeParse(unknownField).success, false, name);
    const saved = JSON.parse(
      readFileSync(new URL(`../schemas/v2/${name}.schema.json`, import.meta.url), 'utf8'),
    );
    assert.deepEqual(saved, schemas[name], `Stale exported schema ${name}`);
  }
});

test('384 snapshot/model combinations preserve every compatible branch and match all fixture consequences', () => {
  let analyses = 0;
  let branches = 0;
  for (const role of roles) {
    const bundle = getReformBundle(role);
    for (const group of ['K1', 'K2'] as const)
      for (const M of states)
        for (const N of states)
          for (const E of states) {
            const value = input(group, M, N, E);
            const result = interpretReform(value, bundle.package.ir);
            assert.equal(
              result.status,
              [M, N, E].every((s) => s === 'established' || s === 'refuted')
                ? 'complete'
                : 'conditional',
            );
            const compatible = fixture.expected.filter(
              (row) =>
                row.input.group === group &&
                (['M', 'N', 'E'] as const).every((p) =>
                  value.findings[p].state === 'established'
                    ? row.input[p]
                    : value.findings[p].state === 'refuted'
                      ? !row.input[p]
                      : true,
                ),
            );
            assert.deepEqual(
              result.branches.map((branch) => branch.when),
              compatible.map((row) => row.input),
            );
            for (const [index, branch] of result.branches.entries()) {
              const expected = compatible[index];
              assert.deepEqual(branch.outcome, {
                qualification: group,
                prisonMonths: expected.prisonMonths[role],
                fineAmount: expected.fineAmount,
                currency: 'DEMO',
              });
              assert.equal(branch.ledger.length, bundle.package.ir.rules.length);
              branches++;
            }
            assert.deepEqual(validateReformResultContext(value, bundle.package.ir, result), result);
            analyses++;
          }
  }
  assert.equal(analyses, 384);
  assert.equal(branches, 1296);
});

test('v2 text limits use Unicode code points consistently and JSON envelopes are bounded before parsing', () => {
  const ajv = new Ajv2020({ strict: true });
  const validate = ajv.compile(exportedReformSchemas()['snapshot-input']);
  const value = input('K1', 'established', 'refuted', 'refuted');
  value.findings.M.rationale = '🚀'.repeat(2000);
  assert.equal(validate(value), true);
  assert.equal(reformContractSchemas['snapshot-input'].safeParse(value).success, true);
  value.findings.M.rationale += '\n';
  assert.equal(validate(value), false);
  assert.equal(reformContractSchemas['snapshot-input'].safeParse(value).success, false);
  assert.deepEqual(parseReformJson('{"value":1}'), { value: 1 });
  assert.throws(() => parseReformJson(JSON.stringify({ value: '🚀'.repeat(131072) })), /512 KiB/);
});

test('exclusion E blocks only N, never M, and equal consequences retain distinct unresolved branches', () => {
  const ir = getReformBundle('B').package.ir;
  const excluded = interpretReform(input('K1', 'established', 'established', 'established'), ir);
  assert.equal(excluded.branches[0].outcome.prisonMonths, 80);
  assert.deepEqual(
    excluded.ledger.find((r) => r.ruleId === 'B-N'),
    { ruleId: 'B-N', status: 'excluded', excludedBy: 'B-X' },
  );
  assert.equal(excluded.ledger.find((r) => r.ruleId === 'B-M')!.status, 'applied');
  const open = interpretReform(input('K1', 'established', 'not-established', 'established'), ir);
  assert.deepEqual(
    open.branches.map((b) => b.outcome.prisonMonths),
    [80, 80],
  );
  assert.equal(open.status, 'conditional');
  assert.equal(open.ledger.find((r) => r.ruleId === 'B-N')!.status, 'unresolved');
});

test('supported semantics reject duplicate obligations, missing rules, code and non-integral packages', () => {
  const ir = getReformBundle('B').package.ir;
  const duplicate = structuredClone(ir);
  duplicate.rules.push(duplicate.rules[0]);
  assert.throws(() => parseSupportedReformIR(duplicate), /Duplicate rule/);
  const noExclusion = structuredClone(ir);
  noExclusion.rules = noExclusion.rules.filter((r) => r.operation.kind !== 'exclude');
  assert.throws(() => parseSupportedReformIR(noExclusion), /exactly one exclude/);
  const fraction = structuredClone(ir);
  const scale = fraction.rules.find((r) => r.operation.kind === 'scale')!;
  assert.equal(scale.operation.kind, 'scale');
  scale.operation.denominator = 7;
  assert.throws(
    () => parseSupportedReformIR(fraction),
    (e) => e instanceof ReformContractError && e.code === 'unsupported',
  );
  assert.throws(() => parseSupportedReformIR({ ...ir, executable: 'plugin.js' }));
  assert.throws(
    () => parseSupportedReformIR({ ...ir, schema: 'normlab.legal-ir/v3' }),
    (e) => e instanceof ReformContractError && e.code === 'unsupported',
  );
  const noRationale = input('K1', 'refuted', 'unreviewed', 'unreviewed');
  noRationale.findings.M.rationale = '';
  assert.throws(() => parseReformInput(noRationale), /rationale/);
});

test('rule IDs and array order do not select normative behavior or transformation order', () => {
  const ir = getReformBundle('B').package.ir;
  const renamed = structuredClone(ir);
  renamed.rules.reverse();
  renamed.rules.forEach((rule, index) => {
    rule.id = `Rule${index}`;
  });
  const value = input('K1', 'established', 'established', 'refuted');
  const original = interpretReform(value, ir);
  const result = interpretReform(value, renamed);
  assert.deepEqual(result.branches[0].outcome, original.branches[0].outcome);
  assert.deepEqual(
    result.branches[0].steps.map((step) => [step.beforeMonths, step.afterMonths]),
    [
      [120, 80],
      [80, 60],
    ],
  );
  validateReformResultContext(value, renamed, result);
});

test('bundle locks bind semantics and provenance independently, and registry copies cannot mutate the fixture', () => {
  const bundle = getReformBundle('B');
  assert.deepEqual(validateReformBundle(bundle), bundle);
  const changedSource = structuredClone(bundle.package);
  changedSource.source.content += '\n';
  assert.throws(() => lockReformPackage(changedSource), /Source digest/);
  changedSource.source.digest = digest(changedSource.source.content);
  const relocked = lockReformPackage(changedSource);
  assert.equal(relocked.semanticDigest, bundle.semanticDigest);
  assert.notEqual(relocked.provenanceDigest, bundle.provenanceDigest);
  const changedLock = structuredClone(bundle);
  changedLock.locks.profileDigest = '0'.repeat(64);
  assert.throws(() => validateReformBundle(changedLock), /lock or digest/);
  const missingSource = structuredClone(bundle.package);
  missingSource.sourceMappings.pop();
  assert.throws(() => lockReformPackage(missingSource), /source mapping/);
  bundle.package.ir.rules[0].id = 'Changed';
  assert.notEqual(getReformBundle('B').package.ir.rules[0].id, 'Changed');
});

test('v2 certificate context rejects lost branches, omitted rules, repeated transforms and stale snapshots', () => {
  const bundle = getReformBundle('B');
  const value = input('K1', 'unreviewed', 'unreviewed', 'unreviewed');
  const result = interpretReform(value, bundle.package.ir);
  const changes = [
    (r: typeof result) => {
      r.branches.pop();
    },
    (r: typeof result) => {
      r.branches[1] = r.branches[0];
    },
    (r: typeof result) => {
      r.status = 'complete';
    },
    (r: typeof result) => {
      r.branches[0].ledger.pop();
    },
    (r: typeof result) => {
      r.ledger.pop();
    },
    (r: typeof result) => {
      r.branches[7].steps[1] = r.branches[7].steps[0];
    },
  ];
  for (const change of changes) {
    const candidate = structuredClone(result);
    change(candidate);
    assert.throws(() => validateReformResultContext(value, bundle.package.ir, candidate));
  }
  const { snap, query, certificate } = decision();
  assert.deepEqual(
    validateReformCertificateBindings(certificate, query, [bundle], snap),
    certificate,
  );
  assert.throws(() => validateReformSnapshot({ ...snap, narrative: 'Changed' }), /Snapshot digest/);
  assert.throws(
    () =>
      validateReformCertificateBindings(
        { ...certificate, queryDigest: '0'.repeat(64) },
        query,
        [bundle],
        snap,
      ),
    /query binding/,
  );
});

test('comparison roles and declared scope bind certificates; finite coverage cannot become a silent subset', () => {
  const a = getReformBundle('A'),
    b = getReformBundle('B');
  const query = reformContractSchemas.query.parse({
    schema: 'normlab.query/v2',
    kind: 'comparison',
    domain: reformDomain,
    assumptions: reformAssumptions,
    baseline: reformBundleRef(a),
    candidate: reformBundleRef(b),
    mapping: 'identity-typed-consequences/v1',
    property: 'equivalence',
    condition: null,
    target: 'prisonMonths',
    preserve: ['qualification', 'fineAmount', 'currency'],
  });
  assert.equal(query.kind, 'comparison');
  const rows = fixture.expected.map((row) => ({
    input: row.input,
    baseline: {
      qualification: row.input.group,
      prisonMonths: row.prisonMonths.A,
      fineAmount: row.fineAmount,
      currency: 'DEMO' as const,
    },
    candidate: {
      qualification: row.input.group,
      prisonMonths: row.prisonMonths.B,
      fineAmount: row.fineAmount,
      currency: 'DEMO' as const,
    },
  }));
  const cert: ReformCertificate = {
    schema: 'normlab.certificate/v2',
    kind: 'comparison',
    queryDigest: digest(query),
    result: { verdict: 'holds', method: 'exhaustive-finite-domain', rows, counterexample: null },
  };
  validateReformCertificateBindings(cert, query, [a, b]);
  const reversed = { ...query, baseline: query.candidate, candidate: query.baseline };
  assert.throws(() => validateReformCertificateBindings(cert, reversed, [a, b]), /query binding/);
  assert.throws(() => validateReformQuery({ ...query, condition: { M: false } }, [a, b]), /scope/);
  const partial = structuredClone(cert);
  assert.equal(partial.kind, 'comparison');
  partial.result.rows.pop();
  assert.throws(() => validateReformCertificateBindings(partial, query, [a, b]), /coverage/);
});

test('receipt bindings reject substituted roles, false coverage and unsupported verified metadata', () => {
  const { bundle, snap, query, certificate } = decision();
  const receipt = receiptFixture(query, certificate);
  validateReformReceiptBindings(receipt, query, certificate, [bundle], snap);
  const role = structuredClone(receipt);
  role.payload.bindings.models[0].role = 'baseline';
  assert.throws(
    () => validateReformReceiptBindings(role, query, certificate, [bundle], snap),
    /role binding/,
  );
  const coverage = structuredClone(receipt);
  coverage.payload.coverage.declaredCardinality = 16;
  coverage.payload.coverage.coveredCardinality = 16;
  assert.throws(
    () => validateReformReceiptBindings(coverage, query, certificate, [bundle], snap),
    /Coverage/,
  );
  const fakeProof = structuredClone(receipt);
  fakeProof.payload.verification.status = 'verified';
  assert.throws(
    () => validateReformReceiptBindings(fakeProof, query, certificate, [bundle], snap),
    /proof metadata/,
  );
});

test('unary property pairs and their receipt coverage bind the same eight mitigation comparisons', () => {
  const bundle = getReformBundle('B');
  const query = reformContractSchemas.query.parse({
    schema: 'normlab.query/v2',
    kind: 'property',
    domain: reformDomain,
    assumptions: reformAssumptions,
    model: reformBundleRef(bundle),
    property: 'strict-M-mitigation',
    target: 'prisonMonths',
    preserve: ['qualification', 'fineAmount', 'currency'],
  });
  const pairs = fixture.expected
    .filter((row) => !row.input.M)
    .map((row) => {
      const after = { ...row.input, M: true };
      const target = fixture.expected.find((r) => digest(r.input) === digest(after))!;
      return {
        before: row.input,
        after,
        baseline: {
          qualification: row.input.group,
          prisonMonths: row.prisonMonths.B,
          fineAmount: row.fineAmount,
          currency: 'DEMO' as const,
        },
        candidate: {
          qualification: after.group,
          prisonMonths: target.prisonMonths.B,
          fineAmount: target.fineAmount,
          currency: 'DEMO' as const,
        },
      };
    });
  const cert: ReformCertificate = {
    schema: 'normlab.certificate/v2',
    kind: 'property',
    queryDigest: digest(query),
    result: { verdict: 'holds', method: 'exhaustive-finite-domain', pairs, counterexample: null },
  };
  validateReformCertificateBindings(cert, query, [bundle]);
  const wrong = structuredClone(cert);
  assert.equal(wrong.kind, 'property');
  wrong.result.pairs[0].after.E = !wrong.result.pairs[0].before.E;
  assert.throws(() => validateReformCertificateBindings(wrong, query, [bundle]), /pair mapping/);
  const first = decision();
  const receipt = receiptFixture(first.query, first.certificate);
  receipt.payload.queryKind = 'property';
  receipt.payload.bindings.queryDigest = digest(query);
  receipt.payload.bindings.certificateDigest = digest(cert);
  receipt.payload.bindings.resultDigest = digest(cert.result);
  receipt.payload.bindings.models = [{ role: 'model', bundle: reformBundleRef(bundle) }];
  receipt.payload.coverage = {
    domainDigest: digest(query.domain),
    kind: 'finite-domain',
    status: 'declared-complete',
    declaredCardinality: 8,
    coveredCardinality: 8,
  };
  validateReformReceiptBindings(receipt, query, cert, [bundle]);
  receipt.payload.coverage.declaredCardinality = 16;
  receipt.payload.coverage.coveredCardinality = 16;
  assert.throws(() => validateReformReceiptBindings(receipt, query, cert, [bundle]), /Coverage/);
});
