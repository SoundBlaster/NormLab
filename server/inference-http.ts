import {
  InferenceAccessError,
  httpFailure,
  parseInferenceFailure,
  type InferenceContext,
} from './inference-errors.js';

export const MAX_INFERENCE_RESPONSE_BYTES = 4 * 1024 * 1024;

export async function readBoundedJson(
  response: Response,
  limit = MAX_INFERENCE_RESPONSE_BYTES,
): Promise<unknown> {
  if (!response.body) throw new Error('Missing inference response.');
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let bytes = 0;
  try {
    for (;;) {
      const part = await reader.read();
      if (part.done) break;
      bytes += part.value.length;
      if (bytes > limit) throw new Error('Inference response exceeded its limit.');
      chunks.push(part.value);
    }
    return JSON.parse(
      new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(chunks)),
    ) as unknown;
  } finally {
    await reader.cancel();
    reader.releaseLock();
  }
}

/** No retries, redirects, user-provided destinations, or provider error bodies. */
export async function inferencePost(
  url: string,
  token: string,
  body: unknown,
  signal: AbortSignal,
  fetcher: typeof fetch = fetch,
  timeoutMs = 120000,
  context: InferenceContext = { provider: 'gateway', stage: 'extraction' },
  trustedGateway = false,
): Promise<unknown> {
  const deadline = AbortSignal.any([signal, AbortSignal.timeout(timeoutMs)]);
  try {
    const response = await fetcher(url, {
      method: 'POST',
      redirect: 'error',
      signal: deadline,
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      if (trustedGateway) {
        try {
          const envelope = await readBoundedJson(response, 4096);
          const failure = parseInferenceFailure(
            envelope && typeof envelope === 'object' && 'inferenceFailure' in envelope
              ? envelope.inferenceFailure
              : undefined,
          );
          if (failure) throw new InferenceAccessError(failure);
        } catch (error) {
          if (error instanceof InferenceAccessError) throw error;
        }
      } else await response.body?.cancel();
      throw new InferenceAccessError({
        ...context,
        code: httpFailure(response.status),
        httpStatus: response.status,
      });
    }
    try {
      return await readBoundedJson(response);
    } catch (error) {
      if (deadline.aborted) throw error;
      throw new InferenceAccessError({ ...context, code: 'invalid_response' });
    }
  } catch (error) {
    if (error instanceof InferenceAccessError) throw error;
    // Fetch exceptions can include URLs; upstream errors can contain source text or secrets.
    throw new InferenceAccessError({ ...context, code: deadline.aborted ? 'timeout' : 'network' });
  }
}
