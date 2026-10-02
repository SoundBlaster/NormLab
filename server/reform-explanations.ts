import { readFileSync } from 'node:fs';
import type {
  ReformBundle,
  ReformCompletedInput,
  ReformOutcome,
  ReformQuery,
  ReformResult,
  ReformRule,
  ReformSnapshot,
} from '../shared/reform-contracts.js';
import {
  reformExplanationSchema,
  reformExplanationReportSchema,
  type ReformExplanation,
  type ReformExplanationReport,
} from '../shared/reform-explanations.js';
import {
  completions,
  interpretReform,
  parseReformJson,
  ReformContractError,
} from '../shared/reform-semantics.js';
import {
  boundReformBundles,
  validateReformCertificateBindings,
  validateReformQuery,
  validateReformSnapshot,
} from './reform-bindings.js';
import { digest } from './hash.js';
import { queryInputs, relationHolds } from './reform-queries.js';
import { reformExportSchema, replayReformReceipt, type ReformExport } from './reform-receipts.js';

const root = new URL('../', import.meta.url);
export const reformExplainerDigest = digest(
  [
    'server/reform-explanations.ts',
    'shared/reform-explanations.ts',
    'shared/reform-semantics.ts',
    'server/reform-queries.ts',
    'server/reform-models.ts',
    'server/hash.ts',
  ].map((path) => ({ path, content: readFileSync(new URL(path, root), 'utf8') })),
);
type Trace = ReformExplanation['cases'][number]['traces'][number];
type ExplanationCase = ReformExplanation['cases'][number];

