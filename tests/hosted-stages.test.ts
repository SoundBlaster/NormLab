import assert from 'node:assert/strict';
import test from 'node:test';
import { once } from 'node:events';
import { createInferenceGateway } from '../server/inference-gateway.js';
import { InferenceProviders } from '../server/inference-providers.js';
import { DEFAULT_INFERENCE_ENDPOINTS } from '../server/inference-endpoints.js';
import { hostedStageTransport } from '../server/inference-client.js';
import { InferenceAccessError } from '../server/inference-errors.js';
import {
  checkedHostedStage,
  hostedProfile,
  hostedStageDigest,
  runHostedStage,
} from '../server/hosted-stages.js';
import { runHostedExtraction, sourceDigest } from '../server/hosted-extraction.js';
import type { HostedStageInput } from '../shared/hosted-stage.js';

const token = 'test-only-stage-token-not-a-real-key-00000000';
const config = {
  token,
  openaiKey: token,
  typesafeKey: token,
  openaiModel: 'test-luna',
  typesafeModel: 'test-jev',
  decisionsModel: 'test-decisions',
  classifier: 'openai' as const,
  requestsPerHour: 2,
  endpoints: DEFAULT_INFERENCE_ENDPOINTS,
};
const quotes = ['Парковка оплачена.', 'В письме: парковка не оплачена.'];
const narrative = quotes.join(' ');
const binding = { narrative, sourceDigest: sourceDigest(narrative) };
const signal = () => AbortSignal.timeout(10000);
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
function fake() {
  const calls: string[] = [];
  const fetcher: typeof fetch = async (url, options) => {
    const body = JSON.parse(options!.body as string);
    const address = typeof url === 'string' ? url : url instanceof URL ? url.href : url.url;
    calls.push(address);
    if (address === config.endpoints.openai.url) {
      const output =
        body.text.format.name === 'discovery'
          ? {
              extractions: quotes.map((statement, i) => ({
                statement,
                statement_attributes: {
                  subject: 'vehicle_1',
                  aboutEpisode: 'episode_1',
                  speaker: i ? 'letter' : 'narrator',
                },
              })),
            }
          : {
              results: Object.fromEntries(
                JSON.parse(body.input).map((f: { fragmentId: string; quote: string }) => [
                  f.fragmentId,
                  {
                    status: 'classified',
                    reason: '',
                    classifications: [
                      {
                        predicate: 'payment',
                        stance: f.fragmentId === 'fragment_1' ? 'asserted' : 'denied',
                        valueText: f.quote,
                      },
                    ],
                  },
                ]),
              ),
            };
      return json({
        id: 'test',
        model: body.model,
        status: 'completed',
        usage: { input_tokens: 1, output_tokens: 1 },
        output: [
          {
            type: 'message',
            status: 'completed',
            content: [{ type: 'output_text', text: JSON.stringify(output) }],
          },
        ],
      });
    }
    const choices = ['asserted', 'denied', 'unknown', 'unsupported'];
    const answer = (name: string) => {
      const choice = name.endsWith('_payment')
        ? name.startsWith('fragment_1_')
          ? 'asserted'
          : 'denied'
        : 'unsupported';
      return {
        type: 'choice',
        choice,
        confidence: 0.4,
        probabilities: Object.fromEntries(choices.map((c) => [c, c === choice ? 0.4 : 0.2])),
      };
    };
    return json({
      model: body.model,
      usage: { input_tokens: 1, output_tokens: 1 },
      answers:
        address === config.endpoints.typesafe.url
          ? Object.fromEntries(Object.keys(body.questions).map((name) => [name, answer(name)]))
          : body.questions.map(({ name }: { name: string }) => {
              const a = answer(name);
              return {
                ...a,
                name,
                probabilities: Object.entries(a.probabilities).map(([value, probability]) => ({
                  value,
                  probability,
                })),
              };
            }),
    });
  };
  return { calls, fetcher };
}
const discoveryInput = (): HostedStageInput => ({
  ...binding,
  configDigest: hostedProfile(config).configDigest,
  stage: 'discovery',
});

