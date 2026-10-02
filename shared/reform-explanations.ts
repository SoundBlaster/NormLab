import { z } from 'zod';
import { digestSchema } from './domain.js';
import {
  REFORM_PROFILE,
  reformBundleRefSchema,
  reformDomainSchema,
  reformOutcomeSchema,
  reformCompletedInputSchema,
  reformRuleSchema,
  reformSnapshotInputSchema,
} from './reform-contracts.js';

const role = z.enum(['model', 'baseline', 'candidate']);
const id = reformRuleSchema.shape.id;
const predicate = z.enum(['M', 'N', 'E']);
const status = z.enum(['applied', 'inapplicable', 'excluded']);
const reason = z.enum([
  'outside-group',
  'baseline-selected',
  'trigger-false',
  'scale-applied',
  'excluded-by-E',
  'exclusion-applied',
  'exclusion-inactive',
]);
const event = z.strictObject({
  ruleId: id,
  status,
  reason,
  excludedBy: id.nullable(),
  conditions: z
    .array(
      z.strictObject({
        predicate,
        value: z.boolean(),
        origin: z.enum(['finding', 'completion', 'domain-input']),
      }),
    )
    .max(2),
  step: z
    .strictObject({
      beforeMonths: z.number().int().min(0).max(3600),
      afterMonths: z.number().int().min(0).max(3600),
    })
    .nullable(),
});
const component = z.discriminatedUnion('component', [
  z.strictObject({
    component: z.literal('prisonMonths'),
    baseline: z.number().int().min(0).max(3600),
    candidate: z.number().int().min(0).max(3600),
    delta: z.number().int().min(-3600).max(3600),
    changed: z.boolean(),
  }),
  z.strictObject({
    component: z.literal('fineAmount'),
    baseline: z.number().int().min(0).max(1000000),
    candidate: z.number().int().min(0).max(1000000),
    delta: z.number().int().min(-1000000).max(1000000),
    changed: z.boolean(),
  }),
  z.strictObject({
    component: z.literal('qualification'),
    baseline: z.enum(['K1', 'K2']),
    candidate: z.enum(['K1', 'K2']),
    delta: z.null(),
    changed: z.boolean(),
  }),
  z.strictObject({
    component: z.literal('currency'),
    baseline: z.literal('DEMO'),
    candidate: z.literal('DEMO'),
    delta: z.null(),
    changed: z.boolean(),
  }),
]);
export const reformExplanationSchema = z.strictObject({
  schema: z.literal('normlab.explanation/v1'),
  profileId: z.literal(REFORM_PROFILE),
  proofStatus: z.literal('unchecked'),
  generatorDigest: digestSchema,
  queryKind: z.enum(['decision', 'comparison', 'property']),
  bindings: z.strictObject({
    queryDigest: digestSchema,
    certificateDigest: digestSchema,
    assumptionsDigest: digestSchema,
    snapshotDigest: digestSchema.nullable(),
    models: z
      .array(z.strictObject({ role, bundle: reformBundleRefSchema }))
      .min(1)
      .max(2),
  }),
  scope: z.strictObject({
    domain: reformDomainSchema,
    kind: z.enum(['snapshot-completions', 'completed-inputs', 'mitigation-pairs']),
    condition: z.strictObject({ M: z.boolean() }).nullable(),
    group: z.enum(['K1', 'K2']).nullable(),
    openPredicates: z.array(predicate).max(3),
  }),
  coverage: z.strictObject({
    kind: z.enum(['snapshot-completions', 'finite-domain', 'corpus']),
    status: z.enum(['declared-complete', 'partial']),
    declaredCardinality: z.number().int().min(1).max(16),
    coveredCardinality: z.number().int().min(1).max(16),
  }),
  property: z.enum([
    'decision',
    'equivalence',
    'component-no-increase',
    'strict-reduction',
    'preserved-outside',
    'strict-M-mitigation',
  ]),
  verdict: z.enum(['complete', 'conditional', 'holds', 'counterexample']),
  assumptions: z.array(z.string().min(1).max(2000)).min(1).max(16),
  findings: reformSnapshotInputSchema.shape.findings.nullable(),
  sources: z
    .array(
      z.strictObject({
        bundleId: id,
        sourceId: id,
        sourceDigest: digestSchema,
        rules: z
          .array(
            z.strictObject({
              rule: reformRuleSchema,
              anchor: id,
              startLine: z.number().int().min(1).max(32768),
              endLine: z.number().int().min(1).max(32768),
              text: z.string().min(1).max(65536),
              originRuleIds: z.array(id).max(12),
            }),
          )
          .min(4)
          .max(12),
      }),
    )
    .min(1)
    .max(2),
  summary: z
    .array(
      z.strictObject({
        ruleId: id,
        status: z.enum(['applied', 'inapplicable', 'excluded', 'unresolved']),
        excludedBy: id.nullable(),
        branches: z
          .array(
            z.strictObject({
              caseIndex: z.number().int().min(0).max(15),
              status,
              excludedBy: id.nullable(),
            }),
          )
          .min(1)
          .max(8),
      }),
    )
    .max(12),
  cases: z
    .array(
      z.strictObject({
        index: z.number().int().min(0).max(15),
        relationSatisfied: z.boolean().nullable(),
        traces: z
          .array(
            z.strictObject({
              role,
              bundleId: id,
              input: reformCompletedInputSchema,
              outcome: reformOutcomeSchema,
              derivationOrigin: z.enum(['certificate-ledger', 'reconstructed-from-locked-model']),
              timeline: z.array(id).min(1).max(4),
              events: z.array(event).min(4).max(12),
            }),
          )
          .min(1)
          .max(2),
        components: z.array(component).max(4),
        ruleChanges: z
          .array(
            z.strictObject({
              slot: z.enum(['baseline', 'M', 'N', 'exclusion']),
              baselineRuleId: id,
              candidateRuleId: id,
              operationChanged: z.boolean(),
              statusChanged: z.boolean(),
              conditionsChanged: z.boolean(),
              stepValuesChanged: z.boolean(),
            }),
          )
          .max(4),
      }),
    )
    .min(1)
    .max(16),
  counterexampleCase: z.number().int().min(0).max(15).nullable(),
});
export type ReformExplanation = z.infer<typeof reformExplanationSchema>;

