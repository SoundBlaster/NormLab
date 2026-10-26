import { z } from 'zod';
import { inferenceFailureSchema } from './inference-failure.js';
import { jobReasonSchema } from './parking-job.js';

const runBase = z.object({
  runId: z.string().uuid(),
  revisionId: z.string().uuid(),
  startedAt: z.string().datetime(),
});
export const parkingRunSchema = z.discriminatedUnion('status', [
  runBase.extend({ status: z.literal('running') }).strict(),
  runBase
    .extend({
      status: z.literal('completed'),
      finishedAt: z.string().datetime(),
      statementCount: z.number().int().min(0).max(256),
    })
    .strict(),
  runBase
    .extend({
      status: z.literal('failed'),
      finishedAt: z.string().datetime(),
      failure: inferenceFailureSchema,
    })
    .strict(),
  runBase.extend({ status: z.literal('conflict'), finishedAt: z.string().datetime() }).strict(),
]);
export type ParkingRun = z.infer<typeof parkingRunSchema>;
const eventBase = z.object({
  id: z.string(),
  at: z.string().datetime(),
  revisionId: z.string().uuid(),
  revision: z.number().int().positive().optional(),
  runId: z.string().uuid().optional(),
});
export const parkingJournalEventSchema = z.discriminatedUnion('kind', [
  eventBase
    .extend({
      kind: z.literal('actor-interpretation'),
      decision: z.enum(['confirmed', 'rejected']),
    })
    .strict(),
  eventBase
    .extend({
      kind: z.literal('legal-proposal'),
      action: z.enum(['started', 'running', 'completed', 'failed', 'conflict', 'interrupted']),
      durationMs: z.number().nonnegative().optional(),
      failure: inferenceFailureSchema.optional(),
    })
    .strict(),
  eventBase
    .extend({
      kind: z.literal('context-proposal'),
      action: z.enum(['started', 'running', 'completed', 'failed', 'conflict', 'interrupted']),
      durationMs: z.number().nonnegative().optional(),
      failure: inferenceFailureSchema.optional(),
    })
    .strict(),
  eventBase
    .extend({ kind: z.literal('legal-assessment'), action: z.enum(['saved', 'calculated']) })
    .strict(),
  eventBase
    .extend({
      kind: z.literal('job-progress'),
      action: z.enum(['started', 'resumed', 'checkpoint', 'paused', 'conflict', 'completed']),
      stage: z.enum(['discovery', 'classification']).optional(),
      reason: jobReasonSchema.optional(),
      failure: inferenceFailureSchema.optional(),
      completedBatches: z.number().int().min(0).max(32),
      unknowns: z.number().int().min(0).max(99),
    })
    .strict(),
  eventBase
    .extend({
      kind: z.enum(['draft-created', 'review-saved', 'review-completed', 'model-applied']),
      statementCount: z.number().int().min(0).max(256),
      confirmed: z.number().int().min(0).max(256),
      rejected: z.number().int().min(0).max(256),
    })
    .strict(),
  eventBase.extend({ kind: z.literal('extraction-started') }).strict(),
  eventBase.extend({ kind: z.literal('extraction-running') }).strict(),
  eventBase
    .extend({
      kind: z.literal('extraction-completed'),
      durationMs: z.number().nonnegative(),
      statementCount: z.number().int().min(0).max(256),
    })
    .strict(),
  eventBase
    .extend({
      kind: z.literal('extraction-failed'),
      durationMs: z.number().nonnegative(),
      failure: inferenceFailureSchema,
    })
    .strict(),
  eventBase.extend({ kind: z.enum(['extraction-interrupted', 'extraction-conflict']) }).strict(),
]);
export type ParkingJournalEvent = z.infer<typeof parkingJournalEventSchema>;
export const parkingJournalSchema = z
  .object({
    events: z.array(parkingJournalEventSchema).max(100),
    total: z.number().int().nonnegative(),
  })
  .strict();
export type ParkingJournal = z.infer<typeof parkingJournalSchema>;
