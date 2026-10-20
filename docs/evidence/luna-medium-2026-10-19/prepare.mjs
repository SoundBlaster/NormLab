// One-off medium arm: reuse the frozen hosted source and bounded low supervisor.
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve, join, relative } from 'node:path';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';

const [repoArg, dependenciesArg, outputArg] = process.argv.slice(2);
assert.ok(
  repoArg && dependenciesArg && outputArg,
  'Expected repo, node_modules, new build directory.',
);
const repo = resolve(repoArg),
  dependencies = resolve(dependenciesArg),
  output = resolve(outputArg);
const hash = (bytes) => createHash('sha256').update(bytes).digest('hex');
const read = (path) => readFileSync(join(repo, path));
const oldDir = 'docs/evidence/luna-development-2026-10-19';
const newDir = 'docs/evidence/luna-medium-2026-10-19';
const low = JSON.parse(read(`${oldDir}/authority.json`));
for (const binding of low.bindings)
  assert.equal(hash(read(binding.path)), binding.sha256, binding.path);
assert.equal(
  hash(read(`${oldDir}/evidence.zip`)),
  'da81366eb21084af19183410210ae9f3e3d51e1b3a12163cd2502f6e915d295a',
);
assert.equal(process.version, low.runtime.node);
assert.equal(hash(readFileSync(process.execPath)), low.runtime.executableSha256);
mkdirSync(output, { mode: 0o700 }); // Never replace a prior prepared runtime.
const require = createRequire(join(dependencies, 'esbuild/package.json'));
const esbuild = require('esbuild');
assert.equal(esbuild.version, low.runtime.esbuild);
const sourcePath = 'server/inference-providers.ts';
const original = read(sourcePath).toString('utf8');
const replaceOnce = (text, from, to) => {
  assert.equal(text.split(from).length, 2, `Unique expected transformation missing: ${from}`);
  return text.replace(from, to);
};
const effective = replaceOnce(
  original,
  "reasoning: { effort: 'low' },",
  "reasoning: { effort: 'medium' },",
);
writeFileSync(join(output, 'effective-inference-providers.ts'), effective, { mode: 0o600 });
const options = {
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
  write: false,
};
const control = await esbuild.build(options);
assert.equal(
  hash(control.outputFiles[0].contents),
  low.runtime.bundleSha256,
  'Regenerated low bundle must equal original; no provider call.',
);
const built = await esbuild.build({
  ...options,
  plugins: [
    {
      name: 'one-effort-literal',
      setup(build) {
        build.onLoad({ filter: /\/server\/inference-providers\.ts$/ }, (args) => {
          assert.equal(args.path, join(repo, sourcePath));
          return { contents: effective, loader: 'ts', resolveDir: join(repo, 'server') };
        });
      },
    },
  ],
});
writeFileSync(join(output, 'runtime.mjs'), built.outputFiles[0].contents, { mode: 0o600 });
const imports = built.metafile.outputs[relative(repo, join(output, 'runtime.mjs'))].imports;
assert.deepEqual(imports, low.runtime.externalImports);
const paths = Object.keys(built.metafile.inputs).filter(
  (path) => path !== 'luna-development-entry.ts',
);
for (const path of paths) {
  const rel = relative(repo, resolve(repo, path));
  assert.ok(
    low.bindings.some((binding) => binding.path === rel && binding.sha256 === hash(read(rel))),
    rel,
  );
}
let driver = read(`${oldDir}/driver.mjs`).toString('utf8');
const patches = [
  [`${oldDir}/authority.json`, `${newDir}/authority.json`],
  [
    "authority.strategy.reasoningEffort !== 'low'",
    "authority.strategy.reasoningEffort !== 'medium'",
  ],
  ["request.reasoning?.effort !== 'low'", "request.reasoning?.effort !== 'medium'"],
  [
    '    hash(readFileSync(bundlePath)) !== authority.runtime.bundleSha256',
    '    hash(readFileSync(new URL(import.meta.url))) !== authority.runtime.driverSha256 ||\n    hash(readFileSync(bundlePath)) !== authority.runtime.bundleSha256',
  ],
  [
    "if (mode === 'dry-run') {",
    "if (HOSTED_PROMPT_DIGEST !== authority.runtime.promptDigest) throw new Error('Prompt digest drift.');\nif (mode === 'dry-run') {",
  ],
];
for (const [from, to] of patches) driver = replaceOnce(driver, from, to);
writeFileSync(join(output, 'driver.mjs'), driver, { mode: 0o600 });
const strategy = { ...low.strategy, reasoningEffort: 'medium' };
const oldPlan = JSON.parse(read(low.planPath));
const plan = {
  schema: 'normlab.one-off-medium-plan/v1',
  strategy,
  inputs: oldPlan.inputs,
  comparisonProtocol: 'docs/LUNA_EFFORT_COMPARISON_PLAN_2026-10-19.md',
  lowAuthorityPath: `${oldDir}/authority.json`,
  lowArchiveSha256: hash(read(`${oldDir}/evidence.zip`)),
  reviewerInputsSentToModel: false,
};
const bindings = [...low.bindings];
for (const path of [
  `${newDir}/prepare.mjs`,
  plan.comparisonProtocol,
  `${oldDir}/authority.json`,
  `${oldDir}/evidence.zip`,
])
  if (!bindings.some((item) => item.path === path))
    bindings.push({ path, sha256: hash(read(path)) });
bindings.push({
  path: `${newDir}/execution-plan.json`,
  sha256: hash(JSON.stringify(plan, null, 2) + '\n'),
});
const { HOSTED_PROMPT_DIGEST } = await import(pathToFileURL(join(output, 'runtime.mjs')));
const authority = {
  schema: 'normlab.one-off-hosted-execution/v1',
  preparedAt: new Date().toISOString(),
  authorization: {
    ...low.authorization,
    user: 'Ок, выполни',
    dateMsk: '2026-10-19',
    scope: 'New ten-case medium arm; same reported account ceiling, not a new dollar allowance.',
  },
  planPath: `${newDir}/execution-plan.json`,
  strategy,
  bindings,
  effectiveSource: {
    path: sourcePath,
    originalSha256: hash(original),
    effectiveSha256: hash(effective),
    replacement: { from: "reasoning: { effort: 'low' },", to: "reasoning: { effort: 'medium' }," },
    productionSourceModified: false,
    originalLowRegeneratedBundleSha256: hash(control.outputFiles[0].contents),
  },
  supervisor: { template: `${oldDir}/driver.mjs`, transformations: patches },
  runtime: {
    ...low.runtime,
    bundleSha256: hash(built.outputFiles[0].contents),
    driverSha256: hash(driver),
    promptDigest: HOSTED_PROMPT_DIGEST,
    externalImports: imports,
  },
};
for (const [name, value] of [
  ['authority.json', authority],
  ['execution-plan.json', plan],
  ['metafile.json', built.metafile],
])
  writeFileSync(join(output, name), JSON.stringify(value, null, 2) + '\n', { mode: 0o600 });
console.log(
  JSON.stringify({
    status: 'medium-prepared',
    providerCalls: 0,
    originalLowBundleEqual: true,
    effectiveSourceChanges: 1,
    supervisorTransformations: patches.length,
    boundFiles: bindings.length,
    bundleSha256: authority.runtime.bundleSha256,
  }),
);
