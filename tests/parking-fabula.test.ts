import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test, { type TestContext } from 'node:test';
import { ParkingReview } from '../server/parking-review.js';
import { digest } from '../server/hash.js';
import {
  emptyLegalFindings,
  type LegalAssessment,
  type LegalWorkspace,
} from '../shared/parking-legal.js';
import { fabulaActorLabel, fabulaSourceSchema } from '../shared/parking-fabula.js';
import { reviewDraftSchema, type ReviewStatement } from '../shared/parking-review.js';
import { confirmedParkingDraft } from './parking-context-fixture.js';

async function fixture(
  t: TestContext,
  quote: string,
  speaker?: string,
  stance: ReviewStatement['stance'] = 'asserted',
) {
  const root = mkdtempSync(join(tmpdir(), 'normlab-fabula-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const api = new ParkingReview(root, null);
  const narrative =
    speaker === 'letter_1' ? `Мне пришло письмо от соседа. В письме: ${quote}` : quote;
  const initial = await confirmedParkingDraft(api, narrative);
  const startOffset = narrative.indexOf(quote);
  const statement: ReviewStatement = {
    id: randomUUID(),
    predicate: 'nlinput:placement',
    stance,
    subject: 'vehicle_1',
    ...(speaker === undefined ? {} : { speaker }),
    aboutEpisode: 'episode_1',
    valueText: quote,
    quote,
    startOffset,
    endOffset: startOffset + quote.length,
    origin: 'human',
    decision: 'pending',
    rationale: '',
  };
  const complete = {
    negatives: true,
    conflicts: true,
    attribution: true,
    sourceSupport: true,
    unknowns: true,
  };
  const added = reviewDraftSchema.parse(
    await api.handle('POST', '/api/parking/review', {
      draftId: initial.draftId,
      expectedRevisionId: initial.revisionId,
      statements: [statement],
      checklist: complete,
      finishReview: false,
    }),
  );
  const draft = reviewDraftSchema.parse(
    await api.handle('POST', '/api/parking/review', {
      draftId: added.draftId,
      expectedRevisionId: added.revisionId,
      statements: [{ ...added.statements[0], decision: 'confirmed' }],
      checklist: complete,
      finishReview: true,
    }),
  );
  const workspace = (await api.handle(
    'GET',
    `/api/parking/legal/${draft.draftId}`,
  )) as LegalWorkspace;
  const record = (await api.handle('POST', '/api/parking/legal', {
    draftId: draft.draftId,
    expectedRevisionId: draft.revisionId,
    expectedAssessmentId: null,
    requestId: randomUUID(),
    packageDigest: workspace.packageDigest,
    action: 'save',
    episode: 'episode_1',
    vehicle: 'vehicle_1',
    participant: 'selected_participant',
    eventDate: '',
    location: '',
    timeInterval: '',
    claimedFine: null,
    findings: emptyLegalFindings().map((finding) =>
      finding.conditionId === 'placement'
        ? {
            ...finding,
            state: 'established',
            rationale: 'Reviewed placement statement.',
            statementIds: [statement.id],
          }
        : finding,
    ),
  })) as LegalAssessment;
  const path = `/api/parking/fabula/${draft.draftId}/${record.id}`;
  const read = async () => fabulaSourceSchema.parse(await api.handle('GET', path));
  const input = (candidateId: string, expectedDecisionId: string | null = null) => ({
    requestId: randomUUID(),
    draftId: draft.draftId,
    expectedRevisionId: draft.revisionId,
    assessmentId: record.id,
    candidateId,
    expectedDecisionId,
    decision: 'confirmed' as const,
  });
  const folder = join(root, 'parking-review', draft.draftId);
  return { api, draft, record, read, input, folder };
}

test('unnamed first person in a letter stays bound to the letter through confirmation and reload', async (t) => {
  const f = await fixture(t, 'Я оставил машину на парковке у дома.', 'letter_1');
  const source = await f.read();
  assert.equal(source.candidates.length, 1);
  const candidate = source.candidates[0];
  assert.equal(candidate.method, 'explicit-first-person/v2');
  assert.equal(candidate.method === 'explicit-first-person/v2' && candidate.speaker, 'letter_1');
  assert.equal(fabulaActorLabel(candidate), 'Автор источника «letter_1» («я»)');
  assert.doesNotMatch(fabulaActorLabel(candidate), /Рассказчик|selected_participant/);
  const revisionFile = join(f.folder, `${f.draft.revisionId}.json`);
  const receiptFile = join(f.folder, 'legal', `${f.record.id}.json`);
  const revision = readFileSync(revisionFile);
  const receipt = readFileSync(receiptFile);
  await f.api.handle('POST', '/api/parking/fabula', f.input(candidate.id));
  const reloaded = await f.read();
  assert.deepEqual(reloaded.decisions[0].candidate, candidate);
  assert.equal(reloaded.decisions[0].input.decision, 'confirmed');
  assert.equal(
    fabulaActorLabel(reloaded.decisions[0].candidate),
    'Автор источника «letter_1» («я»)',
  );
  assert.deepEqual(readFileSync(revisionFile), revision);
  assert.deepEqual(readFileSync(receiptFile), receipt);
});

test('explicit narrator can be labelled narrator', async (t) => {
  const f = await fixture(t, 'Я припарковал машину.', 'narrator');
  assert.equal(fabulaActorLabel((await f.read()).candidates[0]), 'Рассказчик («я»)');
});

test('missing speaker does not identify the overall narrator', async (t) => {
  const f = await fixture(t, 'Я оставил машину на парковке.');
  const candidate = (await f.read()).candidates[0];
  assert.equal(fabulaActorLabel(candidate), 'Автор высказывания («я») · источник не указан');
  assert.equal(Object.hasOwn(candidate, 'speaker'), false);
});

test('explicit name in a letter is preserved independently of its source ID', async (t) => {
  const f = await fixture(t, 'Я, Петров, оставил машину на парковке.', 'letter_1');
  const candidate = (await f.read()).candidates[0];
  assert.equal(candidate.label, 'Петров');
  assert.equal(fabulaActorLabel(candidate), 'Петров');
  assert.equal(candidate.method === 'explicit-first-person/v2' && candidate.speaker, 'letter_1');
});

test('named first-person placement in the main narrative preserves the name', async (t) => {
  const f = await fixture(t, 'Я, Алексей, оставил автомобиль на парковке.', 'narrator');
  assert.equal(fabulaActorLabel((await f.read()).candidates[0]), 'Алексей');
});

for (const [quote, stance] of [
  ['Я не оставлял машину на парковке.', 'asserted'],
  ['Я, Алексей, не оставил машину на парковке.', 'asserted'],
  ['Я оставил машину на парковке.', 'denied'],
  ['Я оставил машину на парковке.', 'unknown'],
] as const) {
  test(`no actor proposal for negation/uncertainty: ${stance} / ${quote}`, async (t) => {
    const f = await fixture(t, quote, 'letter_1', stance);
    assert.deepEqual((await f.read()).candidates, []);
  });
}

test('legacy v1 decision keeps its identity and remains readable without a fabricated narrator', async (t) => {
  const f = await fixture(t, 'Я оставил машину на парковке.', 'letter_1');
  const current = (await f.read()).candidates[0];
  const legacyValue = {
    statementId: current.statementId,
    label: current.label,
    quote: current.quote,
    startOffset: current.startOffset,
    endOffset: current.endOffset,
    method: 'explicit-first-person/v1' as const,
  };
  const candidate = {
    id: digest({ revision: f.draft.revisionId, assessment: f.record.id, ...legacyValue }),
    ...legacyValue,
  };
  const input = f.input(candidate.id);
  const legacy = {
    schema: 'normlab.fabula-actor-decision/v1',
    id: input.requestId,
    sequence: 1,
    at: new Date().toISOString(),
    sourceDigest: f.draft.sourceDigest,
    input,
    candidate,
  };
  mkdirSync(join(f.folder, 'fabula'));
  const file = join(f.folder, 'fabula', `${input.requestId}.json`);
  writeFileSync(file, JSON.stringify(legacy), { flag: 'wx' });
  const before = readFileSync(file);
  const reloaded = await f.read();
  assert.deepEqual(reloaded.decisions[0], legacy);
  assert.equal(
    fabulaActorLabel(reloaded.decisions[0].candidate),
    'Автор высказывания («я») · источник не сохранён',
  );
  await f.api.handle('POST', '/api/parking/fabula', input);
  assert.deepEqual(readFileSync(file), before);
  assert.equal(readdirSync(join(f.folder, 'fabula')).length, 1);
  const next = fabulaSourceSchema.parse(
    await f.api.handle('POST', '/api/parking/fabula', f.input(current.id, input.requestId)),
  );
  assert.equal(next.decisions.length, 2);
  assert.equal(fabulaActorLabel(next.decisions[0].candidate), 'Автор источника «letter_1» («я»)');
  assert.deepEqual(readFileSync(file), before);
});

test('speaker substitution is rejected even when candidate ID is recomputed', async (t) => {
  const f = await fixture(t, 'Я оставил машину на парковке.', 'letter_1');
  const candidate = (await f.read()).candidates[0];
  const input = f.input(candidate.id);
  const saved = fabulaSourceSchema.parse(await f.api.handle('POST', '/api/parking/fabula', input))
    .decisions[0];
  const { id: _oldId, ...identity } = saved.candidate;
  const substituted = {
    ...identity,
    method: 'explicit-first-person/v2' as const,
    speaker: 'narrator',
  };
  const id = digest({ revision: f.draft.revisionId, assessment: f.record.id, ...substituted });
  writeFileSync(
    join(f.folder, 'fabula', `${saved.id}.json`),
    JSON.stringify({
      ...saved,
      input: { ...saved.input, candidateId: id },
      candidate: { id, ...substituted },
    }),
  );
  await assert.rejects(f.read(), /другому источнику/);
});