function fail(message: string): never {
  throw new ReformContractError('invalid', message);
}
function sourceSections(bundle: ReformBundle): ReformExplanation['sources'][number] {
  const lines = bundle.package.source.content.split('\n');
  return {
    bundleId: bundle.id,
    sourceId: bundle.package.source.id,
    sourceDigest: bundle.package.source.digest,
    rules: bundle.package.sourceMappings.map((mapping, index) => {
      const starts = lines.flatMap((line, i) => (line === `### ${mapping.ruleId}` ? [i] : []));
      if (starts.length !== 1) fail(`Ambiguous source section: ${mapping.ruleId}`);
      const start = starts[0];
      let end = start + 1;
      while (end < lines.length && !/^#{1,3} /.test(lines[end])) end++;
      while (end > start + 1 && lines[end - 1].trim() === '') end--;
      return {
        rule: bundle.package.ir.rules[index],
        anchor: mapping.anchor,
        startLine: start + 1,
        endLine: end,
        text: lines.slice(start, end).join('\n'),
        originRuleIds: mapping.originRuleIds,
      };
    }),
  };
}
function branchFor(
  bundle: ReformBundle,
  input: ReformCompletedInput,
): ReformResult['branches'][number] {
  const finding = (value: boolean) => ({
    state: value ? ('established' as const) : ('refuted' as const),
    rationale: 'Completed query input',
  });
  return interpretReform(
    {
      narrative: 'Explanation reconstruction',
      group: input.group,
      findings: { M: finding(input.M), N: finding(input.N), E: finding(input.E) },
    },
    bundle.package.ir,
  ).branches[0];
}
function traceFor(
  bundle: ReformBundle,
  role: Trace['role'],
  branch: ReformResult['branches'][number],
  origin: Trace['derivationOrigin'],
  snapshot?: ReformSnapshot,
): Trace {
  const x = branch.when;
  const conditions = (predicates: ('M' | 'N' | 'E')[]) =>
    predicates.map((predicate) => {
      const state = snapshot?.findings[predicate].state;
      return {
        predicate,
        value: x[predicate],
        origin:
          snapshot === undefined
            ? ('domain-input' as const)
            : state === 'established' || state === 'refuted'
              ? ('finding' as const)
              : ('completion' as const),
      };
    });
  const events = bundle.package.ir.rules.map((rule) => {
    const entry = branch.ledger.find((e) => e.ruleId === rule.id)!;
    const op = rule.operation;
    const scope = rule.groups.includes(x.group);
    const reason = !scope
      ? ('outside-group' as const)
      : op.kind === 'baseline'
        ? ('baseline-selected' as const)
        : op.kind === 'exclude'
          ? entry.status === 'applied'
            ? ('exclusion-applied' as const)
            : ('exclusion-inactive' as const)
          : entry.status === 'excluded'
            ? ('excluded-by-E' as const)
            : entry.status === 'applied'
              ? ('scale-applied' as const)
              : ('trigger-false' as const);
    const step = branch.steps.find((s) => s.ruleId === rule.id);
    return {
      ruleId: rule.id,
      status: entry.status,
      excludedBy: entry.excludedBy,
      reason,
      conditions:
        !scope || op.kind === 'baseline'
          ? []
          : op.kind === 'exclude' || entry.status === 'excluded'
            ? conditions(['N', 'E'])
            : conditions([op.trigger]),
      step: step ? { beforeMonths: step.beforeMonths, afterMonths: step.afterMonths } : null,
    };
  });
  const base = bundle.package.ir.rules.find(
    (r) => r.groups.includes(x.group) && r.operation.kind === 'baseline',
  )!;
  const exclusion = events.find((event) => event.reason === 'exclusion-applied');
  return {
    role,
    bundleId: bundle.id,
    input: x,
    outcome: branch.outcome,
    derivationOrigin: origin,
    timeline: [
      base.id,
      ...(exclusion ? [exclusion.ruleId] : []),
      ...branch.steps.map((s) => s.ruleId),
    ],
    events,
  };
}
function components(a: ReformOutcome, b: ReformOutcome): ExplanationCase['components'] {
  return [
    {
      component: 'qualification',
      baseline: a.qualification,
      candidate: b.qualification,
      delta: null,
      changed: a.qualification !== b.qualification,
    },
    {
      component: 'prisonMonths',
      baseline: a.prisonMonths,
      candidate: b.prisonMonths,
      delta: b.prisonMonths - a.prisonMonths,
      changed: a.prisonMonths !== b.prisonMonths,
    },
    {
      component: 'fineAmount',
      baseline: a.fineAmount,
      candidate: b.fineAmount,
      delta: b.fineAmount - a.fineAmount,
      changed: a.fineAmount !== b.fineAmount,
    },
    {
      component: 'currency',
      baseline: a.currency,
      candidate: b.currency,
      delta: null,
      changed: false,
    },
  ];
}
function changes(
  a: ReformBundle,
  b: ReformBundle,
  ta: Trace,
  tb: Trace,
): ExplanationCase['ruleChanges'] {
  const select = (
    bundle: ReformBundle,
    x: ReformCompletedInput,
    slot: 'baseline' | 'M' | 'N' | 'exclusion',
  ): ReformRule =>
    bundle.package.ir.rules.find(
      (r) =>
        r.groups.includes(x.group) &&
        (slot === 'baseline'
          ? r.operation.kind === 'baseline'
          : slot === 'exclusion'
            ? r.operation.kind === 'exclude'
            : r.operation.kind === 'scale' && r.operation.trigger === slot),
    )!;
  return (['baseline', 'M', 'N', 'exclusion'] as const).map((slot) => {
    const ra = select(a, ta.input, slot),
      rb = select(b, tb.input, slot);
    const ea = ta.events.find((e) => e.ruleId === ra.id)!,
      eb = tb.events.find((e) => e.ruleId === rb.id)!;
    const values = (trace: typeof ea) =>
      trace.conditions.map(({ predicate, value }) => ({ predicate, value }));
    return {
      slot,
      baselineRuleId: ra.id,
      candidateRuleId: rb.id,
      operationChanged: digest(ra.operation) !== digest(rb.operation),
      statusChanged: ea.status !== eb.status,
      conditionsChanged: digest(values(ea)) !== digest(values(eb)),
      stepValuesChanged: digest(ea.step) !== digest(eb.step),
    };
  });
}

// This is a producer-consistent projection, never an independent proof or receipt.
export function projectReformExplanation(
  expectedQuery: ReformQuery,
  bundles: ReformBundle[],
  input: unknown,
  snapshot?: ReformSnapshot,
): ReformExplanation {
  const snap = snapshot === undefined ? undefined : validateReformSnapshot(snapshot);
  const query = validateReformQuery(expectedQuery, bundles, snap);
  const models = boundReformBundles(query, bundles, snap);
  const certificate = validateReformCertificateBindings(input, query, models, snap);
  const bundle = (id: string) => models.find((m) => m.id === id)!;
  const cases: ExplanationCase[] = [];
  const summary: ReformExplanation['summary'] = [];
  let counterexampleCase: number | null = null;
  if (query.kind === 'decision' && certificate.kind === 'decision') {
    const model = bundle(query.model.id);
    const reconstructed = interpretReform(
      { narrative: snap!.narrative, group: snap!.group, findings: snap!.findings },
      model.package.ir,
    );
    if (digest(reconstructed) !== digest(certificate.result))
      fail('Decision derivation differs from locked-model reconstruction');
    certificate.result.branches.forEach((branch, index) => {
      cases.push({
        index,
        relationSatisfied: null,
        traces: [traceFor(model, 'model', branch, 'certificate-ledger', snap)],
        components: [],
        ruleChanges: [],
      });
    });
    for (const entry of certificate.result.ledger)
      summary.push({
        ...entry,
        branches: certificate.result.branches.map((branch, caseIndex) => {
          const item = branch.ledger.find((e) => e.ruleId === entry.ruleId)!;
          return { caseIndex, status: item.status, excludedBy: item.excludedBy };
        }),
      });
  } else if (query.kind === 'comparison' && certificate.kind === 'comparison') {
    const a = bundle(query.baseline.id),
      b = bundle(query.candidate.id);
    certificate.result.rows.forEach((row, index) => {
      const ba = branchFor(a, row.input),
        bb = branchFor(b, row.input);
      if (
        digest(ba.outcome) !== digest(row.baseline) ||
        digest(bb.outcome) !== digest(row.candidate)
      )
        fail('Comparison outcome differs from locked-model reconstruction');
      const ta = traceFor(a, 'baseline', ba, 'reconstructed-from-locked-model'),
        tb = traceFor(b, 'candidate', bb, 'reconstructed-from-locked-model');
      cases.push({
        index,
        relationSatisfied: relationHolds(query, row.baseline, row.candidate),
        traces: [ta, tb],
        components: components(row.baseline, row.candidate),
        ruleChanges: changes(a, b, ta, tb),
      });
    });
    if (certificate.result.counterexample !== null)
      counterexampleCase = certificate.result.rows.findIndex(
        (r) => digest(r) === digest(certificate.result.counterexample),
      );
  } else if (query.kind === 'property' && certificate.kind === 'property') {
    const model = bundle(query.model.id);
    certificate.result.pairs.forEach((pair, index) => {
      const ba = branchFor(model, pair.before),
        bb = branchFor(model, pair.after);
      if (
        digest(ba.outcome) !== digest(pair.baseline) ||
        digest(bb.outcome) !== digest(pair.candidate)
      )
        fail('Property outcome differs from locked-model reconstruction');
      const ta = traceFor(model, 'baseline', ba, 'reconstructed-from-locked-model'),
        tb = traceFor(model, 'candidate', bb, 'reconstructed-from-locked-model');
      const relationSatisfied =
        pair.candidate.prisonMonths < pair.baseline.prisonMonths &&
        pair.candidate.fineAmount === pair.baseline.fineAmount &&
        pair.candidate.qualification === pair.baseline.qualification &&
        pair.candidate.currency === pair.baseline.currency;
      cases.push({
        index,
        relationSatisfied,
        traces: [ta, tb],
        components: components(pair.baseline, pair.candidate),
        ruleChanges: changes(model, model, ta, tb),
      });
    });
    if (certificate.result.counterexample !== null)
      counterexampleCase = certificate.result.pairs.findIndex(
        (r) => digest(r) === digest(certificate.result.counterexample),
      );
  } else fail('Explanation query/certificate kind mismatch');
  if (certificate.kind !== 'decision') {
    const allHold = cases.every((c) => c.relationSatisfied);
    if (
      certificate.result.verdict === 'holds'
        ? !allHold
        : counterexampleCase === null || cases[counterexampleCase]?.relationSatisfied !== false
    )
      fail('Explanation verdict or counterexample differs from reconstructed relation');
  }
  const corpus = certificate.kind !== 'decision' && certificate.result.method === 'corpus';
  return reformExplanationSchema.parse({
    schema: 'normlab.explanation/v1',
    profileId: query.domain.profileId,
    proofStatus: 'unchecked',
    generatorDigest: reformExplainerDigest,
    queryKind: query.kind,
    bindings: {
      queryDigest: digest(query),
      certificateDigest: digest(certificate),
      assumptionsDigest: digest(query.assumptions),
      snapshotDigest: snap?.digest ?? null,
      models:
        query.kind === 'comparison'
          ? [
              { role: 'baseline', bundle: query.baseline },
              { role: 'candidate', bundle: query.candidate },
            ]
          : [{ role: 'model', bundle: query.model }],
    },
    scope: {
      domain: query.domain,
      kind:
        query.kind === 'decision'
          ? 'snapshot-completions'
          : query.kind === 'comparison'
            ? 'completed-inputs'
            : 'mitigation-pairs',
      condition:
        query.kind === 'comparison'
          ? query.condition
          : query.kind === 'property'
            ? { M: false }
            : null,
      group: snap?.group ?? null,
      openPredicates: snap
        ? (['M', 'N', 'E'] as const).filter((p) =>
            ['unreviewed', 'not-established'].includes(snap.findings[p].state),
          )
        : [],
    },
    coverage: {
      kind:
        query.kind === 'decision' ? 'snapshot-completions' : corpus ? 'corpus' : 'finite-domain',
      status: corpus ? 'partial' : 'declared-complete',
      declaredCardinality:
        query.kind === 'decision'
          ? completions({
              narrative: snap!.narrative,
              group: snap!.group,
              findings: snap!.findings,
            }).length
          : queryInputs(query).length,
      coveredCardinality: cases.length,
    },
    property: query.kind === 'decision' ? 'decision' : query.property,
    verdict:
      certificate.kind === 'decision' ? certificate.result.status : certificate.result.verdict,
    assumptions: query.assumptions,
    findings: snap?.findings ?? null,
    sources: models.map(sourceSections),
    summary,
    cases,
    counterexampleCase,
  });
}

export function validateReformExplanation(
  value: unknown,
  query: ReformQuery,
  bundles: ReformBundle[],
  certificate: unknown,
  snapshot?: ReformSnapshot,
): ReformExplanation {
  const supplied = reformExplanationSchema.parse(value);
  const expected = projectReformExplanation(query, bundles, certificate, snapshot);
  if (digest(supplied) !== digest(expected))
    fail('Explanation does not match its exact inputs and current generator');
  return expected;
}

export async function explainReformExport(
  input: unknown,
  trustedPublicKey: string,
): Promise<ReformExplanationReport> {
  // Clone before asynchronous verification so caller mutation cannot change the projection.
  const artifact = reformExportSchema.parse(input);
  const replay = await replayReformReceipt(
    artifact.receipt,
    trustedPublicKey,
    artifact.query,
    artifact.bundles,
    artifact.certificate,
    artifact.snapshot ?? undefined,
  );
  const explanation = replay.current
    ? projectReformExplanation(
        artifact.query,
        artifact.bundles,
        artifact.certificate,
        artifact.snapshot ?? undefined,
      )
    : null;
  return reformExplanationReportSchema.parse({
    schema: 'normlab.explanation-report/v1',
    artifactDigest: digest(artifact),
    explanationDigest: explanation ? digest(explanation) : null,
    explanation,
    evidence: {
      signatureValid: replay.signatureValid,
      bindingsValid: replay.bindingsValid,
      current: replay.current,
      proofStatus: replay.verification?.status ?? 'unchecked',
      proofMethod: replay.verification?.method ?? null,
      toolchainDigest: replay.verification?.toolchainDigest ?? null,
      reason: replay.reason,
    },
  });
}
export async function verifyReformExplanationReport(
  value: unknown,
  artifact: ReformExport,
  trustedPublicKey: string,
): Promise<ReformExplanationReport> {
  const supplied = reformExplanationReportSchema.parse(value);
  const expected = await explainReformExport(artifact, trustedPublicKey);
  if (digest(supplied) !== digest(expected))
    fail('Explanation report does not match fresh replay and deterministic projection');
  return expected;
}
export function parseReformExplanationReport(text: string): ReformExplanationReport {
  return reformExplanationReportSchema.parse(parseReformJson(text));
}