test('profile binds used models/endpoints/prompts, excludes credentials and tolerates credential rotation', () => {
  const profile = hostedProfile(config);
  assert.equal(
    hostedProfile({ ...config, token: 'rotated', openaiKey: 'rotated', typesafeKey: 'rotated' })
      .configDigest,
    profile.configDigest,
  );
  for (const changed of [
    { ...config, openaiModel: 'other' },
    { ...config, classifier: 'typesafe' as const },
    {
      ...config,
      endpoints: {
        ...config.endpoints,
        openai: { ...config.endpoints.openai, url: 'https://another.example/responses' },
      },
    },
  ])
    assert.notEqual(hostedProfile(changed).configDigest, profile.configDigest);
  assert.ok(!JSON.stringify(profile).includes(token));
  assert.ok(!JSON.stringify(profile).includes('https://'));
});

test('each supported classifier performs one call per stage and preserves legacy proposals/evidence', async () => {
  for (const classifier of ['openai', 'typesafe', 'decisions'] as const) {
    const current = { ...config, classifier };
    const fixture = fake();
    const providers = new InferenceProviders(current, fixture.fetcher);
    const input = { ...discoveryInput(), configDigest: hostedProfile(current).configDigest };
    const discovery = await runHostedStage(input, providers, current, signal());
    assert.equal(fixture.calls.length, 1);
    assert.equal(discovery.inputDigest, hostedStageDigest(input));
    assert.equal(discovery.stage, 'discovery');
    if (discovery.stage !== 'discovery') throw new Error('Expected discovery.');
    const batch = {
      ...input,
      stage: 'classification' as const,
      batchIndex: 0,
      fragments: discovery.fragments,
    };
    const result = await runHostedStage(batch, providers, current, signal());
    assert.equal(fixture.calls.length, 2);
    assert.equal(result.stage, 'classification');
    if (result.stage !== 'classification') throw new Error('Expected classification.');
    assert.equal(result.calls.length, 1);
    const legacy = await runHostedExtraction(binding, providers, classifier, signal());
    const withoutId = (items: typeof result.statements) =>
      items.map(({ id: _id, ...rest }) => rest);
    assert.deepEqual(withoutId(result.statements), withoutId(legacy.statements));
    assert.deepEqual(result.decisions, legacy.decisions);
    assert.ok(result.statements.every((s) => s.origin === 'model' && s.decision === 'pending'));
    if (classifier !== 'openai') assert.match(JSON.stringify(result.decisions), /0\.4/);
  }
});

test('tampered source/config/anchors/IDs/bounds are rejected before dispatch', async () => {
  const fixture = fake();
  const providers = new InferenceProviders(config, fixture.fetcher);
  const discovery = await runHostedStage(discoveryInput(), providers, config, signal());
  assert.equal(discovery.stage, 'discovery');
  if (discovery.stage !== 'discovery') throw new Error('Expected discovery.');
  const batch = {
    ...discoveryInput(),
    stage: 'classification' as const,
    batchIndex: 0,
    fragments: discovery.fragments,
  };
  const first = batch.fragments[0];
  const invalid = [
    { ...batch, sourceDigest: 'a'.repeat(64) },
    { ...batch, configDigest: 'b'.repeat(64) },
    { ...batch, narrative: 'changed' },
    { ...batch, model: 'other' },
    { ...batch, batchIndex: 32 },
    { ...batch, fragments: [] },
    { ...batch, fragments: Array(9).fill(first) },
    { ...batch, fragments: [{ ...first, fragmentId: 'fragment_2' }] },
    { ...batch, fragments: [{ ...first, quote: 'made up' }] },
    { ...batch, fragments: [{ ...first, endOffset: 1 }] },
    {
      ...batch,
      fragments: [{ ...first, attributes: { ...first.attributes, subject: 'invented' } }],
    },
  ];
  for (const input of invalid)
    await assert.rejects(runHostedStage(input as HostedStageInput, providers, config, signal()));
  assert.equal(fixture.calls.length, 1);
  assert.throws(() =>
    checkedHostedStage({
      ...batch,
      narrative: `${narrative} ${first.quote}`,
      sourceDigest: sourceDigest(`${narrative} ${first.quote}`),
    }),
  );
});

