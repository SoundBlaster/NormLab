import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
import {
  legalInputSchema,
  legalResultSchema,
  parkingNormDraft,
  type LegalInput,
  type LegalResult,
  type ParkingVerification,
} from '../shared/parking-legal.js';
import { digest } from './hash.js';
import { discoverLean } from './verifier.js';

const root = fileURLToPath(new URL('../', import.meta.url));
const core = readFileSync(join(root, 'lean/Parking.lean'), 'utf8');
const execute = promisify(execFile);
export const parkingNormDigest = createHash('sha256')
  .update(JSON.stringify(parkingNormDraft))
  .digest('hex');
const conditionKinds = {
  inMoscow: 'scope',
  cityParking: 'scope',
  placement: 'core',
  paidRegime: 'core',
  personalCar: 'scope',
  simplePayment: 'scope',
  noPrivilege: 'scope',
  noSpecialCircumstances: 'scope',
  noPayment: 'core',
} as const;
const coordinates = ['vehicle', 'participant', 'eventDate', 'location', 'timeInterval'] as const;
const findings = {
  unreviewed: 'unreviewed',
  established: 'established',
  refuted: 'refuted',
  'not-established': 'notEstablished',
  conflict: 'conflict',
} as const;
const outcomes = {
  conflict: 'conflict',
  unsupported: 'unsupported',
  incomplete: 'incomplete',
  'fragment-refuted': 'fragmentRefuted',
  'fragment-matched': 'fragmentMatched',
} as const;
const comparisons = {
  'not-mentioned': 'notMentioned',
  'not-computable': 'notComputable',
  'draft-match': 'draftMatch',
  'draft-difference': 'draftDifference',
} as const;
const auditedNames = [
  'checked',
  'conflict_blocks',
  'unsupported_blocks',
  'matched_requires_complete',
  'fine_only_when_matched',
].map((name) => `NormLabParking.${name}`);

export const parkingProfileDigest = digest({
  core,
  verifier: readFileSync(join(root, 'server/parking-verifier.ts'), 'utf8'),
  contracts: readFileSync(join(root, 'shared/parking-legal.ts'), 'utf8'),
  package: parkingNormDraft,
});

function conditionToken(id: string): string {
  if (!Object.hasOwn(conditionKinds, id)) throw new Error('Unknown parking condition');
  return `.${id}`;
}
function missingToken(id: string): string {
  if (coordinates.some((key) => key === id)) return `.coordinate .${id}`;
  return `.condition ${conditionToken(id)}`;
}
const optionNat = (value: number | null) => (value === null ? 'none' : `(some ${value})`);

