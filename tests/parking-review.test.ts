import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { HOSTED_DECISIONS_PIPELINE, HOSTED_PIPELINE } from '../server/hosted-extraction.js';
import { ParkingReview } from '../server/parking-review.js';
import {
  emptyReviewChecklist,
  reviewDraftSchema,
  type ReviewDraft,
  type ReviewStatement,
} from '../shared/parking-review.js';

test('manual review preserves revisions and invalidates edited attribution', async () => {
  const folder = mkdtempSync(join(tmpdir(), 'normlab-review-'));
  try {
    const api = new ParkingReview(folder);
    const source = 'Я оплатил парковку.';
    const initial = reviewDraftSchema.parse(
      await api.handle('POST', '/api/parking/drafts', { narrative: source }),
    );
    const statement: ReviewStatement = {
      id: randomUUID(),
      predicate: 'nlinput:payment',
      stance: 'asserted',
      subject: 'vehicle_1',
      speaker: 'narrator',
      aboutEpisode: 'episode_1',
      valueText: source,
      quote: source,
      startOffset: 0,
      endOffset: source.length,
      origin: 'human',
      decision: 'confirmed',
      rationale: '',
    };
    const complete = {
      negatives: true,
      conflicts: true,
      attribution: true,
      sourceSupport: true,
      unknowns: true,
    };
    async function save(draft: ReviewDraft, statements: ReviewStatement[], finishReview = false) {
      return reviewDraftSchema.parse(
        await api.handle('POST', '/api/parking/review', {
          draftId: draft.draftId,
          expectedRevisionId: draft.revisionId,
          statements,
          checklist: complete,
          finishReview,
        }),
      );
    }
    const added = await save(initial, [statement]);
    assert.equal(added.statements[0].decision, 'pending');
    assert.deepEqual(added.checklist, emptyReviewChecklist);
    const reviewed = await save(added, [{ ...added.statements[0], decision: 'confirmed' }], true);
    assert.equal(reviewed.status, 'reviewed');
    await assert.rejects(save(added, added.statements), /Черновик изменился/);
    const edited = await save(reviewed, [{ ...reviewed.statements[0], speaker: 'letter_1' }]);
    assert.equal(edited.status, 'draft');
    assert.equal(edited.statements[0].decision, 'pending');
    assert.deepEqual(edited.checklist, emptyReviewChecklist);
    await assert.rejects(save(edited, [], false), /вместо удаления/);
    await assert.rejects(
      save(edited, [{ ...edited.statements[0], quote: 'Выдуманная цитата' }]),
      /Цитата не совпадает/,
    );
    const history = (await api.handle(
      'GET',
      `/api/parking/history/${initial.draftId}`,
    )) as ReviewDraft[];
    assert.equal(history.length, 4);
    assert.equal(history.find((r) => r.revisionId === reviewed.revisionId)?.status, 'reviewed');
    assert.equal(
      history.find((r) => r.revisionId === reviewed.revisionId)?.statements[0].speaker,
      'narrator',
    );
    const next = reviewDraftSchema.parse(
      await api.handle('POST', '/api/parking/drafts', {
        narrative: `${source} Время не указано.`,
        previousDraftId: initial.draftId,
      }),
    );
    assert.equal(next.previousDraftId, initial.draftId);
    assert.deepEqual(next.statements, []);
    assert.equal(next.status, 'draft');
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test('hosted review accepts both declared pipelines and preserves extraction identity', async () => {
  const folder = mkdtempSync(join(tmpdir(), 'normlab-pipeline-review-'));
  const narrative = 'Я оплатил парковку.';
  try {
    for (const pipeline of [HOSTED_PIPELINE, HOSTED_DECISIONS_PIPELINE]) {
      const api = new ParkingReview(folder, async ({ sourceDigest }) => ({
        pipeline,
        sourceDigest,
        statements: [
          {
            id: randomUUID(),
            predicate: 'nlinput:payment',
            stance: 'asserted',
            subject: 'vehicle_1',
            speaker: 'narrator',
            aboutEpisode: 'episode_1',
            valueText: narrative,
            quote: narrative,
            startOffset: 0,
            endOffset: narrative.length,
            origin: 'model',
            decision: 'pending',
            rationale: '',
          },
        ],
      }));
      const initial = reviewDraftSchema.parse(
        await api.handle('POST', '/api/parking/drafts', { narrative }),
      );
      const result = reviewDraftSchema.parse(
        await api.handle('POST', '/api/parking/extract', {
          draftId: initial.draftId,
          expectedRevisionId: initial.revisionId,
        }),
      );
      assert.equal(result.revision, 2);
      assert.equal((result.originalExtraction as { pipeline: string }).pipeline, pipeline);
      assert.equal(result.statements[0].origin, 'model');
      assert.equal(result.statements[0].decision, 'pending');
      assert.equal(result.status, 'draft');
    }
    for (const pipeline of ['unknown', 'literal-discovery-then-classification/v3']) {
      const api = new ParkingReview(folder, async ({ sourceDigest }) => ({
        pipeline,
        sourceDigest,
        statements: [],
      }));
      const initial = reviewDraftSchema.parse(
        await api.handle('POST', '/api/parking/drafts', { narrative }),
      );
      await assert.rejects(
        api.handle('POST', '/api/parking/extract', {
          draftId: initial.draftId,
          expectedRevisionId: initial.revisionId,
        }),
        /прежняя ревизия сохранена/,
      );
      const history = await api.handle('GET', `/api/parking/history/${initial.draftId}`);
      assert.equal((history as unknown[]).length, 1);
    }
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});
