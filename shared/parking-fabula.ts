import { z } from 'zod';

const uuid = z.string().uuid();
const hash = z.string().regex(/^[a-f0-9]{64}$/);
const actorCandidate = z.object({
  id: hash,
  statementId: uuid,
  label: z.string().min(1).max(128),
  quote: z.string().min(1).max(4096),
  startOffset: z.number().int().nonnegative(),
  endOffset: z.number().int().positive(),
});
export const fabulaActorCandidateSchema = z.discriminatedUnion('method', [
  actorCandidate.extend({ method: z.literal('explicit-first-person/v1') }).strict(),
  actorCandidate
    .extend({
      method: z.literal('explicit-first-person/v2'),
      speaker: z.string().trim().min(1).max(128).optional(),
    })
    .strict(),
]);
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

/** First-person deixis belongs to its source; missing provenance never identifies a narrator. */
export function fabulaActorLabel(candidate: FabulaActorCandidate): string {
  if (!/^[Яя]$/.test(candidate.label)) return candidate.label;
  if (candidate.method === 'explicit-first-person/v1')
    return 'Автор высказывания («я») · источник не сохранён';
  if (candidate.speaker === 'narrator') return 'Рассказчик («я»)';
  return candidate.speaker
    ? `Автор источника «${candidate.speaker}» («я»)`
    : 'Автор высказывания («я») · источник не указан';
}
