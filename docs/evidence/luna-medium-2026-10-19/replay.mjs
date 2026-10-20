// Offline control/replay only. No actual provider transport is available.
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';
const [mode, repoArg, buildArg, captureArg, reportArg] = process.argv.slice(2);
assert.ok(['baseline-control', 'medium-replay'].includes(mode));
const repo = resolve(repoArg),
  build = resolve(buildArg),
  capture = resolve(captureArg);
const json = (path) => JSON.parse(readFileSync(path, 'utf8'));
const hash = (bytes) => createHash('sha256').update(bytes).digest('hex');
const authority = json(join(repo, 'docs/evidence/luna-medium-2026-10-19/authority.json'));
const state = json(join(capture, 'run.json'));
assert.equal(hash(readFileSync(join(build, 'runtime.mjs'))), authority.runtime.bundleSha256);
globalThis.fetch = () => {
  throw new Error('Real network forbidden.');
};
const { runHostedExtraction, InferenceProviders, inferenceEndpoints, HOSTED_PROMPT_DIGEST } =
  await import(pathToFileURL(join(build, 'runtime.mjs')));
assert.equal(HOSTED_PROMPT_DIGEST, authority.runtime.promptDigest);
const canonical = (value) => {
  const result = structuredClone(value);
  delete result.latencyMs;
  for (const statement of result.statements) delete statement.id;
  return result;
};
let requests = 0,
  statements = 0,
  fragments = 0;
const records = [];
for (const item of state.cases.filter((item) => item.status === 'completed')) {
  const input = json(join(repo, item.inputPath));
  const saved = json(join(capture, item.resultPath));
  const attempts = state.attempts.filter((attempt) => attempt.caseId === item.id);
  let cursor = 0;
  const fetcher = async (url, init) => {
    assert.equal(url, authority.strategy.endpoint);
    const attempt = attempts[cursor++];
    assert.ok(attempt);
    const expectedRequest = json(join(capture, attempt.requestPath));
    if (mode === 'baseline-control') expectedRequest.reasoning.effort = 'medium';
    assert.equal(JSON.parse(init.body).reasoning.effort, 'medium');
    assert.deepEqual(JSON.parse(init.body), expectedRequest);
    const bytes = readFileSync(join(capture, attempt.responsePath));
    assert.equal(hash(bytes), attempt.responseSha256);
    assert.equal(attempt.httpStatus, 200);
    requests++;
    return new Response(bytes, { status: 200 });
  };
  const config = {
    endpoints: inferenceEndpoints({
      NORMLAB_OPENAI_BASE_URL: 'https://hub.coreinfra.ai/openai/api/v1',
    }),
    token: 'unused',
    openaiKey: 'offline-placeholder-never-sent',
    openaiModel: 'gpt-6-luna',
    typesafeModel: 'unused',
    decisionsModel: 'unused',
    classifier: 'openai',
    requestsPerHour: 1,
  };
  const result = await runHostedExtraction(
    input,
    new InferenceProviders(config, fetcher),
    'openai',
    new AbortController().signal,
  );
  const expected = structuredClone(saved);
  if (mode === 'baseline-control') {
    expected.promptDigest = HOSTED_PROMPT_DIGEST;
    for (const call of expected.calls) call.request.reasoning.effort = 'medium';
  }
  assert.equal(cursor, attempts.length);
  assert.deepEqual(canonical(result), canonical(expected));
  for (const statement of result.statements) {
    assert.equal(
      input.narrative.slice(statement.startOffset, statement.endOffset),
      statement.quote,
    );
    assert.equal(statement.origin, 'model');
    assert.equal(statement.decision, 'pending');
    statements++;
  }
  for (const fragment of result.fragments) {
    assert.equal(input.narrative.slice(fragment.startOffset, fragment.endOffset), fragment.quote);
    fragments++;
  }
  records.push({
    id: item.id,
    status: 'equal',
    statements: result.statements.length,
    fragments: result.fragments.length,
  });
}
const report = {
  schema: 'normlab.one-off-medium-replay/v1',
  mode,
  status: 'pass',
  liveCalls: 0,
  network: 'Real fetch forbidden; archived responses only',
  requests,
  statements,
  fragments,
  promptDigest: HOSTED_PROMPT_DIGEST,
  comparison:
    mode === 'baseline-control'
      ? 'All archived low request bodies differ only at reasoning.effort. Same saved bytes processed equivalently, except expected promptDigest/request effort and fresh UUIDs/latency.'
      : 'Entire captured medium results equal; excludes only fresh statement UUIDs and measured latency.',
  records,
};
writeFileSync(reportArg, JSON.stringify(report, null, 2) + '\n', { mode: 0o600 });
console.log(
  JSON.stringify({
    mode,
    status: 'pass',
    cases: records.length,
    requests,
    statements,
    fragments,
    liveCalls: 0,
  }),
);
