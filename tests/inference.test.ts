import { confirmedParkingDraft } from './parking-context-fixture.js';
import assert from 'node:assert/strict';
import test from 'node:test';
import { once } from 'node:events';
import { randomUUID } from 'node:crypto';
import { mkdtempSync, rmSync, writeFileSync, chmodSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createServer, request } from 'node:http';
import prompts from '../server/inference-prompts.json';
import subjectRegression from '../fixtures/parking-pilot/hosted-subject-regression/DEV017.json';
import Ajv2020 from 'ajv/dist/2020.js';
import { InferenceProviders, INFERENCE_DESTINATIONS } from '../server/inference-providers.js';
import {
  runHostedExtraction,
  sourceDigest,
  HOSTED_MAX_NARRATIVE,
  HOSTED_PIPELINE,
  HOSTED_PROMPT_DIGEST,
  hostedDiscoverySchema,
} from '../server/hosted-extraction.js';
import { createInferenceGateway, proxiedFetch } from '../server/inference-gateway.js';
import {
  checkedLookup,
  createInferenceEgress,
  inferenceTunnelHost,
  isPublicInferenceAddress,
} from '../server/inference-egress.js';
import {
  readInferenceSecret,
  inferenceClientConfig,
  inferenceGatewayConfig,
} from '../server/inference-config.js';
import { readBoundedJson } from '../server/inference-http.js';
import { DEFAULT_INFERENCE_ENDPOINTS, inferenceEndpoints } from '../server/inference-endpoints.js';
import { ParkingReview } from '../server/parking-review.js';
import { reviewDraftSchema } from '../shared/parking-review.js';

const token = 'test-only-credential-not-a-real-key-0000000000';
const config = {
  endpoints: DEFAULT_INFERENCE_ENDPOINTS,
  token,
  openaiKey: token,
  openaiModel: 'gpt-6-luna',
  typesafeKey: token,
  typesafeModel: 'jev-1.13.0',
  decisionsModel: 'gpt-6-luna',
  classifier: 'openai' as const,
  requestsPerHour: 1,
};
const narrative = 'Я оплатил парковку. В письме: я не оплатил парковку.';
const input = { narrative, sourceDigest: sourceDigest(narrative) };
const quotes = ['Я оплатил парковку.', 'В письме: я не оплатил парковку.'];
const discoveryOutput = {
  extractions: quotes.map((statement, i) => ({
    statement,
    statement_attributes: {
      subject: 'vehicle_1',
      aboutEpisode: 'episode_1',
      speaker: i ? 'letter_1' : 'narrator',
    },
  })),
};
const classificationOutput = {
  results: Object.fromEntries(
    quotes.map((quote, i) => [
      `fragment_${i + 1}`,
      {
        status: 'classified',
        reason: '',
        classifications: [
          { predicate: 'payment', stance: i ? 'denied' : 'asserted', valueText: quote },
        ],
      },
    ]),
  ),
};
function response(body: unknown) {
  return new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
}
function openai(output: unknown) {
  return response({
    id: 'response_test',
    model: 'gpt-6-luna',
    status: 'completed',
    usage: { input_tokens: 10, output_tokens: 10 },
    output: [
      {
        type: 'message',
        status: 'completed',
        content: [{ type: 'output_text', text: JSON.stringify(output) }],
      },
    ],
  });
}
function mockFetch(
  overrides: { discovery?: unknown; classification?: unknown; typesafe?: boolean } = {},
) {
  const requests: { url: string; body: Record<string, unknown>; authorization: string | null }[] =
    [];
  const fetcher: typeof fetch = async (url, options) => {
    const address = typeof url === 'string' ? url : url instanceof URL ? url.href : url.url;
    const body = JSON.parse(options?.body as string) as Record<string, unknown>;
    requests.push({
      url: address,
      body,
      authorization: new Headers(options?.headers).get('authorization'),
    });
    assert.equal(options?.redirect, 'error');
    if (address === INFERENCE_DESTINATIONS.openai)
      return openai(
        requests.length === 1
          ? (overrides.discovery ?? discoveryOutput)
          : (overrides.classification ?? classificationOutput),
      );
    assert.equal(address, INFERENCE_DESTINATIONS.typesafe);
    const questions = body.questions as Record<string, { instructions: string }>;
    return response({
      model: 'jev-1.13.0',
      usage: { input_tokens: 10, output_tokens: 10 },
      answers: Object.fromEntries(
        Object.keys(questions).map((id) => {
          const choice = id.endsWith('_payment')
            ? id.startsWith('fragment_1_')
              ? 'asserted'
              : 'denied'
            : 'unsupported';
          return [
            id,
            {
              type: 'choice',
              choice,
              confidence: 0.01,
              probabilities: Object.fromEntries(
                ['asserted', 'denied', 'unknown', 'unsupported'].map((option) => [
                  option,
                  option === choice ? 0.4 : 0.2,
                ]),
              ),
            },
          ];
        }),
      ),
    });
  };
  return { requests, fetcher };
}
const signal = () => AbortSignal.timeout(10000);

