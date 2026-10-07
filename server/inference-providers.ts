import { z } from 'zod';
import { inferencePost } from './inference-http.js';
import type { InferenceGatewayConfig } from './inference-config.js';
import { DEFAULT_INFERENCE_ENDPOINTS } from './inference-endpoints.js';
import { decisionsChoices } from './inference-decisions.js';

export const INFERENCE_DESTINATIONS = Object.freeze({
  openai: DEFAULT_INFERENCE_ENDPOINTS.openai.url,
  typesafe: DEFAULT_INFERENCE_ENDPOINTS.typesafe.url,
});
/** Discovery quotes the whole source; reasoning tokens also count against this limit. */
export const OPENAI_REQUEST_SETTINGS = Object.freeze({
  reasoning: { effort: 'low' },
  maxOutputTokens: { discovery: 16384, classification: 8192 },
});
export type StructuredStage = keyof typeof OPENAI_REQUEST_SETTINGS.maxOutputTokens;
export type InferenceCall = {
  provider: 'openai' | 'typesafe' | 'openai-decisions';
  endpoint: string;
  stage: string;
  model: string;
  request: unknown;
  response: unknown;
};
const usage = z
  .object({
    input_tokens: z.number().int().nonnegative(),
    output_tokens: z.number().int().nonnegative(),
  })
  .passthrough();
const openaiResponse = z.object({
  id: z.string(),
  model: z.string(),
  status: z.literal('completed'),
  usage,
  output: z.array(
    z.object({
      type: z.string(),
      status: z.string().optional(),
      content: z.array(z.object({ type: z.string(), text: z.string().optional() })).optional(),
    }),
  ),
});
const probability = z.number().min(0).max(1);
export const choiceAnswer = z.object({
  type: z.literal('choice'),
  choice: z.enum(['asserted', 'denied', 'unknown', 'unsupported']),
  probabilities: z
    .object({
      asserted: probability,
      denied: probability,
      unknown: probability,
      unsupported: probability,
    })
    .strict(),
  confidence: probability,
});
export const typesafeResponse = z.object({
  model: z.string(),
  usage,
  answers: z.record(z.string(), choiceAnswer),
});
export type TypeSafeQuestion = {
  type: 'choice';
  instructions: string;
  criteria: Record<string, string>;
};

export class InferenceProviders {
  constructor(
    private readonly config: InferenceGatewayConfig,
    private readonly fetcher: typeof fetch = fetch,
  ) {
    if (config.classifier === 'typesafe' && !config.typesafeKey)
      throw new Error('TypeSafe classifier requires its secret file.');
  }
  async structured(
    stage: StructuredStage,
    instructions: string,
    input: string,
    schema: unknown,
    calls: InferenceCall[],
    signal: AbortSignal,
  ): Promise<unknown> {
    const request = {
      model: this.config.openaiModel,
      store: false,
      instructions,
      input,
      reasoning: OPENAI_REQUEST_SETTINGS.reasoning,
      max_output_tokens: OPENAI_REQUEST_SETTINGS.maxOutputTokens[stage],
      text: { format: { type: 'json_schema', name: stage, strict: true, schema } },
    };
    const response = openaiResponse.parse(
      await inferencePost(
        this.config.endpoints.openai.url,
        this.config.openaiKey,
        request,
        signal,
        this.fetcher,
      ),
    );
    const messages = response.output.filter((item) => item.type === 'message');
    if (
      response.output.some((item) => !['message', 'reasoning'].includes(item.type)) ||
      messages.length !== 1 ||
      messages[0].status !== 'completed'
    )
      throw new Error('Unexpected OpenAI output.');
    const content = messages[0].content;
    if (!content || content.length !== 1 || content[0].type !== 'output_text' || !content[0].text)
      throw new Error('Incomplete or refused OpenAI output.');
    calls.push({
      provider: 'openai',
      endpoint: this.config.endpoints.openai.url,
      stage,
      model: response.model,
      request,
      response,
    });
    return JSON.parse(content[0].text) as unknown;
  }
  async choices(
    state: unknown,
    questions: Record<string, TypeSafeQuestion>,
    calls: InferenceCall[],
    signal: AbortSignal,
  ) {
    if (!this.config.typesafeKey) throw new Error('TypeSafe provider is disabled.');
    const request = { model: this.config.typesafeModel, state, questions };
    const response = typesafeResponse.parse(
      await inferencePost(
        this.config.endpoints.typesafe.url,
        this.config.typesafeKey,
        request,
        signal,
        this.fetcher,
      ),
    );
    const expected = Object.keys(questions).sort();
    if (JSON.stringify(expected) !== JSON.stringify(Object.keys(response.answers).sort()))
      throw new Error('Incomplete TypeSafe answers.');
    for (const answer of Object.values(response.answers)) {
      const probabilities = Object.values(answer.probabilities);
      if (
        Math.abs(probabilities.reduce((a, b) => a + b, 0) - 1) > 0.001 ||
        answer.probabilities[answer.choice] < Math.max(...probabilities) - 0.000001
      )
        throw new Error('Invalid TypeSafe probability distribution.');
    }
    calls.push({
      provider: 'typesafe',
      endpoint: this.config.endpoints.typesafe.url,
      stage: 'classification',
      model: response.model,
      request,
      response,
    });
    return response.answers;
  }
  async decisions(
    state: unknown,
    questions: Record<string, TypeSafeQuestion>,
    calls: InferenceCall[],
    signal: AbortSignal,
  ) {
    return decisionsChoices(this.config, state, questions, calls, signal, this.fetcher);
  }
}
