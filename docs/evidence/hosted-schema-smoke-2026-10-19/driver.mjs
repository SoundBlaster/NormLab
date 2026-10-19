// One-shot supervisor around the unchanged hosted entry point. No retries or repair.
import { readFileSync, writeFileSync, renameSync, mkdirSync, statSync } from 'node:fs';
import { resolve, join, basename } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';

const [mode, repoArg, buildArg, outputArg] = process.argv.slice(2);
if (!['dry-run', 'live'].includes(mode) || !repoArg || !buildArg || !outputArg)
  throw new Error('Expected dry-run/live, repo, build, new output directory.');
const repo = resolve(repoArg),
  build = resolve(buildArg),
  output = resolve(outputArg);
const hash = (bytes) => createHash('sha256').update(bytes).digest('hex');
const readJson = (path) => JSON.parse(readFileSync(path, 'utf8'));
const authorityPath = join(repo, 'docs/evidence/hosted-schema-smoke-2026-10-19/authority.json');
const authorityBytes = readFileSync(authorityPath);
const authority = JSON.parse(authorityBytes);
const plan = readJson(join(repo, authority.planPath));
const bundlePath = join(build, 'runtime.mjs');
const key = mode === 'live' ? process.env.COREINFRA_API_KEY : undefined;
const limits = authority.authorization;
const verify = () => {
  if (
    hash(readFileSync(authorityPath)) !== hash(authorityBytes) ||
    process.version !== authority.runtime.node ||
    hash(readFileSync(process.execPath)) !== authority.runtime.executableSha256 ||
    hash(readFileSync(bundlePath)) !== authority.runtime.bundleSha256
  )
    throw new Error('Runtime drift.');
  for (const binding of authority.bindings)
    if (hash(readFileSync(resolve(repo, binding.path))) !== binding.sha256)
      throw new Error('Source drift.');
  for (const item of plan.inputs) {
    const bytes = readFileSync(join(repo, item.path));
    const dto = JSON.parse(bytes);
    if (
      hash(bytes) !== item.sha256 ||
      Object.keys(dto).sort().join(',') !== 'narrative,sourceDigest' ||
      dto.narrative.length > 8000 ||
      hash(dto.narrative) !== dto.sourceDigest
    )
      throw new Error('Input drift.');
  }
  if (
    limits.maximumAttempts !== 2 ||
    limits.retries !== 0 ||
    limits.repair !== 0 ||
    limits.judge !== 0 ||
    plan.inputs.length !== 1 ||
    limits.maximumSeriesSeconds !== 300 ||
    limits.maximumCaseSeconds !== 300 ||
    limits.userReportedExternalCeilingUsd !== 4 ||
    authority.strategy.endpoint !== 'https://hub.coreinfra.ai/openai/api/v1/responses' ||
    authority.strategy.requestedModel !== 'gpt-6-luna' ||
    authority.strategy.reasoningEffort !== 'low' ||
    authority.runtime.externalImports.some((item) => !item.path.startsWith('node:'))
  )
    throw new Error('Authority mismatch.');
};
verify();
const {
  runHostedExtraction,
  InferenceProviders,
  inferenceEndpoints,
  InferenceAccessError,
  HOSTED_PROMPT_DIGEST,
} = await import(pathToFileURL(bundlePath));
if (HOSTED_PROMPT_DIGEST !== plan.expectedPromptDigest) throw new Error('Prompt/schema drift.');
if (mode === 'dry-run') {
  console.log(
    JSON.stringify({
      status: 'dry-run-pass',
      providerCalls: 0,
      cases: plan.inputs.length,
      promptDigest: HOSTED_PROMPT_DIGEST,
      boundFiles: authority.bindings.length,
    }),
  );
  process.exit(0);
}
if (!key || key.trim() !== key || !/^[\x21-\x7e]{32,8192}$/.test(key))
  throw new Error('Credential unavailable or malformed.');
