import { z } from 'zod';
import { parkingScalarPredicates } from './parking-contracts.js';

export const reviewPredicates = Object.keys(parkingScalarPredicates);
export const reviewStatementSchema = z
  .object({
    id: z.string().uuid(),
    predicate: z.string().refine((value) => reviewPredicates.includes(value), 'Unknown predicate'),
    stance: z.enum(['asserted', 'denied', 'unknown']),
    subject: z.string().trim().min(1).max(128),
    aboutEpisode: z.string().trim().min(1).max(128),
    valueText: z.string().trim().min(1).max(2048),
    quote: z.string().min(1).max(4096),
    startOffset: z.number().int().min(0),
    endOffset: z.number().int().min(1),
    origin: z.enum(['model', 'human']),
    decision: z.enum(['pending', 'confirmed', 'rejected']),
    rationale: z.string().max(2048),
  })
  .strict();
export type ReviewStatement = z.infer<typeof reviewStatementSchema>;
export const reviewChecklistSchema = z
  .object({
    negatives: z.boolean(),
    conflicts: z.boolean(),
    attribution: z.boolean(),
    sourceSupport: z.boolean(),
    unknowns: z.boolean(),
  })
  .strict();
export const emptyReviewChecklist = {
  negatives: false,
  conflicts: false,
  attribution: false,
  sourceSupport: false,
  unknowns: false,
};
export const reviewDraftSchema = z
  .object({
    schema: z.literal('normlab.parking-review/v1'),
    draftId: z.string().uuid(),
    revisionId: z.string().uuid(),
    revision: z.number().int().positive(),
    previousDraftId: z.string().uuid().nullable(),
    createdAt: z.string(),
    narrative: z.string().min(1).max(32768),
    sourceDigest: z.string(),
    originalExtraction: z.unknown().nullable(),
    statements: z.array(reviewStatementSchema).max(256),
    checklist: reviewChecklistSchema,
    status: z.enum(['draft', 'reviewed']),
  })
  .strict();
export type ReviewDraft = z.infer<typeof reviewDraftSchema>;
export function reviewStatementIssues(statement: ReviewStatement, source: string): string[] {
  const issues: string[] = [];
  if (
    statement.endOffset <= statement.startOffset ||
    source.slice(statement.startOffset, statement.endOffset) !== statement.quote
  )
    issues.push('Цитата не совпадает с указанным фрагментом исходного текста.');
  if (statement.decision === 'rejected' && !statement.rationale.trim())
    issues.push('Укажите причину отклонения.');
  return issues;
}
