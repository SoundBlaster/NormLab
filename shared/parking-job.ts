import { z } from 'zod';
import { hostedFragmentSchema, hostedProfileSchema } from './hosted-stage.js';
import { inferenceFailureSchema } from './inference-failure.js';

export const JOB_MAX_ATTEMPTS = 99;
export const JOB_STAGE_ATTEMPTS = 3;
export const JOB_RUN_MS = 300000;
export const jobReasonSchema = z.enum([
  'failure',
  'restart',
  'configuration',
  'revision',
  'limit',
  'attempt-limit',
  'storage',
]);
export const parkingJobSchema = z
  .object({
    jobId: z.string().uuid(),
    draftId: z.string().uuid(),
    revisionId: z.string().uuid(),
    sourceDigest: z.string().regex(/^[a-f0-9]{64}$/),
    status: z.enum(['running', 'paused', 'conflict', 'completed']),
    reason: jobReasonSchema.optional(),
    failure: inferenceFailureSchema.optional(),
    startedAt: z.string().datetime(),
    updatedAt: z.string().datetime(),
    profile: hostedProfileSchema.nullable(),
    fragments: z.array(hostedFragmentSchema).max(256),
    completedBatches: z.number().int().min(0).max(32),
    totalBatches: z.number().int().min(0).max(32),
    attempts: z.number().int().min(0).max(JOB_MAX_ATTEMPTS),
    unknowns: z.number().int().min(0).max(JOB_MAX_ATTEMPTS),
  })
  .strict();
export type ParkingJob = z.infer<typeof parkingJobSchema>;
export const parkingJobInputSchema = z
  .object({
    draftId: z.string().uuid(),
    expectedRevisionId: z.string().uuid(),
    jobId: z.string().uuid().optional(),
    replaceStatements: z.boolean().optional(),
    acknowledgeUnknown: z.boolean().optional(),
  })
  .strict();
