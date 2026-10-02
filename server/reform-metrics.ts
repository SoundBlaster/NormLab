import { readFileSync } from 'node:fs';
import type { ReformBundle, ReformQuery, ReformSnapshot } from '../shared/reform-contracts.js';
import type { ReformExplanation } from '../shared/reform-explanations.js';
import {
  REFORM_METRICS_METHOD,
  reformMetricAnnotationsSchema,
  reformMetricsSchema,
  reformMetricsReportSchema,
  type ReformMetricAnnotations,
  type ReformMetrics,
  type ReformMetricsReport,
} from '../shared/reform-metrics.js';
import { parseReformJson, ReformContractError } from '../shared/reform-semantics.js';
import { reformBundleRef } from './reform-bindings.js';
import {
  explainReformExport,
  projectReformExplanation,
  reformExplainerDigest,
} from './reform-explanations.js';
import { digest } from './hash.js';
import { reformExportSchema, type ReformExport } from './reform-receipts.js';

const root = new URL('../', import.meta.url);
export const reformMetricsGeneratorDigest = digest({
  explanationGenerator: reformExplainerDigest,
  sources: [
    'server/reform-metrics.ts',
    'shared/reform-metrics.ts',
    'shared/reform-contracts.ts',
    'server/reform-bindings.ts',
  ].map((path) => ({ path, content: readFileSync(new URL(path, root), 'utf8') })),
});
const components = ['prisonMonths', 'fineAmount', 'qualification', 'currency'] as const;
type Source = ReformExplanation['sources'][number];
type ModelMetrics = ReformMetrics['models'][number];
type Changes = Extract<ReformMetrics['consequences'], { kind: 'comparison' | 'property' }>;
function fail(message: string): never {
  throw new ReformContractError('invalid', message);
}

