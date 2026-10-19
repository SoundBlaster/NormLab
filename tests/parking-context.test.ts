import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { ParkingReview } from '../server/parking-review.js';
import { HOSTED_PIPELINE } from '../server/hosted-extraction.js';
import {
  emptyNarrativeContext,
  narrativeRoute,
  reviewMetadataIssues,
  type VehicleHypothesis,
} from '../shared/parking-context.js';
import {
  emptyReviewChecklist,
  reviewDraftMetadata,
  reviewDraftSchema,
  type ReviewDraft,
} from '../shared/parking-review.js';
import { confirmedParkingDraft, saveReviewMetadata } from './parking-context-fixture.js';

const source = 'Я припарковался. Оплатить парковку не удалось.';
const complete = {
  negatives: true,
  conflicts: true,
  attribution: true,
  sourceSupport: true,
  unknowns: true,
};
const hypothesis = (): VehicleHypothesis => ({
  id: randomUUID(),
  kind: 'transport-vehicle',
  vehicleKind: 'unspecified',
  vehicleKindDetails: '',
  quote: 'Я припарковался.',
  startOffset: 0,
  endOffset: 'Я припарковался.'.length,
  aboutEpisode: 'episode_1',
  origin: 'human',
  decision: 'pending',
  rationale: '',
});
const temp = () => mkdtempSync(join(tmpdir(), 'normlab-context-'));

test('whole-narrative routing does not turn paid-parking topic into a finding', () => {
  const context = {
    ...emptyNarrativeContext(),
    topic: 'parking' as const,
    parkingContext: 'paid-parking-topic' as const,
    intent: 'information' as const,
  };
  assert.equal(narrativeRoute(context), 'not-a-case');
  assert.equal(narrativeRoute({ ...context, intent: 'incident' }), 'parking-review');
  assert.equal(narrativeRoute({ ...context, topic: 'mixed' }), 'choose-episode');
  assert.equal(narrativeRoute({ ...context, topic: 'other' }), 'other-topic');
  assert.equal(narrativeRoute(emptyNarrativeContext()), 'clarify');
  assert.equal('paidRegime' in context, false);
});

