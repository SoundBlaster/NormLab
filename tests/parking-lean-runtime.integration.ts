import assert from 'node:assert/strict';
import test from 'node:test';
import { execFile } from 'node:child_process';
import {
  chmodSync,
  cpSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';
import { discoverLean } from '../server/verifier.js';

const run = promisify(execFile);
const boundCase = `
  import { createHash } from 'node:crypto';
  import { parkingFixture } from './tests/parking-legal-fixture.ts';
  import { evaluateParkingFragment } from './shared/parking-legal.ts';
  import { parkingRuntimeArtifacts, verifyParkingCalculation } from './server/parking-verifier.ts';
  const { input, draft: seed } = parkingFixture();
  // The binding requires the SHA-256 of the raw source text.
  const draft = { ...seed, sourceDigest: createHash('sha256').update(seed.narrative).digest('hex') };
  const verification = await verifyParkingCalculation(input, evaluateParkingFragment(input), draft);
  console.log(JSON.stringify({ mode: parkingRuntimeArtifacts.mode, verification }));
`;

test('bound proofs import pinned prebuilt runtime artifacts and compile only the case', async () => {
  const lean = await discoverLean();
  assert.ok(
    lean.available && lean.binary,
    'Pinned Lean is required for the runtime artifact check',
  );
  const folder = mkdtempSync(join(tmpdir(), 'parking-lean-runtime-'));
  try {
    // A recording Lean wrapper: --print-prefix points discovery at the wrapper,
    // every other call is logged and executed by the real pinned binary.
    const calls = join(folder, 'calls.log');
    const wrapper = join(folder, 'toolchain/bin/lean');
    mkdirSync(join(folder, 'toolchain/bin'), { recursive: true });
    writeFileSync(
      wrapper,
      `#!/bin/sh
if [ "$1" = "--print-prefix" ]; then echo '${join(folder, 'toolchain')}'; exit 0; fi
printf '%s\\n' "$*" >> '${calls}'
exec '${lean.binary}' "$@"
`,
      { mode: 0o755 },
    );
    const compiles = () =>
      readFileSync(calls, 'utf8')
        .split('\n')
        .filter((line) => line.endsWith('.lean'));
    const runtime = join(folder, 'runtime');
    const env = { ...process.env, LEAN_BIN: wrapper, NORMLAB_LEAN_MEMORY_MB: '1024' };
    await run(
      process.execPath,
      ['--import', 'tsx', 'scripts/parking-lean-runtime.ts', '--output', runtime],
      { env, timeout: 300000 },
    );
    const verify = async (directory: string, extra: Record<string, string> = {}) => {
      writeFileSync(calls, '');
      const { stdout } = await run(
        process.execPath,
        ['--import', 'tsx', '--input-type=module', '-e', boundCase],
        { env: { ...env, NORMLAB_PARKING_LEAN_RUNTIME_DIR: directory, ...extra }, timeout: 60000 },
      );
      return JSON.parse(stdout) as {
        mode: string;
        verification: { status: string; profile: string; profileDigest: string; reason: string };
      };
    };

    const prebuilt = await verify(runtime);
    assert.equal(prebuilt.mode, 'prebuilt');
    assert.equal(prebuilt.verification.status, 'verified', prebuilt.verification.reason);
    assert.equal(prebuilt.verification.profile, 'parking-fragment-poc/v2');
    const [only, ...rest] = compiles();
    assert.deepEqual(rest, [], 'fixed runtime modules must not be recompiled per request');
    assert.match(only, /ParkingCase\.lean$/);
    assert.doesNotMatch(only, / -o /);

    const tampered = join(folder, 'tampered');
    cpSync(runtime, tampered, { recursive: true });
    const olean = join(tampered, 'Parking.olean');
    chmodSync(olean, 0o600);
    const bytes = readFileSync(olean);
    bytes[bytes.length - 1] ^= 1;
    writeFileSync(olean, bytes);
    const mismatch = await verify(tampered);
    assert.equal(mismatch.verification.status, 'inconclusive');
    assert.match(mismatch.verification.reason, /Parking не совпадает с закреплённым/);
    assert.deepEqual(compiles(), [], 'mismatched artifacts must not reach Lean');
    // Receipts pin the manifest digests, so they are equal for the same manifest.
    assert.equal(mismatch.verification.profileDigest, prebuilt.verification.profileDigest);

    // Real binary differs from the wrapper the manifest was built with.
    const otherLean = await verify(runtime, { LEAN_BIN: lean.binary });
    assert.equal(otherLean.verification.status, 'inconclusive');
    assert.match(otherLean.verification.reason, /другой сборкой Lean/);

    const fallback = await verify(join(folder, 'missing'));
    assert.equal(fallback.mode, 'compile');
    assert.equal(fallback.verification.status, 'verified', fallback.verification.reason);
    assert.equal(compiles().filter((line) => line.includes(' -o ')).length, 8);
    assert.notEqual(fallback.verification.profileDigest, prebuilt.verification.profileDigest);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});
