import { createHash, randomUUID } from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  writeFileSync,
  renameSync,
} from 'node:fs';
import { join, resolve } from 'node:path';
import { z } from 'zod';
import {
  HOSTED_DECISIONS_PIPELINE,
  HOSTED_MAX_NARRATIVE,
  HOSTED_PIPELINE,
} from './hosted-extraction.js';
import type { ParkingExtractor } from './inference-client.js';
import { InferenceAccessError, inferenceFailureMessage } from './inference-errors.js';
import {
  emptyReviewChecklist,
  reviewChecklistSchema,
  reviewDraftSchema,
  reviewStatementSchema,
  reviewStatementIssues,
  reviewDraftMetadata,
  type ReviewDraft,
  type ReviewStatement,
} from '../shared/parking-review.js';
import {
  emptyNarrativeContext,
  narrativeContextSchema,
  narrativeRoute,
  reviewMetadataIssues,
  vehicleHypothesisSchema,
} from '../shared/parking-context.js';
import { reviseReviewMetadata } from './parking-review-metadata.js';
import { extractionJournal, revisionJournal, saveParkingRun } from './parking-journal.js';
import type { ParkingRun } from '../shared/parking-journal.js';
import { ParkingJobs } from './parking-jobs.js';
import { parkingJobInputSchema } from '../shared/parking-job.js';

const digest = (text: string) => createHash('sha256').update(text).digest('hex');
export class ParkingReviewError extends Error {
  constructor(
    message: string,
    readonly status = 400,
  ) {
    super(message);
  }
}
const createInput = z
  .object({
    narrative: z.string().min(1).max(32768),
    previousDraftId: z.string().uuid().optional(),
  })
  .strict();
const updateInput = z
  .object({
    draftId: z.string().uuid(),
    expectedRevisionId: z.string().uuid(),
    statements: z.array(reviewStatementSchema).max(256),
    checklist: reviewChecklistSchema,
    finishReview: z.boolean(),
    context: narrativeContextSchema.optional(),
    hypotheses: z.array(vehicleHypothesisSchema).max(64).optional(),
  })
  .strict();
const extractInput = z
  .object({
    draftId: z.string().uuid(),
    expectedRevisionId: z.string().uuid(),
    replaceStatements: z.boolean().optional(),
  })
  .strict();

