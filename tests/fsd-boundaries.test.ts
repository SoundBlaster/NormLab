import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import {
  cpSync,
  mkdtempSync,
  mkdirSync,
  readFileSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const loader = import.meta.resolve('tsx');

function runGate(fixture: string, gate: 'architecture' | 'code') {
  const args =
    gate === 'architecture'
      ? [
          '--import',
          loader,
          join(root, 'scripts/lint-architecture.ts'),
          'client',
          '--fail-on-warnings',
        ]
      : [join(root, 'node_modules/oxlint/bin/oxlint'), '--deny-warnings', 'client'];
  const result = spawnSync(process.execPath, args, {
    cwd: fixture,
    encoding: 'utf8',
    timeout: 30_000,
    maxBuffer: 2 * 1024 * 1024,
  });
  assert.ifError(result.error);
  assert.equal(result.signal, null, 'gate must finish rather than time out/crash');
  return { status: result.status, output: result.stdout + result.stderr };
}

test('FSD gates accept the frontend and reject boundary regressions', { timeout: 180_000 }, () => {
  const fixture = mkdtempSync(join(tmpdir(), 'normlab-fsd-'));
  try {
    cpSync(join(root, 'client'), join(fixture, 'client'), { recursive: true });
    for (const path of ['steiger.config.ts', 'tsconfig.json', '.oxlintrc.json']) {
      cpSync(join(root, path), join(fixture, path));
    }
    writeFileSync(join(fixture, 'package.json'), '{"type":"module"}\n');
    symlinkSync(join(root, 'node_modules'), join(fixture, 'node_modules'), 'dir');
    const positive = runGate(fixture, 'architecture');
    assert.equal(positive.status, 0, positive.output);

    const probes = [
      {
        path: 'client/shared/ui/fsd-probe.ts',
        source: 'import "@/pages/workspace";\n',
        gate: 'architecture',
        rule: 'fsd/forbidden-imports',
      },
      {
        path: 'client/pages/parking-review/ui/fsd-probe.ts',
        source: 'import "@/pages/workspace";\n',
        gate: 'architecture',
        rule: 'fsd/forbidden-imports',
      },
      {
        path: 'client/app/fsd-probe.ts',
        source: 'import "@/pages/workspace/ui/WorkspacePage";\n',
        gate: 'architecture',
        rule: 'fsd/no-public-api-sidestep',
      },
      {
        path: 'client/pages/workspace/index.ts',
        source: 'export { Button } from "@/shared/ui";\n',
        gate: 'code',
        rule: 'no-restricted-imports',
      },
      {
        path: 'client/pages/parking-review/ui/fsd-probe.ts',
        source: 'import "../../../../shared/parking";\n',
        gate: 'code',
        rule: 'no-restricted-imports',
      },
    ] as const;
    for (const probe of probes) {
      const path = join(fixture, probe.path);
      let original: string | undefined;
      try {
        original = readFileSync(path, 'utf8');
      } catch {
        /* new probe file */
      }
      mkdirSync(dirname(path), { recursive: true });
      try {
        writeFileSync(path, (original ?? '') + probe.source);
        const result = runGate(fixture, probe.gate);
        assert.notEqual(result.status, 0, `${probe.path}: forbidden import was accepted`);
        assert.ok(result.output.includes(probe.rule), result.output);
      } finally {
        if (original === undefined) rmSync(path);
        else writeFileSync(path, original);
      }
    }
    // Protect dependencies before configuration is evaluated; rejected globs
    // must cause a nonzero CLI exit rather than an uncontrolled stack overflow.
    writeFileSync(
      join(fixture, 'steiger.config.ts'),
      `import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
require('micromatch').braceExpand('{'.repeat(10000) + 'a,b' + '}'.repeat(10000));
export default [];
`,
    );
    const rejectedGlob = runGate(fixture, 'architecture');
    assert.notEqual(rejectedGlob.status, 0, rejectedGlob.output);
    assert.match(rejectedGlob.output, /FSD glob exceeds 64 opening delimiters/);
    assert.doesNotMatch(rejectedGlob.output, /Maximum call stack size exceeded/);
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});
