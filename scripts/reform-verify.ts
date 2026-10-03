import { parseArgs } from 'node:util';
import { replayReformExport } from '../server/reform-receipts.js';
import { readReformFile } from './reform-file.js';

const { values, positionals } = parseArgs({
  options: { 'issuer-key': { type: 'string' } },
  allowPositionals: true,
});
if (positionals.length !== 1 || !values['issuer-key'])
  throw new Error(
    'Usage: npm run reform:verify -- <export.json> --issuer-key <trusted-public.pem>',
  );
// Trust is an explicit input. Never infer it from the key embedded in the artifact.
const artifact = readReformFile(positionals[0]);
const trustedPublicKey = readReformFile(values['issuer-key'], 16 * 1024);
const replay = await replayReformExport(artifact, trustedPublicKey);
console.log(JSON.stringify(replay, null, 2));
if (!replay.current) process.exitCode = 1;
