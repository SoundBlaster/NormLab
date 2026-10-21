import { z } from 'zod';
import { reviewStatementSchema } from './parking-review.js';

const hash = z.string().regex(/^[a-f0-9]{64}$/);
export const hostedAttributesSchema = z
  .object({
    subject: z
      .string()
      .regex(/^(vehicle|person)_[1-9][0-9]*$/)
      .max(128),
    aboutEpisode: z
      .string()
      .regex(/^episode_[1-9][0-9]*$/)
      .max(128),
    speaker: z.string().trim().min(1).max(128),
  })
  .strict();
export const hostedFragmentSchema = z
  .object({
    fragmentId: z.string().regex(/^fragment_([1-9][0-9]{0,2})$/),
    quote: z.string().min(1).max(2048),
    attributes: hostedAttributesSchema,
    startOffset: z.number().int().min(0).max(8000),
    endOffset: z.number().int().min(1).max(8000),
  })
  .strict();
export type HostedFragment = z.infer<typeof hostedFragmentSchema>;

export const hostedProfileSchema = z
  .object({
    protocol: z.literal('normlab.hosted-stage/v1'),
    configDigest: hash,
    classifier: z.enum(['openai', 'typesafe', 'decisions']),
    discoveryModel: z.string().min(1).max(200),
    classificationModel: z.string().min(1).max(200),
    batchSize: z.literal(8),
    maxFragments: z.literal(256),
  })
  .strict();
export type HostedProfile = z.infer<typeof hostedProfileSchema>;
const binding = {
  narrative: z.string().min(1).max(8000),
  sourceDigest: hash,
  configDigest: hash,
};
export const hostedStageInputSchema = z.discriminatedUnion('stage', [
  z.object({ ...binding, stage: z.literal('discovery') }).strict(),
  z
    .object({
      ...binding,
      stage: z.literal('classification'),
      batchIndex: z.number().int().min(0).max(31),
      fragments: z.array(hostedFragmentSchema).min(1).max(8),
    })
    .strict(),
]);
export type HostedStageInput = z.infer<typeof hostedStageInputSchema>;
const resultBinding = {
  protocol: z.literal('normlab.hosted-stage/v1'),
  inputDigest: hash,
  sourceDigest: hash,
  configDigest: hash,
  // Private provider evidence; never forwarded to journal/status UI.
  calls: z.array(z.unknown()).length(1),
};
export const hostedStageResultSchema = z.discriminatedUnion('stage', [
  z
    .object({
      ...resultBinding,
      stage: z.literal('discovery'),
      fragments: z.array(hostedFragmentSchema).min(1).max(256),
    })
    .strict(),
  z
    .object({
      ...resultBinding,
      stage: z.literal('classification'),
      batchIndex: z.number().int().min(0).max(31),
      statements: z.array(reviewStatementSchema).max(256),
      decisions: z.array(z.unknown()).max(120),
    })
    .strict(),
]);
export type HostedStageResult = z.infer<typeof hostedStageResultSchema>;

export interface HostedStageTransport {
  profile(signal: AbortSignal): Promise<HostedProfile>;
  execute(input: HostedStageInput, signal: AbortSignal): Promise<HostedStageResult>;
}