export class ParkingReview {
  private readonly root: string;
  private extracting = false;
  private activeRunId?: string;
  private readonly jobs: ParkingJobs;
  constructor(
    dataDir: string,
    private readonly extractor?: ParkingExtractor | null,
  ) {
    this.root = join(dataDir, 'parking-review');
    mkdirSync(this.root, { recursive: true, mode: 0o700 });
    this.jobs = new ParkingJobs(this.root, extractor?.stages, {
      current: (id) => this.current(id),
      publish: (draft, jobId, fragments, statements, complete) => {
        this.expected(draft.draftId, draft.revisionId);
        const metadata = reviewDraftMetadata(draft);
        return this.revise(draft, {
          originalExtraction: {
            schema: 'normlab.parking-job-proposal/v1',
            jobId,
            sourceDigest: draft.sourceDigest,
            fragments,
            complete,
            reviewState: 'unreviewed',
          },
          statements,
          hypotheses: metadata.hypotheses.map((item) => ({
            ...item,
            decision: 'pending' as const,
          })),
          checklist: { ...emptyReviewChecklist },
          status: 'draft',
        });
      },
    });
  }
  private folder(id: string) {
    return join(this.root, z.string().uuid().parse(id));
  }
  private current(id: string): ReviewDraft {
    const folder = this.folder(id);
    const revisionId = z
      .string()
      .uuid()
      .parse(JSON.parse(readFileSync(join(folder, 'current.json'), 'utf8')));
    return reviewDraftSchema.parse(
      JSON.parse(readFileSync(join(folder, `${revisionId}.json`), 'utf8')),
    );
  }
  private expected(id: string, revision: string) {
    const draft = this.current(id);
    if (draft.revisionId !== revision)
      throw new ParkingReviewError('Черновик изменился. Обновите страницу.', 409);
    return draft;
  }
  private save(draft: ReviewDraft) {
    const folder = this.folder(draft.draftId);
    mkdirSync(folder, { recursive: true, mode: 0o700 });
    writeFileSync(join(folder, `${draft.revisionId}.json`), JSON.stringify(draft), {
      flag: 'wx',
      mode: 0o600,
    });
    const pointer = join(folder, `${randomUUID()}.tmp`);
    writeFileSync(pointer, JSON.stringify(draft.revisionId), { flag: 'wx', mode: 0o600 });
    renameSync(pointer, join(folder, 'current.json'));
    return draft;
  }
  private revise(draft: ReviewDraft, changes: Partial<ReviewDraft>) {
    return this.save({
      ...draft,
      ...reviewDraftMetadata(draft),
      ...changes,
      schema: 'normlab.parking-review/v2',
      revisionId: randomUUID(),
      revision: draft.revision + 1,
      createdAt: new Date().toISOString(),
    });
  }
  private history(id: string): ReviewDraft[] {
    return readdirSync(this.folder(id))
      .filter((name) => name.endsWith('.json') && name !== 'current.json')
      .map((name) =>
        reviewDraftSchema.parse(JSON.parse(readFileSync(join(this.folder(id), name), 'utf8'))),
      )
      .sort((a, b) => b.revision - a.revision);
  }
  async handle(method: string, path: string, body?: unknown) {
    if (method === 'GET' && path === '/api/parking/bootstrap') {
      const drafts = readdirSync(this.root, { withFileTypes: true })
        .filter((entry) => entry.isDirectory())
        .map((entry) => this.current(entry.name))
        .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
      return {
        drafts,
        externalInference: Boolean(this.extractor),
        stagedInference: this.jobs.available,
        extractorAvailable:
          Boolean(this.extractor) ||
          (this.extractor === undefined &&
            existsSync(resolve('.tools/parking-evaluation/bin/python'))),
        cases: ['P01', 'P02', 'P04', 'P09'].map((id) => ({
          id,
          narrative: readFileSync(
            resolve(`fixtures/parking-pilot/reference/${id}.source.txt`),
            'utf8',
          ),
        })),
      };
    }
    if (method === 'GET' && path.startsWith('/api/parking/history/')) {
      const id = z.string().uuid().parse(path.slice('/api/parking/history/'.length));
      return this.history(id);
    }
    if (method === 'GET' && path.startsWith('/api/parking/journal/')) {
      const id = z.string().uuid().parse(path.slice('/api/parking/journal/'.length));
      this.current(id);
      const events = [
        ...revisionJournal(this.history(id)),
        ...extractionJournal(this.folder(id), this.activeRunId),
        ...(this.jobs?.journal(id) ?? []),
      ]
        .map((event, order) => ({ event, order }))
        .sort((a, b) => b.event.at.localeCompare(a.event.at) || b.order - a.order)
        .map(({ event }) => event);
      return { events: events.slice(0, 100), total: events.length };
    }
    if (method === 'GET' && path.startsWith('/api/parking/job/')) {
      const id = z.string().uuid().parse(path.slice('/api/parking/job/'.length));
      const job = this.jobs?.latest(id) ?? null;
      return { job, draft: this.current(id) };
    }
    if (method === 'POST' && path === '/api/parking/jobs') {
      const input = parkingJobInputSchema.parse(body);
      const draft = this.expected(input.draftId, input.expectedRevisionId);
      if (!this.jobs.available) throw new ParkingReviewError('Поэтапный разбор не настроен.');
      if (this.extracting) throw new ParkingReviewError('Извлечение уже выполняется.');
      const metadata = reviewDraftMetadata(draft);
      if (
        metadata.context.decision !== 'confirmed' ||
        narrativeRoute(metadata.context) !== 'parking-review'
      )
        throw new ParkingReviewError(
          'Сначала сохраните и подтвердите контекст парковочного эпизода.',
        );
      if (draft.narrative.length > HOSTED_MAX_NARRATIVE)
        throw new ParkingReviewError(
          `Внешнее извлечение принимает фабулу до ${HOSTED_MAX_NARRATIVE} символов.`,
        );
      if (input.jobId)
        return this.jobs.resume(
          draft,
          input.jobId,
          input.acknowledgeUnknown,
          input.replaceStatements,
        );
      if (draft.statements.length && !input.replaceStatements)
        throw new ParkingReviewError(
          'Подтвердите замену текущей разметки. Прежняя ревизия останется в истории.',
        );
      return this.jobs.start(draft);
    }
    if (method === 'POST' && path === '/api/parking/drafts') {
      const input = createInput.parse(body);
      if (input.previousDraftId) this.current(input.previousDraftId);
      return this.save({
        schema: 'normlab.parking-review/v2',
        draftId: randomUUID(),
        revisionId: randomUUID(),
        revision: 1,
        previousDraftId: input.previousDraftId ?? null,
        createdAt: new Date().toISOString(),
        narrative: input.narrative,
        sourceDigest: digest(input.narrative),
        originalExtraction: null,
        statements: [],
        context: emptyNarrativeContext(),
        hypotheses: [],
        checklist: { ...emptyReviewChecklist },
        status: 'draft',
      });
    }
    if (method === 'POST' && path === '/api/parking/review') {
      const input = updateInput.parse(body);
      const draft = this.expected(input.draftId, input.expectedRevisionId);
      const priorMetadata = reviewDraftMetadata(draft);
      let metadata;
      try {
        metadata = reviseReviewMetadata(
          priorMetadata,
          {
            context: input.context ?? priorMetadata.context,
            hypotheses: input.hypotheses ?? priorMetadata.hypotheses,
          },
          draft.narrative,
        );
      } catch (error) {
        throw new ParkingReviewError(error instanceof Error ? error.message : 'Ошибка метаданных.');
      }
      if (new Set(input.statements.map((s) => s.id)).size !== input.statements.length)
        throw new ParkingReviewError('Повторяются IDs утверждений.');
      let statementsChanged = false;
      const statements = input.statements.map((statement) => {
        const prior = draft.statements.find((s) => s.id === statement.id);
        const changed =
          !prior ||
          [
            'predicate',
            'stance',
            'subject',
            'speaker',
            'aboutEpisode',
            'valueText',
            'quote',
            'startOffset',
            'endOffset',
          ].some(
            (key) =>
              statement[key as keyof ReviewStatement] !== prior[key as keyof ReviewStatement],
          );
        statementsChanged ||= changed;
        // A content edit must be saved before it can be confirmed in a subsequent revision.
        const result = {
          ...statement,
          origin: changed ? ('human' as const) : prior.origin,
          decision: changed || metadata.changed ? ('pending' as const) : statement.decision,
        };
        const issues = reviewStatementIssues(result, draft.narrative);
        if (issues.length) throw new ParkingReviewError(issues.join(' '));
        return result;
      });
      // Preserve rejected statements as audit records; removal is an explicit rejection.
      if (draft.statements.some((s) => !statements.some((next) => next.id === s.id)))
        throw new ParkingReviewError(
          'Отклоните утверждение с причиной вместо удаления из истории.',
        );
      const contentChanged = statements.some(
        (s) => s.origin === 'human' && s.decision === 'pending',
      );
      const checklistChanged = JSON.stringify(input.checklist) !== JSON.stringify(draft.checklist);
      const checklist =
        contentChanged || metadata.changed ? { ...emptyReviewChecklist } : input.checklist;
      const metadataIssues = reviewMetadataIssues(metadata.context, metadata.hypotheses);
      if (input.finishReview && metadataIssues.length)
        throw new ParkingReviewError(metadataIssues.join(' '));
      if (
        input.finishReview &&
        (!statements.length ||
          statements.some((s) => s.decision === 'pending') ||
          !Object.values(checklist).every(Boolean))
      )
        throw new ParkingReviewError(
          'Подтвердите или отклоните каждое утверждение и выполните checklist.',
        );
      return this.revise(draft, {
        statements,
        context: metadata.context,
        hypotheses: metadata.hypotheses,
        checklist,
        status:
          input.finishReview ||
          (draft.status === 'reviewed' &&
            !statementsChanged &&
            !checklistChanged &&
            !metadata.changed &&
            !metadataIssues.length &&
            statements.every((s) => s.decision !== 'pending'))
            ? 'reviewed'
            : 'draft',
      });
    }
    if (method === 'POST' && path === '/api/parking/extract') {
      const input = extractInput.parse(body);
      const draft = this.expected(input.draftId, input.expectedRevisionId);
      if (this.extracting || this.jobs?.busy)
        throw new ParkingReviewError('Извлечение уже выполняется.');
      if (draft.statements.length && !input.replaceStatements)
        throw new ParkingReviewError(
          'Подтвердите замену текущей разметки новым авторазбором. Прежняя ревизия останется в истории.',
        );
      if (
        this.extractor === null ||
        (!this.extractor && !existsSync(resolve('.tools/parking-evaluation/bin/python')))
      )
        throw new ParkingReviewError('Извлечение не настроено. Ручная разметка доступна.');
      // Rejected before any provider call or quota use.
      if (this.extractor && draft.narrative.length > HOSTED_MAX_NARRATIVE)
        throw new ParkingReviewError(
          `Внешнее извлечение принимает фабулу до ${HOSTED_MAX_NARRATIVE} символов. Ручная разметка доступна.`,
        );
      const metadata = reviewDraftMetadata(draft);
      if (
        metadata.context.decision !== 'confirmed' ||
        narrativeRoute(metadata.context) !== 'parking-review'
      )
        throw new ParkingReviewError(
          'Сначала сохраните и подтвердите контекст парковочного эпизода.',
        );
      const runId = randomUUID();
      const run = { runId, revisionId: draft.revisionId, startedAt: new Date().toISOString() };
      const folder = join(this.folder(draft.draftId), `extraction-${runId}`);
      mkdirSync(folder, { mode: 0o700 });
      writeFileSync(
        join(folder, 'input.json'),
        JSON.stringify({ narrative: draft.narrative, sourceDigest: draft.sourceDigest }),
        { mode: 0o600 },
      );
      saveParkingRun(folder, { ...run, status: 'running' });
      // A missing final record is explicitly displayed as unknown, never as success.
      const finish = (outcome: ParkingRun) => {
        try {
          saveParkingRun(folder, outcome);
        } catch {
          /* Leave the durable start visible as an interrupted/unknown run. */
        }
      };
      this.extracting = true;
      this.activeRunId = runId;
      try {
        let raw: unknown;
        if (this.extractor) {
          raw = await this.extractor({
            narrative: draft.narrative,
            sourceDigest: draft.sourceDigest,
          });
          writeFileSync(join(folder, 'output.json'), JSON.stringify(raw), {
            flag: 'wx',
            mode: 0o600,
          });
        } else {
          await promisify(execFile)(
            resolve('.tools/parking-evaluation/bin/python'),
            [
              resolve('evaluation/two_stage_v3.py'),
              join(folder, 'input.json'),
              join(folder, 'output.json'),
            ],
            { timeout: 420000, maxBuffer: 4 * 1024 * 1024 },
          );
          raw = JSON.parse(readFileSync(join(folder, 'output.json'), 'utf8')) as unknown;
        }
        const result = z
          .object({
            pipeline: this.extractor
              ? z.enum([HOSTED_PIPELINE, HOSTED_DECISIONS_PIPELINE])
              : z.literal('literal-discovery-then-classification/v3'),
            statements: z.array(reviewStatementSchema).max(256),
            sourceDigest: z.string(),
          })
          .passthrough()
          .parse(raw);
        if (result.sourceDigest !== draft.sourceDigest)
          throw new ParkingReviewError('Source binding изменился.');
        for (const statement of result.statements) {
          if (statement.origin !== 'model' || statement.decision !== 'pending')
            throw new ParkingReviewError('Предложение модели требует проверки человеком.');
          if (reviewStatementIssues(statement, draft.narrative).length)
            throw new ParkingReviewError('Extractor вернул неверную цитату.');
        }
        this.expected(input.draftId, input.expectedRevisionId);
        const saved = this.revise(draft, {
          originalExtraction: raw,
          statements: result.statements,
          hypotheses: metadata.hypotheses.map((item) => ({
            ...item,
            decision: 'pending' as const,
          })),
          checklist: { ...emptyReviewChecklist },
          status: 'draft',
        });
        finish({
          ...run,
          status: 'completed',
          finishedAt: new Date().toISOString(),
          statementCount: result.statements.length,
        });
        return saved;
      } catch (error) {
        const finishedAt = new Date().toISOString();
        if (error instanceof ParkingReviewError && error.status === 409) {
          finish({ ...run, status: 'conflict', finishedAt });
          throw error;
        }
        const failure =
          error instanceof InferenceAccessError
            ? error.failure
            : {
                code: 'invalid_response' as const,
                provider: 'gateway' as const,
                stage: 'extraction' as const,
              };
        finish({ ...run, status: 'failed', finishedAt, failure });
        if (error instanceof ParkingReviewError) throw error;
        const unknown = ['network', 'timeout', 'unavailable'].includes(failure.code)
          ? ' Исход запроса не подтверждён: сервис мог выполнить его и списать средства. Повтор запустит весь разбор заново.'
          : '';
        throw new ParkingReviewError(
          `${inferenceFailureMessage(failure)}${unknown} Извлечение не завершено; прежняя ревизия сохранена. Ручная разметка доступна.`,
          503,
        );
      } finally {
        this.extracting = false;
        this.activeRunId = undefined;
      }
    }
    return undefined;
  }
}
