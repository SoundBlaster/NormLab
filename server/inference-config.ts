import { readFileSync, statSync } from 'node:fs';
import { isAbsolute } from 'node:path';
import { z } from 'zod';

/** Only paths enter configuration; credential values never enter env or diagnostics. */
export function readInferenceSecret(path: string | undefined): string {
  if (!path || !isAbsolute(path))
    throw new Error('Inference secret requires an absolute file path.');
  const stat = statSync(path);
  if (!stat.isFile() || stat.size > 8192 || (stat.mode & 0o077) !== 0)
    throw new Error('Inference secret must be a private file (0400 or 0600).');
  const value = readFileSync(path, 'utf8').replace(/\r?\n$/, '');
  if (!/^[\x21-\x7e]{32,8192}$/.test(value)) throw new Error('Invalid inference secret file.');
  return value;
}

export function inferenceClientConfig(env: NodeJS.ProcessEnv) {
  const mode = z
    .enum(['disabled', 'local', 'gateway'])
    .parse(env.NORMLAB_INFERENCE_MODE ?? 'local');
  if (mode !== 'gateway') return { mode };
  const url = env.NORMLAB_INFERENCE_GATEWAY_URL ?? 'http://normlab-inference-gateway:4318';
  if (!['http://normlab-inference-gateway:4318', 'http://127.0.0.1:4318'].includes(url))
    throw new Error('Inference gateway must use the dedicated internal service or local loopback.');
  return { mode, url, token: readInferenceSecret(env.NORMLAB_INFERENCE_TOKEN_FILE) };
}

export function inferenceGatewayConfig(env: NodeJS.ProcessEnv) {
  return {
    token: readInferenceSecret(env.NORMLAB_INFERENCE_TOKEN_FILE),
    openaiKey: readInferenceSecret(env.NORMLAB_OPENAI_API_KEY_FILE),
    openaiModel: z
      .string()
      .regex(/^[a-z0-9][a-z0-9._-]{0,99}$/)
      .parse(env.NORMLAB_OPENAI_MODEL ?? 'gpt-6-luna'),
    typesafeKey: env.NORMLAB_TYPESAFE_API_KEY_FILE
      ? readInferenceSecret(env.NORMLAB_TYPESAFE_API_KEY_FILE)
      : undefined,
    typesafeModel: z
      .string()
      .regex(/^jev-[a-z0-9.-]+$/)
      .parse(env.NORMLAB_TYPESAFE_MODEL ?? 'jev-1.13.0'),
    classifier: z.enum(['openai', 'typesafe']).parse(env.NORMLAB_INFERENCE_CLASSIFIER ?? 'openai'),
    requestsPerHour: z.coerce
      .number()
      .int()
      .min(1)
      .max(60)
      .parse(env.NORMLAB_INFERENCE_REQUESTS_PER_HOUR ?? '6'),
  };
}
export type InferenceGatewayConfig = ReturnType<typeof inferenceGatewayConfig>;
