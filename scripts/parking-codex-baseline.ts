import { spawn, execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import {
  createParkingTypedRequest,
  consumeParkingTypedExtraction,
} from '../server/parking-typed-extraction.js';
import { writeBaselineArtifactManifest } from './baseline-artifact-manifest.js';

const output = resolve(
  process.argv[2] ?? 'experiments/parking-baseline/2026-10-05-codex-gpt-6-luna-low',
);
mkdirSync(resolve(output, '..'), { recursive: true });
mkdirSync(output);
const save = (name: string, value: unknown) =>
  writeFileSync(resolve(output, name), `${JSON.stringify(value, null, 2)}\n`);
const sha256 = (text: string) => createHash('sha256').update(text, 'utf8').digest('hex');
const startedAt = new Date().toISOString();
const model = 'gpt-6-luna';
const timeoutMs = 240000;
const cases = ['P01', 'P02', 'P04', 'P09'];
const version = execFileSync('rtk', ['proxy', 'codex', '--version'], { encoding: 'utf8' }).trim();
const commonArgs = [
  'proxy',
  'codex',
  'exec',
  '--ignore-user-config',
  '--ignore-rules',
  '--ephemeral',
  '--skip-git-repo-check',
  '--sandbox',
  'read-only',
  '--json',
  '--color',
  'never',
  '-m',
  model,
  '-c',
  'model_reasoning_effort="low"',
  '-c',
  'project_doc_max_bytes=0',
  '-c',
  'features.shell_tool=false',
  '-c',
  'features.multi_agent=false',
  '-c',
  'web_search="disabled"',
];
save('run.json', {
  schema: 'normlab.parking-codex-baseline/v1',
  startedAt,
  model,
  reasoningEffort: 'low',
  version,
  timeoutMs,
  cases,
  commonArgs,
  runnerSha256: sha256(readFileSync(new URL(import.meta.url), 'utf8')),
  adapterSha256: sha256(
    readFileSync(new URL('../server/parking-typed-extraction.ts', import.meta.url), 'utf8'),
  ),
  decodeMode: 'prompt-only-no-output-schema',
  notes: [
    'Codex CLI surface, not a direct API model-only comparison: built-in system instructions remain.',
    'Fresh empty cwd per case; project docs disabled; no conversation history/reference graphs/reviewer notes supplied.',
    'Application instructions are part of the user prompt, unlike LM Studio system-role messages.',
    'Temperature, seed and output token cap are not matched to LM Studio.',
    'Tool events are checked after completion; any observed tool use invalidates the case comparison.',
    'Model and effort are requested settings; CLI events may not attest returned model identity.',
  ],
});
const outcomes: unknown[] = [];
for (const caseId of cases) {
  const source = readFileSync(
    new URL(`../fixtures/parking-pilot/reference/${caseId}.source.txt`, import.meta.url),
    'utf8',
  );
  const request = createParkingTypedRequest(`${caseId}-reference-v1`, source);
  const previous = JSON.parse(
    readFileSync(
      new URL(
        `../experiments/parking-baseline/2026-10-05-typed-quotes-gpt-oss-20b/${caseId}.request.json`,
        import.meta.url,
      ),
      'utf8',
    ),
  ) as {
    payload: { messages: { content: string }[] };
  };
  if (
    previous.payload.messages[0]?.content !== request.instructions ||
    previous.payload.messages[1]?.content !== request.modelInput
  )
    throw new Error(`Comparison input drift: ${caseId}`);
  const prompt = `${request.instructions}\n\n${request.modelInput}`;
  const cwd = mkdtempSync(resolve(tmpdir(), 'normlab-extraction-'));
  const contentPath = resolve(output, `${caseId}.content.txt`);
  const args = [...commonArgs, '-C', cwd, '-o', contentPath, '-'];
  save(`${caseId}.request.json`, {
    bindings: request.bindings,
    instructions: request.instructions,
    modelInput: request.modelInput,
    prompt,
    args,
  });
  const begin = performance.now();
  const processResult = await new Promise<{
    exitCode: number | null;
    signal: string | null;
    timedOut: boolean;
    error?: string;
    events: string;
    stderr: string;
  }>((done) => {
    const child = spawn('rtk', args, { cwd, stdio: ['pipe', 'pipe', 'pipe'] });
    let events = '',
      stderr = '',
      timedOut = false;
    let spawnError: string | undefined;
    child.stdout.setEncoding('utf8').on('data', (chunk: string) => {
      events += chunk;
    });
    child.stderr.setEncoding('utf8').on('data', (chunk: string) => {
      stderr += chunk;
    });
    child.on('error', (error) => {
      spawnError = error.message;
    });
    child.stdin.on('error', () => {
      /* Process failure is captured through close/error. */
    });
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill('SIGKILL');
    }, timeoutMs);
    child.on('close', (exitCode, signal) => {
      clearTimeout(timer);
      done({ exitCode, signal, timedOut, error: spawnError, events, stderr });
    });
    child.stdin.end(prompt);
  });
  writeFileSync(resolve(output, `${caseId}.events.jsonl`), processResult.events);
  writeFileSync(resolve(output, `${caseId}.stderr.txt`), processResult.stderr);
  let eventParseFailed = false;
  const events = processResult.events
    .split('\n')
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line) as { type?: string; item?: { type?: string }; usage?: unknown };
      } catch {
        eventParseFailed = true;
        return undefined;
      }
    })
    .filter((event): event is NonNullable<typeof event> => event !== undefined);
  const toolEvents = events.filter(
    (event) => event.item?.type && !['agent_message', 'reasoning'].includes(event.item.type),
  );
  const content = existsSync(contentPath) ? readFileSync(contentPath, 'utf8') : undefined;
  const validation =
    content === undefined ? undefined : consumeParkingTypedExtraction(content, request);
  const outcome = {
    caseId,
    latencyMs: Math.round(performance.now() - begin),
    exitCode: processResult.exitCode,
    signal: processResult.signal,
    timedOut: processResult.timedOut,
    error: processResult.error,
    toolEvents,
    usage: events.find((event) => event.type === 'turn.completed')?.usage,
    contentSha256: content === undefined ? undefined : sha256(content),
    status:
      processResult.exitCode !== 0 ||
      processResult.timedOut ||
      content === undefined ||
      eventParseFailed
        ? 'provider-or-cli-error'
        : toolEvents.length
          ? 'tool-contaminated'
          : validation?.ok
            ? 'structurally-valid'
            : 'rejected',
    validation,
  };
  save(`${caseId}.result.json`, outcome);
  outcomes.push(outcome);
  save('summary.json', { startedAt, updatedAt: new Date().toISOString(), outcomes });
  console.log(`${caseId}: ${outcome.status} (${outcome.latencyMs} ms)`);
  if (outcome.status === 'provider-or-cli-error') {
    console.log('Stopping after provider/CLI failure; remaining cases are unattempted.');
    break;
  }
}
writeBaselineArtifactManifest(output);
console.log(`Captured comparison: ${output}`);
