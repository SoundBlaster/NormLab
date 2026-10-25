import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import {
  legalInputSchema,
  evaluateParkingFragment,
  parkingNormDraft,
} from '../shared/parking-legal.js';
import { reviewDraftSchema } from '../shared/parking-review.js';
import { verifyParkingCalculation } from '../server/parking-verifier.js';
import { ParkingLegal } from '../server/parking-legal.js';
import { digest } from '../server/hash.js';

function argument(name: string): string {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) throw new Error(`Required: ${name}`);
  return process.argv[index + 1];
}
const sourcePath = resolve(argument('--source'));
const inputPath = resolve(argument('--input'));
const output = resolve(argument('--output'));
const sourceBytes = readFileSync(sourcePath);
const source = reviewDraftSchema.parse(JSON.parse(sourceBytes.toString('utf8')));
const input = legalInputSchema.parse(JSON.parse(readFileSync(inputPath, 'utf8')));
if (input.action !== 'calculate') throw new Error('Replay requires a calculation input');
const result = evaluateParkingFragment(input);
const expected = argument('--expected-outcome');
const verification = await verifyParkingCalculation(input, result, source);
mkdirSync(join(output, 'legal'), { recursive: true, mode: 0o700 });
writeFileSync(join(output, `${source.revisionId}.json`), sourceBytes, { flag: 'wx', mode: 0o600 });
writeFileSync(
  join(output, 'legal', `${input.requestId}.json`),
  JSON.stringify({
    schema: 'normlab.parking-legal-assessment/v2',
    id: input.requestId,
    sequence: 1,
    createdAt: new Date().toISOString(),
    actor: 'human-operator',
    sourceDigest: source.sourceDigest,
    input,
    package: parkingNormDraft,
    result,
    verification,
  }),
  { flag: 'wx', mode: 0o600 },
);
const replayed = new ParkingLegal().history(output)[0];
const report = {
  schema: 'normlab.parking-bound-replay/v1',
  createdAt: new Date().toISOString(),
  inference: false,
  source: {
    schema: source.schema,
    fileSHA256: createHash('sha256').update(sourceBytes).digest('hex'),
    digest: source.sourceDigest,
    statements: source.statements.length,
  },
  inputDigest: digest(input),
  resultDigest: digest(result),
  bindingDigest: digest(verification.binding ?? null),
  citedStatements: verification.binding?.statementIds.length ?? 0,
  expectedOutcome: expected,
  actualOutcome: result.outcome,
  verification,
  receiptReplayed:
    digest(replayed.input) === digest(input) && digest(replayed.result) === digest(result),
  sourceUnchanged: sourceBytes.equals(readFileSync(sourcePath)),
};
// The public report excludes original source text and selected coordinate values.
const { binding: _binding, ...publicVerification } = verification;
const publicReport = { ...report, verification: publicVerification };
writeFileSync(join(output, 'report.json'), JSON.stringify(publicReport, null, 2) + '\n', {
  flag: 'wx',
  mode: 0o600,
});
console.log(JSON.stringify(publicReport, null, 2));
if (
  verification.status !== 'verified' ||
  result.outcome !== expected ||
  !report.receiptReplayed ||
  !report.sourceUnchanged
)
  process.exitCode = 1;