/** Only closed enum tokens, bounded integers and coordinate-presence flags enter Lean. */
export function constructParkingStatement(rawInput: unknown, rawResult: unknown): string {
  const input = legalInputSchema.parse(rawInput);
  const result = legalResultSchema.parse(rawResult);
  if (
    input.packageDigest !== parkingNormDigest ||
    parkingNormDraft.candidateSanction.amount !== 5000 ||
    digest(parkingNormDraft.conditions.map((c) => [c.id, c.kind])) !==
      digest(Object.entries(conditionKinds))
  )
    throw new Error('Parking package is outside the supported proof profile');
  const byId = new Map(input.findings.map((f) => [f.conditionId, f.state]));
  const states = Object.keys(conditionKinds)
    .map((id) => `    | ${conditionToken(id)} => .${findings[byId.get(id)!]}`)
    .join('\n');
  const present = coordinates.map((key) => `    | .${key} => ${Boolean(input[key])}`).join('\n');
  const list = (ids: string[]) => `[${ids.map(conditionToken).join(', ')}]`;
  const branches = result.branches.map(
    (b) =>
      `{ condition := ${conditionToken(b.conditionId)}, assumption := .${findings[b.assumedState]}, outcome := .${outcomes[b.outcome]} }`,
  );
  return `namespace NormLabParking
def boundInput : Input := {
  finding := fun
${states}
  present := fun
${present}
  claimedFine := ${optionNat(input.claimedFine)}
}
def candidate : Result := {
  outcome := .${outcomes[result.outcome]}
  conflicts := ${list(result.conflicts)}
  unsupported := ${list(result.unsupported)}
  refuted := ${list(result.refuted)}
  missing := [${result.missing.map(missingToken).join(', ')}]
  candidateFine := ${optionNat(result.candidateFine)}
  comparison := .${comparisons[result.sanctionComparison]}
  branches := [${branches.join(', ')}]
}
theorem checked : ValidResult boundInput candidate := by decide +kernel
${auditedNames.map((name) => `#print axioms ${name}`).join('\n')}
end NormLabParking
`;
}

export async function verifyParkingCalculation(
  input: LegalInput,
  result: LegalResult,
): Promise<ParkingVerification> {
  const started = Date.now();
  // Snapshot before the first await: caller mutation cannot change the proved candidate.
  input = structuredClone(input);
  result = structuredClone(result);
  const base: ParkingVerification = {
    profile: 'parking-fragment-poc/v1',
    status: 'rejected',
    engine: 'lean-kernel',
    version: null,
    inputDigest: digest(input),
    resultDigest: digest(result),
    packageDigest: parkingNormDigest,
    profileDigest: parkingProfileDigest,
    statementDigest: digest({ input, result, profile: parkingProfileDigest }),
    toolchainDigest: null,
    axioms: [],
    reason: '',
    durationMs: 0,
  };
  const finish = (status: ParkingVerification['status'], reason: string): ParkingVerification => ({
    ...base,
    status,
    reason,
    durationMs: Date.now() - started,
  });
  let statement: string;
  try {
    statement = constructParkingStatement(input, result);
    base.statementDigest = digest({ core, statement, input, result, package: parkingNormDraft });
  } catch {
    return finish('rejected', 'Входы или результат не соответствуют парковочному proof profile.');
  }
  const lean = await discoverLean();
  base.version = lean.version;
  if (!lean.available || !lean.binary)
    return finish(
      'inconclusive',
      'Lean 4.30.0 недоступен. Draft-расчёт сохранён без проверки модели.',
    );
  base.toolchainDigest = digest({ lean: lean.digest, profile: parkingProfileDigest });
  const configuredMemory = Number(process.env.NORMLAB_LEAN_MEMORY_MB ?? 512);
  const memory =
    Number.isInteger(configuredMemory) && configuredMemory >= 512 && configuredMemory <= 4096
      ? configuredMemory
      : 512;
  let directory: string | undefined;
  try {
    directory = await mkdtemp(join(tmpdir(), 'normlab-parking-proof-'));
    const file = join(directory, 'ParkingCase.lean');
    await writeFile(file, `${core}\n${statement}`, { mode: 0o600 });
    const { stdout, stderr } = await execute(lean.binary, [`-M${memory}`, '-T200000', file], {
      cwd: root,
      timeout: 20000,
      maxBuffer: 128 * 1024,
      env: { PATH: '/usr/bin:/bin', TMPDIR: directory, LANG: 'en_US.UTF-8' },
    });
    const reports = [
      ...stdout.matchAll(
        /'([^']+)' (?:does not depend on any axioms|depends on axioms: \[([^\]]*)\])/g,
      ),
    ];
    base.axioms = [
      ...new Set(
        reports.flatMap(
          (r) =>
            r[2]
              ?.split(',')
              .map((a) => a.trim())
              .filter(Boolean) ?? [],
        ),
      ),
    ];
    if (
      digest(reports.map((r) => r[1])) !== digest(auditedNames) ||
      base.axioms.some((axiom) => axiom !== 'propext') ||
      stderr.trim() ||
      stdout.includes('warning:')
    )
      return finish('inconclusive', 'Lean не подтвердил ожидаемый аудит аксиом.');
    return finish(
      'verified',
      'Lean проверил результат, причины, сумму и условные ветви по модели PoC.',
    );
  } catch (error) {
    const output = (error as { stdout?: string }).stdout ?? '';
    return output.includes('proved that the proposition') && output.includes('is false')
      ? finish('rejected', 'Lean отверг результат: он не соответствует правилам модели PoC.')
      : finish(
          'inconclusive',
          'Lean не завершил проверку в пределах ресурсов. Draft-расчёт сохранён.',
        );
  } finally {
    if (directory) await rm(directory, { recursive: true, force: true });
  }
}
