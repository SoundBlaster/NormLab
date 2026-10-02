import { z } from 'zod';
import { digestSchema } from './domain.js';
import {
  REFORM_PROFILE,
  reformBundleRefSchema,
  reformCompletedInputSchema,
  reformOutcomeSchema,
  reformRuleSchema,
} from './reform-contracts.js';
import { reformExplanationSchema, reformExplanationReportSchema } from './reform-explanations.js';

export const REFORM_METRICS_METHOD = 'reform-structure-decision-changes/v1' as const;
const id = reformRuleSchema.shape.id;
const predicate = z.enum(['M', 'N', 'E']);
const count = z.number().int().min(0).max(32);
const span = z.strictObject({
  line: z.number().int().min(1).max(32768),
  text: z.string().min(1).max(32768),
});
const sourceAnnotation = z.strictObject({
  bundle: reformBundleRefSchema,
  sourceDigest: digestSchema,
  reviewer: z.string().min(1).max(200),
  review: z.literal('complete-for-mapped-provisions-and-shared-definitions'),
  definitions: z.array(z.strictObject({ predicate, span })).max(3),
  references: z.array(z.strictObject({ fromRuleId: id, toRuleId: id, span })).max(24),
});
export const reformMetricAnnotationsSchema = z.strictObject({
  schema: z.literal('normlab.metrics-source-annotations/v1'),
  models: z.array(sourceAnnotation).min(1).max(4),
});
export type ReformMetricAnnotations = z.infer<typeof reformMetricAnnotationsSchema>;

const componentName = z.enum(['prisonMonths', 'fineAmount', 'qualification', 'currency']);
const componentCounts = {
  changed: count,
  unchanged: count,
};
const componentMetric = z.discriminatedUnion('component', [
  z.strictObject({
    component: z.literal('prisonMonths'),
    unit: z.literal('month'),
    ...componentCounts,
    decreased: count,
    increased: count,
    minDelta: z.number().int().min(-3600).max(3600),
    maxDelta: z.number().int().min(-3600).max(3600),
  }),
  z.strictObject({
    component: z.literal('fineAmount'),
    unit: z.literal('DEMO'),
    ...componentCounts,
    decreased: count,
    increased: count,
    minDelta: z.number().int().min(-1000000).max(1000000),
    maxDelta: z.number().int().min(-1000000).max(1000000),
  }),
  z.strictObject({
    component: z.literal('qualification'),
    unit: z.literal('group-code'),
    ...componentCounts,
  }),
  z.strictObject({
    component: z.literal('currency'),
    unit: z.literal('currency-code'),
    ...componentCounts,
  }),
]);
const edge = z.strictObject({ fromRuleId: id, toRuleId: id });
export const reformMetricsSchema = z.strictObject({
  schema: z.literal('normlab.metrics/v1'),
  profileId: z.literal(REFORM_PROFILE),
  methodology: z.literal(REFORM_METRICS_METHOD),
  proofStatus: z.literal('unchecked'),
  generatorDigest: digestSchema,
  annotationsDigest: digestSchema.nullable(),
  bindings: reformExplanationSchema.shape.bindings,
  scope: reformExplanationSchema.shape.scope,
  coverage: reformExplanationSchema.shape.coverage,
  property: reformExplanationSchema.shape.property,
  verdict: reformExplanationSchema.shape.verdict,
  models: z
    .array(
      z.strictObject({
        role: z.enum(['model', 'baseline', 'candidate']),
        bundle: reformBundleRefSchema,
        structure: z.strictObject({
          representation: z.literal('mapped-source-sections-and-authored-legal-ir/v1'),
          provisions: z
            .array(
              z.strictObject({
                ruleId: id,
                startLine: z.number().int().min(1).max(32768),
                endLine: z.number().int().min(1).max(32768),
              }),
            )
            .min(4)
            .max(12),
          provisionCount: count,
          irRuleCount: count,
          groupExpandedRuleCount: count,
          operationTemplates: z
            .array(
              z.strictObject({
                operation: reformRuleSchema.shape.operation,
                ruleIds: z.array(id).min(1).max(12),
              }),
            )
            .min(1)
            .max(12),
          operationTemplateCount: count,
          repeatedOperationCount: count,
          exclusionReferences: z.array(edge).max(12),
          exclusionReferenceCount: count,
          sourceAnnotations: sourceAnnotation.nullable(),
          definitionCount: count.nullable(),
          normativeTextReferenceCount: count.nullable(),
        }),
        decision: z.strictObject({
          independentConditions: z.array(predicate).min(1).max(3),
          independentConditionCount: count,
          explicitConditionOccurrences: z.array(z.strictObject({ ruleId: id, predicate })).max(12),
          explicitConditionOccurrenceCount: count,
          exceptionRuleIds: z.array(id).max(12),
          exceptionCount: count,
          humanJudgmentPoints: z.array(predicate).min(1).max(3),
          humanJudgmentCount: count,
          outsideScopeInputs: z.tuple([z.literal('group')]),
          orderedScalePairs: z.array(edge).max(12),
          orderedScalePairCount: count,
        }),
      }),
    )
    .min(1)
    .max(2),
  consequences: z.discriminatedUnion('kind', [
    z.strictObject({
      kind: z.literal('decision'),
      unit: z.literal('snapshot-completion'),
      completionCount: count,
      distinctOutcomeCount: count,
      openHumanJudgmentCount: count,
      branches: z
        .array(z.strictObject({ input: reformCompletedInputSchema, outcome: reformOutcomeSchema }))
        .min(1)
        .max(8),
    }),
    z.strictObject({
      kind: z.enum(['comparison', 'property']),
      unit: z.enum(['completed-input', 'mitigation-pair']),
      observedCount: count,
      changedCount: count,
      unchangedCount: count,
      components: z.array(componentMetric).length(4),
      categories: z
        .array(
          z.strictObject({
            group: z.enum(['K1', 'K2']),
            baselineM: z.boolean(),
            observedCount: count,
            changedCount: count,
            changedComponents: z.array(componentName).max(4),
          }),
        )
        .min(1)
        .max(4),
      rows: z
        .array(
          z.strictObject({
            caseIndex: count,
            baselineInput: reformCompletedInputSchema,
            candidateInput: reformCompletedInputSchema,
            baselineOutcome: reformOutcomeSchema,
            candidateOutcome: reformOutcomeSchema,
            changedComponents: z.array(componentName).max(4),
          }),
        )
        .min(1)
        .max(16),
    }),
  ]),
});
export type ReformMetrics = z.infer<typeof reformMetricsSchema>;

