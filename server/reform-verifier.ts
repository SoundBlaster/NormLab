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
  type ReformCompletedInput,
  type ReformOutcome,
  type ReformQuery,
  type ReformReceipt,
  type ReformResult,
  type ReformSnapshot,
} from '../shared/reform-contracts.js';
import { ReformContractError } from '../shared/reform-semantics.js';
import {
  boundReformBundles,
  validateReformCertificateBindings,
  validateReformQuery,
} from './reform-bindings.js';
import { digest } from './hash.js';
import { discoverLean } from './verifier.js';
import { validateReformBundle } from './reform-models.js';

const execute = promisify(execFile);
const coreUrl = new URL('../lean/Reform.lean', import.meta.url);
export const reformLeanCore = readFileSync(coreUrl, 'utf8');
const root = new URL('../', import.meta.url);
function leanMemoryLimit(): number {
  const configured = process.env.NORMLAB_LEAN_MEMORY_MB;
  if (configured === undefined) return 512;
  const value = Number(configured);
  return Number.isInteger(value) && value >= 512 && value <= 4096 ? value : 512;
}
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

const comparisonProperties = {
  equivalence: 'equivalence',
  'component-no-increase': 'noIncrease',
  'strict-reduction': 'strictReduction',
  'preserved-outside': 'preservedOutside',
} as const;
function leanInput(x: ReformCompletedInput): string {
  return `{ group := .${x.group}, M := ${x.M}, N := ${x.N}, E := ${x.E} }`;
}
function leanOutcome(y: ReformOutcome): string {
  return `{ qualification := .${y.qualification}, months := ${y.prisonMonths}, fine := ${y.fineAmount} }`;
}
type ComparisonCertificate = Extract<ReformCertificate, { kind: 'comparison' }>;
type PropertyCertificate = Extract<ReformCertificate, { kind: 'property' }>;
function leanRow(row: ComparisonCertificate['result']['rows'][number]): string {
  return `{ input := ${leanInput(row.input)}, baseline := ${leanOutcome(row.baseline)}, candidate := ${leanOutcome(row.candidate)} }`;
}
function leanPair(pair: PropertyCertificate['result']['pairs'][number]): string {
  return `{ before := ${leanInput(pair.before)}, after := ${leanInput(pair.after)}, baseline := ${leanOutcome(pair.baseline)}, candidate := ${leanOutcome(pair.candidate)} }`;
}

// The query fixes models, direction, property and scope; the candidate supplies only evidence.
export function constructReformStatement(
  expectedQuery: ReformQuery,
  bundles: ReformBundle[],
  input: unknown,
  snapshot?: ReformSnapshot,
): string {
  const query = validateReformQuery(expectedQuery, bundles, snapshot);
  const certificate = reformCertificateSchema.parse(input);
  if (certificate.kind !== query.kind || certificate.queryDigest !== digest(query))
    throw new ReformContractError('invalid', 'Statement query binding mismatch');
  if (
    certificate.kind !== 'decision' &&
    (certificate.result.verdict === 'counterexample') !==
      (certificate.result.counterexample !== null)
  )
    throw new ReformContractError('invalid', 'Verdict/witness mismatch');
  const model = (id: string) => bundles.find((bundle) => bundle.id === id)!;
  if (query.kind === 'decision')
    return constructReformDecisionStatement(query, snapshot!, model(query.model.id), certificate);
  if (query.kind === 'comparison' && certificate.kind === 'comparison') {
    const r = certificate.result;
    const witness = r.counterexample === null ? 'none' : 'some counterexample';
    const witnessDeclaration =
      r.counterexample === null
        ? ''
        : `def counterexample : ComparisonRow := ${leanRow(r.counterexample)}\n`;
    const full = r.method === 'exhaustive-finite-domain';
    const extra =
      r.verdict === 'counterexample'
        ? `theorem scopeRefuted : counterexample.input ∈ comparisonDomain boundProperty ∧ ModelPermissible boundBaseline counterexample.input counterexample.baseline ∧ ModelPermissible boundCandidate counterexample.input counterexample.candidate ∧ ¬ ConsequenceRelation boundProperty counterexample.baseline counterexample.candidate := comparison_counterexample boundBaseline boundCandidate boundProperty ${full} candidateRows counterexample checked\n#print axioms scopeRefuted\n`
        : full
          ? 'theorem scopeChecked : ∀ x, x ∈ comparisonDomain boundProperty → ∀ ya yb, ModelPermissible boundBaseline x ya → ModelPermissible boundCandidate x yb → ConsequenceRelation boundProperty ya yb := comparison_scope_sound boundBaseline boundCandidate boundProperty candidateRows checked\n#print axioms scopeChecked\n'
          : '';
    return `namespace NormLabReform
def boundBaseline : List Rule := ${reformLeanModel(model(query.baseline.id))}
def boundCandidate : List Rule := ${reformLeanModel(model(query.candidate.id))}
def boundProperty : ComparisonProperty := .${comparisonProperties[query.property]}
def candidateRows : List ComparisonRow := [${r.rows.map(leanRow).join(',\n')}]
${witnessDeclaration}theorem baselineSupported : WellFormed boundBaseline := by decide +kernel
theorem candidateSupported : WellFormed boundCandidate := by decide +kernel
theorem checked : ValidComparison boundBaseline boundCandidate boundProperty ${full} candidateRows (${witness}) :=
  ⟨baselineSupported, candidateSupported, by decide +kernel⟩
#print axioms checked
${extra}end NormLabReform
`;
  }
  if (query.kind === 'property' && certificate.kind === 'property') {
    const r = certificate.result;
    const witness = r.counterexample === null ? 'none' : 'some counterexample';
    const witnessDeclaration =
      r.counterexample === null
        ? ''
        : `def counterexample : MitigationPair := ${leanPair(r.counterexample)}\n`;
    const full = r.method === 'exhaustive-finite-domain';
    const extra =
      r.verdict === 'counterexample'
        ? `theorem scopeRefuted : counterexample.before ∈ mitigationDomain ∧ counterexample.after = withM counterexample.before ∧ ModelPermissible boundModel counterexample.before counterexample.baseline ∧ ModelPermissible boundModel counterexample.after counterexample.candidate ∧ ¬ StrictMitigation counterexample := property_counterexample boundModel ${full} candidatePairs counterexample checked\n#print axioms scopeRefuted\n`
        : full
          ? 'theorem scopeChecked : ∀ x, x ∈ mitigationDomain → ∀ ya yb, ModelPermissible boundModel x ya → ModelPermissible boundModel (withM x) yb → Preserved ya yb ∧ yb.months < ya.months := property_scope_sound boundModel candidatePairs checked\n#print axioms scopeChecked\n'
          : '';
    return `namespace NormLabReform
def boundModel : List Rule := ${reformLeanModel(model(query.model.id))}
def candidatePairs : List MitigationPair := [${r.pairs.map(leanPair).join(',\n')}]
${witnessDeclaration}theorem supported : WellFormed boundModel := by decide +kernel
theorem checked : ValidProperty boundModel ${full} candidatePairs (${witness}) :=
  ⟨supported, by decide +kernel⟩
#print axioms checked
${extra}end NormLabReform
`;
  }
  throw new ReformContractError('unsupported', 'Unsupported query/certificate combination');
}