export const reformExplanationReportSchema = z
  .strictObject({
    schema: z.literal('normlab.explanation-report/v1'),
    artifactDigest: digestSchema,
    explanationDigest: digestSchema.nullable(),
    explanation: reformExplanationSchema.nullable(),
    evidence: z.strictObject({
      signatureValid: z.boolean(),
      bindingsValid: z.boolean(),
      current: z.boolean(),
      proofStatus: z.enum(['unchecked', 'verified', 'inconclusive', 'rejected', 'unsupported']),
      proofMethod: z.enum(['case-theorem', 'finite-domain-theorem']).nullable(),
      toolchainDigest: digestSchema.nullable(),
      reason: z.string().min(1).max(4096),
    }),
  })
  .superRefine((report, context) => {
    const hasExplanation = report.explanation !== null;
    if (
      hasExplanation !== (report.explanationDigest !== null) ||
      hasExplanation !== report.evidence.current ||
      (report.evidence.current &&
        (!report.evidence.signatureValid ||
          !report.evidence.bindingsValid ||
          report.evidence.proofStatus !== 'verified' ||
          report.evidence.proofMethod === null ||
          report.evidence.toolchainDigest === null))
    )
      context.addIssue({
        code: 'custom',
        message: 'Explanation availability requires a current trusted receipt and fresh proof',
      });
  });
export type ReformExplanationReport = z.infer<typeof reformExplanationReportSchema>;

