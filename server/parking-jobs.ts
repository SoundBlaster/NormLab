import { randomUUID } from 'node:crypto';
import { mkdirSync, readFileSync, readdirSync, renameSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { z } from 'zod';
import {
  hostedStageResultSchema,
  type HostedStageInput,
  type HostedStageResult,
  type HostedStageTransport,
} from '../shared/hosted-stage.js';
import {
  JOB_MAX_ATTEMPTS,
  JOB_RUN_MS,
  JOB_STAGE_ATTEMPTS,
  parkingJobSchema,
  type ParkingJob,
} from '../shared/parking-job.js';
import { parkingJournalEventSchema, type ParkingJournalEvent } from '../shared/parking-journal.js';
import {
  reviewStatementIssues,
  type ReviewDraft,
  type ReviewStatement,
} from '../shared/parking-review.js';
import { inferenceFailureSchema, type InferenceFailure } from '../shared/inference-failure.js';
import { InferenceAccessError } from './inference-errors.js';
import { checkedHostedStage, hostedStageDigest } from './hosted-stages.js';
import { sourceDigest } from './hosted-extraction.js';
import { MAX_INFERENCE_RESPONSE_BYTES } from './inference-http.js';

const checkpointSchema = z
  .object({
    key: z.string().regex(/^(discovery|classification:([0-9]|[12][0-9]|3[01]))$/),
    file: z.string().uuid(),
    digest: z.string().regex(/^[a-f0-9]{64}$/),
  })
  .strict();
const attemptSchema = z
  .object({
    id: z.string().uuid(),
    key: checkpointSchema.shape.key,
    status: z.enum(['reserved', 'success', 'failed', 'unknown']),
    acknowledged: z.boolean(),
    at: z.string().datetime(),
  })
  .strict();
const stateSchema = parkingJobSchema
  .omit({
    fragments: true,
    completedBatches: true,
    totalBatches: true,
    attempts: true,
    unknowns: true,
  })
  .extend({
    schema: z.literal('normlab.parking-job/v1'),
    checkpoints: z.array(checkpointSchema).max(33),
    attemptLog: z.array(attemptSchema).max(JOB_MAX_ATTEMPTS),
    publishedCount: z.number().int().min(0).max(33),
    events: z.array(parkingJournalEventSchema).max(512),
  })
  .strict();
type JobState = z.infer<typeof stateSchema>;
type Checkpoints = HostedStageResult[];
export class ParkingJobError extends Error {
  constructor(
    message: string,
    readonly status = 400,
  ) {
    super(message);
  }
}
type JobStore = {
  current(draftId: string): ReviewDraft;
  publish(
    draft: ReviewDraft,
    jobId: string,
    fragments: ParkingJob['fragments'],
    statements: ReviewStatement[],
    complete: boolean,
  ): ReviewDraft;
};
const unknownFailure = (failure: InferenceFailure) =>
  ['timeout', 'network', 'unavailable', 'invalid_response'].includes(failure.code);
const keyOf = (input: HostedStageInput) =>
  input.stage === 'discovery' ? 'discovery' : `classification:${input.batchIndex}`;

/** Single process owns jobs. No timers/queues or provider work are attached to browser requests. */
export class ParkingJobs {
  private active?: string;
  constructor(
    private readonly root: string,
    private readonly transport: HostedStageTransport | undefined,
    private readonly store: JobStore,
  ) {}
  get busy() {
    return this.active !== undefined;
  }
  get available() {
    return this.transport !== undefined;
  }
  private folder(draftId: string, jobId: string) {
    return join(
      this.root,
      z.string().uuid().parse(draftId),
      'jobs',
      z.string().uuid().parse(jobId),
    );
  }
  private save(state: JobState) {
    const folder = this.folder(state.draftId, state.jobId);
    mkdirSync(folder, { recursive: true, mode: 0o700 });
    state.updatedAt = new Date().toISOString();
    const file = join(folder, `${randomUUID()}.tmp`);
    writeFileSync(file, JSON.stringify(stateSchema.parse(state)), { flag: 'wx', mode: 0o600 });
    renameSync(file, join(folder, 'job.json'));
  }
  private event(
    state: JobState,
    action: 'started' | 'resumed' | 'checkpoint' | 'paused' | 'conflict' | 'completed',
    stage?: 'discovery' | 'classification',
  ) {
    state.events.push({
      id: randomUUID(),
      at: new Date().toISOString(),
      revisionId: state.revisionId,
      runId: state.jobId,
      kind: 'job-progress',
      action,
      completedBatches: Math.max(0, state.checkpoints.length - 1),
      unknowns: state.attemptLog.filter((a) => a.status === 'unknown' && !a.acknowledged).length,
      ...(stage ? { stage } : {}),
      ...(state.reason ? { reason: state.reason } : {}),
      ...(state.failure ? { failure: state.failure } : {}),
    });
  }
  private pause(
    state: JobState,
    reason: NonNullable<ParkingJob['reason']>,
    failure?: InferenceFailure,
  ) {
    for (const attempt of state.attemptLog)
      if (attempt.status === 'reserved') attempt.status = 'unknown';
    state.status = reason === 'revision' ? 'conflict' : 'paused';
    state.reason = reason;
    state.failure = failure;
    this.event(state, state.status === 'conflict' ? 'conflict' : 'paused');
    this.save(state);
  }
  private read(draftId: string, jobId: string) {
    const state = stateSchema.parse(
      JSON.parse(readFileSync(join(this.folder(draftId, jobId), 'job.json'), 'utf8')),
    );
    if (state.draftId !== draftId || state.jobId !== jobId)
      throw new ParkingJobError('Неверная привязка задания.', 409);
    if (state.status === 'running' && this.active !== jobId) {
      for (const attempt of state.attemptLog)
        if (attempt.status === 'reserved') attempt.status = 'unknown';
      this.pause(state, 'restart');
    }
    return state;
  }
  private select(state: JobState) {
    const parent = join(this.root, state.draftId, 'jobs');
    const file = join(parent, `${randomUUID()}.tmp`);
    writeFileSync(file, JSON.stringify(state.jobId), { flag: 'wx', mode: 0o600 });
    renameSync(file, join(parent, 'current.json'));
  }
  private current(state: JobState) {
    const draft = this.store.current(state.draftId);
    if (draft.revisionId !== state.revisionId || draft.sourceDigest !== state.sourceDigest)
      throw new ParkingJobError('Ревизия изменена. Правки не заменены.', 409);
    return draft;
  }
  private input(state: JobState, draft: ReviewDraft, checkpoints: Checkpoints): HostedStageInput {
    if (!state.profile) throw new Error('Missing profile.');
    const binding = {
      narrative: draft.narrative,
      sourceDigest: state.sourceDigest,
      configDigest: state.profile.configDigest,
    };
    const discovery = checkpoints[0];
    if (!discovery) return { ...binding, stage: 'discovery' };
    if (discovery.stage !== 'discovery') throw new Error('Missing discovery checkpoint.');
    const batchIndex = checkpoints.length - 1;
    return checkedHostedStage({
      ...binding,
      stage: 'classification',
      batchIndex,
      fragments: discovery.fragments.slice(batchIndex * 8, (batchIndex + 1) * 8),
    });
  }
  private validate(raw: unknown, input: HostedStageInput) {
    const result = hostedStageResultSchema.parse(raw);
    if (
      result.sourceDigest !== input.sourceDigest ||
      result.configDigest !== input.configDigest ||
      result.inputDigest !== hostedStageDigest(input) ||
      result.stage !== input.stage
    )
      throw new Error('Checkpoint binding mismatch.');
    if (result.stage === 'discovery') {
      if (
        new Set(result.fragments.map((f) => JSON.stringify([f.quote, f.attributes]))).size !==
        result.fragments.length
      )
        throw new Error('Duplicate discovery fragments.');
      for (let i = 0; i < result.fragments.length; i += 8)
        checkedHostedStage({
          ...input,
          stage: 'classification',
          batchIndex: i / 8,
          fragments: result.fragments.slice(i, i + 8),
        });
    } else {
      if (input.stage !== 'classification' || result.batchIndex !== input.batchIndex)
        throw new Error('Checkpoint batch mismatch.');
      if (new Set(result.statements.map((s) => s.id)).size !== result.statements.length)
        throw new Error('Duplicate statement IDs.');
      for (const statement of result.statements) {
        if (
          statement.origin !== 'model' ||
          statement.decision !== 'pending' ||
          reviewStatementIssues(statement, input.narrative).length ||
          !input.fragments.some(
            (f) =>
              f.quote === statement.quote &&
              f.startOffset === statement.startOffset &&
              f.endOffset === statement.endOffset &&
              f.attributes.subject === statement.subject &&
              f.attributes.speaker === statement.speaker &&
              f.attributes.aboutEpisode === statement.aboutEpisode,
          )
        )
          throw new Error('Invalid checkpoint statement.');
      }
    }
    return result;
  }
  private checkpoints(state: JobState, draft: ReviewDraft) {
    const results: Checkpoints = [];
    for (const ref of state.checkpoints) {
      const file = join(this.folder(state.draftId, state.jobId), `${ref.file}.json`);
      if (statSync(file).size > MAX_INFERENCE_RESPONSE_BYTES)
        throw new Error('Oversized checkpoint.');
      const bytes = readFileSync(file, 'utf8');
      if (sourceDigest(bytes) !== ref.digest) throw new Error('Corrupt checkpoint.');
      const input = this.input(state, draft, results);
      if (keyOf(input) !== ref.key) throw new Error('Checkpoint order mismatch.');
      results.push(this.validate(JSON.parse(bytes), input));
    }
    return results;
  }
  private summary(state: JobState, checkpoints: Checkpoints): ParkingJob {
    const discovery = checkpoints[0];
    const fragments = discovery?.stage === 'discovery' ? discovery.fragments : [];
    return parkingJobSchema.parse({
      ...Object.fromEntries(
        Object.entries(state).filter(
          ([key]) =>
            !['schema', 'checkpoints', 'attemptLog', 'publishedCount', 'events'].includes(key),
        ),
      ),
      fragments,
      completedBatches: Math.max(0, checkpoints.length - 1),
      totalBatches: Math.ceil(fragments.length / 8),
      attempts: state.attemptLog.length,
      unknowns: state.attemptLog.filter((a) => a.status === 'unknown' && !a.acknowledged).length,
    });
  }
  latest(draftId: string): ParkingJob | null {
    const parent = join(this.root, z.string().uuid().parse(draftId), 'jobs');
    let id: string;
    try {
      id = z
        .string()
        .uuid()
        .parse(JSON.parse(readFileSync(join(parent, 'current.json'), 'utf8')));
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return null;
      throw error;
    }
    const state = this.read(draftId, id);
    try {
      return this.summary(state, this.checkpoints(state, this.store.current(draftId)));
    } catch {
      if (state.status !== 'running' && state.reason !== 'storage') this.pause(state, 'storage');
      return this.summary(state, []);
    }
  }
  journal(draftId: string): ParkingJournalEvent[] {
    const parent = join(this.root, z.string().uuid().parse(draftId), 'jobs');
    try {
      return readdirSync(parent)
        .filter((id) => z.string().uuid().safeParse(id).success)
        .flatMap((id) => this.read(draftId, id).events);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
      throw error;
    }
  }
  start(draft: ReviewDraft) {
    if (!this.transport) throw new ParkingJobError('Поэтапный разбор не настроен.');
    if (this.busy) throw new ParkingJobError('Другой разбор уже выполняется.', 409);
    const state: JobState = {
      schema: 'normlab.parking-job/v1',
      jobId: randomUUID(),
      draftId: draft.draftId,
      revisionId: draft.revisionId,
      sourceDigest: draft.sourceDigest,
      status: 'running',
      startedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      profile: null,
      checkpoints: [],
      attemptLog: [],
      publishedCount: 0,
      events: [],
    };
    this.event(state, 'started');
    this.save(state);
    this.select(state);
    this.launch(state);
    return this.summary(state, []);
  }
  resume(draft: ReviewDraft, jobId: string, acknowledgeUnknown = false, replaceStatements = false) {
    if (!this.transport) throw new ParkingJobError('Поэтапный разбор не настроен.');
    if (this.busy) throw new ParkingJobError('Другой разбор уже выполняется.', 409);
    const state = this.read(draft.draftId, jobId);
    if (state.status === 'completed') throw new ParkingJobError('Разбор уже завершён.');
    if (state.events.length >= 450)
      throw new ParkingJobError('Лимит продолжений исчерпан. Создайте новый разбор.');
    if (draft.sourceDigest !== state.sourceDigest)
      throw new ParkingJobError('Источник изменён. Создайте новый разбор.', 409);
    if (state.revisionId !== draft.revisionId) {
      if (!replaceStatements)
        throw new ParkingJobError('Подтвердите замену ручных правок предложениями задания.', 409);
      state.revisionId = draft.revisionId;
      state.publishedCount = 0;
    }
    if (
      state.attemptLog.some((a) => a.status === 'unknown' && !a.acknowledged) &&
      !acknowledgeUnknown
    )
      throw new ParkingJobError('Подтвердите возможную повторную оплату неизвестного исхода.');
    const checkpoints = this.checkpoints(state, draft);
    if (acknowledgeUnknown)
      for (const attempt of state.attemptLog)
        if (attempt.status === 'unknown') attempt.acknowledged = true;
    state.status = 'running';
    state.reason = undefined;
    state.failure = undefined;
    this.event(state, 'resumed');
    this.save(state);
    this.select(state);
    this.launch(state);
    return this.summary(state, checkpoints);
  }
  private launch(state: JobState) {
    this.active = state.jobId;
    void this.run(state)
      .catch(() => {
        // Failed persistence leaves a durable reservation/old state; read() exposes restart/unknown.
        try {
          this.pause(state, 'storage');
        } catch {
          /* Storage remains unavailable. */
        }
      })
      .finally(() => {
        this.active = undefined;
      });
  }
  private async run(state: JobState) {
    const transport = this.transport;
    if (!transport) throw new ParkingJobError('Поэтапный разбор не настроен.');
    const signal = AbortSignal.timeout(JOB_RUN_MS);
    let checkpoints: Checkpoints = [];
    try {
      const profile = await transport.profile(
        AbortSignal.any([signal, AbortSignal.timeout(10000)]),
      );
      if (state.profile && profile.configDigest !== state.profile.configDigest) {
        this.pause(state, 'configuration');
        return;
      }
      state.profile = profile;
      this.save(state);
      checkpoints = this.checkpoints(state, this.current(state));
      for (;;) {
        signal.throwIfAborted();
        let draft = this.current(state);
        const discovery = checkpoints[0];
        const complete =
          discovery?.stage === 'discovery' &&
          checkpoints.length - 1 === Math.ceil(discovery.fragments.length / 8);
        if (checkpoints.length > state.publishedCount) {
          if (discovery?.stage !== 'discovery') throw new Error('Discovery missing.');
          const statements = checkpoints.flatMap((c) =>
            c.stage === 'classification' ? c.statements : [],
          );
          if (
            statements.length > 256 ||
            new Set(statements.map((s) => s.id)).size !== statements.length
          )
            throw new Error('Statement limit.');
          draft = this.store.publish(draft, state.jobId, discovery.fragments, statements, complete);
          state.revisionId = draft.revisionId;
          state.publishedCount = checkpoints.length;
          this.save(state);
        }
        if (complete) {
          state.status = 'completed';
          this.event(state, 'completed');
          this.save(state);
          return;
        }
        const input = this.input(state, draft, checkpoints);
        const key = keyOf(input);
        if (
          state.attemptLog.length >= JOB_MAX_ATTEMPTS ||
          state.attemptLog.filter((a) => a.key === key).length >= JOB_STAGE_ATTEMPTS
        ) {
          this.pause(state, 'attempt-limit');
          return;
        }
        const attempt: z.infer<typeof attemptSchema> = {
          id: randomUUID(),
          key,
          status: 'reserved',
          acknowledged: false,
          at: new Date().toISOString(),
        };
        state.attemptLog.push(attempt);
        this.save(state); // Reserve durably before dispatch; no hidden retries.
        let result: HostedStageResult;
        try {
          result = this.validate(await transport.execute(input, signal), input);
          const statements = [...checkpoints, result].flatMap((c) =>
            c.stage === 'classification' ? c.statements : [],
          );
          if (
            statements.length > 256 ||
            new Set(statements.map((s) => s.id)).size !== statements.length
          )
            throw new Error('Combined statement limit or duplicate IDs.');
        } catch (error) {
          const failure: InferenceFailure =
            error instanceof InferenceAccessError
              ? error.failure
              : { provider: 'gateway', stage: input.stage, code: 'invalid_response' };
          attempt.status = unknownFailure(failure) ? 'unknown' : 'failed';
          this.pause(state, 'failure', failure);
          return;
        }
        const file = randomUUID();
        const bytes = JSON.stringify(result);
        if (Buffer.byteLength(bytes) > MAX_INFERENCE_RESPONSE_BYTES)
          throw new Error('Oversized checkpoint.');
        writeFileSync(join(this.folder(state.draftId, state.jobId), `${file}.json`), bytes, {
          flag: 'wx',
          mode: 0o600,
        });
        state.checkpoints.push({ key, file, digest: sourceDigest(bytes) });
        attempt.status = 'success';
        this.event(state, 'checkpoint', input.stage);
        this.save(state); // Commit reference before publication or dependent dispatch.
        checkpoints.push(result);
      }
    } catch (error) {
      if (error instanceof ParkingJobError && error.status === 409) this.pause(state, 'revision');
      else if (error instanceof InferenceAccessError)
        this.pause(state, 'failure', inferenceFailureSchema.parse(error.failure));
      else if (signal.aborted) this.pause(state, 'limit');
      else this.pause(state, 'storage');
    }
  }
}
