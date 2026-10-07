import assert from 'node:assert/strict';
import test from 'node:test';
import { once } from 'node:events';
import { randomUUID } from 'node:crypto';
import { mkdtempSync, rmSync, writeFileSync, chmodSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { request } from 'node:http';
import prompts from '../server/inference-prompts.json';
import { InferenceProviders, INFERENCE_DESTINATIONS } from '../server/inference-providers.js';
import { runHostedExtraction, sourceDigest, HOSTED_PIPELINE } from '../server/hosted-extraction.js';
import { createInferenceGateway } from '../server/inference-gateway.js';
import {
  createInferenceEgress,
  inferenceTunnelHost,
  isPublicInferenceAddress,
} from '../server/inference-egress.js';
import { readInferenceSecret, inferenceClientConfig } from '../server/inference-config.js';
import { readBoundedJson } from '../server/inference-http.js';
import { ParkingReview } from '../server/parking-review.js';
import { reviewDraftSchema } from '../shared/parking-review.js';

const token = 'test-only-credential-not-a-real-key-0000000000';
const config = {
  token,
  openaiKey: token,
  openaiModel: 'gpt-6-luna',
  typesafeKey: token,
  typesafeModel: 'jev-1.13.0',
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

test('provider rejects incomplete, refusal, invalid distributions and transport errors without leaking bodies', async () => {
  const incomplete: typeof fetch = async () => response({ status: 'incomplete' });
  await assert.rejects(
    new InferenceProviders(config, incomplete).structured('test', '', '', {}, [], signal()),
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
    new InferenceProviders(config, refusal).structured('test', '', '', {}, [], signal()),
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
    new InferenceProviders(config, failed).structured('test', '', '', {}, [], signal()),
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
      1,
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
    const initial = reviewDraftSchema.parse(
      await api.handle('POST', '/api/parking/drafts', { narrative }),
    );
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
    assert.equal(history.length, 2);
    assert.equal(history[0].revisionId, updated.revisionId);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});
