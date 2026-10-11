import { z } from 'zod';

const failureSchema = z
  .object({
    code: z.enum([
      'authentication',
      'endpoint',
      'rate_limit',
      'unavailable',
      'timeout',
      'network',
      'invalid_response',
      'rejected',
    ]),
    provider: z.enum(['openai', 'typesafe', 'openai-decisions', 'gateway']),
    stage: z.enum(['discovery', 'classification', 'extraction']),
    httpStatus: z.number().int().min(400).max(599).optional(),
  })
  .strict();
export type InferenceFailure = z.infer<typeof failureSchema>;
export type InferenceContext = Pick<InferenceFailure, 'provider' | 'stage'>;

/** Only allowlisted metadata may cross the gateway boundary. */
export class InferenceAccessError extends Error {
  readonly failure: InferenceFailure;
  constructor(failure: InferenceFailure) {
    super('Inference transport failed.');
    this.failure = failureSchema.parse(failure);
  }
}

export function parseInferenceFailure(value: unknown): InferenceFailure | undefined {
  const parsed = failureSchema.safeParse(value);
  return parsed.success ? parsed.data : undefined;
}

export function httpFailure(status: number): InferenceFailure['code'] {
  if (status === 401 || status === 403) return 'authentication';
  if (status === 404 || status === 405) return 'endpoint';
  if (status === 429) return 'rate_limit';
  if (status >= 500) return 'unavailable';
  return 'rejected';
}

export function inferenceFailureMessage(failure: InferenceFailure): string {
  const provider = {
    openai: 'API генерации (OpenAI-совместимый gateway)',
    typesafe: 'Jev / TypeSafe API',
    'openai-decisions': 'OpenAI Decisions API',
    gateway: 'Сервис инференса NormLab',
  }[failure.provider];
  const stage = {
    discovery: 'выделение фрагментов',
    classification: 'классификация утверждений',
    extraction: 'разбор фабулы',
  }[failure.stage];
  const reason = {
    authentication: 'доступ отклонён: требуется проверить ключ и права доступа',
    endpoint: 'endpoint недоступен: требуется проверить URL и поддержку API',
    rate_limit:
      'достигнут лимит запросов или квоты; повторите позже, администратору следует проверить квоту',
    unavailable: 'сервис временно недоступен; повторите позже',
    timeout: 'превышено время ожидания ответа; повторите позже',
    network: 'не удалось установить соединение; требуется проверить сеть и доступность API',
    invalid_response:
      'получен некорректный ответ API; требуется проверить совместимость провайдера',
    rejected: 'API отклонил запрос; требуется проверить конфигурацию',
  }[failure.code];
  return `${provider}: ${reason}${failure.httpStatus ? ` (HTTP ${failure.httpStatus})` : ''}. Этап: ${stage}.`;
}
