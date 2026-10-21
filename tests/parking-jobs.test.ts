import assert from 'node:assert/strict';
import test from 'node:test';
import { once } from 'node:events';
import { Agent, fetch as freshFetch } from 'undici';
import { mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { ParkingReview } from '../server/parking-review.js';
import { InferenceAccessError } from '../server/inference-errors.js';
import { hostedStageDigest } from '../server/hosted-stages.js';
import { sourceDigest } from '../server/hosted-extraction.js';
import type { ParkingExtractor } from '../server/inference-client.js';
import type { HostedStageInput, HostedStageTransport } from '../shared/hosted-stage.js';
import { parkingJobSchema, type ParkingJob } from '../shared/parking-job.js';
import { reviewDraftSchema, type ReviewDraft } from '../shared/parking-review.js';
import { parkingJournalSchema } from '../shared/parking-journal.js';
import { confirmedParkingDraft } from './parking-context-fixture.js';
import { createApp } from '../server/app.js';

const profile = {
  protocol: 'normlab.hosted-stage/v1' as const,
  configDigest: sourceDigest('test-config'),
  classifier: 'openai' as const,
  discoveryModel: 'fake',
  classificationModel: 'fake',
  batchSize: 8 as const,
  maxFragments: 256 as const,
};
const source = Array.from({ length: 10 }, (_, i) => `Эпизод ${i + 1}: парковка оплачена.`).join(
  ' ',
);
function fixture(onCall?: (input: HostedStageInput) => Promise<void>) {
  const calls: string[] = [];
  let configDigest = profile.configDigest;
  const transport: HostedStageTransport = {
    profile: async () => ({ ...profile, configDigest }),
    execute: async (input) => {
      calls.push(input.stage === 'discovery' ? 'discovery' : `classification:${input.batchIndex}`);
      await onCall?.(input);
      const binding = {
        protocol: profile.protocol,
        sourceDigest: input.sourceDigest,
        configDigest: input.configDigest,
        inputDigest: hostedStageDigest(input),
        calls: [{ test: true, probability: 0.4 }],
      };
      if (input.stage === 'discovery')
        return {
          ...binding,
          stage: 'discovery',
          fragments: input.narrative.split(/(?<=\.) /).map((quote, index) => ({
            fragmentId: `fragment_${index + 1}`,
            quote,
            startOffset: input.narrative.indexOf(quote),
            endOffset: input.narrative.indexOf(quote) + quote.length,
            attributes: { subject: 'vehicle_1', speaker: 'narrator', aboutEpisode: 'episode_1' },
          })),
        };
      return {
        ...binding,
        stage: 'classification',
        batchIndex: input.batchIndex,
        decisions: [],
        statements: input.fragments.map((f) => ({
          id: randomUUID(),
          ...f.attributes,
          predicate: 'nlinput:payment',
          stance: 'asserted',
          valueText: f.quote,
          quote: f.quote,
          startOffset: f.startOffset,
          endOffset: f.endOffset,
          origin: 'model',
          decision: 'pending',
          rationale: '',
        })),
      };
    },
  };
  const extractor: ParkingExtractor = Object.assign(
    async () => {
      throw new Error('Legacy extractor must not run.');
    },
    { stages: transport },
  );
  const dir = mkdtempSync(join(tmpdir(), 'normlab-jobs-'));
  const api = new ParkingReview(dir, extractor);
  return {
    api,
    calls,
    dir,
    extractor,
    transport,
    changeConfig: () => {
      configDigest = sourceDigest('changed-config');
    },
    close: () => rmSync(dir, { recursive: true, force: true }),
  };
}
type Snapshot = { job: ParkingJob; draft: ReviewDraft };
async function snapshot(api: ParkingReview, draftId: string): Promise<Snapshot> {
  const raw = (await api.handle('GET', `/api/parking/job/${draftId}`)) as Snapshot;
  return { job: parkingJobSchema.parse(raw.job), draft: reviewDraftSchema.parse(raw.draft) };
}
async function stopped(api: ParkingReview, draftId: string) {
  for (let i = 0; i < 1000; i++) {
    const current = await snapshot(api, draftId);
    if (current.job.status !== 'running') return current;
    await new Promise<void>((done) => setImmediate(done));
  }
  throw new Error('Job did not settle.');
}
async function start(api: ParkingReview) {
  const draft = await confirmedParkingDraft(api, source);
  const job = parkingJobSchema.parse(
    await api.handle('POST', '/api/parking/jobs', {
      draftId: draft.draftId,
      expectedRevisionId: draft.revisionId,
    }),
  );
  return { draft, job };
}
const resume = (api: ParkingReview, saved: Snapshot, extra = {}) =>
  api.handle('POST', '/api/parking/jobs', {
    draftId: saved.draft.draftId,
    expectedRevisionId: saved.draft.revisionId,
    jobId: saved.job.jobId,
    ...extra,
  });
const diskState = (dir: string, draft: ReviewDraft, jobId: string) =>
  join(dir, 'parking-review', draft.draftId, 'jobs', jobId, 'job.json');

test('background job publishes discovery/partial batches and resumes only the missing batch after quota repair', async () => {
  let fail = true;
  const f = fixture(async (input) => {
    if (input.stage === 'classification' && input.batchIndex === 1 && fail)
      throw new InferenceAccessError({
        provider: 'openai',
        stage: 'classification',
        code: 'quota',
        httpStatus: 402,
      });
  });
  try {
    const { draft, job } = await start(f.api);
    assert.equal(job.status, 'running'); // Does not wait for inference; no browser request owns it.
    let saved = await stopped(f.api, draft.draftId);
    assert.equal(saved.job.status, 'paused');
    assert.equal(saved.job.failure?.code, 'quota');
    assert.equal(saved.job.fragments.length, 10);
    assert.equal(saved.job.completedBatches, 1);
    assert.equal(saved.job.unknowns, 0);
    assert.equal(saved.draft.statements.length, 8);
    assert.ok(saved.draft.statements.every((s) => s.decision === 'pending'));
    const ids = saved.draft.statements.map((s) => s.id);
    const file = diskState(f.dir, draft, job.jobId);
    assert.equal(statSync(file).mode & 0o777, 0o600);
    assert.ok(!readFileSync(file, 'utf8').includes(source));
    const restarted = new ParkingReview(f.dir, f.extractor);
    fail = false;
    await resume(restarted, saved);
    saved = await stopped(restarted, draft.draftId);
    assert.equal(saved.job.status, 'completed');
    assert.equal(saved.draft.statements.length, 10);
    assert.deepEqual(
      saved.draft.statements.slice(0, 8).map((s) => s.id),
      ids,
    );
    assert.deepEqual(f.calls, [
      'discovery',
      'classification:0',
      'classification:1',
      'classification:1',
    ]);
    const journal = parkingJournalSchema.parse(
      await restarted.handle('GET', `/api/parking/journal/${draft.draftId}`),
    );
    assert.ok(journal.events.some((e) => e.kind === 'job-progress' && e.action === 'resumed'));
    assert.ok(journal.events.some((e) => e.kind === 'job-progress' && e.failure?.code === 'quota'));
    assert.ok(!JSON.stringify(journal).includes(source));
    const disabled = new ParkingReview(f.dir, null);
    const historical = parkingJournalSchema.parse(
      await disabled.handle('GET', `/api/parking/journal/${draft.draftId}`),
    );
    assert.ok(
      historical.events.some((e) => e.kind === 'job-progress' && e.failure?.code === 'quota'),
    );
    assert.equal((await snapshot(disabled, draft.draftId)).job.status, 'completed');
    await assert.rejects(resume(disabled, saved), /не настроен/);
  } finally {
    f.close();
  }
});

test('network unknown requires explicit acknowledgement and history retains the unknown attempt after success', async () => {
  let fail = true;
  const f = fixture(async () => {
    if (fail)
      throw new InferenceAccessError({ provider: 'gateway', stage: 'discovery', code: 'network' });
  });
  try {
    const { draft, job } = await start(f.api);
    let saved = await stopped(f.api, draft.draftId);
    assert.equal(saved.job.unknowns, 1);
    await assert.rejects(resume(f.api, saved), /повторную оплату/);
    assert.equal(f.calls.length, 1);
    fail = false;
    await resume(f.api, saved, { acknowledgeUnknown: true });
    saved = await stopped(f.api, draft.draftId);
    assert.equal(saved.job.status, 'completed');
    const state = JSON.parse(readFileSync(diskState(f.dir, draft, job.jobId), 'utf8'));
    assert.equal(state.attemptLog[0].status, 'unknown');
    assert.equal(state.attemptLog[0].acknowledged, true);
    assert.equal(state.attemptLog.length, 4);
  } finally {
    f.close();
  }
});

test('manual revision wins over an in-flight batch; explicit replacement reuses the committed reply', async () => {
  let release!: () => void;
  let entered!: () => void;
  const waiting = new Promise<void>((done) => {
    entered = done;
  });
  const f = fixture(async (input) => {
    if (input.stage === 'classification' && input.batchIndex === 0) {
      entered();
      await new Promise<void>((done) => {
        release = done;
      });
    }
  });
  try {
    const { draft } = await start(f.api);
    await waiting;
    const partial = await snapshot(f.api, draft.draftId);
    assert.equal(partial.job.fragments.length, 10);
    const human = reviewDraftSchema.parse(
      await f.api.handle('POST', '/api/parking/review', {
        statements: [],
        draftId: draft.draftId,
        expectedRevisionId: partial.draft.revisionId,
        checklist: partial.draft.checklist,
        finishReview: false,
      }),
    );
    release();
    let saved = await stopped(f.api, draft.draftId);
    assert.equal(saved.job.status, 'conflict');
    assert.equal(saved.draft.revisionId, human.revisionId);
    assert.equal(saved.draft.statements.length, 0);
    await assert.rejects(resume(f.api, saved), /замену ручных правок/);
    await resume(f.api, saved, { replaceStatements: true });
    saved = await stopped(f.api, draft.draftId);
    assert.equal(saved.job.status, 'completed');
    assert.deepEqual(f.calls, ['discovery', 'classification:0', 'classification:1']);
  } finally {
    release?.();
    f.close();
  }
});

test('crashed reservation is unknown on restart and never redispatched by GET', async () => {
  const f = fixture(async () => {
    throw new InferenceAccessError({
      provider: 'openai',
      stage: 'discovery',
      code: 'quota',
      httpStatus: 402,
    });
  });
  try {
    const { draft, job } = await start(f.api);
    await stopped(f.api, draft.draftId);
    const file = diskState(f.dir, draft, job.jobId);
    const state = JSON.parse(readFileSync(file, 'utf8'));
    state.status = 'running';
    state.attemptLog[0].status = 'reserved';
    writeFileSync(file, JSON.stringify(state));
    const restarted = new ParkingReview(f.dir, f.extractor);
    const saved = await snapshot(restarted, draft.draftId);
    assert.equal(saved.job.reason, 'restart');
    assert.equal(saved.job.unknowns, 1);
    assert.equal(f.calls.length, 1);
    await assert.rejects(resume(restarted, saved), /повторную оплату/);
    assert.equal(f.calls.length, 1);
  } finally {
    f.close();
  }
});

test('changed configuration and corrupt checkpoint never trigger a provider call', async () => {
  const f = fixture(async (input) => {
    if (input.stage === 'classification')
      throw new InferenceAccessError({
        provider: 'openai',
        stage: 'classification',
        code: 'quota',
        httpStatus: 402,
      });
  });
  try {
    const { draft, job } = await start(f.api);
    let saved = await stopped(f.api, draft.draftId);
    f.changeConfig();
    await resume(f.api, saved);
    saved = await stopped(f.api, draft.draftId);
    assert.equal(saved.job.reason, 'configuration');
    assert.equal(f.calls.length, 2);
    const folder = join(f.dir, 'parking-review', draft.draftId, 'jobs', job.jobId);
    const checkpoint = readdirSync(folder).find(
      (name) => name !== 'job.json' && name.endsWith('.json'),
    )!;
    writeFileSync(join(folder, checkpoint), '{}');
    saved = await snapshot(f.api, draft.draftId);
    assert.equal(saved.job.reason, 'storage');
    const before = readFileSync(diskState(f.dir, draft, job.jobId), 'utf8');
    await snapshot(f.api, draft.draftId);
    assert.equal(readFileSync(diskState(f.dir, draft, job.jobId), 'utf8'), before);
    await assert.rejects(resume(f.api, saved));
    assert.equal(f.calls.length, 2);
  } finally {
    f.close();
  }
});

test('per-stage attempt cap prevents endless retries', async () => {
  const f = fixture(async () => {
    throw new InferenceAccessError({
      provider: 'openai',
      stage: 'discovery',
      code: 'quota',
      httpStatus: 402,
    });
  });
  try {
    const { draft } = await start(f.api);
    let saved = await stopped(f.api, draft.draftId);
    for (let i = 0; i < 3; i++) {
      await resume(f.api, saved);
      saved = await stopped(f.api, draft.draftId);
    }
    assert.equal(saved.job.reason, 'attempt-limit');
    assert.equal(f.calls.length, 3);
  } finally {
    f.close();
  }
});

test('a confirmed or unanchored model statement is never published or reused', async () => {
  for (const patch of [{ decision: 'confirmed' }, { quote: 'invented source' }]) {
    const f = fixture();
    const original = f.transport.execute.bind(f.transport);
    f.transport.execute = async (input, signal) => {
      const result = await original(input, signal);
      if (result.stage === 'classification')
        return { ...result, statements: [{ ...result.statements[0], ...patch }] } as typeof result;
      return result;
    };
    try {
      const { draft } = await start(f.api);
      const saved = await stopped(f.api, draft.draftId);
      assert.equal(saved.job.status, 'paused');
      assert.equal(saved.job.failure?.code, 'invalid_response');
      assert.equal(saved.job.unknowns, 1);
      assert.equal(saved.job.completedBatches, 0);
      assert.equal(saved.draft.statements.length, 0);
      assert.equal(saved.job.fragments.length, 10);
      assert.deepEqual(f.calls, ['discovery', 'classification:0']);
    } finally {
      f.close();
    }
  }
});

test('HTTP start returns before inference; closing client connections preserves background work and legacy lock', async () => {
  let release!: () => void;
  let entered!: () => void;
  const waiting = new Promise<void>((done) => {
    entered = done;
  });
  const f = fixture(async (input) => {
    if (input.stage === 'discovery') {
      entered();
      await new Promise<void>((done) => {
        release = done;
      });
    }
  });
  const draft = await confirmedParkingDraft(f.api, source);
  const app = await createApp({ dataDir: f.dir, parkingExtractor: f.extractor, web: false });
  app.server.listen(0, '127.0.0.1');
  await once(app.server, 'listening');
  const address = app.server.address();
  assert.ok(address && typeof address !== 'string');
  const url = `http://127.0.0.1:${address.port}`;
  const reconnected = new Agent();
  try {
    const bootstrap = (await (await fetch(url + '/api/bootstrap')).json()) as { csrfToken: string };
    const post = (path: string) =>
      fetch(url + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-NormLab-Token': bootstrap.csrfToken },
        body: JSON.stringify({ draftId: draft.draftId, expectedRevisionId: draft.revisionId }),
      });
    assert.equal(
      (
        await fetch(url + '/api/parking/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: '{}',
        })
      ).status,
      403,
    );
    const response = await post('/api/parking/jobs');
    assert.equal(response.status, 200);
    assert.equal(parkingJobSchema.parse(await response.json()).status, 'running');
    await waiting;
    assert.equal((await post('/api/parking/extract')).status, 400);
    assert.equal((await post('/api/parking/jobs')).status, 409);
    app.server.closeAllConnections(); // Browser connections are gone; no provider cancellation.
    release();
    let saved: Snapshot | undefined;
    for (let i = 0; i < 100; i++) {
      saved = (await (
        await freshFetch(url + `/api/parking/job/${draft.draftId}`, { dispatcher: reconnected })
      ).json()) as Snapshot;
      if (saved.job.status === 'completed') break;
      await new Promise<void>((done) => setImmediate(done));
    }
    assert.equal(saved?.job.status, 'completed');
    assert.equal(saved.draft.statements.length, 10);
    assert.deepEqual(f.calls, ['discovery', 'classification:0', 'classification:1']);
  } finally {
    release?.();
    await reconnected.close();
    app.server.closeAllConnections();
    await app.close();
    f.close();
  }
});
