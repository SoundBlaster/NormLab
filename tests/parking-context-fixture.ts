import type { ParkingReview } from '../server/parking-review.js';
import { emptyNarrativeContext } from '../shared/parking-context.js';
import {
  reviewDraftMetadata,
  reviewDraftSchema,
  type ReviewDraft,
} from '../shared/parking-review.js';

export async function confirmedParkingDraft(api: ParkingReview, narrative: string) {
  let draft = reviewDraftSchema.parse(
    await api.handle('POST', '/api/parking/drafts', { narrative }),
  );
  const context = {
    ...emptyNarrativeContext(),
    topic: 'parking' as const,
    parkingContext: 'parking-unspecified' as const,
    intent: 'incident' as const,
  };
  draft = await saveReviewMetadata(api, draft, { context });
  return saveReviewMetadata(api, draft, { context: { ...context, decision: 'confirmed' } });
}

export async function saveReviewMetadata(
  api: ParkingReview,
  draft: ReviewDraft,
  patch: Partial<ReturnType<typeof reviewDraftMetadata>>,
) {
  return reviewDraftSchema.parse(
    await api.handle('POST', '/api/parking/review', {
      draftId: draft.draftId,
      expectedRevisionId: draft.revisionId,
      statements: draft.statements,
      checklist: draft.checklist,
      finishReview: false,
      ...reviewDraftMetadata(draft),
      ...patch,
    }),
  );
}
