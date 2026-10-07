import assert from 'node:assert/strict';
import test from 'node:test';
import { InferenceProviders } from '../server/inference-providers.js';
import { inferenceEndpoints } from '../server/inference-endpoints.js';
import {
  runHostedExtraction,
  sourceDigest,
  HOSTED_DECISIONS_PIPELINE,
  HOSTED_DECISIONS_PROMPT_DIGEST,
  HOSTED_PROMPT_DIGEST,
} from '../server/hosted-extraction.js';

const token = 'test-only-credential-not-a-real-key-0000000000';
const base = 'https://hub.coreinfra.ai/codex/api/v1';
const config = {
  endpoints: inferenceEndpoints({ NORMLAB_OPENAI_BASE_URL: base }),
  token,
  openaiKey: token,
  openaiModel: 'responses-alias',
  decisionsModel: 'gpt-6-luna',
  typesafeKey: undefined,
  typesafeModel: 'jev-1.13.0',
  classifier: 'decisions' as const,
  requestsPerHour: 1,
};
const source = 'Парковка оплачена. В письме: парковка не оплачена. Оплата мне неизвестна.';
const quotes = ['Парковка оплачена.', 'В письме: парковка не оплачена.', 'Оплата мне неизвестна.'];
const input = { narrative: source, sourceDigest: sourceDigest(source) };
const json = (body: unknown) =>
  new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
type WireAnswer = {
  name: string;
  type: string;
  choice: string;
  confidence: number;
  probabilities: { value: string; probability: number }[];
};

function mock(mutate: (answers: WireAnswer[]) => unknown[] = (answers) => answers) {
  const requests: Record<string, unknown>[] = [];
  const fetcher: typeof fetch = async (url, options) => {
    const address = typeof url === 'string' ? url : url instanceof URL ? url.href : url.url;
    assert.equal(new Headers(options?.headers).get('authorization'), `Bearer ${token}`);
    assert.equal(options?.redirect, 'error');
    const body = JSON.parse(options?.body as string);
    requests.push(body);
    if (address === base + '/responses') {
      assert.equal(body.model, 'responses-alias');
      return json({
        id: 'test',
        model: body.model,
        status: 'completed',
        usage: { input_tokens: 1, output_tokens: 1 },
        output: [
          {
            type: 'message',
            status: 'completed',
            content: [
              {
                type: 'output_text',
                text: JSON.stringify({
                  extractions: quotes.map((statement, i) => ({
                    statement,
                    statement_attributes: {
                      subject: 'vehicle_1',
                      aboutEpisode: 'episode_1',
                      speaker: i === 1 ? 'letter_1' : 'narrator',
                    },
                  })),
                }),
              },
            ],
          },
        ],
      });
    }
    assert.equal(address, base + '/decisions');
    assert.equal(body.model, 'gpt-6-luna');
    assert.equal(typeof body.input, 'string');
    assert.equal(JSON.parse(body.input).length, 3);
    assert.deepEqual(Object.keys(body).sort(), ['input', 'model', 'questions']);
    const answers = body.questions.map(
      (question: {
        name: string;
        type: string;
        instructions: string;
        choices: { value: string; description: string }[];
      }) => {
        assert.equal(question.type, 'choice');
        assert.match(question.instructions, /untrusted.*Preserve/);
        assert.deepEqual(
          question.choices.map((option) => option.value),
          ['asserted', 'denied', 'unknown', 'unsupported'],
        );
        const choice = question.name.endsWith('_payment')
          ? ['asserted', 'denied', 'unknown'][Number(question.name.split('_')[1]) - 1]
          : 'unsupported';
        return {
          name: question.name,
          type: 'choice',
          choice,
          confidence: 0.01,
          probabilities: question.choices.map(({ value }) => ({
            value,
            probability: value === choice ? 0.4 : 0.2,
          })),
        };
      },
    );
    return json({
      model: body.model,
      usage: { input_tokens: 1, output_tokens: 1 },
      answers: mutate(answers),
    });
  };
  return { fetcher, requests };
}