test('OpenAI hosted pipeline preserves opposing source statements as pending proposals', async () => {
  const mock = mockFetch();
  const result = await runHostedExtraction(
    input,
    new InferenceProviders(config, mock.fetcher),
    'openai',
    signal(),
  );
  assert.equal(result.pipeline, HOSTED_PIPELINE);
  assert.deepEqual(
    result.statements.map((s) => [s.stance, s.speaker, s.decision, s.origin]),
    [
      ['asserted', 'narrator', 'pending', 'model'],
      ['denied', 'letter_1', 'pending', 'model'],
    ],
  );
  for (const statement of result.statements)
    assert.equal(narrative.slice(statement.startOffset, statement.endOffset), statement.quote);
  assert.equal(mock.requests.length, 2);
  for (const call of mock.requests) {
    assert.equal(call.url, INFERENCE_DESTINATIONS.openai);
    assert.equal(call.body.store, false);
    assert.equal(call.body.model, config.openaiModel);
    assert.equal(call.body.tools, undefined);
    assert.equal(call.authorization, `Bearer ${token}`);
  }
  assert.ok(!JSON.stringify(result).includes(token));
});

test('Jev evaluates each fragment/predicate and preserves low-confidence suggestions for human review', async () => {
  const mock = mockFetch();
  const result = await runHostedExtraction(
    input,
    new InferenceProviders({ ...config, classifier: 'typesafe' }, mock.fetcher),
    'typesafe',
    signal(),
  );
  assert.deepEqual(
    result.statements.map((s) => [s.stance, s.valueText, s.decision]),
    [
      ['asserted', quotes[0], 'pending'],
      ['denied', quotes[1], 'pending'],
    ],
  );
  assert.equal(mock.requests.length, 2);
  const questions = mock.requests[1].body.questions as Record<string, { instructions: string }>;
  assert.equal(Object.keys(questions).length, 2 * Object.keys(prompts.definitions).length);
  assert.match(questions.fragment_2_payment.instructions, /fragment_2.*payment/);
  assert.match(JSON.stringify(result.decisions), /confidence/);
});

test('OpenAI classification batches fragments to bound strict schema and response size', async () => {
  const statements = Array.from({ length: 9 }, (_, i) => `Эпизод ${i + 1}: парковка оплачена.`);
  const source = statements.join(' ');
  let calls = 0;
  const sizes: number[] = [];
  const fetcher: typeof fetch = async (_url, options) => {
    const body = JSON.parse(options?.body as string) as Record<string, unknown>;
    if (calls++ === 0)
      return openai({
        extractions: statements.map((statement) => ({
          statement,
          statement_attributes: discoveryOutput.extractions[0].statement_attributes,
        })),
      });
    const batch = JSON.parse(body.input as string) as { fragmentId: string; quote: string }[];
    sizes.push(batch.length);
    return openai({
      results: Object.fromEntries(
        batch.map((fragment) => [
          fragment.fragmentId,
          {
            status: 'classified',
            reason: '',
            classifications: [
              {
                predicate: 'payment',
                stance: 'asserted',
                valueText: fragment.quote,
              },
            ],
          },
        ]),
      ),
    });
  };
  const result = await runHostedExtraction(
    { narrative: source, sourceDigest: sourceDigest(source) },
    new InferenceProviders(config, fetcher),
    'openai',
    signal(),
  );
  assert.equal(result.statements.length, 9);
  assert.deepEqual(sizes, [8, 1]);
  assert.equal(calls, 3);
});

test('discovery rejects wrong bindings, hallucinated/repeated quotes, and missing classification decisions', async () => {
  const mock = mockFetch();
  await assert.rejects(
    runHostedExtraction(
      { ...input, sourceDigest: '0'.repeat(64) },
      new InferenceProviders(config, mock.fetcher),
      'openai',
      signal(),
    ),
    /binding/,
  );
  assert.equal(mock.requests.length, 0);
  const hallucinated = mockFetch({
    discovery: { extractions: [{ ...discoveryOutput.extractions[0], statement: 'invented fact' }] },
  });
  await assert.rejects(
    runHostedExtraction(
      input,
      new InferenceProviders(config, hallucinated.fetcher),
      'openai',
      signal(),
    ),
    /quote/,
  );
  assert.equal(hallucinated.requests.length, 1);
  const repeated = quotes[0] + quotes[0];
  await assert.rejects(
    runHostedExtraction(
      { narrative: repeated, sourceDigest: sourceDigest(repeated) },
      new InferenceProviders(
        config,
        mockFetch({ discovery: { extractions: [discoveryOutput.extractions[0]] } }).fetcher,
      ),
      'openai',
      signal(),
    ),
    /ambiguous/,
  );
  await assert.rejects(
    runHostedExtraction(
      input,
      new InferenceProviders(
        config,
        mockFetch({
          classification: { results: { fragment_1: classificationOutput.results.fragment_1 } },
        }).fetcher,
      ),
      'openai',
      signal(),
    ),
  );
});