test('unconfirmed, irrelevant and mixed context block extraction before any provider call', async () => {
  const dir = temp();
  let calls = 0;
  try {
    const api = new ParkingReview(dir, async () => {
      calls++;
      throw new Error('must not call');
    });
    let draft = reviewDraftSchema.parse(
      await api.handle('POST', '/api/parking/drafts', { narrative: source }),
    );
    assert.equal(draft.schema, 'normlab.parking-review/v2');
    draft = await saveReviewMetadata(api, draft, {
      context: { ...emptyNarrativeContext(), topic: 'parking', intent: 'incident' },
    });
    await assert.rejects(
      api.handle('POST', '/api/parking/extract', {
        draftId: draft.draftId,
        expectedRevisionId: draft.revisionId,
      }),
      /контекст парковочного эпизода/,
    );
    draft = await saveReviewMetadata(api, draft, {
      context: { ...reviewDraftMetadata(draft).context, intent: 'information' },
    });
    draft = await saveReviewMetadata(api, draft, {
      context: { ...reviewDraftMetadata(draft).context, decision: 'confirmed' },
    });
    await assert.rejects(
      api.handle('POST', '/api/parking/extract', {
        draftId: draft.draftId,
        expectedRevisionId: draft.revisionId,
      }),
      /контекст парковочного эпизода/,
    );
    for (const topic of ['unclear', 'other', 'mixed'] as const) {
      draft = await saveReviewMetadata(api, draft, {
        context: { ...emptyNarrativeContext(), topic, intent: 'incident' },
      });
      draft = await saveReviewMetadata(api, draft, {
        context: { ...reviewDraftMetadata(draft).context, decision: 'confirmed' },
      });
      await assert.rejects(
        api.handle('POST', '/api/parking/extract', {
          draftId: draft.draftId,
          expectedRevisionId: draft.revisionId,
        }),
        /контекст парковочного эпизода/,
      );
    }
    assert.equal(calls, 0);
    assert.deepEqual(draft.statements, []);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('hypotheses require separate saved confirmation and kind clarification; edits invalidate review', async () => {
  const dir = temp();
  try {
    const api = new ParkingReview(dir);
    let draft = await confirmedParkingDraft(api, source);
    const id = randomUUID();
    draft = reviewDraftSchema.parse(
      await api.handle('POST', '/api/parking/review', {
        draftId: draft.draftId,
        expectedRevisionId: draft.revisionId,
        ...reviewDraftMetadata(draft),
        hypotheses: [{ ...hypothesis(), decision: 'confirmed' }],
        statements: [
          {
            id,
            predicate: 'nlinput:payment',
            stance: 'denied',
            subject: 'person_1',
            aboutEpisode: 'episode_1',
            quote: source,
            startOffset: 0,
            endOffset: source.length,
            valueText: 'Рассказчику не удалось оплатить.',
            origin: 'human',
            decision: 'confirmed',
            rationale: '',
          },
        ],
        checklist: complete,
        finishReview: false,
      }),
    );
    let metadata = reviewDraftMetadata(draft);
    assert.equal(metadata.hypotheses[0].decision, 'pending');
    assert.equal(metadata.hypotheses[0].vehicleKind, 'unspecified');
    assert.equal(draft.statements.length, 1); // No statement is created from the hypothesis.
    assert.equal(draft.statements[0].decision, 'pending');
    draft = await saveReviewMetadata(api, draft, {
      hypotheses: metadata.hypotheses.map((h) => ({ ...h, decision: 'confirmed' })),
    });
    metadata = reviewDraftMetadata(draft);
    assert.equal(metadata.hypotheses[0].decision, 'confirmed');
    assert.match(reviewMetadataIssues(metadata.context, metadata.hypotheses).join(' '), /вид ТС/);
    await assert.rejects(
      api.handle('POST', '/api/parking/review', {
        draftId: draft.draftId,
        expectedRevisionId: draft.revisionId,
        ...metadata,
        statements: draft.statements.map((s) => ({ ...s, decision: 'confirmed' })),
        checklist: complete,
        finishReview: true,
      }),
      /вид ТС/,
    );
    draft = await saveReviewMetadata(api, draft, {
      hypotheses: metadata.hypotheses.map((h) => ({
        ...h,
        vehicleKind: 'bicycle',
        decision: 'confirmed',
      })),
    });
    assert.equal(reviewDraftMetadata(draft).hypotheses[0].decision, 'pending');
    await assert.rejects(
      api.handle('POST', '/api/parking/review', {
        draftId: draft.draftId,
        expectedRevisionId: draft.revisionId,
        context: reviewDraftMetadata(draft).context,
        hypotheses: reviewDraftMetadata(draft).hypotheses.map((h) => ({
          ...h,
          decision: 'confirmed',
        })),
        statements: draft.statements.map((s) => ({ ...s, decision: 'confirmed' })),
        checklist: complete,
        finishReview: true,
      }),
      /Подтвердите или отклоните каждое утверждение/,
    );
    draft = await saveReviewMetadata(api, draft, {
      hypotheses: reviewDraftMetadata(draft).hypotheses.map((h) => ({
        ...h,
        decision: 'confirmed',
      })),
    });
    draft = reviewDraftSchema.parse(
      await api.handle('POST', '/api/parking/review', {
        draftId: draft.draftId,
        expectedRevisionId: draft.revisionId,
        ...reviewDraftMetadata(draft),
        statements: draft.statements.map((s) => ({ ...s, decision: 'confirmed' })),
        checklist: complete,
        finishReview: true,
      }),
    );
    assert.equal(draft.status, 'reviewed');
    assert.equal(draft.statements[0].subject, 'person_1');
    const reviewed = draft;
    draft = await saveReviewMetadata(api, draft, {
      context: {
        ...reviewDraftMetadata(draft).context,
        rationale: 'Уточнение контекста',
        decision: 'confirmed',
      },
    });
    assert.equal(draft.status, 'draft');
    assert.equal(reviewDraftMetadata(draft).context.decision, 'pending');
    assert.equal(reviewDraftMetadata(draft).hypotheses[0].decision, 'pending');
    assert.equal(draft.statements[0].decision, 'pending');
    assert.deepEqual(draft.checklist, emptyReviewChecklist);
    const history = (await api.handle(
      'GET',
      `/api/parking/history/${draft.draftId}`,
    )) as ReviewDraft[];
    assert.deepEqual(
      history.find((d) => d.revisionId === reviewed.revisionId),
      reviewed,
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('hypothesis rejection preserves audit records and invalid quote/duplicate/removal is rejected', async () => {
  const dir = temp();
  try {
    const api = new ParkingReview(dir);
    let draft = await confirmedParkingDraft(api, source);
    const h = hypothesis();
    await assert.rejects(
      saveReviewMetadata(api, draft, { hypotheses: [{ ...h, quote: 'Выдумка' }] }),
      /Цитата гипотезы/,
    );
    await assert.rejects(saveReviewMetadata(api, draft, { hypotheses: [h, h] }), /Повторяются/);
    draft = await saveReviewMetadata(api, draft, { hypotheses: [h] });
    await assert.rejects(
      saveReviewMetadata(api, draft, { hypotheses: [{ ...h, decision: 'rejected' }] }),
      /причину отклонения/,
    );
    draft = await saveReviewMetadata(api, draft, {
      hypotheses: [{ ...h, rationale: 'Рассказчик имел в виду прогулку.' }],
    });
    draft = await saveReviewMetadata(api, draft, {
      hypotheses: reviewDraftMetadata(draft).hypotheses.map((h) => ({
        ...h,
        decision: 'rejected',
      })),
    });
    await assert.rejects(saveReviewMetadata(api, draft, { hypotheses: [] }), /вместо удаления/);
    assert.equal(reviewDraftMetadata(draft).hypotheses[0].decision, 'rejected');
    const next = reviewDraftSchema.parse(
      await api.handle('POST', '/api/parking/drafts', {
        narrative: source + ' Новый эпизод.',
        previousDraftId: draft.draftId,
      }),
    );
    assert.deepEqual(reviewDraftMetadata(next).hypotheses, []);
    assert.equal(reviewDraftMetadata(next).context.decision, 'pending');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('re-extraction invalidates hypothesis confirmation without promoting it to statements', async () => {
  const dir = temp();
  try {
    const api = new ParkingReview(dir, async ({ sourceDigest }) => ({
      pipeline: HOSTED_PIPELINE,
      sourceDigest,
      statements: [],
    }));
    let draft = await confirmedParkingDraft(api, source);
    draft = await saveReviewMetadata(api, draft, {
      hypotheses: [{ ...hypothesis(), vehicleKind: 'car' }],
    });
    draft = await saveReviewMetadata(api, draft, {
      hypotheses: reviewDraftMetadata(draft).hypotheses.map((h) => ({
        ...h,
        decision: 'confirmed',
      })),
    });
    const result = reviewDraftSchema.parse(
      await api.handle('POST', '/api/parking/extract', {
        draftId: draft.draftId,
        expectedRevisionId: draft.revisionId,
      }),
    );
    assert.equal(reviewDraftMetadata(result).hypotheses[0].decision, 'pending');
    assert.equal(reviewDraftMetadata(result).context.decision, 'confirmed');
    assert.deepEqual(result.statements, []);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('legacy v1 revisions stay byte-identical; next save creates v2 with unconfirmed context', async () => {
  const dir = temp();
  try {
    const api = new ParkingReview(dir);
    const draftId = randomUUID(),
      revisionId = randomUUID();
    const legacy = {
      schema: 'normlab.parking-review/v1',
      draftId,
      revisionId,
      revision: 1,
      previousDraftId: null,
      createdAt: new Date().toISOString(),
      narrative: source,
      sourceDigest: 'legacy-bound',
      originalExtraction: null,
      statements: [],
      checklist: complete,
      status: 'reviewed',
    };
    const path = join(dir, 'parking-review', draftId);
    mkdirSync(path);
    const bytes = JSON.stringify(legacy);
    writeFileSync(join(path, revisionId + '.json'), bytes);
    writeFileSync(join(path, 'current.json'), JSON.stringify(revisionId));
    const history = (await api.handle('GET', `/api/parking/history/${draftId}`)) as ReviewDraft[];
    assert.deepEqual(history, [legacy]);
    assert.equal(readFileSync(join(path, revisionId + '.json'), 'utf8'), bytes);
    const current = await saveReviewMetadata(api, history[0], {});
    assert.equal(current.schema, 'normlab.parking-review/v2');
    assert.equal(current.status, 'draft');
    assert.equal(reviewDraftMetadata(current).context.decision, 'pending');
    assert.equal(readFileSync(join(path, revisionId + '.json'), 'utf8'), bytes);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
