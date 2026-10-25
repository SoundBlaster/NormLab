import { z } from 'zod';
import manifest from '../norms/moscow-parking/manifest.json';

export const parkingNormDraft = manifest;
export const legalStates = [
  'unreviewed',
  'established',
  'refuted',
  'not-established',
  'conflict',
] as const;
export const legalStateLabels: Record<(typeof legalStates)[number], string> = {
  unreviewed: 'Не рассмотрено',
  established: 'Установлено',
  refuted: 'Опровергнуто',
  'not-established': 'Не установлено',
  conflict: 'Противоречие',
};
// Stored wire format is separate from admission policy. Tightening the latter
// must not retroactively invalidate immutable assessment receipts.
const storedLegalFindingSchema = z
  .object({
    conditionId: z.string().min(1).max(128),
    state: z.enum(legalStates),
    rationale: z.string().trim().max(2048),
    statementIds: z.array(z.string().uuid()).max(256),
    /** Source candidate, which the human may amend; not automatic acceptance. */
    proposalId: z.string().uuid().optional(),
  })
  .strict();
export const legalFindingSchema = storedLegalFindingSchema.superRefine((finding, ctx) => {
  if (!manifest.conditions.some((condition) => condition.id === finding.conditionId))
    ctx.addIssue({ code: 'custom', message: 'Неизвестное условие нормы.', path: ['conditionId'] });
  if (finding.state !== 'unreviewed' && !finding.rationale)
    ctx.addIssue({ code: 'custom', message: 'Укажите основание решения.', path: ['rationale'] });
  if (new Set(finding.statementIds).size !== finding.statementIds.length)
    ctx.addIssue({ code: 'custom', message: 'Повторяются ссылки на утверждения.' });
});
export type LegalFinding = z.infer<typeof legalFindingSchema>;
/** An operator-selected definitive state, with no quoted source references. */
export const isUncitedLegalFinding = (finding: LegalFinding): boolean =>
  ['established', 'refuted', 'conflict'].includes(finding.state) && !finding.statementIds.length;
export const emptyLegalFindings = (): LegalFinding[] =>
  manifest.conditions.map((c) => ({
    conditionId: c.id,
    state: 'unreviewed',
    rationale: '',
    statementIds: [],
  }));
/** Frozen stored assessment v1/v2 wire format; no current finding admission policy. */
export const storedLegalInputSchema = z
  .object({
    draftId: z.string().uuid(),
    expectedRevisionId: z.string().uuid(),
    expectedAssessmentId: z.string().uuid().nullable(),
    requestId: z.string().uuid(),
    packageDigest: z.string().regex(/^[a-f0-9]{64}$/),
    action: z.enum(['save', 'calculate']),
    episode: z.string().trim().min(1).max(128),
    vehicle: z.string().trim().max(256),
    participant: z.string().trim().max(256),
    eventDate: z
      .string()
      .regex(/^(?:\d{4}-\d{2}-\d{2})?$/)
      .refine((value) => {
        if (!value) return true;
        const date = new Date(`${value}T00:00:00Z`);
        return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
      }, 'Укажите действительную дату события.'),
    location: z.string().trim().max(512),
    timeInterval: z.string().trim().max(512),
    claimedFine: z.number().int().min(0).max(1000000).nullable(),
    coordinateProposalId: z.string().uuid().optional(),
    findings: z.array(storedLegalFindingSchema).length(9),
  })
  .strict();
export const legalInputSchema = storedLegalInputSchema
  .extend({ findings: z.array(legalFindingSchema).length(manifest.conditions.length) })
  .superRefine((input, ctx) => {
    if (new Set(input.findings.map((f) => f.conditionId)).size !== manifest.conditions.length)
      ctx.addIssue({ code: 'custom', message: 'Нужен один finding для каждого условия.' });
  });
