import { z } from 'zod';

export const findingSchema = z.enum(['unreviewed', 'established', 'refuted', 'not-established']);
export type FindingState = z.infer<typeof findingSchema>;
export const terminalSchema = z.enum(['established', 'refuted']);
export const bundleIdSchema = z.enum(['reduction-v1', 'reduction-v2']);
export const snapshotInputSchema = z
  .object({
    narrative: z.string().trim().min(1).max(6000),
    finding: findingSchema,
    rationale: z.string().trim().max(2000),
  })
  .strict()
  .superRefine((input, ctx) => {
    if (input.finding !== 'unreviewed' && input.rationale.length < 3) {
      ctx.addIssue({
        code: 'custom',
        path: ['rationale'],
        message: 'Добавьте основание установления (от 3 символов).',
      });
    }
  });
export type SnapshotInput = z.infer<typeof snapshotInputSchema>;
export type Snapshot = SnapshotInput & {
  id: string;
  caseId: string;
  revision: number;
  createdAt: string;
  supersedes: string | null;
  authority: 'simulated-reviewer';
  digest: string;
};

export const legalIrSchema = z
  .object({
    schema: z.literal('normlab.legal-ir/v1'),
    profile: z.literal('demo.conditional-transform/v1'),
    baseline: z
      .object({
        prisonMonths: z.literal(120),
        fineAmount: z.literal(200000),
        currency: z.literal('DEMO'),
      })
      .strict(),
    adjustment: z
      .object({
        id: z.literal('reduce-prison-term'),
        trigger: z.literal('A'),
        numerator: z.number().int().min(1).max(12),
        denominator: z.number().int().min(1).max(12),
        mandatory: z.literal(true),
        target: z.literal('prison-months'),
        applyCount: z.literal(1),
        preserveFine: z.literal(true),
      })
      .strict(),
    coverage: z.literal('synthetic-single-adjustment'),
  })
  .strict()
  .refine(
    (ir) =>
      ir.adjustment.numerator <= ir.adjustment.denominator &&
      (120 * ir.adjustment.numerator) % ir.adjustment.denominator === 0,
    { message: 'The profile requires an integral reduction of the baseline.' },
  );
export type LegalIR = z.infer<typeof legalIrSchema>;
export type Bundle = {
  id: z.infer<typeof bundleIdSchema>;
  version: string;
  title: string;
  description: string;
  ir: LegalIR;
  semanticDigest: string;
  provenanceDigest: string;
  source: string;
  sourceKind: 'synthetic';
};

export const outcomeSchema = z
  .object({
    when: terminalSchema,
    prisonMonths: z.number().int().min(0).max(120),
    fineAmount: z.number().int().min(0).max(1000000),
    currency: z.literal('DEMO'),
    ruleStatus: z.enum(['applied', 'inapplicable']),
  })
  .strict();
export type Outcome = z.infer<typeof outcomeSchema>;
export const resultSchema = z
  .object({
    status: z.enum(['complete', 'conditional']),
    outcomes: z.array(outcomeSchema).min(1).max(2),
    ledger: z
      .array(
        z
          .object({
            ruleId: z.literal('reduce-prison-term'),
            status: z.enum(['applied', 'inapplicable', 'unresolved']),
          })
          .strict(),
      )
      .length(1),
  })
  .strict();
export type DecisionResult = z.infer<typeof resultSchema>;
export const digestSchema = z.string().regex(/^[a-f0-9]{64}$/);
export const certificateSchema = z
  .object({
    schema: z.literal('normlab.certificate/v1'),
    snapshotDigest: digestSchema,
    bundleSemanticDigest: digestSchema,
    bundleProvenanceDigest: digestSchema,
    query: z.literal('decision/v1'),
    result: resultSchema,
  })
  .strict();
export type Certificate = z.infer<typeof certificateSchema>;
export type Verification = {
  status: 'verified' | 'inconclusive' | 'rejected';
  engine: 'lean-kernel';
  version: string | null;
  statementDigest: string;
  toolchainDigest: string | null;
  axioms: string[];
  reason: string;
  durationMs: number;
};
export type ReceiptPayload = {
  schema: 'normlab.receipt/v1';
  id: string;
  createdAt: string;
  snapshotId: string;
  snapshotDigest: string;
  bundleId: Bundle['id'];
  bundleSemanticDigest: string;
  bundleProvenanceDigest: string;
  queryDigest: string;
  certificateDigest: string;
  resultDigest: string;
  assumptionDigest: string;
  assumptions: string[];
  scope: 'synthetic-single-adjustment';
  coverageStatus: 'declared-complete';
  verification: Verification;
  issuer: string;
};
export type SignedReceipt = { payload: ReceiptPayload; signature: string; publicKey: string };
export type Analysis = {
  bundle?: Bundle;
  id: string;
  snapshotId: string;
  bundleId: Bundle['id'];
  certificate: Certificate;
  receipt: SignedReceipt;
};
export type Workspace = {
  caseId: string;
  title: string;
  snapshots: Snapshot[];
  analyses: Analysis[];
};
export type Comparison = {
  baselineId: Bundle['id'];
  candidateId: Bundle['id'];
  domain: ['established', 'refuted'];
  coverage: 'exhaustive-finite-domain';
  rows: {
    finding: 'established' | 'refuted';
    baseline: Outcome;
    candidate: Outcome;
    prisonDelta: number;
  }[];
  equivalent: boolean;
  property: string;
};
export type Bootstrap = {
  csrfToken: string;
  workspace: Workspace;
  bundles: Bundle[];
  verifier: { available: boolean; version: string | null; toolchainDigest: string | null };
  comparison: Comparison;
};
