import { z } from 'zod';

/** Public diagnostics contain only allowlisted metadata, never provider text. */
export const inferenceFailureSchema = z
  .object({
    code: z.enum([
      'authentication',
      'endpoint',
      'rate_limit',
      'quota',
      'unavailable',
      'timeout',
      'network',
      'invalid_response',
      'rejected',
    ]),
    provider: z.enum(['openai', 'typesafe', 'openai-decisions', 'gateway']),
    stage: z.enum(['discovery', 'classification', 'extraction', 'context', 'legal-proposal']),
    httpStatus: z.number().int().min(400).max(599).optional(),
  })
  .strict();
export type InferenceFailure = z.infer<typeof inferenceFailureSchema>;

export function inferenceFailureMessage(failure: InferenceFailure): string {
  const provider = {
    openai: 'API генерации (OpenAI-совместимый gateway)',
    typesafe: 'Jev / TypeSafe API',
    'openai-decisions': 'OpenAI Decisions API',
    gateway: 'Сервис инференса NormLab',
  }[failure.provider];
  const stage = {
    context: 'определение контекста',
    'legal-proposal': 'подготовка юридических обстоятельств',
    discovery: 'выделение фрагментов',
    classification: 'классификация утверждений',
    extraction: 'разбор фабулы',
  }[failure.stage];
  const reason = {
    authentication: 'доступ отклонён: требуется проверить ключ и права доступа',
    endpoint: 'endpoint недоступен: требуется проверить URL и поддержку API',
    rate_limit:
      'достигнут лимит запросов или квоты; повторите позже, администратору следует проверить квоту',
    quota: 'API требует оплаты; администратору следует проверить баланс и доступный тариф',
    unavailable: 'сервис временно недоступен; повторите позже',
    timeout: 'превышено время ожидания ответа',
    network: 'соединение прервано; требуется проверить сеть и доступность API',
    invalid_response:
      'получен некорректный ответ API; требуется проверить совместимость провайдера',
    rejected: 'API отклонил запрос; требуется проверить конфигурацию',
  }[failure.code];
  return `${provider}: ${reason}${failure.httpStatus ? ` (HTTP ${failure.httpStatus})` : ''}. Этап: ${stage}.`;
}
