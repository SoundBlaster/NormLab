import { confirmedParkingDraft } from './parking-context-fixture.js';
import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { once } from 'node:events';
import { inferencePost } from '../server/inference-http.js';
import { InferenceAccessError, inferenceFailureMessage } from '../server/inference-errors.js';
import { createInferenceGateway } from '../server/inference-gateway.js';
import { DEFAULT_INFERENCE_ENDPOINTS } from '../server/inference-endpoints.js';
import { ParkingReview, ParkingReviewError } from '../server/parking-review.js';

const context = { provider: 'typesafe', stage: 'classification' } as const;
const token = 'test-credential-must-never-reach-the-user';
const signal = () => new AbortController().signal;

test('provider HTTP failures keep safe status and discard body, URL and credential', async () => {
  for (const [status, code] of [
    [401, 'authentication'],
    [403, 'authentication'],
    [402, 'quota'],
    [404, 'endpoint'],
    [405, 'endpoint'],
    [429, 'rate_limit'],
    [502, 'unavailable'],
    [400, 'rejected'],
  ] as const) {
    let calls = 0;
    const fetcher: typeof fetch = async () => {
      calls++;
      return new Response(`${token} private narrative`, { status });
    };
    await assert.rejects(
      inferencePost('https://secret.example/private', token, {}, signal(), fetcher, 1000, context),
      (error: unknown) => {
        assert.ok(error instanceof InferenceAccessError);
        assert.deepEqual(error.failure, { ...context, code, httpStatus: status });
        const message = inferenceFailureMessage(error.failure);
        assert.match(message, /Jev \/ TypeSafe API/);
        assert.match(message, /классификация/);
        assert.ok(!JSON.stringify(error).includes(token));
        assert.ok(!message.includes('private'));
        return true;
      },
    );
    assert.equal(calls, 1);
  }
});

test('network, deadline and malformed responses have distinct safe reasons', async () => {
  const network: typeof fetch = async () => {
    throw new Error(token);
  };
  const malformed: typeof fetch = async () => new Response(token);
  const timed: typeof fetch = async (_url, options) =>
    new Promise((_resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('fixture did not abort')), 1000);
      options?.signal?.addEventListener(
        'abort',
        () => {
          clearTimeout(timer);
          reject(new Error(token));
        },
        { once: true },
      );
    });
  for (const [fetcher, code] of [
    [network, 'network'],
    [malformed, 'invalid_response'],
    [timed, 'timeout'],
  ] as const) {
    await assert.rejects(
      inferencePost('https://example.test', token, {}, signal(), fetcher, 10, context),
      (error: unknown) => error instanceof InferenceAccessError && error.failure.code === code,
    );
  }
});

test('only trusted gateway metadata is parsed, and unknown fields are rejected', async () => {
  const safe = { ...context, code: 'authentication', httpStatus: 401 };
  const fetcher: typeof fetch = async () =>
    Response.json({ inferenceFailure: safe }, { status: 503 });
  await assert.rejects(
    inferencePost('http://gateway', token, {}, signal(), fetcher, 1000, undefined, true),
    (error: unknown) =>
      error instanceof InferenceAccessError && error.failure.provider === 'typesafe',
  );
  await assert.rejects(
    inferencePost('https://provider', token, {}, signal(), fetcher),
    (error: unknown) =>
      error instanceof InferenceAccessError &&
      error.failure.provider === 'gateway' &&
      error.failure.code === 'unavailable',
  );
  const malicious: typeof fetch = async () =>
    Response.json({ inferenceFailure: { ...safe, secret: token } }, { status: 503 });
  await assert.rejects(
    inferencePost('http://gateway', token, {}, signal(), malicious, 1000, undefined, true),
    (error: unknown) =>
      error instanceof InferenceAccessError &&
      error.failure.provider === 'gateway' &&
      !JSON.stringify(error).includes(token),
  );
});

test('provider failure crosses actual gateway and review API without changing the draft', async () => {
  const config = {
    endpoints: DEFAULT_INFERENCE_ENDPOINTS,
    token,
    openaiKey: token,
    openaiModel: 'gpt-6-luna',
    typesafeKey: token,
    typesafeModel: 'jev-1.13.0',
    decisionsModel: 'gpt-6-luna',
    classifier: 'typesafe' as const,
    requestsPerHour: 6,
  };
  const server = createInferenceGateway(config, async () => new Response(token, { status: 401 }));
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const address = server.address();
  assert.ok(address && typeof address !== 'string');
  const url = `http://127.0.0.1:${address.port}/v1/extract`;
  const folder = mkdtempSync(join(tmpdir(), 'normlab-api-failure-'));
  try {
    const api = new ParkingReview(folder, (input) =>
      inferencePost(url, token, input, signal(), fetch, 1000, undefined, true),
    );
    const created = await confirmedParkingDraft(api, 'Парковка не оплачена.');
    await assert.rejects(
      api.handle('POST', '/api/parking/extract', {
        draftId: created.draftId,
        expectedRevisionId: created.revisionId,
      }),
      (error: unknown) => {
        assert.ok(error instanceof ParkingReviewError);
        assert.equal(error.status, 503);
        assert.match(error.message, /ключ и права доступа/);
        assert.match(error.message, /HTTP 401/);
        assert.match(error.message, /выделение фрагментов/);
        assert.match(error.message, /Ручная разметка доступна/);
        assert.ok(!error.message.includes(token));
        return true;
      },
    );
    assert.equal(
      ((await api.handle('GET', `/api/parking/history/${created.draftId}`)) as unknown[]).length,
      3,
    );
    const failure = new InferenceAccessError({
      ...context,
      code: 'authentication',
      httpStatus: 403,
    });
    const jevApi = new ParkingReview(folder, async () => {
      throw failure;
    });
    await assert.rejects(
      jevApi.handle('POST', '/api/parking/extract', {
        draftId: created.draftId,
        expectedRevisionId: created.revisionId,
      }),
      /Jev \/ TypeSafe API/,
    );
  } finally {
    server.closeAllConnections();
    await new Promise<void>((resolve) => server.close(() => resolve()));
    rmSync(folder, { recursive: true, force: true });
  }
});