if (execFileSync('git', ['status', '--porcelain'], { cwd: repo, encoding: 'utf8' }).trim())
  throw new Error('Execution requires a clean committed tree.');
mkdirSync(output, { mode: 0o700 }); // Existing directory prevents accidental replay.
if ((statSync(output).mode & 0o077) !== 0) throw new Error('Output must be private.');
const write = (name, value, raw = false) => {
  const bytes = raw ? Buffer.from(value) : Buffer.from(JSON.stringify(value, null, 2) + '\n');
  if (bytes.includes(Buffer.from(key)))
    throw new Error('Credential reflection; artifact withheld.');
  const path = join(output, name);
  writeFileSync(path + '.tmp', bytes, { mode: 0o600 });
  renameSync(path + '.tmp', path);
};
const started = Date.now();
const series = new AbortController();
const deadline = AbortSignal.timeout(limits.maximumSeriesSeconds * 1000);
const attempts = [],
  pending = new Set();
const state = {
  schema: 'normlab.one-off-hosted-run/v1',
  status: 'running',
  startedAt: new Date(started).toISOString(),
  executionCommit: execFileSync('git', ['rev-parse', 'HEAD'], {
    cwd: repo,
    encoding: 'utf8',
  }).trim(),
  authoritySha256: hash(authorityBytes),
  runtime: authority.runtime,
  promptDigest: HOSTED_PROMPT_DIGEST,
  cases: plan.inputs.map((item) => ({
    id: basename(item.path, '.json'),
    inputPath: item.path,
    status: 'not-executed',
  })),
  attempts,
  stopReason: null,
  humanCorrectionSessions: 0,
  activeHumanReviewSeconds: null,
  costUsd: null,
};
const checkpoint = () => write('run.json', state);
write('authority.json', authority);
write('preparation-plan.json', plan);
checkpoint();
let currentCase;
const nativeFetch = globalThis.fetch;
const fetcher = (url, init) => {
  verify();
  const request = JSON.parse(init.body);
  if (
    series.signal.aborted ||
    deadline.aborted ||
    init.signal.aborted ||
    attempts.length >= limits.maximumAttempts ||
    url !== authority.strategy.endpoint ||
    init.method !== 'POST' ||
    init.redirect !== 'error' ||
    request.model !== authority.strategy.requestedModel ||
    request.reasoning?.effort !== 'low' ||
    !['discovery', 'classification'].includes(request.text?.format?.name) ||
    request.store !== false
  )
    throw new Error('Pre-dispatch stop.');
  const stage = request.text.format.name;
  if (request.max_output_tokens !== (stage === 'discovery' ? 16384 : 8192))
    throw new Error('Request settings drift.');
  const number = attempts.length + 1;
  const prefix = `attempt-${String(number).padStart(2, '0')}`;
  const attempt = {
    number,
    caseId: currentCase.id,
    stage,
    outcome: 'dispatching-unknown',
    startedAt: new Date().toISOString(),
    requestPath: `${prefix}.request.json`,
    responsePath: null,
    httpStatus: null,
    usage: null,
  };
  write(attempt.requestPath, request);
  attempts.push(attempt);
  checkpoint(); // Reserve before dispatch, including under parallel classification workers.
  const operation = (async () => {
    const chunks = [];
    let reader;
    try {
      const response = await nativeFetch(url, init);
      attempt.httpStatus = response.status;
      attempt.providerRequestId = response.headers.get('x-request-id');
      reader = response.body?.getReader();
      let bytes = 0;
      if (reader)
        for (;;) {
          const part = await reader.read();
          if (part.done) break;
          if (bytes + part.value.length > 4 * 1024 * 1024) throw new Error('Response size bound.');
          chunks.push(part.value);
          bytes += part.value.length;
        }
      const raw = Buffer.concat(chunks);
      write(`${prefix}.response.txt`, raw, true);
      attempt.responsePath = `${prefix}.response.txt`;
      attempt.responseSha256 = hash(raw);
      attempt.outcome = 'http-complete';
      try {
        const envelope = JSON.parse(raw.toString('utf8'));
        attempt.usage = envelope.usage ?? null;
        attempt.returnedModel = envelope.model ?? null;
        attempt.providerResponseId = envelope.id ?? null;
      } catch {
        /* Existing provider parser determines validity. */
      }
      return new Response(raw, { status: response.status, headers: response.headers });
    } catch {
      attempt.outcome = 'transport-or-capture-failure-unknown';
      if (chunks.length) {
        write(`${prefix}.partial.txt`, Buffer.concat(chunks), true);
        attempt.partialResponsePath = `${prefix}.partial.txt`;
      }
      throw new Error('Bounded transport failed.');
    } finally {
      if (reader) {
        await reader.cancel().catch(() => {});
        reader.releaseLock();
      }
      attempt.finishedAt = new Date().toISOString();
      checkpoint();
    }
  })();
  pending.add(operation);
  operation.then(
    () => pending.delete(operation),
    () => pending.delete(operation),
  );
  return operation;
};
const config = {
  endpoints: inferenceEndpoints({
    NORMLAB_OPENAI_BASE_URL: 'https://hub.coreinfra.ai/openai/api/v1',
  }),
  token: 'unused-direct-local-entry',
  openaiKey: key,
  openaiModel: authority.strategy.requestedModel,
  typesafeModel: 'unused',
  decisionsModel: 'unused',
  classifier: 'openai',
  requestsPerHour: 1,
};
const providers = new InferenceProviders(config, fetcher);
for (const item of state.cases) {
  currentCase = item;
  item.status = 'running';
  const before = attempts.length;
  checkpoint();
  try {
    verify();
    const input = readJson(join(repo, item.inputPath));
    const signal = AbortSignal.any([
      series.signal,
      deadline,
      AbortSignal.timeout(limits.maximumCaseSeconds * 1000),
    ]);
    const result = await runHostedExtraction(input, providers, 'openai', signal);
    item.resultPath = `${item.id}.result.json`;
    write(item.resultPath, result);
    item.status = 'completed';
    item.statements = result.statements.length;
    item.fragments = result.fragments.length;
  } catch (error) {
    series.abort();
    await Promise.allSettled([...pending]);
    item.status = 'operational-or-protocol-failure';
    item.failure =
      error instanceof InferenceAccessError
        ? error.failure
        : {
            code: error?.name === 'ZodError' ? 'schema-invalid' : 'pipeline-or-authority-rejected',
            issues:
              error?.name === 'ZodError'
                ? error.issues.map(({ path, code }) => ({ path, code }))
                : undefined,
          };
    state.stopReason = 'first-operational-protocol-unknown-or-authority-failure';
  }
  item.providerAttempts = attempts.length - before;
  checkpoint();
  console.log(
    JSON.stringify({
      case: item.id,
      status: item.status,
      attempts: attempts.length,
      statements: item.statements ?? null,
    }),
  );
  if (state.stopReason) break;
}
await Promise.allSettled([...pending]);
state.status = state.stopReason ? 'stopped' : 'completed';
state.finishedAt = new Date().toISOString();
state.elapsedMs = Date.now() - started;
state.knownTokens = attempts.reduce(
  (sum, attempt) => ({
    input: sum.input + (attempt.usage?.input_tokens ?? 0),
    output: sum.output + (attempt.usage?.output_tokens ?? 0),
  }),
  { input: 0, output: 0 },
);
state.attemptsWithUnknownUsage = attempts.filter((attempt) => !attempt.usage).length;
checkpoint();
console.log(
  JSON.stringify({
    status: state.status,
    attempts: attempts.length,
    completedCases: state.cases.filter((item) => item.status === 'completed').length,
    knownTokens: state.knownTokens,
    unknownUsage: state.attemptsWithUnknownUsage,
    elapsedMs: state.elapsedMs,
  }),
);
