import { z } from 'zod';
import { legalFindingSchema, legalInputSchema, parkingNormDraft } from './parking-legal.js';
import { reviewStatementSchema } from './parking-review.js';

export const legalCoordinateKeys = [
  'participant',
  'vehicle',
  'location',
  'eventDate',
  'timeInterval',
] as const;
export type LegalCoordinateKey = (typeof legalCoordinateKeys)[number];
const hash = z.string().regex(/^[a-f0-9]{64}$/);
const references = z
  .array(z.string().uuid())
  .max(256)
  .refine((ids) => new Set(ids).size === ids.length, 'Duplicate statement references.');
const coordinate = (value: z.ZodType<string>) =>
  z
    .strictObject({
      value,
      rationale: z.string().trim().min(1).max(2048),
      statementIds: references,
    })
    .refine(
      (item) => !item.value || item.statementIds.length > 0,
      'A proposed coordinate needs source support.',
    );

export const legalSuggestionSchema = z
  .strictObject({
    coordinates: z.strictObject({
      participant: coordinate(legalInputSchema.shape.participant),
      vehicle: coordinate(legalInputSchema.shape.vehicle),
      location: coordinate(legalInputSchema.shape.location),
      eventDate: coordinate(legalInputSchema.shape.eventDate),
      timeInterval: coordinate(legalInputSchema.shape.timeInterval),
    }),
    findings: z.array(legalFindingSchema).length(parkingNormDraft.conditions.length),
  })
  .superRefine((value, ctx) => {
    if (
      new Set(value.findings.map((item) => item.conditionId)).size !==
      parkingNormDraft.conditions.length
    )
      ctx.addIssue({ code: 'custom', message: 'Expected every condition exactly once.' });
    for (const [index, finding] of value.findings.entries()) {
      if (finding.proposalId)
        ctx.addIssue({
          code: 'custom',
          message: 'The model cannot assign provenance.',
          path: ['findings', index],
        });
      if (
        ['established', 'refuted', 'conflict'].includes(finding.state) &&
        !finding.statementIds.length
      )
        ctx.addIssue({
          code: 'custom',
          message: 'A proposed decision needs source support.',
          path: ['findings', index],
        });
    }
  });
export type LegalSuggestion = z.infer<typeof legalSuggestionSchema>;

export const legalProposalRequestSchema = z.strictObject({
  draftId: z.string().uuid(),
  expectedRevisionId: z.string().uuid(),
  expectedAssessmentId: z.string().uuid().nullable(),
  episode: z.string().trim().min(1).max(128),
});
// Only the selected episode's reviewed words are sent; rejected/pending material is excluded.
export const legalProposalInputSchema = z
  .strictObject({
    draftId: z.string().uuid(),
    revisionId: z.string().uuid(),
    sourceDigest: hash,
    packageDigest: hash,
    episode: z.string().trim().min(1).max(128),
    statements: z
      .array(
        z.strictObject({
          id: reviewStatementSchema.shape.id,
          predicate: reviewStatementSchema.shape.predicate,
          stance: reviewStatementSchema.shape.stance,
          subject: reviewStatementSchema.shape.subject,
          speaker: z.string().max(128).nullable(),
          valueText: reviewStatementSchema.shape.valueText,
          quote: reviewStatementSchema.shape.quote,
        }),
      )
      .min(1)
      .max(256),
  })
  .refine(
    (input) => new Set(input.statements.map((item) => item.id)).size === input.statements.length,
    'Duplicate statement IDs.',
  );
export type LegalProposalInput = z.infer<typeof legalProposalInputSchema>;

export const legalProposalSchema = z.strictObject({
  schema: z.literal('normlab.parking-legal-proposal/v1'),
  draftId: z.string().uuid(),
  revisionId: z.string().uuid(),
  sourceDigest: hash,
  packageDigest: hash,
  episode: z.string().trim().min(1).max(128),
  inputDigest: hash,
  promptDigest: hash,
  configDigest: hash,
  model: z.string().min(1).max(256),
  usage: z.strictObject({
    inputTokens: z.number().int().nonnegative(),
    outputTokens: z.number().int().nonnegative(),
  }),
  suggestion: legalSuggestionSchema,
});
export type LegalProposal = z.infer<typeof legalProposalSchema>;
export const savedLegalProposalSchema = legalProposalSchema.extend({
  proposalId: z.string().uuid(),
});
export type SavedLegalProposal = z.infer<typeof savedLegalProposalSchema>;

/** This checks reference membership, not the truth or meaning of a proposed conclusion. */
export function legalProposalMatches(input: LegalProposalInput, proposal: LegalProposal): boolean {
  const ids = new Set(input.statements.map((item) => item.id));
  return (
    proposal.draftId === input.draftId &&
    proposal.revisionId === input.revisionId &&
    proposal.sourceDigest === input.sourceDigest &&
    proposal.packageDigest === input.packageDigest &&
    proposal.episode === input.episode &&
    [...Object.values(proposal.suggestion.coordinates), ...proposal.suggestion.findings].every(
      (item) => item.statementIds.every((id) => ids.has(id)),
    )
  );
}
