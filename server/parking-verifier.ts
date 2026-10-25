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
import type { ReviewDraft } from '../shared/parking-review.js';
import { constructParkingBinding } from './parking-binding.js';

const root = fileURLToPath(new URL('../', import.meta.url));
const core = readFileSync(join(root, 'lean/Parking.lean'), 'utf8');
const runtimeModules = [
  'Relations',
  'StateRelations',
  'DerivationTraces',
  'EventTransitions',
  'ActionAttribution',
  'ParkingAttribution',
  'Parking',
  'ParkingRuntime',
];
// Snapshot fixed local sources. Each is compiled separately in the private
// request directory; the case imports only artifacts built from this snapshot.
const runtimeSources = runtimeModules.map((name) => ({
  name,
  source: readFileSync(join(root, `lean/${name}.lean`), 'utf8'),
}));
const runtimeCore = runtimeSources.map(({ source }) => source).join('\n');
const execute = promisify(execFile);
// One active parking proof and one waiter per server process. Waiting does not
// consume the proof's 20-second execution budget; excess work is explicit busy.
let queuedProofs = 0;
let proofTail = Promise.resolve();
async function acquireProofSlot(): Promise<(() => void) | undefined> {
  if (queuedProofs >= 2) return undefined;
  queuedProofs++;
  const previous = proofTail;
  let release = () => {};
  proofTail = new Promise<void>((resolve) => {
    release = resolve;
  });
  await previous;
  return () => {
    queuedProofs--;
    release();
  };
}
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
const bindingAuditedNames = [
  'binding_checked',
  'review_checked',
  'scope_checked',
  'snapshot_checked',
  'supports_checked',
  'uncited_checked',
].map((name) => `NormLabParkingRuntime.${name}`);

