import { readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { parseArgs } from 'node:util';
import { replayReformExport } from '../server/reform-receipts.js';

const { values, positionals } = parseArgs({
  options: { 'issuer-key': { type: 'string' } },
  allowPositionals: true,
});
if (positionals.length !== 1 || !values['issuer-key'])
  throw new Error(
    'Usage: npm run reform:verify -- <export.json> --issuer-key <trusted-public.pem>',
  );
function readBounded(path: string, limit: number): string {
  const absolute = resolve(path);
  const size = statSync(absolute);
  if (!size.isFile() || size.size > limit)
    throw new Error(`Expected a file within ${limit} bytes: ${absolute}`);
  return readFileSync(absolute, 'utf8');
}
// Trust is an explicit input. Never infer it from the key embedded in the artifact.
const artifact = readBounded(positionals[0], 512 * 1024);
const trustedPublicKey = readBounded(values['issuer-key'], 16 * 1024);
const replay = await replayReformExport(artifact, trustedPublicKey);
console.log(JSON.stringify(replay, null, 2));
if (!replay.current) process.exitCode = 1;
