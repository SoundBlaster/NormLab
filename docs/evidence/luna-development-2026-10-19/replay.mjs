// Offline replay of all saved HTTP responses through the same frozen hosted bundle.
import { readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';

const [repoArg, buildArg, captureArg, reportArg] = process.argv.slice(2);
const repo = resolve(repoArg),
  build = resolve(buildArg),
  capture = resolve(captureArg);
const hash = (bytes) => createHash('sha256').update(bytes).digest('hex');
const json = (path) => JSON.parse(readFileSync(path, 'utf8'));
const state = json(join(capture, 'run.json'));
const authority = json(join(capture, 'authority.json'));
assert.equal(hash(readFileSync(join(build, 'runtime.mjs'))), authority.runtime.bundleSha256);
assert.equal(hash(readFileSync(join(capture, 'authority.json'))), state.authoritySha256);
assert.equal(state.status, 'completed');
assert.equal(state.attempts.length, 20);
assert.equal(state.cases.length, 10);
assert.equal(state.attemptsWithUnknownUsage, 0);
globalThis.fetch = () => {
  throw new Error('Network forbidden during replay.');
};
const { runHostedExtraction, InferenceProviders, inferenceEndpoints } = await import(
  pathToFileURL(join(build, 'runtime.mjs'))
);
let replayRequests = 0;
let quoteAnchors = 0;
let fragments = 0;
const canonical = (result) => {
  const copy = structuredClone(result);
  delete copy.latencyMs;
  for (const statement of copy.statements) delete statement.id;
  return copy;
};
const records = [];
for (const item of state.cases) {
  assert.equal(item.status, 'completed');
  const expected = json(join(capture, item.resultPath));
  const input = json(join(repo, item.inputPath));
  assert.equal(hash(input.narrative), input.sourceDigest);
  assert.equal(expected.sourceDigest, input.sourceDigest);
  const attempts = state.attempts.filter((attempt) => attempt.caseId === item.id);
  assert.equal(attempts.length, 2);
  let cursor = 0;
  const fetcher = async (url, init) => {
    assert.equal(url, authority.strategy.endpoint);
    const attempt = attempts[cursor++];
    assert.ok(attempt, 'Unexpected additional request.');
    assert.equal(attempt.outcome, 'http-complete');
    assert.equal(attempt.httpStatus, 200);
    assert.deepEqual(JSON.parse(init.body), json(join(capture, attempt.requestPath)));
    const bytes = readFileSync(join(capture, attempt.responsePath));
    assert.equal(hash(bytes), attempt.responseSha256);
    replayRequests++;
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
  const actual = await runHostedExtraction(
    input,
    new InferenceProviders(config, fetcher),
    'openai',
    new AbortController().signal,
  );
  assert.equal(cursor, attempts.length);
  assert.deepEqual(canonical(actual), canonical(expected));
  for (const statement of expected.statements) {
    assert.equal(
      input.narrative.slice(statement.startOffset, statement.endOffset),
      statement.quote,
    );
    assert.equal(statement.origin, 'model');
    assert.equal(statement.decision, 'pending');
    quoteAnchors++;
  }
  for (const fragment of expected.fragments) {
    assert.equal(input.narrative.slice(fragment.startOffset, fragment.endOffset), fragment.quote);
    fragments++;
  }
  records.push({
    id: item.id,
    status: 'replay-equal',
    statements: expected.statements.length,
    fragments: expected.fragments.length,
  });
}
const report = {
  schema: 'normlab.one-off-hosted-replay/v1',
  status: 'pass',
  liveCalls: 0,
  network: 'global fetch forbidden; injected transport returns archived bytes only',
  replayRequests,
  compared:
    'all result fields including calls/decisions/fragments; exclude only new statement UUIDs and latencyMs',
  quoteAnchors,
  fragments,
  records,
};
writeFileSync(reportArg, JSON.stringify(report, null, 2) + '\n', { mode: 0o600 });
console.log(
  JSON.stringify({
    status: report.status,
    replayCases: records.length,
    replayRequests,
    liveCalls: 0,
    quoteAnchors,
    fragments,
  }),
);