test('Decisions classifier preserves opposing/unknown quotes, low confidence and pending human review through CoreInfra', async () => {
  const fixture = mock((answers) => answers.reverse());
  const result = await runHostedExtraction(
    input,
    new InferenceProviders(config, fixture.fetcher),
    'decisions',
    AbortSignal.timeout(10000),
  );
  assert.equal(result.pipeline, HOSTED_DECISIONS_PIPELINE);
  assert.equal(result.promptDigest, HOSTED_DECISIONS_PROMPT_DIGEST);
  assert.notEqual(result.promptDigest, HOSTED_PROMPT_DIGEST);
  assert.equal(result.valueTextMethod, 'exact-source-quote');
  assert.deepEqual(
    result.statements.map((s) => [s.stance, s.quote, s.valueText, s.speaker, s.decision]),
    quotes.map((quote, i) => [
      ['asserted', 'denied', 'unknown'][i],
      quote,
      quote,
      i === 1 ? 'letter_1' : 'narrator',
      'pending',
    ]),
  );
  for (const statement of result.statements)
    assert.equal(source.slice(statement.startOffset, statement.endOffset), statement.quote);
  assert.equal(result.calls[1].provider, 'openai-decisions');
  assert.equal(result.calls[1].endpoint, base + '/decisions');
  assert.ok(!JSON.stringify(result).includes(token));
  assert.equal(fixture.requests.length, 2);
  assert.match(JSON.stringify(result.decisions), /confidence/);
});

test('Decisions rejects refusals, wrong names/types, incomplete or duplicate answers and invalid probability vectors', async () => {
  const invalid: ((answers: WireAnswer[]) => unknown[])[] = [
    (a) => [{ name: a[0].name, type: 'refusal' }, ...a.slice(1)],
    (a) => a.slice(1),
    (a) => [a[0], a[0], ...a.slice(2)],
    (a) => [{ ...a[0], name: 'unrequested' }, ...a.slice(1)],
    (a) => [{ ...a[0], name: null }, ...a.slice(1)],
    (a) => [{ ...a[0], type: 'predicate' }, ...a.slice(1)],
    (a) => [{ ...a[0], choice: 'invented' }, ...a.slice(1)],
    (a) => [{ ...a[0], confidence: 2 }, ...a.slice(1)],
    (a) => [{ ...a[0], probabilities: a[0].probabilities.slice(1) }, ...a.slice(1)],
    (a) => [{ ...a[0], probabilities: Array(4).fill(a[0].probabilities[0]) }, ...a.slice(1)],
    (a) => [
      { ...a[0], probabilities: a[0].probabilities.map((p) => ({ ...p, probability: 0.1 })) },
      ...a.slice(1),
    ],
  ];
  for (const mutate of invalid) {
    const fixture = mock(mutate);
    await assert.rejects(
      runHostedExtraction(
        input,
        new InferenceProviders(config, fixture.fetcher),
        'decisions',
        AbortSignal.timeout(10000),
      ),
    );
  }
});

test('Decisions question bounds fail before transport and incomplete responses never record partial calls', async () => {
  const fixture = mock();
  const provider = new InferenceProviders(config, fixture.fetcher);
  const question = { type: 'choice' as const, instructions: 'test', criteria: {} };
  await assert.rejects(
    provider.decisions({}, {}, [], AbortSignal.timeout(10000)),
    /question count/,
  );
  await assert.rejects(
    provider.decisions(
      {},
      Object.fromEntries(Array.from({ length: 121 }, (_, i) => [String(i), question])),
      [],
      AbortSignal.timeout(10000),
    ),
    /question count/,
  );
  assert.equal(fixture.requests.length, 0);
  const calls: Parameters<InferenceProviders['decisions']>[2] = [];
  const broken: typeof fetch = async () =>
    json({ model: 'gpt-6-luna', usage: { input_tokens: 1, output_tokens: 1 }, answers: [] });
  await assert.rejects(
    new InferenceProviders(config, broken).decisions(
      {},
      { expected: question },
      calls,
      AbortSignal.timeout(10000),
    ),
  );
  assert.deepEqual(calls, []);
});
