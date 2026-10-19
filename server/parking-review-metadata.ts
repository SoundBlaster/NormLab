import {
  narrativeContextIssues,
  vehicleHypothesisIssues,
  type NarrativeContext,
  type VehicleHypothesis,
} from '../shared/parking-context.js';

type Metadata = { context: NarrativeContext; hypotheses: VehicleHypothesis[] };
const withoutDecision = <T extends { decision: string }>(value: T) => ({
  ...value,
  decision: 'pending',
});
const equal = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

/** Content edits need a saved revision before confirmation; no metadata creates statements. */
export function reviseReviewMetadata(prior: Metadata, input: Metadata, narrative: string) {
  const contextChanged = !equal(withoutDecision(prior.context), withoutDecision(input.context));
  const context = contextChanged
    ? { ...input.context, decision: 'pending' as const }
    : input.context;
  const contextIssues = narrativeContextIssues(context);
  if (contextIssues.length) throw new Error(contextIssues.join(' '));
  if (new Set(input.hypotheses.map((h) => h.id)).size !== input.hypotheses.length)
    throw new Error('Повторяются IDs гипотез.');
  if (prior.hypotheses.some((h) => !input.hypotheses.some((next) => next.id === h.id)))
    throw new Error('Отклоните гипотезу с причиной вместо удаления из истории.');
  const hypotheses = input.hypotheses.map((item) => {
    const before = prior.hypotheses.find((h) => h.id === item.id);
    const changed = !before || !equal(withoutDecision(before), withoutDecision(item));
    const result = contextChanged || changed ? { ...item, decision: 'pending' as const } : item;
    const issues = vehicleHypothesisIssues(result, narrative);
    if (issues.length) throw new Error(issues.join(' '));
    return result;
  });
  return {
    context,
    hypotheses,
    changed: !equal(prior, { context, hypotheses }),
  };
}