function parseAnnotations(value?: unknown): ReformMetricAnnotations | null {
  if (value === undefined || value === null) return null;
  const annotations = reformMetricAnnotationsSchema.parse(value);
  if (new Set(annotations.models.map((m) => m.bundle.id)).size !== annotations.models.length)
    fail('Repeated model in source annotations');
  return annotations;
}
function annotationFor(
  bundle: ReformBundle,
  source: Source,
  annotations: ReformMetricAnnotations | null,
) {
  const entry = annotations?.models.find((m) => m.bundle.id === bundle.id) ?? null;
  if (!entry) return null; // Absence is unavailable, never a measured zero.
  if (
    digest(entry.bundle) !== digest(reformBundleRef(bundle)) ||
    entry.sourceDigest !== source.sourceDigest
  )
    fail('Source annotation does not match exact locked model and source');
  const lines = bundle.package.source.content.split('\n');
  const checkSpan = (span: { line: number; text: string }) => {
    if (lines[span.line - 1] !== span.text)
      fail('Source annotation span does not match locked text');
  };
  const definitions = new Set<string>();
  for (const definition of entry.definitions) {
    checkSpan(definition.span);
    if (definitions.has(definition.predicate)) fail('Repeated predicate definition annotation');
    definitions.add(definition.predicate);
  }
  const references = new Set<string>();
  for (const reference of entry.references) {
    checkSpan(reference.span);
    const from = source.rules.find((r) => r.rule.id === reference.fromRuleId);
    if (
      !from ||
      reference.span.line < from.startLine ||
      reference.span.line > from.endLine ||
      !source.rules.some((r) => r.rule.id === reference.toRuleId)
    )
      fail('Normative reference is outside its mapped source section or model');
    if (
      !new RegExp(`(^|[^A-Za-z0-9_-])${reference.toRuleId}($|[^A-Za-z0-9_-])`).test(
        reference.span.text,
      )
    )
      fail('Normative reference target is absent from its annotated source line');
    const key = `${reference.fromRuleId}/${reference.toRuleId}/${reference.span.line}`;
    if (references.has(key)) fail('Repeated normative reference annotation');
    references.add(key);
  }
  return entry;
}
function modelMetrics(
  bundle: ReformBundle,
  source: Source,
  role: ModelMetrics['role'],
  annotations: ReformMetricAnnotations | null,
): ModelMetrics {
  const rules = bundle.package.ir.rules;
  const templates = new Map<string, ModelMetrics['structure']['operationTemplates'][number]>();
  for (const rule of rules) {
    // group scope is deliberately factored out; rule IDs and source prose are not operations.
    const key = digest({
      mandatory: rule.mandatory,
      applyCount: rule.applyCount,
      operation: rule.operation,
    });
    const template = templates.get(key);
    if (template) template.ruleIds.push(rule.id);
    else templates.set(key, { operation: rule.operation, ruleIds: [rule.id] });
  }
  const overlap = (a: (typeof rules)[number], b: (typeof rules)[number]) =>
    a.groups.some((g) => b.groups.includes(g));
  const scales = rules.filter((r) => r.operation.kind === 'scale');
  const exceptions = rules.filter((r) => r.operation.kind === 'exclude');
  const exclusionReferences = exceptions.flatMap((from) =>
    scales
      .filter(
        (to) =>
          to.operation.kind === 'scale' &&
          from.operation.kind === 'exclude' &&
          to.operation.trigger === from.operation.targetTrigger &&
          overlap(from, to),
      )
      .map((to) => ({ fromRuleId: from.id, toRuleId: to.id })),
  );
  const orderedScalePairs = scales
    .filter((r) => r.operation.kind === 'scale' && r.operation.trigger === 'M')
    .flatMap((from) =>
      scales
        .filter(
          (to) =>
            to.operation.kind === 'scale' && to.operation.trigger === 'N' && overlap(from, to),
        )
        .map((to) => ({ fromRuleId: from.id, toRuleId: to.id })),
    );
  const occurrences = rules.flatMap((rule) =>
    rule.operation.kind === 'baseline'
      ? []
      : [{ ruleId: rule.id, predicate: rule.operation.trigger }],
  );
  const independentConditions = bundle.profile.predicates.filter((p) =>
    occurrences.some((x) => x.predicate === p),
  );
  const annotation = annotationFor(bundle, source, annotations);
  return {
    role,
    bundle: reformBundleRef(bundle),
    structure: {
      representation: 'mapped-source-sections-and-authored-legal-ir/v1',
      provisions: source.rules.map((r) => ({
        ruleId: r.rule.id,
        startLine: r.startLine,
        endLine: r.endLine,
      })),
      provisionCount: source.rules.length,
      irRuleCount: rules.length,
      groupExpandedRuleCount: rules.reduce((sum, rule) => sum + rule.groups.length, 0),
      operationTemplates: [...templates.values()],
      operationTemplateCount: templates.size,
      repeatedOperationCount: rules.length - templates.size,
      exclusionReferences,
      exclusionReferenceCount: exclusionReferences.length,
      sourceAnnotations: annotation,
      definitionCount: annotation?.definitions.length ?? null,
      normativeTextReferenceCount: annotation?.references.length ?? null,
    },
    decision: {
      independentConditions,
      independentConditionCount: independentConditions.length,
      explicitConditionOccurrences: occurrences,
      explicitConditionOccurrenceCount: occurrences.length,
      exceptionRuleIds: exceptions.map((r) => r.id),
      exceptionCount: exceptions.length,
      humanJudgmentPoints: [...bundle.profile.predicates],
      humanJudgmentCount: bundle.profile.predicates.length,
      outsideScopeInputs: ['group'],
      orderedScalePairs,
      orderedScalePairCount: orderedScalePairs.length,
    },
  };
}
function consequenceMetrics(explanation: ReformExplanation): ReformMetrics['consequences'] {
  if (explanation.queryKind === 'decision') {
    const branches = explanation.cases.map((c) => ({
      input: c.traces[0].input,
      outcome: c.traces[0].outcome,
    }));
    return {
      kind: 'decision',
      unit: 'snapshot-completion',
      completionCount: branches.length,
      distinctOutcomeCount: new Set(branches.map((b) => digest(b.outcome))).size,
      openHumanJudgmentCount: explanation.scope.openPredicates.length,
      branches,
    };
  }
  const rows: Changes['rows'] = explanation.cases.map((row) => {
    const [baseline, candidate] = row.traces;
    return {
      caseIndex: row.index,
      baselineInput: baseline.input,
      candidateInput: candidate.input,
      baselineOutcome: baseline.outcome,
      candidateOutcome: candidate.outcome,
      changedComponents: components.filter(
        (component) => baseline.outcome[component] !== candidate.outcome[component],
      ),
    };
  });
  const counts: Changes['components'] = components.map((component) => {
    const changed = rows.filter((r) => r.changedComponents.includes(component)).length;
    const common = { changed, unchanged: rows.length - changed };
    if (component === 'qualification') return { component, unit: 'group-code', ...common };
    if (component === 'currency') return { component, unit: 'currency-code', ...common };
    const deltas = rows.map((r) => r.candidateOutcome[component] - r.baselineOutcome[component]);
    const numeric = {
      ...common,
      decreased: deltas.filter((d) => d < 0).length,
      increased: deltas.filter((d) => d > 0).length,
      minDelta: Math.min(...deltas),
      maxDelta: Math.max(...deltas),
    };
    return component === 'prisonMonths'
      ? { component, unit: 'month', ...numeric }
      : { component, unit: 'DEMO', ...numeric };
  });
  const categories: Changes['categories'] = [];
  for (const group of explanation.scope.domain.groups)
    for (const baselineM of [false, true]) {
      const selected = rows.filter(
        (r) => r.baselineInput.group === group && r.baselineInput.M === baselineM,
      );
      if (selected.length)
        categories.push({
          group,
          baselineM,
          observedCount: selected.length,
          changedCount: selected.filter((r) => r.changedComponents.length > 0).length,
          changedComponents: components.filter((p) =>
            selected.some((r) => r.changedComponents.includes(p)),
          ),
        });
    }
  const changedCount = rows.filter((r) => r.changedComponents.length > 0).length;
  return {
    kind: explanation.queryKind,
    unit: explanation.queryKind === 'comparison' ? 'completed-input' : 'mitigation-pair',
    observedCount: rows.length,
    changedCount,
    unchangedCount: rows.length - changedCount,
    components: counts,
    categories,
    rows,
  };
}

