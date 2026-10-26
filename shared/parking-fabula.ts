import { z } from 'zod';

const uuid = z.string().uuid();
const hash = z.string().regex(/^[a-f0-9]{64}$/);
export const fabulaActorCandidateSchema = z
  .object({
    id: hash,
    statementId: uuid,
    label: z.string().min(1).max(128),
    quote: z.string().min(1).max(4096),
    startOffset: z.number().int().nonnegative(),
    endOffset: z.number().int().positive(),
    method: z.literal('explicit-first-person/v1'),
  })
  .strict();
export const fabulaActorInputSchema = z
  .object({
    requestId: uuid,
    draftId: uuid,
    expectedRevisionId: uuid,
    assessmentId: uuid,
    candidateId: hash,
    expectedDecisionId: uuid.nullable(),
    decision: z.enum(['confirmed', 'rejected']),
  })
  .strict();
export const fabulaActorDecisionSchema = z
  .object({
    schema: z.literal('normlab.fabula-actor-decision/v1'),
    id: uuid,
    sequence: z.number().int().positive(),
    at: z.string().datetime(),
    sourceDigest: hash,
    input: fabulaActorInputSchema,
    candidate: fabulaActorCandidateSchema,
  })
  .strict();
export const fabulaSourceSchema = z
  .object({
    draftId: uuid,
    revisionId: uuid,
    assessmentId: uuid,
    sourceDigest: hash,
    narrative: z.string().min(1).max(32768),
    candidates: z.array(fabulaActorCandidateSchema).max(256),
    decisions: z.array(fabulaActorDecisionSchema),
  })
  .strict();
export type FabulaActorInput = z.infer<typeof fabulaActorInputSchema>;
export type FabulaActorCandidate = z.infer<typeof fabulaActorCandidateSchema>;
export type FabulaSource = z.infer<typeof fabulaSourceSchema>;
