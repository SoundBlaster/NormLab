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
  emptyReviewChecklist,
  reviewChecklistSchema,
  reviewDraftSchema,
  reviewStatementSchema,
  reviewStatementIssues,
  type ReviewDraft,
  type ReviewStatement,
} from '../shared/parking-review.js';

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
  })
  .strict();
const extractInput = z
  .object({ draftId: z.string().uuid(), expectedRevisionId: z.string().uuid() })
  .strict();

export class ParkingReview {
  private readonly root: string;
  private extracting = false;
  constructor(dataDir: string) {
    this.root = join(dataDir, 'parking-review');
    mkdirSync(this.root, { recursive: true, mode: 0o700 });
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
      throw new ParkingReviewError('Черновик изменился. Обновите страницу.');
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
      ...changes,
      revisionId: randomUUID(),
      revision: draft.revision + 1,
      createdAt: new Date().toISOString(),
    });
  }
  async handle(method: string, path: string, body?: unknown) {
    if (method === 'GET' && path === '/api/parking/bootstrap') {
      const drafts = readdirSync(this.root, { withFileTypes: true })
        .filter((entry) => entry.isDirectory())
        .map((entry) => this.current(entry.name))
        .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
      return {
        drafts,
        extractorAvailable: existsSync(resolve('.tools/parking-evaluation/bin/python')),
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
      return readdirSync(this.folder(id))
        .filter((name) => name.endsWith('.json') && name !== 'current.json')
        .map((name) =>
          reviewDraftSchema.parse(JSON.parse(readFileSync(join(this.folder(id), name), 'utf8'))),
        )
        .sort((a, b) => b.revision - a.revision);
    }
    if (method === 'POST' && path === '/api/parking/drafts') {
      const input = createInput.parse(body);
      if (input.previousDraftId) this.current(input.previousDraftId);
      return this.save({
        schema: 'normlab.parking-review/v1',
        draftId: randomUUID(),
        revisionId: randomUUID(),
        revision: 1,
        previousDraftId: input.previousDraftId ?? null,
        createdAt: new Date().toISOString(),
        narrative: input.narrative,
        sourceDigest: digest(input.narrative),
        originalExtraction: null,
        statements: [],
        checklist: { ...emptyReviewChecklist },
        status: 'draft',
      });
    }
    if (method === 'POST' && path === '/api/parking/review') {
      const input = updateInput.parse(body);
      const draft = this.expected(input.draftId, input.expectedRevisionId);
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
          decision: changed ? ('pending' as const) : statement.decision,
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
      const checklist = contentChanged ? { ...emptyReviewChecklist } : input.checklist;
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
        checklist,
        status:
          input.finishReview ||
          (draft.status === 'reviewed' && !statementsChanged && !checklistChanged)
            ? 'reviewed'
            : 'draft',
      });
    }
    if (method === 'POST' && path === '/api/parking/extract') {
      const input = extractInput.parse(body);
      const draft = this.expected(input.draftId, input.expectedRevisionId);
      if (this.extracting) throw new ParkingReviewError('Извлечение уже выполняется.');
      if (!existsSync(resolve('.tools/parking-evaluation/bin/python')))
        throw new ParkingReviewError(
          'Установите evaluation environment по docs/EVALUATION_SETUP.md.',
        );
      this.extracting = true;
      const folder = join(this.folder(draft.draftId), `extraction-${randomUUID()}`);
      mkdirSync(folder, { mode: 0o700 });
      writeFileSync(
        join(folder, 'input.json'),
        JSON.stringify({ narrative: draft.narrative, sourceDigest: draft.sourceDigest }),
        { mode: 0o600 },
      );
      try {
        await promisify(execFile)(
          resolve('.tools/parking-evaluation/bin/python'),
          [
            resolve('evaluation/two_stage.py'),
            join(folder, 'input.json'),
            join(folder, 'output.json'),
          ],
          { timeout: 420000, maxBuffer: 4 * 1024 * 1024 },
        );
        const raw: unknown = JSON.parse(readFileSync(join(folder, 'output.json'), 'utf8'));
        const result = z
          .object({ statements: z.array(reviewStatementSchema).max(256), sourceDigest: z.string() })
          .passthrough()
          .parse(raw);
        if (result.sourceDigest !== draft.sourceDigest)
          throw new ParkingReviewError('Source binding изменился.');
        for (const statement of result.statements) {
          if (reviewStatementIssues(statement, draft.narrative).length)
            throw new ParkingReviewError('Extractor вернул неверную цитату.');
        }
        this.expected(input.draftId, input.expectedRevisionId);
        return this.revise(draft, {
          originalExtraction: raw,
          statements: result.statements,
          checklist: { ...emptyReviewChecklist },
          status: 'draft',
        });
      } catch (error) {
        if (error instanceof ParkingReviewError) throw error;
        throw new ParkingReviewError(
          'Извлечение не завершено. Проверьте локальную модель; прежняя ревизия сохранена. Ручная разметка доступна.',
          503,
        );
      } finally {
        this.extracting = false;
      }
    }
    return undefined;
  }
}