test('discovery IDs share syntax while unsupported length constraints remain local', async () => {
  const idSchemas =
    hostedDiscoverySchema.properties.extractions.items.properties.statement_attributes.properties;
  for (const field of ['subject', 'aboutEpisode'] as const) {
    assert.deepEqual(Object.keys(idSchemas[field]).sort(), ['pattern', 'type']);
    assert.equal(idSchemas[field].type, 'string');
    assert.equal(typeof idSchemas[field].pattern, 'string');
  }
  const validate = new Ajv2020({ strict: true }).compile(hostedDiscoverySchema);
  const ids = [
    { field: 'subject', value: 'vehicle_1', valid: true },
    { field: 'subject', value: 'person_21', valid: true },
    { field: 'subject', value: `vehicle_${'9'.repeat(120)}`, valid: true },
    { field: 'subject', value: `person_${'9'.repeat(121)}`, valid: true },
    { field: 'subject', value: `person_${'9'.repeat(122)}`, valid: false, wireValid: true },
    { field: 'subject', value: 'Приложение и СМС', valid: false },
    { field: 'subject', value: 'narrator', valid: false },
    { field: 'subject', value: 'vehicle_0', valid: false },
    { field: 'subject', value: 'vehicle_01', valid: false },
    { field: 'subject', value: 'person_-1', valid: false },
    { field: 'subject', value: 'person_١', valid: false },
    { field: 'subject', value: 'person_1 ', valid: false },
    { field: 'subject', value: ' person_1', valid: false },
    { field: 'aboutEpisode', value: 'episode_1', valid: true },
    { field: 'aboutEpisode', value: `episode_${'9'.repeat(120)}`, valid: true },
    { field: 'aboutEpisode', value: `episode_${'9'.repeat(121)}`, valid: false, wireValid: true },
    { field: 'aboutEpisode', value: 'episode_0', valid: false },
    { field: 'aboutEpisode', value: 'episode_01', valid: false },
    { field: 'aboutEpisode', value: 'vehicle_1', valid: false },
  ];
  for (const { field, value, valid, wireValid = valid } of ids) {
    const output = structuredClone(discoveryOutput);
    for (const extraction of output.extractions)
      Object.assign(extraction.statement_attributes, { [field]: value });
    const label = `${field}=${JSON.stringify(value)}`;
    assert.equal(validate(output), wireValid, `provider schema: ${label}`);
    const mock = mockFetch({ discovery: output });
    const run = runHostedExtraction(
      input,
      new InferenceProviders(config, mock.fetcher),
      'openai',
      signal(),
    );
    if (valid) {
      const result = await run;
      assert.equal(result.statements[0][field as 'subject' | 'aboutEpisode'], value, label);
      assert.equal(mock.requests.length, 2, label);
    } else {
      await assert.rejects(run, { name: 'ZodError' }, label);
      assert.equal(mock.requests.length, 1, label);
    }
  }
});

test('saved DEV017 subject is rejected by emitted schema and locally before classification', async () => {
  const before = structuredClone(subjectRegression);
  const validate = new Ajv2020({ strict: true }).compile(hostedDiscoverySchema);
  assert.equal(
    sourceDigest(subjectRegression.input.narrative),
    subjectRegression.input.sourceDigest,
  );
  assert.equal(validate(subjectRegression.discovery), false);
  assert.ok(validate.errors?.some((error) => error.instancePath.endsWith('/subject')));
  const mock = mockFetch({ discovery: subjectRegression.discovery });
  await assert.rejects(
    runHostedExtraction(
      subjectRegression.input,
      new InferenceProviders(config, mock.fetcher),
      'openai',
      signal(),
    ),
    { name: 'ZodError' },
  );
  assert.equal(mock.requests.length, 1);
  assert.deepEqual(
    (mock.requests[0].body.text as { format: { schema: unknown } }).format.schema,
    hostedDiscoverySchema,
  );
  assert.deepEqual(subjectRegression, before); // Never repair or relink the saved model output.
});