test('gateway authenticates stage/profile, profiles cost no calls/quota, invalid stages cost no quota', async () => {
  const fixture = fake();
  const gateway = createInferenceGateway(config, fixture.fetcher);
  gateway.listen(0, '127.0.0.1');
  await once(gateway, 'listening');
  const address = gateway.address();
  assert.ok(address && typeof address !== 'string');
  const url = `http://127.0.0.1:${address.port}`;
  const post = (path: string, body: unknown, bearer = token) =>
    fetch(url + path, {
      method: 'POST',
      headers: { Authorization: `Bearer ${bearer}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  try {
    assert.equal((await post('/v1/profile', {}, 'wrong')).status, 401);
    assert.equal((await post('/v1/stage', discoveryInput(), 'wrong')).status, 401);
    assert.equal((await post('/v1/profile', { model: 'other' })).status, 400);
    assert.equal(
      (await post('/v1/stage', { ...discoveryInput(), sourceDigest: 'a'.repeat(64) })).status,
      400,
    );
    assert.equal(
      (await post('/v1/stage', { ...discoveryInput(), configDigest: 'b'.repeat(64) })).status,
      409,
    );
    const client = hostedStageTransport(url, token);
    for (let i = 0; i < 3; i++)
      assert.deepEqual(await client.profile(signal()), hostedProfile(config));
    assert.equal(fixture.calls.length, 0);
    const discovered = await client.execute(discoveryInput(), signal());
    if (discovered.stage !== 'discovery') throw new Error('Expected discovery.');
    const result = await client.execute(
      {
        ...discoveryInput(),
        stage: 'classification',
        batchIndex: 0,
        fragments: discovered.fragments,
      },
      signal(),
    );
    assert.equal(result.stage, 'classification');
    assert.equal(fixture.calls.length, 2);
    await assert.rejects(
      client.execute(discoveryInput(), signal()),
      (error: unknown) =>
        error instanceof InferenceAccessError && error.failure.code === 'rate_limit',
    );
    assert.deepEqual(await client.profile(signal()), hostedProfile(config));
    assert.equal(fixture.calls.length, 2);
  } finally {
    gateway.closeAllConnections();
    await new Promise<void>((done) => gateway.close(() => done()));
  }
});

test('transport rejects wrong reply source/config/stage/input binding without retry', async () => {
  const fixture = fake();
  const result = await runHostedStage(
    discoveryInput(),
    new InferenceProviders(config, fixture.fetcher),
    config,
    signal(),
  );
  for (const field of ['sourceDigest', 'configDigest', 'inputDigest'] as const) {
    let calls = 0;
    const client = hostedStageTransport('http://gateway', token, async () => {
      calls++;
      return json({ ...result, [field]: 'f'.repeat(64) });
    });
    await assert.rejects(client.execute(discoveryInput(), signal()), InferenceAccessError);
    assert.equal(calls, 1);
  }
});

test('malformed stage/profile replies use safe protocol failure, not storage diagnostics', async () => {
  const client = hostedStageTransport('http://gateway', token, async () =>
    json({ unexpected: 'private response' }),
  );
  for (const call of [
    () => client.profile(signal()),
    () => client.execute(discoveryInput(), signal()),
  ])
    await assert.rejects(
      call(),
      (error: unknown) =>
        error instanceof InferenceAccessError &&
        error.failure.code === 'invalid_response' &&
        !error.message.includes('private response'),
    );
});
