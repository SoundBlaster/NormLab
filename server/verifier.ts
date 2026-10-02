import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { homedir, tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import {
  certificateSchema,
  type Bundle,
  type Certificate,
  type Snapshot,
  type Verification,
} from '../shared/domain.js';
import { validateLockedBundle } from './bundles.js';
import { canonical, digest } from './hash.js';

const execute = promisify(execFile);
const root = fileURLToPath(new URL('../', import.meta.url));
const core = readFileSync(join(root, 'lean/NormLab.lean'), 'utf8');
type Toolchain = {
  available: boolean;
  version: string | null;
  binary: string | null;
  digest: string | null;
};
let discovery: Promise<Toolchain> | undefined;

export function discoverLean(): Promise<Toolchain> {
  discovery ??= (async () => {
    const launcher =
      process.env.LEAN_BIN ??
      (existsSync(join(homedir(), '.elan/bin/lean')) ? join(homedir(), '.elan/bin/lean') : 'lean');
    try {
      const { stdout: version } = await execute(launcher, ['--version'], {
        cwd: root,
        timeout: 10000,
      });
      if (!version.includes('version 4.30.0'))
        return { available: false, version: version.trim(), binary: null, digest: null };
      const { stdout: prefix } = await execute(launcher, ['--print-prefix'], {
        cwd: root,
        timeout: 10000,
      });
      const binary = resolve(prefix.trim(), 'bin/lean');
      const hash = createHash('sha256').update(readFileSync(binary)).digest('hex');
      return {
        available: true,
        version: version.trim(),
        binary,
        digest: digest({
          version: version.trim(),
          binary: hash,
          core,
          node: process.version,
          verifier: readFileSync(join(root, 'server/verifier.ts'), 'utf8'),
          registry: readFileSync(join(root, 'server/bundles.ts'), 'utf8'),
          contracts: readFileSync(join(root, 'shared/domain.ts'), 'utf8'),
          hashing: readFileSync(join(root, 'server/hash.ts'), 'utf8'),
          dependencies: readFileSync(join(root, 'package-lock.json'), 'utf8'),
        }),
      };
    } catch {
      return { available: false, version: null, binary: null, digest: null };
    }
  })();
  return discovery;
}

// Independent checker: validates constraints, never calls the producing interpreter.
export function checkCertificate(snapshot: Snapshot, bundle: Bundle, input: unknown): Certificate {
  validateLockedBundle(bundle);
  const { digest: suppliedDigest, ...snapshotData } = snapshot;
  if (digest(snapshotData) !== suppliedDigest) throw new Error('Snapshot integrity mismatch');
  const cert = certificateSchema.parse(input);
  if (
    cert.snapshotDigest !== snapshot.digest ||
    cert.bundleSemanticDigest !== bundle.semanticDigest ||
    cert.bundleProvenanceDigest !== bundle.provenanceDigest
  )
    throw new Error('Certificate input binding mismatch');
  const { result } = cert;
  const complete = snapshot.finding === 'established' || snapshot.finding === 'refuted';
  const expectedStates = complete ? [snapshot.finding] : ['established', 'refuted'];
  if (
    result.status !== (complete ? 'complete' : 'conditional') ||
    canonical(result.outcomes.map((o) => o.when)) !== canonical(expectedStates)
  ) {
    throw new Error('Incomplete or incorrect branch coverage');
  }
  const expectedLedger = complete
    ? snapshot.finding === 'established'
      ? 'applied'
      : 'inapplicable'
    : 'unresolved';
  if (result.ledger[0].status !== expectedLedger) throw new Error('Mandatory rule ledger mismatch');
  for (const outcome of result.outcomes) {
    if (outcome.fineAmount !== 200000 || outcome.currency !== 'DEMO')
      throw new Error('Fine must be preserved');
    if (outcome.when === 'established') {
      if (
        outcome.prisonMonths * bundle.ir.adjustment.denominator !==
          120 * bundle.ir.adjustment.numerator ||
        outcome.ruleStatus !== 'applied'
      )
        throw new Error('Mandatory reduction is missing or incorrect');
    } else if (outcome.prisonMonths !== 120 || outcome.ruleStatus !== 'inapplicable') {
      throw new Error('Refuted trigger must preserve the baseline');
    }
  }
  return cert;
}

const leanFinding = {
  unreviewed: 'unreviewed',
  established: 'established',
  refuted: 'refuted',
  'not-established': 'notEstablished',
} as const;

// Only bounded integers, booleans, and hardcoded enum tokens enter the template.
// Narrative, rationale, source text, and user Lean code are never interpolated.
export function constructStatement(snapshot: Snapshot, bundle: Bundle, cert: Certificate): string {
  const outcomes = cert.result.outcomes
    .map(
      (o) =>
        `{ finding := .${leanFinding[o.when]}, prisonMonths := ${o.prisonMonths}, fineAmount := ${o.fineAmount}, ruleStatus := .${o.ruleStatus} }`,
    )
    .join(',\n');
  return `namespace NormLab\ntheorem checked : ValidResult .${leanFinding[snapshot.finding]} ${bundle.ir.adjustment.numerator} ${bundle.ir.adjustment.denominator} ${cert.result.status === 'conditional'} .${cert.result.ledger[0].status} [${outcomes}] := by decide\n#print axioms checked\nend NormLab\n`;
}

export async function verifyCertificate(
  snapshot: Snapshot,
  bundle: Bundle,
  input: unknown,
): Promise<Verification> {
  const started = Date.now();
  const base: Verification = {
    status: 'rejected',
    engine: 'lean-kernel',
    version: null,
    statementDigest: digest({
      query: 'decision/v1',
      snapshot: snapshot.digest,
      bundle: bundle.semanticDigest,
    }),
    toolchainDigest: null,
    axioms: [],
    reason: '',
    durationMs: 0,
  };
  let cert: Certificate;
  try {
    cert = checkCertificate(snapshot, bundle, input);
  } catch (error) {
    return {
      ...base,
      reason: error instanceof Error ? error.message : 'Certificate rejected',
      durationMs: Date.now() - started,
    };
  }
  const statement = constructStatement(snapshot, bundle, cert);
  base.statementDigest = digest({
    core,
    statement,
    snapshot: snapshot.digest,
    bundle: bundle.semanticDigest,
    provenance: bundle.provenanceDigest,
  });
  const toolchain = await discoverLean();
  base.version = toolchain.version;
  base.toolchainDigest = toolchain.digest;
  if (!toolchain.available || !toolchain.binary) {
    return {
      ...base,
      status: 'inconclusive',
      reason:
        'Нужен Lean 4.30.0. Структура сертификата проверена, формальная проверка не выполнена.',
      durationMs: Date.now() - started,
    };
  }
  const temporary = await mkdtemp(join(tmpdir(), 'normlab-proof-'));
  try {
    const file = join(temporary, 'Certificate.lean');
    await writeFile(file, `${core}\n${statement}`, { mode: 0o600 });
    const { stdout, stderr } = await execute(toolchain.binary, ['-M512', '-T200000', file], {
      cwd: root,
      timeout: 20000,
      maxBuffer: 128 * 1024,
      env: { PATH: '/usr/bin:/bin', TMPDIR: temporary, LANG: 'en_US.UTF-8' },
    });
    const axiomReport = /'NormLab\.checked' depends on axioms: \[([^\]]*)\]/.exec(stdout);
    const axiomFree = stdout.includes("'NormLab.checked' does not depend on any axioms");
    const axioms = axiomReport
      ? axiomReport[1]
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean)
      : [];
    // Lean's standard propositional extensionality is explicitly accepted.
    // sorryAx, native-evaluation axioms and all custom axioms are rejected.
    if (
      (!axiomFree && !axiomReport) ||
      axioms.some((value) => value !== 'propext') ||
      stderr.trim() ||
      stdout.includes('warning:')
    ) {
      return {
        ...base,
        status: 'inconclusive',
        reason: 'Lean завершился без подтверждённого аудита аксиом.',
        durationMs: Date.now() - started,
      };
    }
    return {
      ...base,
      status: 'verified',
      axioms,
      reason:
        'Lean kernel проверил результат и все условные ветви; зависимости от аксиом соответствуют явному allowlist.',
      durationMs: Date.now() - started,
    };
  } catch {
    return {
      ...base,
      status: 'inconclusive',
      reason: 'Lean не завершил проверку в заданных пределах ресурсов или вернул ошибку.',
      durationMs: Date.now() - started,
    };
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
}
