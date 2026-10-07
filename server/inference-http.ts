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
): Promise<unknown> {
  try {
    const response = await fetcher(url, {
      method: 'POST',
      redirect: 'error',
      signal: AbortSignal.any([signal, AbortSignal.timeout(timeoutMs)]),
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      await response.body?.cancel();
      throw new Error('Inference request rejected.');
    }
    return await readBoundedJson(response);
  } catch {
    // Fetch exceptions can include URLs; upstream errors can contain source text or secrets.
    throw new Error('Inference transport failed.');
  }
}
