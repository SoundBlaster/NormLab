import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

/** Finalize checksums after the runner has finished writing raw and derived artifacts. */
export function writeBaselineArtifactManifest(output: string) {
  const entries = readdirSync(output, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name !== 'artifact-manifest.json')
    .map((entry) => entry.name)
    .sort()
    .map((path) => ({
      path,
      sha256: createHash('sha256')
        .update(readFileSync(resolve(output, path)))
        .digest('hex'),
    }));
  writeFileSync(
    resolve(output, 'artifact-manifest.json'),
    `${JSON.stringify({ schema: 'normlab.baseline-artifacts/v1', signed: false, entries }, null, 2)}\n`,
  );
}
