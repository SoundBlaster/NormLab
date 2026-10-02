import {
  reformCertificateSchema,
  reformQuerySchema,
  reformReceiptSchema,
  reformSnapshotSchema,
  type ReformBundle,
  type ReformCertificate,
  type ReformQuery,
  type ReformReceipt,
  type ReformSnapshot,
  type ReformSnapshotInput,
} from '../shared/reform-contracts.js';
import {
  completeDomain,
  completions,
  parseReformInput,
  ReformContractError,
  validateReformResultContext,
} from '../shared/reform-semantics.js';
import { digest } from './hash.js';
import { validateReformBundle } from './reform-models.js';

export const reformDomain = {
  id: 'D16',
  profileId: 'demo.reform-mitigation/v1',
  groups: ['K1', 'K2'],
  predicates: ['M', 'N', 'E'],
  cardinality: 16,
  restrictions: [],
} as const;
export const reformAssumptions = [
  'Synthetic rules, one subject and episode; liability and group are supplied context.',
  'Simulated findings; narrative truth and real legislation are outside the proof scope.',
  'Exact integer months, DEMO currency; all mandatory rules in the locked profile scope.',
];

export function reformBundleRef(bundle: ReformBundle) {
  const locked = validateReformBundle(bundle);
  return {
    id: locked.id,
    semanticDigest: locked.semanticDigest,
    provenanceDigest: locked.provenanceDigest,
    profileDigest: locked.locks.profileDigest,
  };
}

export function validateReformSnapshot(value: unknown): ReformSnapshot {
  const snapshot = reformSnapshotSchema.parse(value);
  parseReformInput(snapshotInput(snapshot));
  const { digest: claimed, ...content } = snapshot;
  if (claimed !== digest(content))
    throw new ReformContractError('invalid', 'Snapshot digest mismatch');
  return snapshot;
}

function snapshotInput(snapshot: ReformSnapshot): ReformSnapshotInput {
  return { narrative: snapshot.narrative, group: snapshot.group, findings: snapshot.findings };
}

export function decisionQuery(snapshot: ReformSnapshot, bundle: ReformBundle): ReformQuery {
  const value = validateReformSnapshot(snapshot);
  return reformQuerySchema.parse({
    schema: 'normlab.query/v2',
    kind: 'decision',
    domain: reformDomain,
    assumptions: reformAssumptions,
    snapshotDigest: value.digest,
    model: reformBundleRef(bundle),
  });
}

export function validateReformQuery(
  value: unknown,
  bundles: ReformBundle[],
  snapshot?: ReformSnapshot,
): ReformQuery {
  const query = reformQuerySchema.parse(value);
  const refs = query.kind === 'comparison' ? [query.baseline, query.candidate] : [query.model];
  for (const ref of refs) {
    const bundle = bundles.find((b) => b.id === ref.id);
    if (!bundle || digest(ref) !== digest(reformBundleRef(bundle)))
      throw new ReformContractError('invalid', 'Query bundle binding mismatch');
  }
  if (query.kind === 'decision') {
    if (!snapshot || validateReformSnapshot(snapshot).digest !== query.snapshotDigest)
      throw new ReformContractError('invalid', 'Query snapshot binding mismatch');
  } else if (snapshot !== undefined) {
    throw new ReformContractError(
      'invalid',
      'General property query must not silently bind a case',
    );
  }
  if (query.kind === 'comparison') {
    const required =
      query.property === 'strict-reduction'
        ? true
        : query.property === 'preserved-outside'
          ? false
          : null;
    if (required === null ? query.condition !== null : query.condition?.M !== required)
      throw new ReformContractError(
        'invalid',
        'Property condition changes the declared query scope',
      );
  }
  return query;
}