export const reformMetricsReportSchema = z
  .strictObject({
    schema: z.literal('normlab.metrics-report/v1'),
    artifactDigest: digestSchema,
    metricsDigest: digestSchema.nullable(),
    metrics: reformMetricsSchema.nullable(),
    evidence: reformExplanationReportSchema.shape.evidence,
  })
  .superRefine((report, context) => {
    const hasMetrics = report.metrics !== null;
    if (
      hasMetrics !== (report.metricsDigest !== null) ||
      hasMetrics !== report.evidence.current ||
      (report.evidence.current &&
        (!report.evidence.signatureValid ||
          !report.evidence.bindingsValid ||
          report.evidence.proofStatus !== 'verified' ||
          report.evidence.proofMethod === null ||
          report.evidence.toolchainDigest === null))
    )
      context.addIssue({
        code: 'custom',
        message: 'Metrics availability requires a current trusted receipt and fresh proof',
      });
  });
export type ReformMetricsReport = z.infer<typeof reformMetricsReportSchema>;

export function renderReformMetricsMarkdown(value: unknown): string {
  const report = reformMetricsReportSchema.parse(value);
  const m = report.metrics;
  const lines = [
    '# Метрики NormLab',
    '',
    `Signature: **${report.evidence.signatureValid}**; bindings: **${report.evidence.bindingsValid}**; current: **${report.evidence.current}**.`,
    '',
    `Исходный proof: **${report.evidence.proofStatus}**; method: **${report.evidence.proofMethod ?? 'none'}**.`,
    '',
  ];
  if (!m)
    return lines
      .concat('Метрики недоступны: текущий trusted receipt не подтверждён.', '')
      .join('\n');
  lines.push(
    `Методика: ${m.methodology}.`,
    '',
    `Scope: ${m.scope.domain.id}; ${m.scope.kind}; ${m.scope.kind === 'snapshot-completions' ? 'ограничения findings snapshot' : `condition M=${m.scope.condition?.M ?? 'any'}`}${m.scope.group ? `; group=${m.scope.group}` : ''}.`,
    '',
    `Coverage: **${m.coverage.status}**, ${m.coverage.coveredCardinality}/${m.coverage.declaredCardinality} (${m.coverage.kind}).`,
    '',
    'Счётчики — deterministic projection с proofStatus=unchecked. Lean проверяет исходный certificate; подсчёт и human annotations не имеют отдельного Lean proof.',
    '',
    '## Структура',
    '',
    '| Model / role | Положения source | IR rules | Group-expanded rules | Templates | Повторы operations | Определения | Отсылки text | Exclusion edges |',
    '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |',
  );
  for (const model of m.models) {
    const s = model.structure;
    lines.push(
      `| ${model.bundle.id} / ${model.role} | ${s.provisionCount} | ${s.irRuleCount} | ${s.groupExpandedRuleCount} | ${s.operationTemplateCount} | ${s.repeatedOperationCount} | ${s.definitionCount ?? 'unavailable'} | ${s.normativeTextReferenceCount ?? 'unavailable'} | ${s.exclusionReferenceCount} |`,
    );
  }
  lines.push(
    '',
    'Повторы: дополнительные экземпляры одинаковой typed operation при вынесенном group scope; это не подсчёт одинаковых строк текста. Definitions и text references требуют полной reviewed source annotation.',
    '',
    '## Получение решения',
    '',
    '| Model / role | Независимые условия | Explicit trigger occurrences | Exception rules | Human judgment points | Ordered M/N pairs |',
    '| --- | ---: | ---: | ---: | ---: | ---: |',
  );
  for (const model of m.models) {
    const d = model.decision;
    lines.push(
      `| ${model.bundle.id} / ${model.role} | ${d.independentConditionCount} | ${d.explicitConditionOccurrenceCount} | ${d.exceptionCount} | ${d.humanJudgmentCount} | ${d.orderedScalePairCount} |`,
    );
  }
  lines.push(
    '',
    'Human judgment points — M/N/E в scope этого profile. Выбор group задан извне; число точек не измеряет трудозатраты reviewer.',
    '',
    '## Последствия',
    '',
  );
  const c = m.consequences;
  if (c.kind === 'decision') {
    lines.push(
      `Completions: **${c.completionCount}**; различных полных outcomes: **${c.distinctOutcomeCount}**; открытых human judgment points: **${c.openHumanJudgmentCount}**.`,
      '',
      'Равные outcomes не удаляют разные completions. Сравнение моделей для этого decision query не выполняется.',
      '',
    );
    for (const b of c.branches)
      lines.push(
        `- ${b.input.group}; M=${b.input.M}; N=${b.input.N}; E=${b.input.E}: ${b.outcome.prisonMonths} месяцев; ${b.outcome.fineAmount} ${b.outcome.currency}; ${b.outcome.qualification}.`,
      );
  } else {
    lines.push(
      `Единица наблюдения: **${c.unit}**. Изменено **${c.changedCount}/${c.observedCount}**, сохранено **${c.unchangedCount}/${c.observedCount}** в покрытой области.`,
      '',
      '| Компонент | Единица | Изменено | Сохранено | Уменьшено | Увеличено | Delta min…max |',
      '| --- | --- | ---: | ---: | ---: | ---: | --- |',
    );
    for (const x of c.components)
      lines.push(
        `| ${x.component} | ${x.unit} | ${x.changed} | ${x.unchanged} | ${'decreased' in x ? x.decreased : 'n/a'} | ${'increased' in x ? x.increased : 'n/a'} | ${'minDelta' in x ? `${x.minDelta}…${x.maxDelta}` : 'n/a'} |`,
      );
    lines.push(
      '',
      'Delta = candidate − baseline; диапазон включает все наблюдения, включая сохранённые. Категории — непересекающиеся (group, baseline M), описательные, без заявления причинности.',
      '',
      '| Group | Baseline M | Наблюдений | Изменено | Компоненты |',
      '| --- | --- | ---: | ---: | --- |',
    );
    for (const x of c.categories)
      lines.push(
        `| ${x.group} | ${x.baselineM} | ${x.observedCount} | ${x.changedCount} | ${x.changedComponents.join(', ') || 'нет'} |`,
      );
    lines.push(
      '',
      '### Все наблюдения',
      '',
      '| Input baseline → candidate | Prison months | Fine DEMO | Изменено |',
      '| --- | --- | --- | --- |',
    );
    const input = (x: z.infer<typeof reformCompletedInputSchema>) =>
      `${x.group}/M=${x.M}/N=${x.N}/E=${x.E}`;
    for (const row of c.rows)
      lines.push(
        `| ${input(row.baselineInput)} → ${input(row.candidateInput)} | ${row.baselineOutcome.prisonMonths} → ${row.candidateOutcome.prisonMonths} | ${row.baselineOutcome.fineAmount} → ${row.candidateOutcome.fineAmount} | ${row.changedComponents.join(', ') || 'нет'} |`,
      );
  }
  lines.push(
    '',
    '## Bindings',
    '',
    `Artifact: ${report.artifactDigest}`,
    '',
    `Query: ${m.bindings.queryDigest}`,
    '',
    `Certificate: ${m.bindings.certificateDigest}`,
    '',
    `Annotations: ${m.annotationsDigest ?? 'none'}`,
    '',
    `Generator: ${m.generatorDigest}`,
    '',
    `Metrics: ${report.metricsDigest}`,
    '',
    'Sidecar не подписан receipt. Для доверия требуется fresh replay и повторный подсчёт по точным исходным artifacts и annotations. Общего индекса гуманности нет.',
    '',
  );
  return lines.join('\n');
}