test('authored thematic-person reference retains technical failure quote without inventing a car', async () => {
  // Explicit test reference, not an automatic correction or another model result.
  const reference = structuredClone(subjectRegression.discovery);
  reference.extractions[1].statement_attributes.subject = 'person_1';
  const validate = new Ajv2020({ strict: true }).compile(hostedDiscoverySchema);
  assert.equal(validate(reference), true);
  const mock = mockFetch({
    discovery: reference,
    classification: {
      results: {
        fragment_1: {
          status: 'classified',
          reason: '',
          classifications: [
            {
              predicate: 'cityParking',
              stance: 'asserted',
              valueText: 'Место названо городской парковкой.',
            },
          ],
        },
        fragment_2: {
          status: 'classified',
          reason: '',
          classifications: [
            {
              predicate: 'payment',
              stance: 'denied',
              valueText: 'Рассказчику не удалось оплатить парковку.',
            },
          ],
        },
      },
    },
  });
  const result = await runHostedExtraction(
    subjectRegression.input,
    new InferenceProviders(config, mock.fetcher),
    'openai',
    signal(),
  );
  assert.ok(result.statements.every((statement) => statement.subject === 'person_1'));
  assert.equal(result.statements[1].quote, reference.extractions[1].statement);
  assert.match(result.statements[1].quote, /Приложение и СМС не работали/);
  assert.equal(result.statements[1].decision, 'pending');
  assert.equal(mock.requests.length, 2);
  assert.equal(
    subjectRegression.discovery.extractions[1].statement_attributes.subject,
    'Приложение и СМС',
  );
  assert.match(mock.requests[0].body.instructions as string, /не грамматическое подлежащее/);
  assert.match(mock.requests[0].body.instructions as string, /Не выдумывай/);
});

test('provider rejects incomplete, refusal, invalid distributions and transport errors without leaking bodies', async () => {
  const incomplete: typeof fetch = async () => response({ status: 'incomplete' });
  await assert.rejects(
    new InferenceProviders(config, incomplete).structured(
      'classification',
      '',
      '',
      {},
      [],
      signal(),
    ),
  );
  const refusal: typeof fetch = async () =>
    response({
      id: 'response_test',
      model: 'gpt-6-luna',
      status: 'completed',
      usage: { input_tokens: 10, output_tokens: 10 },
      output: [{ type: 'message', status: 'completed', content: [{ type: 'refusal' }] }],
    });
  await assert.rejects(
    new InferenceProviders(config, refusal).structured('classification', '', '', {}, [], signal()),
    /refused/,
  );
  const badDistribution: typeof fetch = async () =>
    response({
      model: 'jev-1.13.0',
      usage: { input_tokens: 1, output_tokens: 1 },
      answers: {
        q: {
          type: 'choice',
          choice: 'asserted',
          confidence: 1,
          probabilities: { asserted: 0, denied: 0, unknown: 0, unsupported: 0 },
        },
      },
    });
  await assert.rejects(
    new InferenceProviders(config, badDistribution).choices(
      '',
      { q: { type: 'choice', instructions: 'test', criteria: {} } },
      [],
      signal(),
    ),
    /distribution/,
  );
  const failed: typeof fetch = async () => new Response(token, { status: 401 });
  await assert.rejects(
    new InferenceProviders(config, failed).structured('classification', '', '', {}, [], signal()),
    (error: Error) => !error.message.includes(token) && /transport failed/.test(error.message),
  );
  await assert.rejects(readBoundedJson(new Response('123456789'), 2), /limit/);
});

async function listen(server: ReturnType<typeof createInferenceGateway>) {
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const address = server.address();
  assert.ok(address && typeof address !== 'string');
  return `http://127.0.0.1:${address.port}`;
}
test('gateway authenticates exact RPC route, blocks arbitrary URLs and enforces hourly quota', async () => {
  const mock = mockFetch();
  const server = createInferenceGateway(config, mock.fetcher);
  const url = await listen(server);
  try {
    assert.equal((await fetch(`${url}/v1/extract`, { method: 'POST' })).status, 401);
    const options = {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    };
    assert.equal((await fetch(`${url}/v1/extract?url=https://evil.example`, options)).status, 404);
    assert.equal(
      (
        await fetch(`${url}/v1/extract`, {
          ...options,
          body: JSON.stringify({ ...input, url: 'https://evil.example' }),
        })
      ).status,
      400,
    );
    const long = 'а'.repeat(HOSTED_MAX_NARRATIVE + 1);
    assert.equal(
      (
        await fetch(`${url}/v1/extract`, {
          ...options,
          body: JSON.stringify({ narrative: long, sourceDigest: sourceDigest(long) }),
        })
      ).status,
      400,
    );
    const result = await fetch(`${url}/v1/extract`, options);
    assert.equal(result.status, 200);
    assert.ok(!JSON.stringify(await result.json()).includes(token));
    assert.equal((await fetch(`${url}/v1/extract`, options)).status, 429);
    assert.equal(mock.requests.length, 2);
  } finally {
    server.closeAllConnections();
    await new Promise<void>((done) => server.close(() => done()));
  }
});

