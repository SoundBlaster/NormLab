import { inferenceFailureSchema, type InferenceFailure } from '../shared/inference-failure.js';
export { inferenceFailureMessage, type InferenceFailure } from '../shared/inference-failure.js';

export type InferenceContext = Pick<InferenceFailure, 'provider' | 'stage'>;

/** Only allowlisted metadata may cross the gateway boundary. */
export class InferenceAccessError extends Error {
  readonly failure: InferenceFailure;
  constructor(failure: InferenceFailure) {
    super('Inference transport failed.');
    this.failure = inferenceFailureSchema.parse(failure);
  }
}

export function parseInferenceFailure(value: unknown): InferenceFailure | undefined {
  const parsed = inferenceFailureSchema.safeParse(value);
  return parsed.success ? parsed.data : undefined;
}

export function httpFailure(status: number): InferenceFailure['code'] {
  if (status === 401 || status === 403) return 'authentication';
  if (status === 404 || status === 405) return 'endpoint';
  if (status === 402) return 'quota';
  if (status === 429) return 'rate_limit';
  if (status >= 500) return 'unavailable';
  return 'rejected';
}
