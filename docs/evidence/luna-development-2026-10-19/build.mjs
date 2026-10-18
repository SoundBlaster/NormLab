// One-off build for the authorized ten-case experiment; no provider calls.
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve, relative, join } from 'node:path';
import { createHash } from 'node:crypto';

const [repoArg, dependencyArg, outputArg] = process.argv.slice(2);
if (!repoArg || !dependencyArg || !outputArg)
  throw new Error('Expected repo, node_modules, build directory.');
const repo = resolve(repoArg);
const dependencies = resolve(dependencyArg);
const output = resolve(outputArg);
const require = createRequire(join(dependencies, 'esbuild/package.json'));
const esbuild = require('esbuild');
const hash = (bytes) => createHash('sha256').update(bytes).digest('hex');
mkdirSync(output, { recursive: true, mode: 0o700 });
const result = await esbuild.build({
  absWorkingDir: repo,
  stdin: {
    contents: [
      "export {runHostedExtraction, HOSTED_PROMPT_DIGEST} from './server/hosted-extraction.ts';",
      "export {InferenceProviders} from './server/inference-providers.ts';",
      "export {inferenceEndpoints} from './server/inference-endpoints.ts';",
      "export {InferenceAccessError} from './server/inference-errors.ts';",
    ].join('\n'),
    resolveDir: repo,
    sourcefile: 'luna-development-entry.ts',
  },
  bundle: true,
  platform: 'node',
  format: 'esm',
  target: 'node26',
  nodePaths: [dependencies],
  outfile: join(output, 'runtime.mjs'),
  metafile: true,
  legalComments: 'inline',
});
const bindings = Object.keys(result.metafile.inputs)
  .filter((path) => path !== 'luna-development-entry.ts')
  .sort()
  .map((path) => ({
    path: relative(repo, resolve(repo, path)),
    sha256: hash(readFileSync(resolve(repo, path))),
  }));
const driver = 'docs/evidence/luna-development-2026-10-19/driver.mjs';
const packet = 'fixtures/parking-pilot/luna-development-pilot-v1';
const plan = JSON.parse(readFileSync(join(repo, packet, 'plan.json')));
const extraPaths = [
  driver,
  'docs/evidence/luna-development-2026-10-19/build.mjs',
  `${packet}/plan.json`,
  ...Object.keys(plan.sourceBindings),
  ...plan.inputs.map((item) => item.path),
  ...['selection', 'rubric', 'reviewerOnly', 'worksheet'].map((key) => plan[key].path),
];
for (const path of extraPaths)
  if (!bindings.some((item) => item.path === path))
    bindings.push({ path, sha256: hash(readFileSync(join(repo, path))) });
const authority = {
  schema: 'normlab.one-off-hosted-execution/v1',
  preparedAt: new Date().toISOString(),
  authorization: {
    user: 'Платный прогон разрешаю',
    dateMsk: '2026-10-19',
    maximumAttempts: 30,
    maximumSeriesSeconds: 900,
    maximumCaseSeconds: 300,
    retries: 0,
    repair: 0,
    judge: 0,
    userReportedExternalCeilingUsd: 4,
    externalCeilingIndependentlyVerified: false,
    pricingVerified: false,
    interpretation:
      'Existing account ceiling remains in force; no claim that runner enforces dollars or knows price.',
  },
  planPath: `${packet}/plan.json`,
  strategy: plan.strategy,
  runtime: {
    node: process.version,
    executableSha256: hash(readFileSync(process.execPath)),
    esbuild: esbuild.version,
    bundleSha256: hash(readFileSync(join(output, 'runtime.mjs'))),
    importsBundled: true,
    externalImports:
      result.metafile.outputs[relative(repo, join(output, 'runtime.mjs'))]?.imports ?? [],
  },
  bindings,
};
writeFileSync(join(output, 'authority.json'), JSON.stringify(authority, null, 2) + '\n', {
  mode: 0o600,
});
writeFileSync(join(output, 'metafile.json'), JSON.stringify(result.metafile, null, 2) + '\n', {
  mode: 0o600,
});
console.log(
  JSON.stringify({
    build: 'complete-no-inference',
    sourceBindings: bindings.length,
    node: process.version,
    esbuild: esbuild.version,
    bundleSha256: authority.runtime.bundleSha256,
  }),
);