export type LegalInput = z.infer<typeof legalInputSchema>;
export const legalOutcomeLabels = {
  'fragment-matched': 'Условия фрагмента неуплаты выполнены',
  'fragment-refuted': 'Условие фрагмента опровергнуто',
  unsupported: 'Сценарий выходит за границы пилота',
  conflict: 'Требуется разрешить противоречие',
  incomplete: 'Требуется уточнение',
} as const;
export type LegalOutcome = keyof typeof legalOutcomeLabels;

const conditionIdSchema = z.string().refine((id) => manifest.conditions.some((c) => c.id === id));
const outcomeSchema = z.enum([
  'conflict',
  'unsupported',
  'incomplete',
  'fragment-refuted',
  'fragment-matched',
]);
export const legalResultSchema = z.strictObject({
  outcome: outcomeSchema,
  conflicts: z.array(conditionIdSchema).max(9),
  unsupported: z.array(conditionIdSchema).max(9),
  refuted: z.array(conditionIdSchema).max(9),
  missing: z.array(z.string()).max(14),
  candidateFine: z.number().int().min(0).max(1000000).nullable(),
  sanctionComparison: z.enum([
    'not-mentioned',
    'not-computable',
    'draft-match',
    'draft-difference',
  ]),
  branches: z
    .array(
      z.strictObject({
        conditionId: conditionIdSchema,
        assumedState: z.enum(['established', 'refuted']),
        outcome: outcomeSchema,
      }),
    )
    .max(2),
  normativeStatus: z.literal('research-draft'),
  liability: z.literal('not-assessed'),
  proof: z.literal('none'),
});
export type LegalResult = z.infer<typeof legalResultSchema>;

const parkingScopeBindingFields = {
  action: z.literal('record-reviewed-findings'),
  draftId: z.string().uuid(),
  revisionId: z.string().uuid(),
  assessmentId: z.string().uuid(),
  sourceDigest: z.string().regex(/^[a-f0-9]{64}$/),
  sourceRevisionDigest: z.string().regex(/^[a-f0-9]{64}$/),
  sourceStatementsDigest: z.string().regex(/^[a-f0-9]{64}$/),
  findingsDigest: z.string().regex(/^[a-f0-9]{64}$/),
  scope: z.strictObject({
    episode: legalInputSchema.shape.episode,
    participant: legalInputSchema.shape.participant,
    vehicle: legalInputSchema.shape.vehicle,
    eventDate: legalInputSchema.shape.eventDate,
    location: legalInputSchema.shape.location,
    timeInterval: legalInputSchema.shape.timeInterval,
  }),
  statementIds: z.array(z.string().uuid()).max(256),
};
export const parkingScopeBindingSchema = z.discriminatedUnion('schema', [
  z.strictObject({
    ...parkingScopeBindingFields,
    schema: z.literal('normlab.parking-scope-binding/v1'),
  }),
  z.strictObject({
    ...parkingScopeBindingFields,
    schema: z.literal('normlab.parking-scope-binding/v2'),
    uncitedConditions: z.array(conditionIdSchema).max(9),
  }),
]);
export type ParkingScopeBinding = z.infer<typeof parkingScopeBindingSchema>;

export const parkingVerificationSchema = z
  .strictObject({
    profile: z.enum(['parking-fragment-poc/v1', 'parking-fragment-poc/v2']),
    status: z.enum(['verified', 'inconclusive', 'rejected']),
    engine: z.literal('lean-kernel'),
    version: z.string().nullable(),
    inputDigest: z.string().regex(/^[a-f0-9]{64}$/),
    resultDigest: z.string().regex(/^[a-f0-9]{64}$/),
    packageDigest: z.string().regex(/^[a-f0-9]{64}$/),
    profileDigest: z.string().regex(/^[a-f0-9]{64}$/),
    statementDigest: z.string().regex(/^[a-f0-9]{64}$/),
    toolchainDigest: z
      .string()
      .regex(/^[a-f0-9]{64}$/)
      .nullable(),
    axioms: z.array(z.string()).max(16),
    reason: z.string().max(2048),
    durationMs: z.number().int().nonnegative(),
    binding: parkingScopeBindingSchema.optional(),
  })
  .refine(
    (v) =>
      v.status !== 'verified' ||
      (v.version?.includes('version 4.30.0') &&
        v.toolchainDigest !== null &&
        v.axioms.every(
          (axiom) =>
            axiom === 'propext' ||
            (v.profile === 'parking-fragment-poc/v2' && axiom === 'Quot.sound'),
        ) &&
        (v.profile !== 'parking-fragment-poc/v2' || v.binding !== undefined)),
    'Verified parking proof requires the pinned toolchain and audited axioms.',
  )
  .refine(
    (v) => v.profile !== 'parking-fragment-poc/v1' || v.binding === undefined,
    'Legacy verification cannot claim a reviewed-episode binding.',
  );
