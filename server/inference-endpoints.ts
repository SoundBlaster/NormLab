import { isIP } from 'node:net';

export type InferenceEndpoint = Readonly<{
  baseUrl: string;
  url: string;
  authority: string;
}>;
export type InferenceEndpoints = Readonly<{
  openai: InferenceEndpoint;
  typesafe: InferenceEndpoint;
}>;

/** Operator configuration only. Errors never echo a URL that might contain a credential. */
function endpoint(base: string, resource: string): InferenceEndpoint {
  const invalid = () =>
    new Error(
      'Inference base URL requires HTTPS, a DNS host, port 443 and a plain API path; credentials, queries and fragments are forbidden.',
    );
  let parsed: URL;
  try {
    parsed = new URL(base);
  } catch {
    throw invalid();
  }
  if (
    base !== base.trim() ||
    /[\\%?#]/.test(base) ||
    /\/\.\.?(?:\/|$)/.test(base) ||
    parsed.protocol !== 'https:' ||
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash ||
    (parsed.port && parsed.port !== '443') ||
    isIP(parsed.hostname) ||
    parsed.hostname.length > 253 ||
    !/^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(
      parsed.hostname,
    ) ||
    !/^\/[A-Za-z0-9._~/-]*$/.test(parsed.pathname) ||
    parsed.pathname.includes('//')
  )
    throw invalid();
  const baseUrl = parsed.origin + parsed.pathname.replace(/\/$/, '');
  return Object.freeze({
    baseUrl,
    url: `${baseUrl}/${resource}`,
    authority: `${parsed.hostname}:443`,
  });
}

/** Both gateway and egress independently derive their policy from the same Compose values. */
export function inferenceEndpoints(env: NodeJS.ProcessEnv = {}): InferenceEndpoints {
  return Object.freeze({
    openai: endpoint(env.NORMLAB_OPENAI_BASE_URL ?? 'https://api.openai.com/v1', 'responses'),
    typesafe: endpoint(env.NORMLAB_TYPESAFE_BASE_URL ?? 'https://api.typesafe.ai/v1', 'systemone'),
  });
}
export const DEFAULT_INFERENCE_ENDPOINTS = inferenceEndpoints();
