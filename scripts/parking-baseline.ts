import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
  createParkingExtractionRequest,
  consumeParkingExtraction,
} from '../server/parking-extraction.js';

const baseUrl = 'http://127.0.0.1:1234';
const model = 'openai/gpt-oss-20b';
const output = resolve(process.argv[2] ?? 'experiments/parking-baseline/2026-10-04-gpt-oss-20b');
mkdirSync(resolve(output, '..'), { recursive: true });
// Never replace prior evidence. Use a fresh directory for a new run.
mkdirSync(output);
const save = (name: string, value: unknown) =>
  writeFileSync(resolve(output, name), `${JSON.stringify(value, null, 2)}\n`);
const sha256 = (text: string) => createHash('sha256').update(text, 'utf8').digest('hex');
const settings = { model, temperature: 0, seed: 42, max_tokens: 8192, stream: false };
const timeoutMs = 240000;
const startedAt = new Date().toISOString();
const environmentResponse = await fetch(`${baseUrl}/api/v0/models`, {
  signal: AbortSignal.timeout(10000),
});
const environmentRaw = await environmentResponse.text();
writeFileSync(resolve(output, 'server-models.json'), environmentRaw);
save('run.json', {
  schema: 'normlab.parking-baseline-run/v1',
  startedAt,
  baseUrl,
  settings,
  timeoutMs,
  decodeMode: 'prompt-only-json-no-provider-grammar',
  cases: ['P01', 'P02', 'P04', 'P09'],
  notes: [
    'Settings are requested, not proof of deterministic decoding.',
    'Only source text and common instructions/schema sent; no reference graphs or reviewer notes.',
  ],
});
const outcomes: unknown[] = [];
for (const caseId of ['P01', 'P02', 'P04', 'P09']) {
  const source = readFileSync(
    new URL(`../fixtures/parking-pilot/reference/${caseId}.source.txt`, import.meta.url),
    'utf8',
  );
  const request = createParkingExtractionRequest(`${caseId}-reference-v1`, source);
  const payload = {
    ...settings,
    messages: [
      { role: 'system', content: request.instructions },
      { role: 'user', content: request.modelInput },
    ],
  };
  save(`${caseId}.request.json`, { bindings: request.bindings, payload });
  const begin = performance.now();
  let outcome: unknown;
  try {
    const response = await fetch(`${baseUrl}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(timeoutMs),
    });
    const raw = await response.text();
    writeFileSync(resolve(output, `${caseId}.response.json`), raw);
    const latencyMs = Math.round(performance.now() - begin);
    if (!response.ok) {
      outcome = {
        caseId,
        status: 'provider-error',
        httpStatus: response.status,
        latencyMs,
        responseSha256: sha256(raw),
      };
    } else {
      const data = JSON.parse(raw) as {
        choices?: { message?: { content?: string | null }; finish_reason?: string }[];
        usage?: unknown;
        model?: string;
      };
      const content = data.choices?.[0]?.message?.content;
      if (typeof content !== 'string') outcome = { caseId, status: 'missing-content', latencyMs };
      else {
        writeFileSync(resolve(output, `${caseId}.content.txt`), content);
        const validation = consumeParkingExtraction(content, request);
        outcome = {
          caseId,
          status: validation.ok ? 'structurally-valid' : 'rejected',
          latencyMs,
          returnedModel: data.model,
          usage: data.usage,
          finishReason: data.choices?.[0]?.finish_reason,
          responseSha256: sha256(raw),
          contentSha256: sha256(content),
          validation,
        };
      }
    }
  } catch (error) {
    outcome = {
      caseId,
      status: 'transport-or-response-error',
      latencyMs: Math.round(performance.now() - begin),
      error: error instanceof Error ? error.message : String(error),
    };
  }
  save(`${caseId}.result.json`, outcome);
  outcomes.push(outcome);
  save('summary.json', { startedAt, updatedAt: new Date().toISOString(), outcomes });
  console.log(`${caseId}: saved result (${Math.round(performance.now() - begin)} ms)`);
}
console.log(`Baseline completed: ${output}`);