export type ParkingVerification = z.infer<typeof parkingVerificationSchema>;

/** Producer only. Independent model verification is attached to the assessment. */
export function evaluateParkingFragment(input: LegalInput): LegalResult {
  const { findings, claimedFine } = input;
  const byId = new Map(findings.map((f) => [f.conditionId, f.state]));
  const ids = (state: LegalFinding['state']) =>
    manifest.conditions.filter((c) => byId.get(c.id) === state).map((c) => c.id);
  const conflicts = ids('conflict');
  const unsupported = manifest.conditions
    .filter((c) => c.kind === 'scope' && byId.get(c.id) === 'refuted')
    .map((c) => c.id);
  const refuted = manifest.conditions
    .filter((c) => c.kind === 'core' && byId.get(c.id) === 'refuted')
    .map((c) => c.id);
  const missing = manifest.conditions
    .filter((c) => !['established', 'refuted', 'conflict'].includes(byId.get(c.id) ?? ''))
    .map((c) => c.id);
  const coordinateLabels = [
    'vehicle',
    'participant',
    'eventDate',
    'location',
    'timeInterval',
  ] as const;
  const missingCoordinates = coordinateLabels.filter((key) => !input[key]);
  missing.push(...missingCoordinates);
  const outcome: LegalOutcome = conflicts.length
    ? 'conflict'
    : unsupported.length
      ? 'unsupported'
      : missing.length
        ? 'incomplete'
        : refuted.length
          ? 'fragment-refuted'
          : 'fragment-matched';
  const candidateFine = outcome === 'fragment-matched' ? manifest.candidateSanction.amount : null;
  return {
    outcome,
    conflicts,
    unsupported,
    refuted,
    missing,
    candidateFine,
    sanctionComparison:
      claimedFine === null
        ? ('not-mentioned' as const)
        : candidateFine === null
          ? ('not-computable' as const)
          : claimedFine === candidateFine
            ? ('draft-match' as const)
            : ('draft-difference' as const),
    // One split only; never enumerate the Cartesian product or change accepted findings.
    branches:
      outcome === 'incomplete' && missing.length === 1 && !missingCoordinates.length
        ? (['established', 'refuted'] as const).map((state) => {
            const conditionId = missing[0];
            const condition = manifest.conditions.find((c) => c.id === conditionId)!;
            const branchOutcome: LegalOutcome =
              state === 'refuted' && condition.kind === 'scope'
                ? 'unsupported'
                : refuted.length || state === 'refuted'
                  ? 'fragment-refuted'
                  : 'fragment-matched';
            return { conditionId, assumedState: state, outcome: branchOutcome };
          })
        : [],
    normativeStatus: 'research-draft' as const,
    liability: 'not-assessed' as const,
    proof: 'none' as const,
  };
}
export type LegalAssessment = {
  schema: 'normlab.parking-legal-assessment/v1' | 'normlab.parking-legal-assessment/v2';
  id: string;
  sequence: number;
  createdAt: string;
  actor: 'human-operator';
  sourceDigest: string;
  input: LegalInput;
  package: typeof manifest;
  result: LegalResult | null;
  verification?: ParkingVerification | null;
  /** Derived on read against the running profile; never stored in the immutable receipt. */
  readonly verifiedByPreviousProfile?: boolean;
};
export type LegalWorkspace = {
  package: typeof manifest;
  packageDigest: string;
  assessments: LegalAssessment[];
};