// Only producer consistency: callers must use measureReformExport for actual replay evidence.
export function projectReformMetrics(
  query: ReformQuery,
  bundles: ReformBundle[],
  certificate: unknown,
  snapshot?: ReformSnapshot,
  sourceAnnotations?: unknown,
): ReformMetrics {
  const explanation = projectReformExplanation(query, bundles, certificate, snapshot);
  const annotations = parseAnnotations(sourceAnnotations);
  return reformMetricsSchema.parse({
    schema: 'normlab.metrics/v1',
    profileId: explanation.profileId,
    methodology: REFORM_METRICS_METHOD,
    proofStatus: 'unchecked',
    generatorDigest: reformMetricsGeneratorDigest,
    annotationsDigest: annotations ? digest(annotations) : null,
    bindings: explanation.bindings,
    scope: explanation.scope,
    coverage: explanation.coverage,
    property: explanation.property,
    verdict: explanation.verdict,
    models: explanation.bindings.models.map(({ role, bundle }) =>
      modelMetrics(
        bundles.find((b) => b.id === bundle.id)!,
        explanation.sources.find((s) => s.bundleId === bundle.id)!,
        role,
        annotations,
      ),
    ),
    consequences: consequenceMetrics(explanation),
  });
}
export function validateReformMetrics(
  value: unknown,
  query: ReformQuery,
  bundles: ReformBundle[],
  certificate: unknown,
  snapshot?: ReformSnapshot,
  sourceAnnotations?: unknown,
): ReformMetrics {
  const supplied = reformMetricsSchema.parse(value);
  const expected = projectReformMetrics(query, bundles, certificate, snapshot, sourceAnnotations);
  if (digest(supplied) !== digest(expected))
    fail('Metrics do not match exact inputs, annotations and current generator');
  return expected;
}
export async function measureReformExport(
  input: unknown,
  trustedPublicKey: string,
  sourceAnnotations?: unknown,
): Promise<ReformMetricsReport> {
  // Parse/clone all mutable caller input before the asynchronous proof boundary.
  const artifact = reformExportSchema.parse(input);
  const annotations = parseAnnotations(sourceAnnotations);
  const explanationReport = await explainReformExport(artifact, trustedPublicKey);
  const metrics = explanationReport.evidence.current
    ? projectReformMetrics(
        artifact.query,
        artifact.bundles,
        artifact.certificate,
        artifact.snapshot ?? undefined,
        annotations,
      )
    : null;
  return reformMetricsReportSchema.parse({
    schema: 'normlab.metrics-report/v1',
    artifactDigest: digest(artifact),
    metricsDigest: metrics ? digest(metrics) : null,
    metrics,
    evidence: explanationReport.evidence,
  });
}
export async function verifyReformMetricsReport(
  value: unknown,
  artifact: ReformExport,
  trustedPublicKey: string,
  sourceAnnotations?: unknown,
): Promise<ReformMetricsReport> {
  const supplied = reformMetricsReportSchema.parse(value);
  const expected = await measureReformExport(artifact, trustedPublicKey, sourceAnnotations);
  if (digest(supplied) !== digest(expected))
    fail('Metrics report does not match fresh replay and deterministic recount');
  return expected;
}
export function parseReformMetricsReport(text: string): ReformMetricsReport {
  return reformMetricsReportSchema.parse(parseReformJson(text));
}
