import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { parseArgs } from 'node:util';
import { ReformStore } from '../server/reform-store.js';
import { parsePortableExperiment, replayPortableExperiment } from '../server/reform-transfer.js';
import { MAX_EXPERIMENT_BYTES } from '../shared/reform-transfer.js';
import { digest } from '../server/hash.js';
import { readReformFile } from './reform-file.js';

const { values, positionals } = parseArgs({
  options: { 'issuer-key': { type: 'string' }, 'data-dir': { type: 'string' } },
  allowPositionals: true,
});
if (positionals.length !== 1 || !values['issuer-key'])
  throw new Error(
    'Usage: npm run reform:import -- <experiment.json> --issuer-key <trusted-public.pem> [--data-dir <directory>]',
  );
const key = readReformFile(values['issuer-key'], 16384);
const experiment = parsePortableExperiment(readReformFile(positionals[0], MAX_EXPERIMENT_BYTES));
const replay = await replayPortableExperiment(experiment, key);
console.log(
  JSON.stringify(
    {
      experimentDigest: digest(replay.experiment),
      issuer: replay.experiment.issuer,
      current: replay.current,
      reports: replay.reports.map((r) => ({
        artifactDigest: r.artifactDigest,
        evidence: r.evidence,
      })),
    },
    null,
    2,
  ),
);
if (!replay.current) process.exitCode = 1;
else if (values['data-dir']) {
  mkdirSync(values['data-dir'], { recursive: true, mode: 0o700 });
  const store = new ReformStore(join(values['data-dir'], 'normlab.sqlite'));
  try {
    const record = store.saveImport({
      id: digest(replay.experiment),
      importedAt: new Date().toISOString(),
      trustedPublicKey: key,
      experiment: replay.experiment,
    });
    console.log(`Saved read-only experiment: ${record.id}`);
  } finally {
    store.close();
  }
}