test('egress admits exactly two TLS authorities and rejects non-public DNS answers', async () => {
  for (const authority of [
    'localhost:443',
    '127.0.0.1:443',
    'api.openai.com:80',
    'api.openai.com.evil.example:443',
    'api.openai.com:443/path',
    'API.OPENAI.COM:443',
    '[::1]:443',
  ])
    assert.equal(inferenceTunnelHost(authority), undefined);
  assert.equal(inferenceTunnelHost('api.openai.com:443'), 'api.openai.com');
  assert.equal(inferenceTunnelHost('api.typesafe.ai:443'), 'api.typesafe.ai');
  for (const ip of [
    '127.0.0.1',
    '10.0.0.1',
    '169.254.169.254',
    '172.16.0.1',
    '192.168.1.1',
    '100.64.0.1',
    '::1',
    '::ffff:127.0.0.1',
    'fe80::1',
    'fc00::1',
    '2001:db8::1',
    '2002:7f00:1::',
  ])
    assert.equal(isPublicInferenceAddress(ip), false, ip);
  assert.equal(isPublicInferenceAddress('8.8.8.8'), true);
  assert.equal(isPublicInferenceAddress('2606:4700::1111'), true);
  const resolver = (async () => [{ address: '127.0.0.1', family: 4 }]) as unknown as Parameters<
    typeof createInferenceEgress
  >[0];
  const server = createInferenceEgress(resolver);
  const url = await listen(server);
  try {
    assert.equal((await fetch(`${url}/http://evil.example`)).status, 403);
    const status = await new Promise<number>((done, reject) => {
      const req = request(url, { method: 'CONNECT', path: 'api.openai.com:443' });
      req.on('connect', (res, socket) => {
        socket.destroy();
        done(res.statusCode ?? 0);
      });
      req.on('error', reject);
      req.end();
    });
    assert.equal(status, 403);
  } finally {
    await new Promise<void>((done) => server.close(() => done()));
  }
});

