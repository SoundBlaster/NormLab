import { randomUUID } from 'node:crypto';
import stories from '../fixtures/parking-pilot/walkthroughs/cases.json';
import { parkingNormDigest } from '../server/parking-verifier.js';
import { emptyNarrativeContext } from '../shared/parking-context.js';
import {
  legalInputSchema,
  type LegalInput,
  type LegalResult,
  type ParkingVerification,
} from '../shared/parking-legal.js';
import { reviewDraftSchema } from '../shared/parking-review.js';
import { digest } from '../server/hash.js';

export const parkingStories = stories.cases;
export function parkingFixture(index = 0) {
  const story = parkingStories[index];
  // Minimal manual review seed, not a model extraction or completeness benchmark.
  const draft = reviewDraftSchema.parse({
    schema: 'normlab.parking-review/v2',
    draftId: randomUUID(),
    revisionId: randomUUID(),
    revision: 1,
    previousDraftId: null,
    createdAt: new Date().toISOString(),
    narrative: story.text,
    sourceDigest: digest(story.text),
    originalExtraction: null,
    status: 'reviewed',
    context: {
      ...emptyNarrativeContext(),
      topic: 'parking',
      parkingContext: 'parking-unspecified',
      intent: 'incident',
      decision: 'confirmed',
    },
    hypotheses: [],
    statements: [
      {
        id: randomUUID(),
        predicate: 'nlinput:placement',
        stance: 'asserted',
        subject: 'narrator',
        speaker: 'narrator',
        aboutEpisode: 'Эпизод 1',
        valueText: story.text,
        quote: story.text,
        startOffset: 0,
        endOffset: story.text.length,
        origin: 'human',
        decision: 'confirmed',
        rationale: 'Synthetic manual flow seed, not extraction evidence.',
      },
    ],
    checklist: {
      negatives: true,
      conflicts: true,
      attribution: true,
      sourceSupport: true,
      unknowns: true,
    },
  });
  const input = legalInputSchema.parse({
    ...story.reviewPlan.coordinates,
    claimedFine: story.reviewPlan.claimedFine,
    findings: story.reviewPlan.findings.map((f) => ({
      conditionId: f.conditionId,
      state: f.state,
      rationale: f.rationale,
      statementIds: [],
    })),
    draftId: draft.draftId,
    expectedRevisionId: draft.revisionId,
    expectedAssessmentId: null,
    requestId: randomUUID(),
    packageDigest: parkingNormDigest,
    action: 'calculate',
  });
  return { story, draft, input };
}

export function inconclusiveParkingProof(
  input: LegalInput,
  result: LegalResult,
): ParkingVerification {
  return {
    profile: 'parking-fragment-poc/v1',
    status: 'inconclusive',
    engine: 'lean-kernel',
    version: null,
    inputDigest: digest(input),
    resultDigest: digest(result),
    packageDigest: parkingNormDigest,
    profileDigest: '0'.repeat(64),
    statementDigest: '1'.repeat(64),
    toolchainDigest: null,
    axioms: [],
    reason: 'Mock: Lean unavailable',
    durationMs: 0,
  };
}
