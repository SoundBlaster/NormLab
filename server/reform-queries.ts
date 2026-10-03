import { readFileSync } from 'node:fs';
import {
  reformQuerySchema,
  type ReformBundle,
  type ReformCertificate,
  type ReformCompletedInput,
  type ReformOutcome,
  type ReformQuery,
  type ReformSnapshot,
} from '../shared/reform-contracts.js';
import {
  completeDomain,
  interpretReform,
  ReformContractError,
} from '../shared/reform-semantics.js';
import {
  reformAssumptions,
  reformBundleRef,
  reformDomain,
  validateReformCertificateBindings,
  validateReformQuery,
} from './reform-bindings.js';
import { digest } from './hash.js';
import { getReformBundle, lockReformPackage } from './reform-models.js';

export function comparisonQuery(
  baseline: ReformBundle,
  candidate: ReformBundle,
  property: Extract<ReformQuery, { kind: 'comparison' }>['property'],
): ReformQuery {
  return reformQuerySchema.parse({
    schema: 'normlab.query/v2',
    kind: 'comparison',
    domain: reformDomain,
    assumptions: reformAssumptions,
    baseline: reformBundleRef(baseline),
    candidate: reformBundleRef(candidate),
    mapping: 'identity-typed-consequences/v1',
    property,
    condition:
      property === 'strict-reduction'
        ? { M: true }
        : property === 'preserved-outside'
          ? { M: false }
          : null,
    target: 'prisonMonths',
    preserve: ['qualification', 'fineAmount', 'currency'],
  });
}
export function mitigationQuery(model: ReformBundle): ReformQuery {
  return reformQuerySchema.parse({
    schema: 'normlab.query/v2',
    kind: 'property',
    domain: reformDomain,
    assumptions: reformAssumptions,
    model: reformBundleRef(model),
    property: 'strict-M-mitigation',
    target: 'prisonMonths',
    preserve: ['qualification', 'fineAmount', 'currency'],
  });
}
export function queryInputs(query: ReformQuery): ReformCompletedInput[] {
  if (query.kind === 'decision')
    throw new ReformContractError('invalid', 'Decision scope is snapshot-bound');
  return completeDomain().filter((x) =>
    query.kind === 'property' ? !x.M : query.condition === null || x.M === query.condition.M,
  );
}
function outcome(bundle: ReformBundle, x: ReformCompletedInput): ReformOutcome {
  const finding = (value: boolean) => ({
    state: value ? ('established' as const) : ('refuted' as const),
    rationale: 'Completed domain input',
  });
  return interpretReform(
    {
      narrative: 'Synthetic finite query',
      group: x.group,
      findings: { M: finding(x.M), N: finding(x.N), E: finding(x.E) },
    },
    bundle.package.ir,
  ).branches[0].outcome;
}
export function relationHolds(
  query: Extract<ReformQuery, { kind: 'comparison' }>,
  a: ReformOutcome,
  b: ReformOutcome,
): boolean {
  if (query.property === 'equivalence' || query.property === 'preserved-outside')
    return digest(a) === digest(b);
  const preserved =
    a.qualification === b.qualification &&
    a.fineAmount === b.fineAmount &&
    a.currency === b.currency;
  return (
    preserved &&
    (query.property === 'strict-reduction'
      ? b.prisonMonths < a.prisonMonths
      : b.prisonMonths <= a.prisonMonths)
  );
}

// This is the untrusted producer path; Lean verifies its outcomes and claims independently.
export function proposeReformQuery(
  expectedQuery: ReformQuery,
  bundles: ReformBundle[],
  options: { method?: 'corpus' | 'exhaustive-finite-domain'; inputs?: ReformCompletedInput[] } = {},
  snapshot?: ReformSnapshot,
): ReformCertificate {
  const query = validateReformQuery(expectedQuery, bundles, snapshot);
  const model = (id: string) => bundles.find((bundle) => bundle.id === id)!;
  let certificate: ReformCertificate;
  if (query.kind === 'decision') {
    if (options.inputs || options.method)
      throw new ReformContractError('invalid', 'Decision cannot change snapshot coverage');
    certificate = {
      schema: 'normlab.certificate/v2',
      kind: 'decision',
      queryDigest: digest(query),
      result: interpretReform(
        { narrative: snapshot!.narrative, group: snapshot!.group, findings: snapshot!.findings },
        model(query.model.id).package.ir,
      ),
    };
  } else if (query.kind === 'comparison') {
    const rows = (options.inputs ?? queryInputs(query)).map((input) => ({
      input,
      baseline: outcome(model(query.baseline.id), input),
      candidate: outcome(model(query.candidate.id), input),
    }));
    const counterexample =
      rows.find((row) => !relationHolds(query, row.baseline, row.candidate)) ?? null;
    certificate = {
      schema: 'normlab.certificate/v2',
      kind: 'comparison',
      queryDigest: digest(query),
      result: {
        method: options.method ?? 'exhaustive-finite-domain',
        rows,
        verdict: counterexample ? 'counterexample' : 'holds',
        counterexample,
      },
    };
  } else {
    const bundle = model(query.model.id);
    const pairs = (options.inputs ?? queryInputs(query)).map((before) => {
      const after = { ...before, M: true };
      return {
        before,
        after,
        baseline: outcome(bundle, before),
        candidate: outcome(bundle, after),
      };
    });
    const counterexample =
      pairs.find(
        (pair) =>
          pair.candidate.prisonMonths >= pair.baseline.prisonMonths ||
          pair.baseline.qualification !== pair.candidate.qualification ||
          pair.baseline.fineAmount !== pair.candidate.fineAmount ||
          pair.baseline.currency !== pair.candidate.currency,
      ) ?? null;
    certificate = {
      schema: 'normlab.certificate/v2',
      kind: 'property',
      queryDigest: digest(query),
      result: {
        method: options.method ?? 'exhaustive-finite-domain',
        pairs,
        verdict: counterexample ? 'counterexample' : 'holds',
        counterexample,
      },
    };
  }
  return validateReformCertificateBindings(certificate, query, bundles, snapshot);
}

export function getReformCounterexampleBundle(): ReformBundle {
  const pkg = getReformBundle('C').package;
  pkg.id = 'reform-C-unintended-N';
  const content = readFileSync(
    new URL('../fixtures/reform-counterexample/source.md', import.meta.url),
    'utf8',
  );
  pkg.source = { id: 'unintended-N-source', content, digest: digest(content) };
  pkg.sourceMappings = pkg.ir.rules.map((rule) => {
    const origin = rule.id;
    rule.id = origin.replace('C-', 'D-');
    if (rule.operation.kind === 'scale' && rule.operation.trigger === 'N') {
      rule.operation.numerator = 2;
      rule.operation.denominator = 3;
    }
    return {
      ruleId: rule.id,
      sourceId: pkg.source.id,
      anchor: rule.id.toLowerCase(),
      originRuleIds: [origin],
    };
  });
  return lockReformPackage(pkg);
}