// User text is rendered as literal text, never as links, HTML or Markdown structure.
function literal(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replace(/[\\`*_{}\[\]()#+.!|]/g, '\\$&')
    .replace(/[\r\n]/g, ' ');
}
const inputText = (x: ReformExplanation['cases'][number]['traces'][number]['input']) =>
  `${x.group}; M=${x.M}; N=${x.N}; E=${x.E}`;

export function renderReformExplanationMarkdown(value: unknown): string {
  const report = reformExplanationReportSchema.parse(value);
  const e = report.explanation;
  const lines = [
    '# Объяснение NormLab',
    '',
    `Signature: **${report.evidence.signatureValid}**; bindings: **${report.evidence.bindingsValid}**; current: **${report.evidence.current}**.`,
    '',
    `Proof status: **${report.evidence.proofStatus}**; method: **${report.evidence.proofMethod ?? 'none'}**.`,
    '',
    literal(report.evidence.reason),
    '',
  ];
  if (!e)
    return lines.concat('Объяснение недоступно: текущий receipt не подтверждён.', '').join('\n');
  lines.push(
    `## ${e.queryKind}: ${e.property}`,
    '',
    `Verdict: **${e.verdict}**.`,
    '',
    `Scope: ${e.scope.domain.id}; ${e.scope.kind}; ${e.scope.kind === 'snapshot-completions' ? 'ограничения findings snapshot' : e.scope.condition === null ? 'весь D16' : `M=${e.scope.condition.M}`}${e.scope.group ? `; group=${e.scope.group}` : ''}.`,
    '',
    `Coverage: **${e.coverage.status}**, ${e.coverage.coveredCardinality}/${e.coverage.declaredCardinality} (${e.coverage.kind}).`,
    '',
    'Объяснение — deterministic projection. Lean проверяет исходное утверждение; текст и reconstructed ledger не имеют отдельного Lean proof.',
    '',
    '## Assumptions',
    '',
    ...e.assumptions.map((a) => `- ${literal(a)}`),
    '',
  );
  if (e.findings) {
    lines.push('## Findings', '');
    for (const p of ['M', 'N', 'E'] as const)
      lines.push(`- ${p}: ${e.findings[p].state}; rationale: ${literal(e.findings[p].rationale)}`);
    lines.push('', `Открытые условия: ${e.scope.openPredicates.join(', ') || 'нет'}.`, '');
  }
  if (e.summary.length) {
    lines.push('## Summary ledger', '');
    for (const entry of e.summary)
      lines.push(
        `- ${entry.ruleId}: **${entry.status}**${entry.excludedBy ? `; excluded by ${entry.excludedBy}` : ''}; branches: ${entry.branches.map((b) => `${b.caseIndex}: ${b.status}${b.excludedBy ? `/${b.excludedBy}` : ''}`).join(', ')}`,
      );
    lines.push('');
  }
  const reasons: Record<z.infer<typeof reason>, string> = {
    'outside-group': 'Правило относится к другой группе.',
    'baseline-selected': 'Базовое последствие выбрано по заданной группе.',
    'trigger-false': 'В этом completed input условие правила ложно.',
    'scale-applied': 'Обязательный множитель применён ровно один раз.',
    'excluded-by-E': 'N исключено правилом E; обязательность M сохраняется.',
    'exclusion-applied': 'N и E истинны; исключение блокирует только N.',
    'exclusion-inactive': 'N и E не установлены одновременно в этом completed input.',
  };
  for (const row of e.cases) {
    lines.push(
      `## Case ${row.index}${e.counterexampleCase === row.index ? ' — counterexample' : ''}`,
      '',
    );
    if (row.relationSatisfied !== null)
      lines.push(`Свойство на этой строке: **${row.relationSatisfied}**.`, '');
    for (const trace of row.traces) {
      lines.push(
        `### ${trace.role}: ${trace.bundleId}`,
        '',
        inputText(trace.input),
        '',
        `Последствие: ${trace.outcome.qualification}; **${trace.outcome.prisonMonths} месяцев**; ${trace.outcome.fineAmount} ${trace.outcome.currency}.`,
        '',
        `Derivation: ${trace.derivationOrigin}; timeline: ${trace.timeline.join(' → ')}.`,
        '',
      );
      const source = e.sources.find((s) => s.bundleId === trace.bundleId)!;
      for (const event of trace.events) {
        const mapping = source.rules.find((s) => s.rule.id === event.ruleId)!;
        const op = mapping.rule.operation;
        const scale = op.kind === 'scale' ? ` × ${op.numerator}/${op.denominator}` : '';
        lines.push(
          `- **${event.ruleId}: ${event.status}**. ${reasons[event.reason]}${event.excludedBy ? ` Excluded by ${event.excludedBy}.` : ''}${event.step ? ` ${event.step.beforeMonths}${scale} = ${event.step.afterMonths} месяцев.` : ''} Source: ${source.sourceId}#${mapping.anchor}, lines ${mapping.startLine}–${mapping.endLine}.`,
        );
        if (event.conditions.length)
          lines.push(
            `  Conditions: ${event.conditions.map((c) => `${c.predicate}=${c.value} (${c.origin})`).join(', ')}.`,
          );
      }
      lines.push('');
    }
    for (const c of row.components)
      lines.push(
        `- ${c.component}: ${c.baseline} → ${c.candidate}; ${c.changed ? `изменено${c.delta !== null ? `, delta=${c.delta}` : ''}` : 'сохранено'}.`,
      );
    for (const change of row.ruleChanges)
      if (
        change.operationChanged ||
        change.statusChanged ||
        change.conditionsChanged ||
        change.stepValuesChanged
      ) {
        const labels = [
          change.operationChanged ? 'изменена операция' : '',
          change.statusChanged ? 'изменён status' : '',
          change.conditionsChanged ? 'изменены условия' : '',
          change.stepValuesChanged && !change.operationChanged
            ? 'изменены значения шага при той же операции'
            : '',
        ].filter(Boolean);
        lines.push(
          `- ${change.slot}: ${change.baselineRuleId} → ${change.candidateRuleId}; ${labels.join('; ')}.`,
        );
      }
    lines.push('');
  }
  lines.push('## Источники', '');
  for (const source of e.sources) {
    lines.push(
      `### ${source.bundleId}: ${source.sourceId}`,
      '',
      `Source digest: ${source.sourceDigest}.`,
      '',
    );
    for (const mapping of source.rules) {
      lines.push(
        `#### ${mapping.rule.id} / ${mapping.anchor}`,
        '',
        `Lines ${mapping.startLine}–${mapping.endLine}; origin rules: ${mapping.originRuleIds.join(', ') || 'нет'}.`,
        '',
        ...mapping.text.split('\n').map((line) => `    ${line}`),
        '',
      );
    }
  }
  lines.push(
    '## Bindings',
    '',
    `Query: ${e.bindings.queryDigest}`,
    '',
    `Certificate: ${e.bindings.certificateDigest}`,
    '',
    `Generator: ${e.generatorDigest}`,
    '',
    `Explanation: ${report.explanationDigest}`,
    '',
  );
  return lines.join('\n');
}