export function validateReformCertificateBindings(
  value: unknown,
  expectedQuery: ReformQuery,
  bundles: ReformBundle[],
  snapshot?: ReformSnapshot,
): ReformCertificate {
  const query = validateReformQuery(expectedQuery, bundles, snapshot);
  const certificate = reformCertificateSchema.parse(value);
  if (certificate.kind !== query.kind || certificate.queryDigest !== digest(query))
    throw new ReformContractError('invalid', 'Certificate query binding mismatch');
  if (certificate.kind === 'decision' && query.kind === 'decision') {
    const bundle = bundles.find((b) => b.id === query.model.id)!;
    validateReformResultContext(snapshotInput(snapshot!), bundle.package.ir, certificate.result);
  } else if (certificate.kind === 'comparison' && query.kind === 'comparison') {
    const domain = completeDomain().filter(
      (x) => query.condition === null || x.M === query.condition.M,
    );
    const rows = certificate.result.rows;
    const supplied = rows.map((row) => digest(row.input));
    const expected = domain.map(digest);
    if (
      new Set(supplied).size !== supplied.length ||
      supplied.some((hash) => !expected.includes(hash)) ||
      (certificate.result.method === 'exhaustive-finite-domain' &&
        digest(supplied) !== digest(expected))
    )
      throw new ReformContractError('invalid', 'Comparison domain coverage mismatch');
    for (const row of rows)
      if (
        row.baseline.qualification !== row.input.group ||
        row.candidate.qualification !== row.input.group
      )
        throw new ReformContractError('invalid', 'Comparison qualification mismatch');
    const witness = certificate.result.counterexample;
    if (
      (certificate.result.verdict === 'counterexample') !== (witness !== null) ||
      (witness !== null && !rows.some((row) => digest(row) === digest(witness)))
    )
      throw new ReformContractError('invalid', 'Counterexample does not bind a supplied row');
  } else if (certificate.kind === 'property' && query.kind === 'property') {
    const expected = completeDomain()
      .filter((x) => !x.M)
      .map(digest);
    const supplied = certificate.result.pairs.map((pair) => digest(pair.before));
    if (
      new Set(supplied).size !== supplied.length ||
      supplied.some((hash) => !expected.includes(hash)) ||
      (certificate.result.method === 'exhaustive-finite-domain' &&
        digest(supplied) !== digest(expected))
    )
      throw new ReformContractError('invalid', 'Property pair coverage mismatch');
    for (const pair of certificate.result.pairs)
      if (
        digest(pair.after) !== digest({ ...pair.before, M: true }) ||
        pair.baseline.qualification !== pair.before.group ||
        pair.candidate.qualification !== pair.after.group
      )
        throw new ReformContractError('invalid', 'Invalid mitigation pair mapping');
    const witness = certificate.result.counterexample;
    if (
      (certificate.result.verdict === 'counterexample') !== (witness !== null) ||
      (witness !== null &&
        !certificate.result.pairs.some((pair) => digest(pair) === digest(witness)))
    )
      throw new ReformContractError('invalid', 'Counterexample does not bind a supplied pair');
  }
  return certificate;
}

// Structural consistency only. Signature/issuer trust and actual Lean evidence must be checked separately.
export function validateReformReceiptBindings(
  value: unknown,
  query: ReformQuery,
  certificate: ReformCertificate,
  bundles: ReformBundle[],
  snapshot?: ReformSnapshot,
): ReformReceipt {
  const expectedQuery = validateReformQuery(query, bundles, snapshot);
  const cert = validateReformCertificateBindings(certificate, expectedQuery, bundles, snapshot);
  const receipt = reformReceiptSchema.parse(value);
  const payload = receipt.payload;
  const models =
    expectedQuery.kind === 'comparison'
      ? [
          { role: 'baseline', bundle: expectedQuery.baseline },
          { role: 'candidate', bundle: expectedQuery.candidate },
        ]
      : [{ role: 'model', bundle: expectedQuery.model }];
  if (
    payload.queryKind !== expectedQuery.kind ||
    payload.bindings.queryDigest !== digest(expectedQuery) ||
    payload.bindings.certificateDigest !== digest(cert) ||
    payload.bindings.resultDigest !== digest(cert.result) ||
    payload.bindings.assumptionsDigest !== digest(expectedQuery.assumptions) ||
    digest(payload.bindings.models) !== digest(models) ||
    payload.coverage.domainDigest !== digest(expectedQuery.domain)
  )
    throw new ReformContractError('invalid', 'Receipt input or role binding mismatch');
  if (
    payload.coverage.coveredCardinality > payload.coverage.declaredCardinality ||
    (payload.coverage.status === 'declared-complete' &&
      payload.coverage.coveredCardinality !== payload.coverage.declaredCardinality)
  )
    throw new ReformContractError('invalid', 'False coverage declaration');
  const declared =
    expectedQuery.kind === 'decision'
      ? completions(snapshotInput(snapshot!)).length
      : expectedQuery.kind === 'property' || expectedQuery.condition !== null
        ? 8
        : 16;
  const covered =
    cert.kind === 'decision'
      ? cert.result.branches.length
      : cert.kind === 'comparison'
        ? cert.result.rows.length
        : cert.result.pairs.length;
  const coverageKind =
    cert.kind === 'decision'
      ? 'snapshot-completions'
      : cert.result.method === 'corpus'
        ? 'corpus'
        : 'finite-domain';
  if (
    payload.coverage.declaredCardinality !== declared ||
    payload.coverage.coveredCardinality !== covered ||
    payload.coverage.kind !== coverageKind
  )
    throw new ReformContractError(
      'invalid',
      'Coverage does not match the authenticated query and certificate',
    );
  if (
    payload.verification.status === 'verified' &&
    (!payload.verification.version ||
      !payload.verification.toolchainDigest ||
      !payload.verification.method ||
      payload.verification.axioms.some((axiom) => axiom !== 'propext'))
  )
    throw new ReformContractError('invalid', 'Verified receipt lacks supported proof metadata');
  return receipt;
}
