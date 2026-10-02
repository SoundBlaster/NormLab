import {
  reformIrSchema,
  reformResultSchema,
  reformSnapshotInputSchema,
  type ReformCompletedInput,
  type ReformIR,
  type ReformResult,
  type ReformRule,
  type ReformSnapshotInput,
} from './reform-contracts.js';

export class ReformContractError extends Error {
  constructor(
    readonly code: 'unsupported' | 'invalid',
    message: string,
  ) {
    super(message);
    this.name = 'ReformContractError';
  }
}

export const MAX_REFORM_JSON_BYTES = 512 * 1024;
export function parseReformJson(text: string): unknown {
  if (new TextEncoder().encode(text).byteLength > MAX_REFORM_JSON_BYTES)
    throw new ReformContractError('invalid', 'JSON envelope exceeds 512 KiB');
  return JSON.parse(text) as unknown;
}

function requireContract(condition: unknown, message: string): asserts condition {
  if (!condition) throw new ReformContractError('invalid', message);
}

export function completeDomain(): ReformCompletedInput[] {
  const rows: ReformCompletedInput[] = [];
  for (const group of ['K1', 'K2'] as const)
    for (const M of [false, true])
      for (const N of [false, true]) for (const E of [false, true]) rows.push({ group, M, N, E });
  return rows;
}

export function parseReformInput(value: unknown): ReformSnapshotInput {
  const input = reformSnapshotInputSchema.parse(value);
  requireContract(input.narrative.trim().length > 0, 'Empty narrative');
  for (const finding of Object.values(input.findings)) {
    requireContract(
      finding.state === 'unreviewed' || Array.from(finding.rationale.trim()).length >= 3,
      'Reviewed findings require rationale',
    );
  }
  return input;
}

export function completions(input: ReformSnapshotInput): ReformCompletedInput[] {
  const value = parseReformInput(input);
  return completeDomain().filter(
    (row) =>
      row.group === value.group &&
      (['M', 'N', 'E'] as const).every((predicate) => {
        const state = value.findings[predicate].state;
        return state === 'established'
          ? row[predicate]
          : state === 'refuted'
            ? !row[predicate]
            : true;
      }),
  );
}

export function isComplete(input: ReformSnapshotInput): boolean {
  return Object.values(input.findings).every(
    (f) => f.state === 'established' || f.state === 'refuted',
  );
}

function selected(ir: ReformIR, input: ReformCompletedInput): ReformRule[] {
  return ir.rules.filter((rule) => rule.groups.includes(input.group));
}

// Producer semantics. Independent permissibility and Lean proofs are a separate obligation.
function evaluateBranch(
  ir: ReformIR,
  input: ReformCompletedInput,
): ReformResult['branches'][number] {
  const matching = selected(ir, input);
  const base = matching.find((r) => r.operation.kind === 'baseline')!;
  const exclusion = matching.find((r) => r.operation.kind === 'exclude')!;
  requireContract(
    base?.operation.kind === 'baseline' && exclusion?.operation.kind === 'exclude',
    'Missing baseline or exclusion',
  );
  const excluded = input.N && input.E;
  const ledger: ReformResult['branches'][number]['ledger'] = ir.rules.map((rule) => {
    if (!matching.includes(rule))
      return { ruleId: rule.id, status: 'inapplicable', excludedBy: null };
    const op = rule.operation;
    if (op.kind === 'baseline') return { ruleId: rule.id, status: 'applied', excludedBy: null };
    if (op.kind === 'exclude')
      return { ruleId: rule.id, status: excluded ? 'applied' : 'inapplicable', excludedBy: null };
    if (!input[op.trigger]) return { ruleId: rule.id, status: 'inapplicable', excludedBy: null };
    if (op.trigger === 'N' && excluded)
      return { ruleId: rule.id, status: 'excluded', excludedBy: exclusion.id };
    return { ruleId: rule.id, status: 'applied', excludedBy: null };
  });
  let prisonMonths = base.operation.prisonMonths;
  const steps: ReformResult['branches'][number]['steps'] = [];
  for (const trigger of ['M', 'N'] as const) {
    const rule = matching.find(
      (r) => r.operation.kind === 'scale' && r.operation.trigger === trigger,
    )!;
    requireContract(rule?.operation.kind === 'scale', `Missing transform ${trigger}`);
    if (ledger.find((entry) => entry.ruleId === rule.id)!.status !== 'applied') continue;
    const product = BigInt(prisonMonths) * BigInt(rule.operation.numerator);
    const denominator = BigInt(rule.operation.denominator);
    if (product % denominator !== 0n)
      throw new ReformContractError('unsupported', 'Non-integral intermediate consequence');
    const afterMonths = Number(product / denominator);
    steps.push({ ruleId: rule.id, beforeMonths: prisonMonths, afterMonths });
    prisonMonths = afterMonths;
  }
  return {
    when: input,
    outcome: {
      qualification: input.group,
      prisonMonths,
      fineAmount: base.operation.fineAmount,
      currency: 'DEMO',
    },
    ledger,
    steps,
  };
}

