import { z } from 'zod';
import type { InferenceGatewayConfig } from './inference-config.js';
import type { InferenceCall, TypeSafeQuestion } from './inference-providers.js';
import { inferencePost } from './inference-http.js';

export const DECISIONS_SETTINGS = Object.freeze({
  resource: 'decisions',
  choices: ['asserted', 'denied', 'unknown', 'unsupported'] as const,
  maxQuestions: 120,
  inputMethod: 'json-string',
});
const stance = z.enum(DECISIONS_SETTINGS.choices);
const probability = z.number().min(0).max(1);
const choice = z.object({
  type: z.literal('choice'),
  name: z.string().min(1),
  choice: stance,
  confidence: probability,
  probabilities: z.array(z.object({ value: stance, probability })).length(4),
});
const responseSchema = z.object({
  model: z.string().min(1),
  usage: z
    .object({
      input_tokens: z.number().int().nonnegative(),
      output_tokens: z.number().int().nonnegative(),
    })
    .passthrough(),
  // A refusal, predicate or score is never converted into a stance.
  answers: z.array(choice).min(1).max(DECISIONS_SETTINGS.maxQuestions),
});
type Answer = {
  type: 'choice';
  choice: z.infer<typeof stance>;
  confidence: number;
  probabilities: Record<z.infer<typeof stance>, number>;
};

/** Dedicated Decisions wire contract; discovery continues to use Responses. */
export async function decisionsChoices(
  config: InferenceGatewayConfig,
  state: unknown,
  questions: Record<string, TypeSafeQuestion>,
  calls: InferenceCall[],
  signal: AbortSignal,
  fetcher: typeof fetch,
): Promise<Record<string, Answer>> {
  const names = Object.keys(questions);
  if (!names.length || names.length > DECISIONS_SETTINGS.maxQuestions)
    throw new Error('Decisions question count outside limits.');
  const request = {
    model: config.decisionsModel,
    input: JSON.stringify(state),
    questions: names.map((name) => ({
      name,
      type: 'choice',
      instructions: questions[name].instructions,
      choices: DECISIONS_SETTINGS.choices.map((value) => ({
        value,
        description: questions[name].criteria[value],
      })),
    })),
  };
  const endpoint = `${config.endpoints.openai.baseUrl}/${DECISIONS_SETTINGS.resource}`;
  const response = responseSchema.parse(
    await inferencePost(endpoint, config.openaiKey, request, signal, fetcher, 120000, {
      provider: 'openai-decisions',
      stage: 'classification',
    }),
  );
  const seen = new Set<string>();
  const answers: Record<string, Answer> = Object.create(null) as Record<string, Answer>;
  for (const answer of response.answers) {
    if (!Object.hasOwn(questions, answer.name) || seen.has(answer.name))
      throw new Error('Unexpected or duplicate Decisions answer.');
    seen.add(answer.name);
    if (
      new Set(answer.probabilities.map((entry) => entry.value)).size !== 4 ||
      Math.abs(answer.probabilities.reduce((sum, entry) => sum + entry.probability, 0) - 1) > 0.001
    )
      throw new Error('Invalid Decisions probability distribution.');
    answers[answer.name] = {
      type: 'choice',
      choice: answer.choice,
      confidence: answer.confidence,
      probabilities: Object.fromEntries(
        answer.probabilities.map((entry) => [entry.value, entry.probability]),
      ) as Answer['probabilities'],
    };
  }
  if (seen.size !== names.length) throw new Error('Incomplete Decisions answers.');
  calls.push({
    provider: 'openai-decisions',
    endpoint,
    stage: 'classification',
    model: response.model,
    request,
    response,
  });
  return answers;
}
