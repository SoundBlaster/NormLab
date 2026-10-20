import {
  narrativeContextIssues,
  reviewDraftSchema,
  reviewStatementIssues,
  vehicleHypothesisIssues,
  type NarrativeContext,
  type ReviewDraft,
  type ReviewStatement,
  type VehicleHypothesis,
} from './contracts.js';

export type ReviewContent = {
  statements: ReviewStatement[];
  context: NarrativeContext;
  hypotheses: VehicleHypothesis[];
  checklist: ReviewDraft['checklist'];
};

/** Validate content for persistence; pending review decisions are intentionally valid. */
export function canPersistReview(draft: ReviewDraft, content: ReviewContent) {
  return (
    reviewDraftSchema.safeParse({ ...draft, schema: 'normlab.parking-review/v2', ...content })
      .success &&
    narrativeContextIssues(content.context).length === 0 &&
    content.statements.every(
      (statement) => reviewStatementIssues(statement, draft.narrative).length === 0,
    ) &&
    content.hypotheses.every(
      (hypothesis) => vehicleHypothesisIssues(hypothesis, draft.narrative).length === 0,
    )
  );
}
