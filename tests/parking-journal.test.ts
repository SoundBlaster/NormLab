import assert from 'node:assert/strict';
import test from 'node:test';
import { randomUUID } from 'node:crypto';
import { mkdtempSync, mkdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { ParkingReview } from '../server/parking-review.js';
import { InferenceAccessError } from '../server/inference-errors.js';
import { saveParkingRun } from '../server/parking-journal.js';
import { HOSTED_PIPELINE } from '../server/hosted-extraction.js';
import { parkingJournalSchema } from '../shared/parking-journal.js';
import { reviewDraftSchema, type ReviewDraft } from '../shared/parking-review.js';
import { confirmedParkingDraft, saveReviewMetadata } from './parking-context-fixture.js';

const narrative = 'Я оплатил парковку.';
const statement = () => ({
  id: randomUUID(),
  predicate: 'nlinput:payment',
  stance: 'asserted' as const,
  subject: 'vehicle_1',
  aboutEpisode: 'episode_1',
  valueText: narrative,
  quote: narrative,
  startOffset: 0,
  endOffset: narrative.length,
  origin: 'model' as const,
  decision: 'pending' as const,
  rationale: '',
});
const output = (sourceDigest: string) => ({
  pipeline: HOSTED_PIPELINE,
  sourceDigest,
  statements: [statement()],
});
const journal = async (api: ParkingReview, draft: ReviewDraft) =>
  parkingJournalSchema.parse(await api.handle('GET', `/api/parking/journal/${draft.draftId}`));
const input = (draft: ReviewDraft) => ({
  draftId: draft.draftId,
  expectedRevisionId: draft.revisionId,
});

test('persistent journal derives manual actions from revisions without copying source or statements', async () => {
  const folder = mkdtempSync(join(tmpdir(), 'normlab-journal-'));
  try {
    const api = new ParkingReview(folder, null);
    const draft = await confirmedParkingDraft(api, narrative);
    const result = await journal(new ParkingReview(folder, null), draft);
    assert.equal(result.total, 3);
    assert.equal(result.events.filter((e) => e.kind === 'draft-created').length, 1);
    assert.equal(result.events.filter((e) => e.kind === 'review-saved').length, 2);
    assert.ok(!JSON.stringify(result).includes(narrative));
    assert.ok(result.events.every((e) => !('statements' in e) && !('context' in e)));
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test('provider failure survives restart with stage/status, prior revision and no automatic retry', async () => {
  const folder = mkdtempSync(join(tmpdir(), 'normlab-journal-failure-'));
  let calls = 0;
  const failure = {
    code: 'authentication' as const,
    provider: 'typesafe' as const,
    stage: 'classification' as const,
    httpStatus: 401,
  };
  try {
    const api = new ParkingReview(folder, async () => {
      calls++;
      throw new InferenceAccessError(failure);
    });
    const draft = await confirmedParkingDraft(api, narrative);
    await assert.rejects(api.handle('POST', '/api/parking/extract', input(draft)), /HTTP 401/);
    const restored = new ParkingReview(folder, null);
    const result = await journal(restored, draft);
    const event = result.events.find((e) => e.kind === 'extraction-failed');
    assert.ok(event?.kind === 'extraction-failed');
    assert.deepEqual(event.failure, failure);
    assert.equal(result.events.filter((e) => e.kind === 'extraction-started').length, 1);
    assert.equal(
      result.events.some((e) => e.kind === 'extraction-running'),
      false,
    );
    assert.ok(!JSON.stringify(result).includes(narrative));
    assert.equal(
      ((await restored.handle('GET', `/api/parking/history/${draft.draftId}`)) as ReviewDraft[])[0]
        .revisionId,
      draft.revisionId,
    );
    assert.equal(calls, 1);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test('unknown network outcome is explicit and exception text never enters journal', async () => {
  const folder = mkdtempSync(join(tmpdir(), 'normlab-journal-unknown-'));
  try {
    for (const error of [
      new InferenceAccessError({ code: 'timeout', provider: 'openai', stage: 'discovery' }),
      new Error('private-token-and-provider-body'),
    ]) {
      const api = new ParkingReview(folder, async () => {
        throw error;
      });
      const draft = await confirmedParkingDraft(api, narrative);
      await assert.rejects(
        api.handle('POST', '/api/parking/extract', input(draft)),
        error instanceof InferenceAccessError
          ? /мог выполнить.*списать/
          : /прежняя ревизия сохранена/,
      );
      assert.ok(!JSON.stringify(await journal(api, draft)).includes('private-token'));
    }
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test('running extraction is observable and complete result remains pending human review', async () => {
  const folder = mkdtempSync(join(tmpdir(), 'normlab-journal-success-'));
  let release!: () => void;
  const wait = new Promise<void>((done) => {
    release = done;
  });
  try {
    const api = new ParkingReview(folder, async ({ sourceDigest }) => {
      await wait;
      return output(sourceDigest);
    });
    const draft = await confirmedParkingDraft(api, narrative);
    const work = api.handle('POST', '/api/parking/extract', input(draft));
    assert.ok((await journal(api, draft)).events.some((e) => e.kind === 'extraction-running'));
    release();
    const saved = reviewDraftSchema.parse(await work);
    assert.ok(saved.statements.every((s) => s.decision === 'pending'));
    const result = await journal(new ParkingReview(folder, null), saved);
    assert.ok(result.events.some((e) => e.kind === 'extraction-completed'));
    assert.ok(result.events.some((e) => e.kind === 'model-applied'));
  } finally {
    release();
    rmSync(folder, { recursive: true, force: true });
  }
});

test('later response never overwrites a concurrently saved revision and conflict stays visible', async () => {
  const folder = mkdtempSync(join(tmpdir(), 'normlab-journal-conflict-'));
  let release!: () => void;
  const wait = new Promise<void>((done) => {
    release = done;
  });
  try {
    const api = new ParkingReview(folder, async ({ sourceDigest }) => {
      await wait;
      return output(sourceDigest);
    });
    const draft = await confirmedParkingDraft(api, narrative);
    const work = api.handle('POST', '/api/parking/extract', input(draft));
    const edited = await saveReviewMetadata(api, draft, {});
    release();
    await assert.rejects(work, /Черновик изменился/);
    const result = await journal(api, edited);
    assert.ok(result.events.some((e) => e.kind === 'extraction-conflict'));
    assert.equal(
      result.events.some((e) => e.kind === 'extraction-completed'),
      false,
    );
    const history = (await api.handle(
      'GET',
      `/api/parking/history/${draft.draftId}`,
    )) as ReviewDraft[];
    assert.equal(history[0].revisionId, edited.revisionId);
  } finally {
    release();
    rmSync(folder, { recursive: true, force: true });
  }
});

test('replacing saved statements needs explicit approval before any new provider call', async () => {
  const folder = mkdtempSync(join(tmpdir(), 'normlab-journal-replace-'));
  let calls = 0;
  try {
    const api = new ParkingReview(folder, async ({ sourceDigest }) => {
      calls++;
      return output(sourceDigest);
    });
    const draft = await confirmedParkingDraft(api, narrative);
    const saved = reviewDraftSchema.parse(
      await api.handle('POST', '/api/parking/extract', input(draft)),
    );
    await assert.rejects(
      api.handle('POST', '/api/parking/extract', input(saved)),
      /Подтвердите замену/,
    );
    assert.equal(calls, 1);
    await api.handle('POST', '/api/parking/extract', { ...input(saved), replaceStatements: true });
    assert.equal(calls, 2);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test('unfinished durable start after restart is unknown, never an automatic redispatch', async () => {
  const folder = mkdtempSync(join(tmpdir(), 'normlab-journal-restart-'));
  try {
    const api = new ParkingReview(folder, null);
    const draft = await confirmedParkingDraft(api, narrative);
    const runId = randomUUID();
    const runFolder = join(folder, 'parking-review', draft.draftId, `extraction-${runId}`);
    mkdirSync(runFolder);
    saveParkingRun(runFolder, {
      runId,
      revisionId: draft.revisionId,
      startedAt: new Date().toISOString(),
      status: 'running',
    });
    const result = await journal(new ParkingReview(folder, null), draft);
    assert.ok(result.events.some((e) => e.kind === 'extraction-interrupted'));
    assert.equal(
      result.events.some((e) => e.kind === 'extraction-running'),
      false,
    );
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test('same-timestamp revisions stay newest-first and UI limit does not delete history', async (t) => {
  t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2026-10-21T12:00:00Z') });
  const folder = mkdtempSync(join(tmpdir(), 'normlab-journal-page-'));
  try {
    const api = new ParkingReview(folder, null);
    let draft = await confirmedParkingDraft(api, narrative);
    for (let i = 0; i < 100; i++) draft = await saveReviewMetadata(api, draft, {});
    const result = await journal(api, draft);
    assert.equal(result.total, 103);
    assert.equal(result.events.length, 100);
    assert.equal(result.events[0].revision, 103);
    assert.equal(result.events[99].revision, 4);
    const history = (await api.handle(
      'GET',
      `/api/parking/history/${draft.draftId}`,
    )) as ReviewDraft[];
    assert.equal(history.length, 103);
    const failed = new ParkingReview(folder, async () => {
      throw new InferenceAccessError({ code: 'timeout', provider: 'openai', stage: 'discovery' });
    });
    await assert.rejects(failed.handle('POST', '/api/parking/extract', input(draft)));
    const withRun = await journal(failed, draft);
    assert.equal(withRun.events[0].kind, 'extraction-failed');
    assert.equal(withRun.events[1].kind, 'extraction-started');
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});