export async function verifyReformCertificate(
  query: ReformQuery,
  bundles: ReformBundle[],
  input: unknown,
  snapshot?: ReformSnapshot,
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
    statementDigest: digest({ core: reformLeanCore, query, snapshot: snapshot ?? null, bundles }),
    durationMs: 0,
  };
  let certificate: ReformCertificate;
  let statement: string;
  try {
    reformQuerySchema.parse(query);
    bundles = boundReformBundles(query, bundles, snapshot);
    const cert = validateReformCertificateBindings(input, query, bundles, snapshot);
    certificate = cert;
    statement = constructReformStatement(query, bundles, certificate, snapshot);
    base.certificateDigest = digest(certificate);
    base.statementDigest = digest({
      core: reformLeanCore,
      statement,
      query,
      snapshot: snapshot ?? null,
      bundles,
      certificate,
    });
  } catch (error) {
    return {
      ...base,
      status:
        error instanceof ReformContractError && error.code === 'unsupported'
          ? 'unsupported'
          : 'rejected',
      reason: error instanceof Error ? error.message : 'Invalid certificate',
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
  base.method =
    certificate.kind !== 'decision' && certificate.result.method === 'exhaustive-finite-domain'
      ? 'finite-domain-theorem'
      : 'case-theorem';
  let directory: string | undefined;
  try {
    directory = await mkdtemp(join(tmpdir(), 'normlab-reform-proof-'));
    const path = join(directory, 'Decision.lean');
    await writeFile(path, `${reformLeanCore}\n${statement}`, { mode: 0o600 });
    const { stdout, stderr } = await execute(
      lean.binary,
      [`-M${leanMemoryLimit()}`, '-T200000', path],
      {
        cwd: root,
        timeout: 30000,
        maxBuffer: 128 * 1024,
        env: { PATH: '/usr/bin:/bin', TMPDIR: directory, LANG: 'en_US.UTF-8' },
      },
    );
    const expectedNames = ['NormLabReform.checked'];
    if (certificate.kind !== 'decision') {
      if (certificate.result.verdict === 'counterexample')
        expectedNames.push('NormLabReform.scopeRefuted');
      else if (certificate.result.method === 'exhaustive-finite-domain')
        expectedNames.push('NormLabReform.scopeChecked');
    }
    const reports = [
      ...stdout.matchAll(
        /'([^']+)' (?:does not depend on any axioms|depends on axioms: \[([^\]]*)\])/g,
      ),
    ];
    const axioms = [
      ...new Set(
        reports.flatMap(
          (report) =>
            report[2]
              ?.split(',')
              .map((x) => x.trim())
              .filter(Boolean) ?? [],
        ),
      ),
    ];
    if (
      digest(reports.map((report) => report[1])) !== digest(expectedNames) ||
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
        certificate.kind === 'decision'
          ? 'Kernel checked exact consequences, mandatory ledger, ordered steps and every snapshot completion'
          : certificate.result.verdict === 'counterexample'
            ? 'Kernel checked admissible outcomes and a bound counterexample in the declared query scope'
            : certificate.result.method === 'exhaustive-finite-domain'
              ? 'Kernel checked all finite-domain outcomes and the universal property in the declared scope'
              : 'Kernel checked supplied corpus outcomes and their property; no universal coverage claimed',
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

// Preserve the decision-only entry point. General queries use verifyReformCertificate.
export async function verifyReformDecision(
  query: ReformQuery,
  snapshot: ReformSnapshot,
  bundle: ReformBundle,
  input: unknown,
): Promise<ReformVerification> {
  if (query.kind !== 'decision')
    return {
      status: 'unsupported',
      engine: 'lean-kernel',
      version: null,
      method: null,
      toolchainDigest: null,
      axioms: [],
      reason: 'Decision entry point only accepts decision queries',
      queryDigest: digest(query),
      certificateDigest: null,
      statementDigest: digest({ query, snapshot, bundle }),
      durationMs: 0,
    };
  return verifyReformCertificate(query, [bundle], input, snapshot);
}