export const parkingProfileDigest = digest({
  core,
  runtimeCore,
  binding: readFileSync(join(root, 'server/parking-binding.ts'), 'utf8'),
  reviewContracts: [
    'shared/parking-review.ts',
    'shared/parking-context.ts',
    'shared/parking-contracts.ts',
    'server/hash.ts',
    'package-lock.json',
  ].map((path) => [path, readFileSync(join(root, path), 'utf8')]),
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
function constructParkingProof(rawInput: unknown, rawResult: unknown, draft?: ReviewDraft) {
  const input = legalInputSchema.parse(rawInput);
  const result = legalResultSchema.parse(rawResult);
  const projection = draft === undefined ? undefined : constructParkingBinding(input, draft);
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
  const boundInput = projection
    ? 'NormLabParkingRuntime.normInput NormLabParkingRuntime.boundRequest'
    : `{
  finding := fun
${states}
  present := fun
${present}
  claimedFine := ${optionNat(input.claimedFine)}
}`;
  const names = [...auditedNames, ...(projection ? bindingAuditedNames : [])];
  const statement = `${projection?.statement ?? ''}namespace NormLabParking
def boundInput : Input := ${boundInput}
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
${names.map((name) => `#print axioms ${name}`).join('\n')}
end NormLabParking
`;
  return { statement, binding: projection?.binding, names };
}

/** Legacy calls retain the original profile; reviewed calls bind exact scope/source identities. */
export function constructParkingStatement(
  rawInput: unknown,
  rawResult: unknown,
  draft?: ReviewDraft,
): string {
  return constructParkingProof(rawInput, rawResult, draft).statement;
}

export async function verifyParkingCalculation(
  input: LegalInput,
  result: LegalResult,
  draft?: ReviewDraft,
): Promise<ParkingVerification> {
  const started = Date.now();
  // Snapshot before the first await: caller mutation cannot change the proved candidate.
  input = structuredClone(input);
  result = structuredClone(result);
  draft = draft === undefined ? undefined : structuredClone(draft);
  const bound = draft !== undefined;
  const proofCore = bound ? runtimeCore : core;
  const base: ParkingVerification = {
    profile: bound ? 'parking-fragment-poc/v2' : 'parking-fragment-poc/v1',
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
  let names: string[];
  try {
    const proof = constructParkingProof(input, result, draft);
    statement = proof.statement;
    names = proof.names;
    if (proof.binding) base.binding = proof.binding;
    base.statementDigest = digest({
      core: proofCore,
      statement,
      input,
      result,
      package: parkingNormDraft,
    });
  } catch {
    return finish(
      'rejected',
      'Входы, результат или привязка к исходной ревизии не соответствуют proof profile. Lean не запускался.',
    );
  }
  const release = await acquireProofSlot();
  if (!release)
    return finish(
      'inconclusive',
      'Очередь парковочных проверок Lean заполнена. Расчёт сохранён без проверки; повторите её позже.',
    );
  const configuredMemory = Number(process.env.NORMLAB_LEAN_MEMORY_MB ?? 512);
  const memory =
    Number.isInteger(configuredMemory) && configuredMemory >= 512 && configuredMemory <= 4096
      ? configuredMemory
      : 512;
  let directory: string | undefined;
  let checkingCandidate = false;
  try {
    const lean = await discoverLean();
    base.version = lean.version;
    if (!lean.available || !lean.binary)
      return finish(
        'inconclusive',
        'Lean 4.30.0 недоступен. Draft-расчёт сохранён без проверки модели.',
      );
    base.toolchainDigest = digest({ lean: lean.digest, profile: parkingProfileDigest });
    directory = await mkdtemp(join(tmpdir(), 'normlab-parking-proof-'));
    const deadline = Date.now() + 20000;
    const environment = {
      PATH: '/usr/bin:/bin',
      TMPDIR: directory,
      LANG: 'en_US.UTF-8',
      LEAN_PATH: directory,
    };
    const remaining = () => {
      const milliseconds = deadline - Date.now();
      if (milliseconds <= 0) throw new Error('Parking proof deadline exceeded');
      return milliseconds;
    };
    if (bound) {
      for (const module of runtimeSources) {
        const source = join(directory, `${module.name}.lean`);
        await writeFile(source, module.source, { mode: 0o600 });
        const compiled = await execute(
          lean.binary,
          [
            '-DwarningAsError=true',
            `-M${memory}`,
            '-T200000',
            '-o',
            join(directory, `${module.name}.olean`),
            source,
          ],
          { cwd: directory, env: environment, timeout: remaining(), maxBuffer: 128 * 1024 },
        );
        if (compiled.stderr.trim() || compiled.stdout.includes('warning:'))
          throw new Error('Parking runtime module compilation did not pass');
      }
    }
    const file = join(directory, 'ParkingCase.lean');
    await writeFile(file, `${bound ? 'import ParkingRuntime' : core}\n${statement}`, {
      mode: 0o600,
    });
    checkingCandidate = true;
    const { stdout, stderr } = await execute(
      lean.binary,
      ['-DwarningAsError=true', `-M${memory}`, '-T200000', file],
      {
        cwd: directory,
        timeout: remaining(),
        maxBuffer: 128 * 1024,
        env: environment,
      },
    );
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
      digest(reports.map((r) => r[1])) !== digest(names) ||
      base.axioms.some((axiom) => axiom !== 'propext' && !(bound && axiom === 'Quot.sound')) ||
      stderr.trim() ||
      stdout.includes('warning:')
    )
      return finish('inconclusive', 'Lean не подтвердил ожидаемый аудит аксиом.');
    return finish(
      'verified',
      bound
        ? 'Lean проверил расчёт PoC, идентичность ревизии, сохранение выбранных идентификаторов и принадлежность указанных ссылок эпизоду. Смысл ссылок и соответствие участника/ТС тексту не проверялись.'
        : 'Lean проверил результат, причины, сумму и условные ветви по модели PoC.',
    );
  } catch (error) {
    const output = (error as { stdout?: string }).stdout ?? '';
    return checkingCandidate &&
      output.includes('proved that the proposition') &&
      output.includes('is false')
      ? finish('rejected', 'Lean отверг результат: он не соответствует правилам модели PoC.')
      : finish(
          'inconclusive',
          'Lean не завершил проверку в пределах ресурсов. Draft-расчёт сохранён.',
        );
  } finally {
    try {
      if (directory) await rm(directory, { recursive: true, force: true });
    } finally {
      release();
    }
  }
}
