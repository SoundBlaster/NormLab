import { execFile } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';
import {
  reformCertificateSchema,
  reformQuerySchema,
  type ReformBundle,
  type ReformCertificate,
  type ReformQuery,
  type ReformReceipt,
  type ReformResult,
  type ReformSnapshot,
} from '../shared/reform-contracts.js';
import { ReformContractError } from '../shared/reform-semantics.js';
import { validateReformCertificateBindings, validateReformQuery } from './reform-bindings.js';
import { digest } from './hash.js';
import { discoverLean } from './verifier.js';
import { validateReformBundle } from './reform-models.js';

const execute = promisify(execFile);
const coreUrl = new URL('../lean/Reform.lean', import.meta.url);
export const reformLeanCore = readFileSync(coreUrl, 'utf8');
const root = new URL('../', import.meta.url);
const checkerSources = [
  'server/reform-verifier.ts',
  'server/reform-bindings.ts',
  'server/reform-models.ts',
  'shared/reform-contracts.ts',
  'shared/reform-semantics.ts',
].map((path) => ({ path, content: readFileSync(new URL(path, root), 'utf8') }));
const findings = {
  unreviewed: 'unreviewed',
  established: 'established',
  refuted: 'refuted',
  'not-established': 'notEstablished',
} as const;
type DecisionCertificate = Extract<ReformCertificate, { kind: 'decision' }>;
export type ReformVerification = ReformReceipt['payload']['verification'] & {
  queryDigest: string;
  certificateDigest: string | null;
  statementDigest: string;
  durationMs: number;
};

// Only schema-bounded integers and literal enum tokens enter Lean source.
// Wire rule IDs are mapped injectively to their indices; text is never interpolated.
export function reformLeanModel(bundle: ReformBundle): string {
  bundle = validateReformBundle(bundle);
  return `[${bundle.package.ir.rules
    .map((rule, index) => {
      const op = rule.operation;
      const operation =
        op.kind === 'baseline'
          ? `.baseline ${op.prisonMonths} ${op.fineAmount}`
          : op.kind === 'scale'
            ? `.scale .${op.trigger} ${op.numerator} ${op.denominator}`
            : '.exclude';
      return `{ id := ${index}, groups := [${rule.groups.map((g) => `.${g}`).join(', ')}], operation := ${operation} }`;
    })
    .join(',\n')}]`;
}

function leanResult(bundle: ReformBundle, result: ReformResult): string {
  const index = (id: string): number => {
    const value = bundle.package.ir.rules.findIndex((rule) => rule.id === id);
    if (value < 0) throw new ReformContractError('invalid', 'Unknown rule in Lean statement');
    return value;
  };
  const ledger = (entries: ReformResult['ledger']) =>
    `[${entries
      .map(
        (entry) =>
          `{ rule := ${index(entry.ruleId)}, status := .${entry.status}, excludedBy := ${entry.excludedBy === null ? 'none' : `some ${index(entry.excludedBy)}`} }`,
      )
      .join(', ')}]`;
  const branches = result.branches.map((branch) => {
    const x = branch.when;
    const y = branch.outcome;
    const steps = branch.steps.map(
      (step) =>
        `{ rule := ${index(step.ruleId)}, beforeMonths := ${step.beforeMonths}, afterMonths := ${step.afterMonths} }`,
    );
    return `{ input := { group := .${x.group}, M := ${x.M}, N := ${x.N}, E := ${x.E} }, outcome := { qualification := .${y.qualification}, months := ${y.prisonMonths}, fine := ${y.fineAmount} }, ledger := ${ledger(branch.ledger)}, steps := [${steps.join(', ')}] }`;
  });
  return `{ conditional := ${result.status === 'conditional'}, branches := [${branches.join(',\n')}], ledger := ${ledger(result.ledger)} }`;
}

// Validates input bindings and wire shape. Normative result checks occur in Lean.
// Keeping shape validation separate permits negative tests that bypass contextual guards.
export function constructReformDecisionStatement(
  query: ReformQuery,
  snapshot: ReformSnapshot,
  bundle: ReformBundle,
  input: unknown,
): string {
  const bound = validateReformQuery(query, [bundle], snapshot);
  const cert = reformCertificateSchema.parse(input);
  if (bound.kind !== 'decision' || cert.kind !== 'decision' || cert.queryDigest !== digest(bound))
    throw new ReformContractError('invalid', 'Decision statement binding mismatch');
  const s = `{ group := .${snapshot.group}, M := .${findings[snapshot.findings.M.state]}, N := .${findings[snapshot.findings.N.state]}, E := .${findings[snapshot.findings.E.state]} }`;
  return `namespace NormLabReform
def boundModel : List Rule := ${reformLeanModel(bundle)}
def boundSnapshot : Snapshot := ${s}
def candidateResult : Result := ${leanResult(bundle, cert.result)}
theorem supported : WellFormed boundModel := by decide +kernel
theorem checked : ValidResult boundModel boundSnapshot candidateResult :=
  ⟨supported, by decide +kernel⟩
#print axioms checked
end NormLabReform
`;
}

