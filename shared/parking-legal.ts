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
export const legalFindingSchema = z
  .object({
    conditionId: z.string().refine((id) => manifest.conditions.some((c) => c.id === id)),
    state: z.enum(legalStates),
    rationale: z.string().trim().max(2048),
    statementIds: z.array(z.string().uuid()).max(256),
  })
  .strict()
  .superRefine((finding, ctx) => {
    if (finding.state !== 'unreviewed' && !finding.rationale)
      ctx.addIssue({ code: 'custom', message: 'Укажите основание решения.', path: ['rationale'] });
    if (new Set(finding.statementIds).size !== finding.statementIds.length)
      ctx.addIssue({ code: 'custom', message: 'Повторяются ссылки на утверждения.' });
  });
export type LegalFinding = z.infer<typeof legalFindingSchema>;
export const emptyLegalFindings = (): LegalFinding[] =>
  manifest.conditions.map((c) => ({
    conditionId: c.id,
    state: 'unreviewed',
    rationale: '',
    statementIds: [],
  }));
export const legalInputSchema = z
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
    findings: z.array(legalFindingSchema).length(manifest.conditions.length),
  })
  .strict()
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

/** A finite fragment evaluator, not a determination of liability or a Lean certificate. */
export function evaluateParkingFragment(input: LegalInput) {
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
export type LegalResult = ReturnType<typeof evaluateParkingFragment>;
export type LegalAssessment = {
  schema: 'normlab.parking-legal-assessment/v1';
  id: string;
  sequence: number;
  createdAt: string;
  actor: 'human-operator';
  sourceDigest: string;
  input: LegalInput;
  package: typeof manifest;
  result: LegalResult | null;
};
export type LegalWorkspace = {
  package: typeof manifest;
  packageDigest: string;
  assessments: LegalAssessment[];
};