export function parseSupportedReformIR(value: unknown): ReformIR {
  if (
    typeof value === 'object' &&
    value !== null &&
    'profileId' in value &&
    value.profileId !== 'demo.reform-mitigation/v1'
  )
    throw new ReformContractError('unsupported', 'Unsupported semantic profile');
  if (
    typeof value === 'object' &&
    value !== null &&
    'schema' in value &&
    value.schema !== 'normlab.legal-ir/v2'
  )
    throw new ReformContractError('unsupported', 'Unsupported Legal IR version');
  const ir = reformIrSchema.parse(value);
  requireContract(new Set(ir.rules.map((r) => r.id)).size === ir.rules.length, 'Duplicate rule ID');
  for (const rule of ir.rules) {
    requireContract(new Set(rule.groups).size === rule.groups.length, 'Duplicate group scope');
    if (rule.operation.kind === 'scale')
      requireContract(
        rule.operation.numerator <= rule.operation.denominator,
        'Reduction increases term',
      );
  }
  for (const input of completeDomain()) {
    const rules = selected(ir, input);
    for (const kind of ['baseline', 'exclude'] as const)
      requireContract(
        rules.filter((r) => r.operation.kind === kind).length === 1,
        `Expected exactly one ${kind} for ${input.group}`,
      );
    for (const trigger of ['M', 'N'] as const)
      requireContract(
        rules.filter((r) => r.operation.kind === 'scale' && r.operation.trigger === trigger)
          .length === 1,
        `Expected exactly one ${trigger} for ${input.group}`,
      );
    evaluateBranch(ir, input); // Reject a package that is unsupported anywhere in its declared D16.
  }
  return ir;
}

export function interpretReform(input: ReformSnapshotInput, value: unknown): ReformResult {
  const snapshot = parseReformInput(input);
  const ir = parseSupportedReformIR(value);
  const branches = completions(snapshot).map((when) => evaluateBranch(ir, when));
  const ledger: ReformResult['ledger'] = ir.rules.map((rule) => {
    const entries = branches.map((branch) =>
      branch.ledger.find((entry) => entry.ruleId === rule.id)!,
    );
    const first = entries[0];
    return entries.every(
      (entry) => entry.status === first.status && entry.excludedBy === first.excludedBy,
    )
      ? { ...first }
      : { ruleId: rule.id, status: 'unresolved', excludedBy: null };
  });
  return reformResultSchema.parse({
    schema: 'normlab.decision-result/v2',
    status: isComplete(snapshot) ? 'complete' : 'conditional',
    branches,
    ledger,
  });
}

// Shape, branch coverage and reference checks only; this does not certify arithmetic or permissibility.
export function validateReformResultContext(
  input: ReformSnapshotInput,
  ir: ReformIR,
  value: unknown,
): ReformResult {
  const result = reformResultSchema.parse(value);
  const expected = completions(input);
  requireContract(
    result.status === (isComplete(input) ? 'complete' : 'conditional'),
    'Wrong completion status',
  );
  requireContract(
    JSON.stringify(result.branches.map((b) => b.when)) === JSON.stringify(expected),
    'Lost, duplicated or reordered completion branch',
  );
  const ruleIds = ir.rules.map((r) => r.id);
  const checkLedger = (entries: ReformResult['ledger']) => {
    requireContract(
      JSON.stringify(entries.map((e) => e.ruleId)) === JSON.stringify(ruleIds),
      'Incomplete rule ledger',
    );
    for (const entry of entries) {
      requireContract(
        (entry.status === 'excluded') === (entry.excludedBy !== null),
        'Wrong exclusion binding',
      );
      if (entry.excludedBy !== null)
        requireContract(
          ir.rules.some((r) => r.id === entry.excludedBy && r.operation.kind === 'exclude'),
          'Unknown excluding rule',
        );
    }
  };
  checkLedger(result.ledger);
  for (const branch of result.branches) {
    checkLedger(branch.ledger);
    requireContract(branch.outcome.qualification === input.group, 'Changed qualification');
    requireContract(
      new Set(branch.steps.map((s) => s.ruleId)).size === branch.steps.length,
      'Repeated transform',
    );
    for (const step of branch.steps)
      requireContract(
        ir.rules.some((r) => r.id === step.ruleId && r.operation.kind === 'scale'),
        'Unknown transform',
      );
  }
  for (const entry of result.ledger) {
    const branches = result.branches.map((b) => b.ledger.find((e) => e.ruleId === entry.ruleId)!);
    const first = branches[0];
    const same = branches.every(
      (b) => b.status === first.status && b.excludedBy === first.excludedBy,
    );
    requireContract(
      entry.status === (same ? first.status : 'unresolved') &&
        entry.excludedBy === (same ? first.excludedBy : null),
      'Wrong summary ledger',
    );
  }
  return result;
}
