import { writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';
import { reformExportSchema } from '../server/reform-receipts.js';
import { packPortableExperiment } from '../server/reform-transfer.js';
import { parseReformJson } from '../shared/reform-semantics.js';
import { readReformFile } from './reform-file.js';

const { values, positionals } = parseArgs({
  options: {
    'issuer-key': { type: 'string' },
    annotations: { type: 'string' },
    output: { type: 'string' },
  },
  allowPositionals: true,
});
if (!positionals.length || !values['issuer-key'] || !values.output)
  throw new Error(
    'Usage: npm run reform:pack -- <export.json> [...] --issuer-key <trusted-public.pem> [--annotations <sidecar.json>] --output <experiment.json>',
  );
const key = readReformFile(values['issuer-key'], 16384);
const annotations = values.annotations ? parseReformJson(readReformFile(values.annotations)) : null;
const experiment = packPortableExperiment(
  positionals.map((path) => ({
    artifact: reformExportSchema.parse(parseReformJson(readReformFile(path))),
    annotations,
  })),
  key,
);
// Never overwrite an existing transfer artifact.
writeFileSync(values.output, `${JSON.stringify(experiment)}\n`, { mode: 0o600, flag: 'wx' });
console.log(
  `Packed ${experiment.items.length} artifacts into ${values.output}. Issuer: ${experiment.issuer}`,
);
