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
  import { readFileSync, writeFileSync } from 'node:fs';
  // The whole server module graph must load whatever state the artifacts are in.
  import './server/app.ts';
  import { parkingFixture } from './tests/parking-legal-fixture.ts';
  import { evaluateParkingFragment } from './shared/parking-legal.ts';
  import { parkingRuntimeArtifacts, verifyParkingCalculation } from './server/parking-verifier.ts';
  const { input, draft: seed } = parkingFixture();
  // The binding requires the SHA-256 of the raw source text.
  const draft = { ...seed, sourceDigest: createHash('sha256').update(seed.narrative).digest('hex') };
  const verify = () => verifyParkingCalculation(input, evaluateParkingFragment(input), draft);
  const verification = await verify();
  // Optionally change the Lean launcher in place (same size) and verify again in this process.
  const replace = process.env.NORMLAB_TEST_REPLACE_LEAN;
  let replaced = null;
  if (replace) {
    writeFileSync(replace, readFileSync(replace, 'utf8').replace('# rev-a', '# rev-b'));
    replaced = await verify();
  }
  console.log(JSON.stringify({ mode: parkingRuntimeArtifacts.mode, verification, replaced }));
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
# rev-a
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
      type Receipt = {
        status: string;
        profile: string;
        profileDigest: string;
        toolchainDigest: string;
        reason: string;
      };
      return JSON.parse(stdout) as {
        mode: string;
        verification: Receipt;
        replaced: Receipt | null;
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

    // Lean changes after the first request of the same process: the next
    // request rehashes it, refuses the artifacts and records the new identity.
    const swapped = await verify(runtime, { NORMLAB_TEST_REPLACE_LEAN: wrapper });
    assert.equal(swapped.verification.status, 'verified', swapped.verification.reason);
    assert.equal(swapped.replaced?.status, 'inconclusive');
    assert.match(swapped.replaced.reason, /другой сборкой Lean/);
    assert.notEqual(swapped.replaced.toolchainDigest, swapped.verification.toolchainDigest);
    assert.equal(compiles().length, 1, 'only the first request reaches Lean');
    writeFileSync(wrapper, readFileSync(wrapper, 'utf8').replace('# rev-b', '# rev-a'));

    // An unreadable manifest (here a directory) disables bound proofs, not the server.
    const unreadable = join(folder, 'unreadable');
    mkdirSync(join(unreadable, 'manifest.json'), { recursive: true });
    const blocked = await verify(unreadable);
    assert.equal(blocked.mode, 'invalid');
    assert.equal(blocked.verification.status, 'inconclusive');
    assert.match(blocked.verification.reason, /Manifest предсобранных модулей Lean недоступен/);
    assert.deepEqual(compiles(), []);

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
