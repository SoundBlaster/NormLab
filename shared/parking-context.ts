import { z } from 'zod';

export const narrativeContextSchema = z
  .object({
    topic: z.enum(['parking', 'other', 'unclear', 'mixed']),
    parkingContext: z.enum([
      'paid-parking-topic',
      'parking-payment-topic',
      'parking-unspecified',
      'not-established',
    ]),
    intent: z.enum(['incident', 'information', 'unclear']),
    origin: z.literal('human'),
    decision: z.enum(['pending', 'confirmed']),
    rationale: z.string().max(2048),
  })
  .strict();
export type NarrativeContext = z.infer<typeof narrativeContextSchema>;
export const emptyNarrativeContext = (): NarrativeContext => ({
  topic: 'unclear',
  parkingContext: 'not-established',
  intent: 'unclear',
  origin: 'human',
  decision: 'pending',
  rationale: '',
});

export function narrativeRoute(context: NarrativeContext) {
  if (context.topic === 'mixed') return 'choose-episode';
  if (context.topic === 'other') return 'other-topic';
  if (context.topic === 'unclear' || context.intent === 'unclear') return 'clarify';
  if (context.parkingContext === 'not-established') return 'clarify';
  if (context.intent === 'information') return 'not-a-case';
  return 'parking-review';
}
export function narrativeContextIssues(context: NarrativeContext): string[] {
  if (['other', 'unclear'].includes(context.topic) && context.parkingContext !== 'not-established')
    return ['Парковочный контекст не согласован с выбранной темой.'];
  return [];
}

export const vehicleHypothesisSchema = z
  .object({
    id: z.string().uuid(),
    kind: z.literal('transport-vehicle'),
    vehicleKind: z.enum(['unspecified', 'car', 'motorcycle', 'bicycle', 'other']),
    vehicleKindDetails: z.string().max(256),
    aboutEpisode: z.string().trim().min(1).max(128),
    quote: z.string().min(1).max(4096),
    startOffset: z.number().int().min(0),
    endOffset: z.number().int().min(1),
    origin: z.literal('human'),
    decision: z.enum(['pending', 'confirmed', 'rejected']),
    rationale: z.string().max(2048),
  })
  .strict();
export type VehicleHypothesis = z.infer<typeof vehicleHypothesisSchema>;

export function vehicleHypothesisIssues(hypothesis: VehicleHypothesis, source: string) {
  const issues: string[] = [];
  if (
    hypothesis.endOffset <= hypothesis.startOffset ||
    source.slice(hypothesis.startOffset, hypothesis.endOffset) !== hypothesis.quote
  )
    issues.push('Цитата гипотезы не совпадает с исходным текстом.');
  if (hypothesis.decision === 'rejected' && !hypothesis.rationale.trim())
    issues.push('Укажите причину отклонения гипотезы.');
  if (
    hypothesis.decision === 'confirmed' &&
    hypothesis.vehicleKind === 'other' &&
    !hypothesis.vehicleKindDetails.trim()
  )
    issues.push('Укажите вид транспортного средства.');
  return issues;
}

export function reviewMetadataIssues(
  context: NarrativeContext,
  hypotheses: VehicleHypothesis[],
): string[] {
  const issues = narrativeContextIssues(context);
  if (context.decision !== 'confirmed') issues.push('Подтвердите контекст обращения.');
  if (narrativeRoute(context) !== 'parking-review')
    issues.push('Для парковочного разбора уточните тему и выберите один эпизод.');
  if (hypotheses.some((item) => item.decision === 'pending'))
    issues.push('Подтвердите или отклоните каждую гипотезу.');
  if (
    hypotheses.some((item) => item.decision === 'confirmed' && item.vehicleKind === 'unspecified')
  )
    issues.push('Уточните вид ТС у подтверждённой гипотезы.');
  return issues;
}