export async function verifyReformDecision(
  query: ReformQuery,
  snapshot: ReformSnapshot,
  bundle: ReformBundle,
  input: unknown,
): Promise<ReformVerification> {
  const started = Date.now();
  const base: ReformVerification = {
    status: 'rejected',
    engine: 'lean-kernel',
    version: null,
    method: null,
    toolchainDigest: null,
    axioms: [],
    reason: 'Certificate not checked',
    queryDigest: digest(query),
    certificateDigest: null,
    statementDigest: digest({ core: reformLeanCore, query, snapshot, bundle }),
    durationMs: 0,
  };
  let certificate: DecisionCertificate;
  let statement: string;
  try {
    const parsedQuery = reformQuerySchema.parse(query);
    if (parsedQuery.kind !== 'decision')
      throw new ReformContractError('unsupported', 'Only decision verification is implemented');
    const cert = validateReformCertificateBindings(input, query, [bundle], snapshot);
    if (cert.kind !== 'decision')
      throw new ReformContractError('unsupported', 'Only decision verification is implemented');
    certificate = cert;
    statement = constructReformDecisionStatement(query, snapshot, bundle, certificate);
    base.certificateDigest = digest(certificate);
    base.statementDigest = digest({
      core: reformLeanCore,
      statement,
      query,
      snapshot,
      bundle,
      certificate,
    });
  } catch (error) {
    return {
      ...base,
      status:
        error instanceof ReformContractError && error.code === 'unsupported'
          ? 'unsupported'
          : 'rejected',
      reason: error instanceof Error ? error.message : 'Invalid decision certificate',
      durationMs: Date.now() - started,
    };
  }
  const lean = await discoverLean();
  base.version = lean.version;
  if (!lean.available || !lean.binary) {
    return {
      ...base,
      status: 'inconclusive',
      reason: 'Exact Lean 4.30.0 unavailable',
      durationMs: Date.now() - started,
    };
  }
  base.toolchainDigest = digest({
    lean: lean.digest,
    core: reformLeanCore,
    sources: checkerSources,
  });
  base.method = 'case-theorem';
  let directory: string | undefined;
  try {
    directory = await mkdtemp(join(tmpdir(), 'normlab-reform-proof-'));
    const path = join(directory, 'Decision.lean');
    await writeFile(path, `${reformLeanCore}\n${statement}`, { mode: 0o600 });
    const { stdout, stderr } = await execute(lean.binary, ['-M512', '-T200000', path], {
      cwd: root,
      timeout: 30000,
      maxBuffer: 128 * 1024,
      env: { PATH: '/usr/bin:/bin', TMPDIR: directory, LANG: 'en_US.UTF-8' },
    });
    const report = /'NormLabReform\.checked' depends on axioms: \[([^\]]*)\]/.exec(stdout);
    const free = stdout.includes("'NormLabReform.checked' does not depend on any axioms");
    const axioms = report
      ? report[1]
          .split(',')
          .map((x) => x.trim())
          .filter(Boolean)
      : [];
    if (
      (!report && !free) ||
      axioms.some((x) => x !== 'propext') ||
      stderr.trim() ||
      stdout.includes('warning:')
    )
      return {
        ...base,
        status: 'inconclusive',
        reason: 'Lean axiom audit unavailable or outside allowlist',
        durationMs: Date.now() - started,
      };
    return {
      ...base,
      status: 'verified',
      axioms,
      reason:
        'Kernel checked exact consequences, mandatory ledger, ordered steps and every snapshot completion',
      durationMs: Date.now() - started,
    };
  } catch (error) {
    const output = error as { stdout?: string };
    const falseStatement =
      output.stdout?.includes('proved that the proposition') && output.stdout.includes('is false');
    return {
      ...base,
      status: falseStatement ? 'rejected' : 'inconclusive',
      reason: falseStatement
        ? 'Lean independently refuted the candidate result'
        : 'Lean failed or exceeded resource limits',
      durationMs: Date.now() - started,
    };
  } finally {
    if (directory) await rm(directory, { recursive: true, force: true });
  }
}
