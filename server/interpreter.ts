import type {
  Bundle,
  Certificate,
  Comparison,
  DecisionResult,
  FindingState,
  Outcome,
  Snapshot,
} from '../shared/domain.js';

// Producer only. The verifier does not call this function.
export function interpret(finding: FindingState, bundle: Bundle): DecisionResult {
  const { baseline, adjustment } = bundle.ir;
  const branch = (when: 'established' | 'refuted'): Outcome => ({
    when,
    prisonMonths:
      when === 'established'
        ? (baseline.prisonMonths * adjustment.numerator) / adjustment.denominator
        : baseline.prisonMonths,
    fineAmount: baseline.fineAmount,
    currency: baseline.currency,
    ruleStatus: when === 'established' ? 'applied' : 'inapplicable',
  });
  const complete = finding === 'established' || finding === 'refuted';
  return {
    status: complete ? 'complete' : 'conditional',
    outcomes: complete ? [branch(finding)] : [branch('established'), branch('refuted')],
    ledger: [
      { ruleId: adjustment.id, status: complete ? branch(finding).ruleStatus : 'unresolved' },
    ],
  };
}

export function propose(snapshot: Snapshot, bundle: Bundle): Certificate {
  return {
    schema: 'normlab.certificate/v1',
    snapshotDigest: snapshot.digest,
    bundleSemanticDigest: bundle.semanticDigest,
    bundleProvenanceDigest: bundle.provenanceDigest,
    query: 'decision/v1',
    result: interpret(snapshot.finding, bundle),
  };
}

export function compare(baseline: Bundle, candidate: Bundle): Comparison {
  const domain = ['established', 'refuted'] as const;
  const rows = domain.map((finding) => {
    const left = interpret(finding, baseline).outcomes[0];
    const right = interpret(finding, candidate).outcomes[0];
    return {
      finding,
      baseline: left,
      candidate: right,
      prisonDelta: right.prisonMonths - left.prisonMonths,
    };
  });
  return {
    baselineId: baseline.id,
    candidateId: candidate.id,
    domain: [...domain],
    coverage: 'exhaustive-finite-domain',
    rows,
    equivalent: rows.every(
      (row) => row.prisonDelta === 0 && row.baseline.fineAmount === row.candidate.fineAmount,
    ),
    property:
      'Equality of typed consequences for both completed states of A; no claim about real legislation.',
  };
}