test('secrets require private files and client configuration cannot select an external gateway', () => {
  const folder = mkdtempSync(join(tmpdir(), 'normlab-inference-secret-'));
  try {
    const path = join(folder, 'test-key');
    writeFileSync(path, token + '\n', { mode: 0o400 });
    assert.equal(readInferenceSecret(path), token);
    const gateway = inferenceGatewayConfig({
      NORMLAB_INFERENCE_TOKEN_FILE: path,
      NORMLAB_OPENAI_API_KEY_FILE: path,
      NORMLAB_OPENAI_BASE_URL: 'https://hub.coreinfra.ai/codex/api/v1',
      NORMLAB_OPENAI_MODEL: 'vendor/model-alias',
    });
    assert.equal(gateway.endpoints.openai.url, 'https://hub.coreinfra.ai/codex/api/v1/responses');
    assert.equal(gateway.openaiModel, 'vendor/model-alias');
    chmodSync(path, 0o644);
    assert.throws(() => readInferenceSecret(path), /private file/);
    assert.throws(
      () =>
        inferenceClientConfig({
          NORMLAB_INFERENCE_MODE: 'gateway',
          NORMLAB_INFERENCE_GATEWAY_URL: 'https://evil.example',
        }),
      /internal/,
    );
    assert.deepEqual(inferenceClientConfig({ NORMLAB_INFERENCE_MODE: 'disabled' }), {
      mode: 'disabled',
    });
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test('provider failures and model-confirmed proposals cannot overwrite a parking review revision', async () => {
  const folder = mkdtempSync(join(tmpdir(), 'normlab-hosted-review-'));
  try {
    const api = new ParkingReview(folder, async () => {
      throw new Error(token);
    });
    const initial = await confirmedParkingDraft(api, narrative);
    await assert.rejects(
      api.handle('POST', '/api/parking/extract', {
        draftId: initial.draftId,
        expectedRevisionId: initial.revisionId,
      }),
      /прежняя ревизия сохранена/,
    );
    const history = await api.handle('GET', `/api/parking/history/${initial.draftId}`);
    assert.equal((history as unknown[]).length, 3);
    const invalid = new ParkingReview(folder, async () => ({
      pipeline: HOSTED_PIPELINE,
      sourceDigest: initial.sourceDigest,
      statements: [
        {
          id: randomUUID(),
          predicate: 'nlinput:payment',
          stance: 'asserted',
          subject: 'vehicle_1',
          aboutEpisode: 'episode_1',
          valueText: 'payment',
          quote: quotes[0],
          startOffset: 0,
          endOffset: quotes[0].length,
          origin: 'model',
          decision: 'confirmed',
          rationale: '',
        },
      ],
    }));
    await assert.rejects(
      invalid.handle('POST', '/api/parking/extract', {
        draftId: initial.draftId,
        expectedRevisionId: initial.revisionId,
      }),
      /проверки человеком/,
    );
    assert.equal(
      ((await invalid.handle('GET', `/api/parking/history/${initial.draftId}`)) as unknown[])
        .length,
      3,
    );
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test('extraction completing after a human edit preserves the newer review revision', async () => {
  const folder = mkdtempSync(join(tmpdir(), 'normlab-stale-hosted-review-'));
  try {
    let finish!: (value: unknown) => void;
    let started!: () => void;
    const running = new Promise<void>((resolve) => {
      started = resolve;
    });
    const api = new ParkingReview(folder, async () => {
      started();
      return await new Promise<unknown>((resolve) => {
        finish = resolve;
      });
    });
    const initial = await confirmedParkingDraft(api, narrative);
    const extraction = api.handle('POST', '/api/parking/extract', {
      draftId: initial.draftId,
      expectedRevisionId: initial.revisionId,
    });
    const rejected = assert.rejects(extraction, /Черновик изменился/);
    await running;
    const updated = reviewDraftSchema.parse(
      await api.handle('POST', '/api/parking/review', {
        draftId: initial.draftId,
        expectedRevisionId: initial.revisionId,
        statements: [],
        checklist: initial.checklist,
        finishReview: false,
      }),
    );
    finish(
      await runHostedExtraction(
        input,
        new InferenceProviders(config, mockFetch().fetcher),
        'openai',
        signal(),
      ),
    );
    await rejected;
    const history = (await api.handle('GET', `/api/parking/history/${initial.draftId}`)) as {
      revisionId: string;
    }[];
    assert.equal(history.length, initial.revision + 1);
    assert.equal(history[0].revisionId, updated.revisionId);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test('OpenAI stages use their own output limits and the digest covers every behavioural input', async () => {
  const mock = mockFetch();
  const result = await runHostedExtraction(
    input,
    new InferenceProviders(config, mock.fetcher),
    'openai',
    signal(),
  );
  assert.deepEqual(
    mock.requests.map((call) => call.body.max_output_tokens),
    [16384, 8192],
  );
  assert.ok((mock.requests[0].body.instructions as string).endsWith(prompts.discovery));
  // Pinned: prompts, inline prefixes, Jev template/criteria, schemas, batch size and request
  // settings all feed this value. Update with a versioned change and recorded verification;
  // historical evaluation captures keep their original digest.
  assert.equal(
    HOSTED_PROMPT_DIGEST,
    '16ebf6180f0072481cffe984cf58699ef110a01282f66522bccd28a839020723',
  );
  assert.equal(result.promptDigest, HOSTED_PROMPT_DIGEST);
  assert.notEqual(HOSTED_PROMPT_DIGEST, sourceDigest(JSON.stringify(prompts)));
});

function batchedFetcher(
  statements: string[],
  classify: (
    batch: { fragmentId: string; quote: string }[],
    signal: AbortSignal,
  ) => Promise<Response>,
) {
  let discovered = false;
  const fetcher: typeof fetch = async (_url, options) => {
    if (!discovered) {
      discovered = true;
      return openai({
        extractions: statements.map((statement) => ({
          statement,
          statement_attributes: discoveryOutput.extractions[0].statement_attributes,
        })),
      });
    }
    const body = JSON.parse(options?.body as string) as Record<string, unknown>;
    return classify(JSON.parse(body.input as string), options!.signal!);
  };
  return fetcher;
}
const classifiedBatch = (batch: { fragmentId: string; quote: string }[]) =>
  openai({
    results: Object.fromEntries(
      batch.map((fragment) => [
        fragment.fragmentId,
        {
          status: 'classified',
          reason: '',
          classifications: [
            { predicate: 'payment', stance: 'asserted', valueText: fragment.quote },
          ],
        },
      ]),
    ),
  });
const untilAborted = (abort: AbortSignal) =>
  new Promise<never>((_, reject) =>
    abort.addEventListener('abort', () => reject(new Error('aborted')), { once: true }),
  );

test('classification batches run with bounded concurrency and keep source order', async () => {
  const statements = Array.from({ length: 20 }, (_, i) => `Эпизод ${i + 1}: парковка оплачена.`);
  const source = statements.join(' ');
  let active = 0;
  let peak = 0;
  const fetcher = batchedFetcher(statements, async (batch) => {
    active++;
    peak = Math.max(peak, active);
    // Later batches finish first; results must still follow the source order.
    await new Promise((done) => setTimeout(done, 60 - Number(batch[0].fragmentId.slice(9)) * 2));
    active--;
    return classifiedBatch(batch);
  });
  const result = await runHostedExtraction(
    { narrative: source, sourceDigest: sourceDigest(source) },
    new InferenceProviders(config, fetcher),
    'openai',
    signal(),
  );
  assert.equal(peak, 3);
  assert.deepEqual(
    result.statements.map((s) => s.quote),
    statements,
  );
  assert.deepEqual(
    result.calls.map((call) =>
      call.stage === 'discovery'
        ? 'discovery'
        : (JSON.parse((call.request as { input: string }).input) as { fragmentId: string }[])[0]
            .fragmentId,
    ),
    ['discovery', 'fragment_1', 'fragment_9', 'fragment_17'],
  );
});

test('a failed classification batch cancels in-flight batches and starts no more', async () => {
  const statements = Array.from({ length: 25 }, (_, i) => `Эпизод ${i + 1}: парковка оплачена.`);
  const source = statements.join(' ');
  const started: string[] = [];
  const aborted: string[] = [];
  const fetcher = batchedFetcher(statements, async (batch, abort) => {
    const id = batch[0].fragmentId;
    started.push(id);
    if (id === 'fragment_9') {
      await new Promise((done) => setTimeout(done, 20));
      return new Response('{}', { status: 500 });
    }
    abort.addEventListener('abort', () => aborted.push(id), { once: true });
    return untilAborted(abort);
  });
  await assert.rejects(
    runHostedExtraction(
      { narrative: source, sourceDigest: sourceDigest(source) },
      new InferenceProviders(config, fetcher),
      'openai',
      signal(),
    ),
  );
  assert.deepEqual(started, ['fragment_1', 'fragment_9', 'fragment_17']);
  assert.deepEqual(aborted.sort(), ['fragment_1', 'fragment_17']);
});

test('hosted extraction rejects an over-limit narrative before calling the provider', async () => {
  const folder = mkdtempSync(join(tmpdir(), 'normlab-hosted-limit-'));
  try {
    let called = false;
    const api = new ParkingReview(folder, async () => {
      called = true;
      return {};
    });
    const draft = reviewDraftSchema.parse(
      await api.handle('POST', '/api/parking/drafts', {
        narrative: 'Я оплатил парковку. '.repeat(Math.ceil(HOSTED_MAX_NARRATIVE / 20) + 1),
      }),
    );
    await assert.rejects(
      api.handle('POST', '/api/parking/extract', {
        draftId: draft.draftId,
        expectedRevisionId: draft.revisionId,
      }),
      new RegExp(`до ${HOSTED_MAX_NARRATIVE} символов`),
    );
    assert.equal(called, false);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test('gateway transport tunnels through the configured proxy without global dispatcher state', async () => {
  const authorities: string[] = [];
  const proxy = createServer((_req, res) => res.writeHead(403).end());
  proxy.on('connect', (req, socket) => {
    authorities.push(req.url ?? '');
    socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n');
  });
  proxy.listen(0, '127.0.0.1');
  await once(proxy, 'listening');
  const address = proxy.address();
  assert.ok(address && typeof address !== 'string');
  try {
    const fetcher = proxiedFetch(`http://127.0.0.1:${address.port}`);
    await assert.rejects(fetcher(INFERENCE_DESTINATIONS.openai, { method: 'POST', body: '{}' }));
    assert.deepEqual(authorities, ['api.openai.com:443']);
  } finally {
    await new Promise<void>((done) => proxy.close(() => done()));
  }
});

test('egress dials only checked DNS answers and offers all of them for family fallback', () => {
  const addresses = [
    { address: '2606:4700::1111', family: 6 },
    { address: '8.8.8.8', family: 4 },
  ];
  const lookup = checkedLookup(addresses);
  const seen: unknown[] = [];
  lookup('api.openai.com', { all: true }, (_error, result) => seen.push(result));
  lookup('api.openai.com', {}, (_error, address, family) => seen.push([address, family]));
  assert.deepEqual(seen, [addresses, ['2606:4700::1111', 6]]);
});

const coreinfraBase = 'https://hub.coreinfra.ai/codex/api/v1';

test('operator base URLs preserve API prefixes and replace the exact proxy authority', () => {
  const endpoints = inferenceEndpoints({ NORMLAB_OPENAI_BASE_URL: coreinfraBase + '/' });
  assert.deepEqual(endpoints.openai, {
    baseUrl: coreinfraBase,
    url: coreinfraBase + '/responses',
    authority: 'hub.coreinfra.ai:443',
  });
  assert.equal(endpoints.typesafe.url, INFERENCE_DESTINATIONS.typesafe);
  assert.equal(inferenceTunnelHost('hub.coreinfra.ai:443', endpoints), 'hub.coreinfra.ai');
  for (const authority of [
    'api.openai.com:443',
    'hub.coreinfra.ai:80',
    'hub.coreinfra.ai.evil.example:443',
    'HUB.COREINFRA.AI:443',
  ])
    assert.equal(inferenceTunnelHost(authority, endpoints), undefined);
  const other = inferenceEndpoints({
    NORMLAB_TYPESAFE_BASE_URL: 'https://jev.provider.example/proxy/v1',
  });
  assert.equal(other.typesafe.url, 'https://jev.provider.example/proxy/v1/systemone');
  assert.equal(inferenceTunnelHost('api.typesafe.ai:443', other), undefined);
});

test('base URL configuration rejects credentials, IPs, redirects via paths and URL parameters without echoing values', () => {
  const forbidden = [
    'http://hub.coreinfra.ai/codex/api/v1',
    `https://operator:${token}@hub.coreinfra.ai/v1`,
    `https://hub.coreinfra.ai/v1?key=${token}`,
    'https://hub.coreinfra.ai/v1#fragment',
    'https://hub.coreinfra.ai:8443/v1',
    'https://127.0.0.1/v1',
    'https://2130706433/v1',
    'https://[::1]/v1',
    'https://localhost/v1',
    'https://hub.coreinfra.ai/a/../v1',
    'https://hub.coreinfra.ai/%2e%2e/v1',
    'https://hub.coreinfra.ai/v1//proxy',
    'https://hub.coreinfra.ai\\v1',
    coreinfraBase + '?',
    coreinfraBase + '#',
    ' ' + coreinfraBase,
  ];
  for (const base of forbidden)
    for (const setting of ['NORMLAB_OPENAI_BASE_URL', 'NORMLAB_TYPESAFE_BASE_URL'])
      assert.throws(
        () => inferenceEndpoints({ [setting]: base }),
        (error: Error) =>
          /Inference base URL/.test(error.message) && !error.message.includes(token),
      );
});

test('CoreInfra configuration controls adapter URL, Bearer key and recorded endpoint without changing request schema', async () => {
  const endpoints = inferenceEndpoints({ NORMLAB_OPENAI_BASE_URL: coreinfraBase });
  const requests: { url: string; body: Record<string, unknown> }[] = [];
  const fetcher: typeof fetch = async (url, options) => {
    assert.equal(url, endpoints.openai.url);
    assert.equal(new Headers(options?.headers).get('authorization'), `Bearer ${token}`);
    assert.equal(options?.redirect, 'error');
    requests.push({ url: String(url), body: JSON.parse(options?.body as string) });
    return openai(requests.length === 1 ? discoveryOutput : classificationOutput);
  };
  const result = await runHostedExtraction(
    input,
    new InferenceProviders({ ...config, endpoints }, fetcher),
    'openai',
    signal(),
  );
  assert.equal(requests.length, 2);
  assert.ok(requests.every((request) => request.url === coreinfraBase + '/responses'));
  assert.ok(
    requests.every(
      (request) =>
        (request.body.text as { format: { type: string } }).format.type === 'json_schema',
    ),
  );
  assert.ok(result.calls.every((call) => call.endpoint === endpoints.openai.url));
  assert.ok(!JSON.stringify(result).includes(token));
  assert.deepEqual(
    result.statements.map((s) => s.decision),
    ['pending', 'pending'],
  );
});

test('custom proxy authority still rejects private DNS answers before connecting', async () => {
  const endpoints = inferenceEndpoints({ NORMLAB_OPENAI_BASE_URL: coreinfraBase });
  const resolved: string[] = [];
  const resolver = (async (host: string) => {
    resolved.push(host);
    return [{ address: '127.0.0.1', family: 4 }];
  }) as unknown as Parameters<typeof createInferenceEgress>[0];
  const server = createInferenceEgress(resolver, endpoints);
  const url = await listen(server);
  try {
    for (const authority of ['hub.coreinfra.ai:443', 'api.openai.com:443']) {
      const status = await new Promise<number>((done, reject) => {
        const req = request(url, { method: 'CONNECT', path: authority });
        req.on('connect', (res, socket) => {
          socket.destroy();
          done(res.statusCode ?? 0);
        });
        req.on('error', reject);
        req.end();
      });
      assert.equal(status, 403);
    }
    assert.deepEqual(resolved, ['hub.coreinfra.ai']);
  } finally {
    await new Promise<void>((done) => server.close(() => done()));
  }
});
