import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
import {
  compileParkingRuntime,
  parkingLeanEnvironment,
  parkingRuntimeGates,
  parkingRuntimeManifestSchema,
  parkingRuntimeSourceIdentity,
} from '../server/parking-verifier.js';
import { discoverLean } from '../server/verifier.js';

// Builds the immutable parking runtime artifacts once (image build / CI), with the
// verifier's own compile flags, then runs the axiom gates against those exact bytes.
const root = fileURLToPath(new URL('../', import.meta.url));
const index = process.argv.indexOf('--output');
const output = resolve(index < 0 ? join(root, '.lean-runtime') : process.argv[index + 1]);
const lean = await discoverLean();
if (!lean.available || !lean.binary || !lean.binaryDigest || !lean.version)
  throw new Error('Pinned Lean 4.30.0 is required to build parking runtime artifacts');
const work = mkdtempSync(join(tmpdir(), 'normlab-parking-runtime-'));
try {
  const started = Date.now();
  await compileParkingRuntime(lean.binary, work, () => 600000);
  const compiledMs = Date.now() - started;
  for (const gate of parkingRuntimeGates) {
    // Gates import the Lean package and need more than the per-request -M cap.
    const { stdout, stderr } = await promisify(execFile)(
      lean.binary,
      ['-DwarningAsError=true', join(root, `lean/${gate}.lean`)],
      {
        cwd: work,
        env: parkingLeanEnvironment(work),
        timeout: 600000,
        maxBuffer: 1024 * 1024,
      },
    );
    if (stderr.trim() || stdout.includes('warning:') || !stdout.includes('gate passed'))
      throw new Error(`Parking runtime gate ${gate} did not pass`);
  }
  const identity = parkingRuntimeSourceIdentity();
  const manifest = parkingRuntimeManifestSchema.parse({
    schema: 'normlab.parking-lean-runtime/v1',
    lean: { version: lean.version, binaryDigest: lean.binaryDigest },
    modules: identity.modules.map((module) => ({
      ...module,
      oleanDigest: createHash('sha256')
        .update(readFileSync(join(work, `${module.name}.olean`)))
        .digest('hex'),
    })),
    gates: identity.gates,
  });
  // Fails if the output exists: artifacts are never refreshed in place.
  mkdirSync(output);
  for (const { name } of manifest.modules)
    copyFileSync(join(work, `${name}.olean`), join(output, `${name}.olean`));
  writeFileSync(join(output, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  console.log(
    JSON.stringify({
      output,
      compiledMs,
      modules: manifest.modules.length,
      gates: manifest.gates.length,
    }),
  );
} finally {
  rmSync(work, { recursive: true, force: true });
}
