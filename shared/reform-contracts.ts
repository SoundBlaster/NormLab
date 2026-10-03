import { z } from 'zod';
import { digestSchema, findingSchema } from './domain.js';

export const REFORM_PROFILE = 'demo.reform-mitigation/v1' as const;
const id = z
  .string()
  .min(1)
  .max(96)
  .regex(/^[A-Za-z][A-Za-z0-9_-]*$/);
const version = z
  .string()
  .max(14)
  .regex(/^\d+\.\d+\.\d+$/);
const group = z.enum(['K1', 'K2']);
const months = z.number().int().min(0).max(3600);
const money = z.number().int().min(0).max(1000000);
const instant = z.iso.datetime({ precision: 3 });
const ruleStatus = z.enum(['applied', 'inapplicable', 'excluded', 'unresolved']);
// JSON Schema counts Unicode code points. Use the same unit in the runtime validator.
const text = (min: number, max: number) =>
  z
    .string()
    .regex(new RegExp(`^[\\s\\S]{${min},${max}}(?![\\s\\S])`, 'u'))
    .meta({ minLength: min, maxLength: max });
const preserved = z.tuple([
  z.literal('qualification'),
  z.literal('fineAmount'),
  z.literal('currency'),
]);

export const reformProfileSchema = z.strictObject({
  schema: z.literal('normlab.semantic-profile/v1'),
  id: z.literal(REFORM_PROFILE),
  version: z.literal('1.0.0'),
  groups: z.tuple([z.literal('K1'), z.literal('K2')]),
  predicates: z.tuple([z.literal('M'), z.literal('N'), z.literal('E')]),
  completion: z.literal('all-findings-terminal'),
  openFindings: z.tuple([z.literal('unreviewed'), z.literal('not-established')]),
  order: z.tuple([z.literal('baseline'), z.literal('exclusions'), z.literal('M'), z.literal('N')]),
  arithmetic: z.literal('exact-rational-reject-non-integral'),
  currency: z.literal('DEMO'),
  maxRules: z.literal(12),
  maxBranches: z.literal(8),
});

export const reformRuleSchema = z.strictObject({
  id,
  groups: z.array(group).min(1).max(2),
  mandatory: z.literal(true),
  applyCount: z.literal(1),
  operation: z.discriminatedUnion('kind', [
    z.strictObject({ kind: z.literal('baseline'), prisonMonths: months, fineAmount: money }),
    z.strictObject({
      kind: z.literal('scale'),
      trigger: z.enum(['M', 'N']),
      numerator: z.number().int().min(1).max(12),
      denominator: z.number().int().min(1).max(12),
      preserveFine: z.literal(true),
    }),
    z.strictObject({
      kind: z.literal('exclude'),
      trigger: z.literal('E'),
      targetTrigger: z.literal('N'),
    }),
  ]),
});

export const reformIrSchema = z.strictObject({
  schema: z.literal('normlab.legal-ir/v2'),
  profileId: z.literal(REFORM_PROFILE),
  rules: z.array(reformRuleSchema).min(4).max(12),
  scope: z.literal('synthetic-reform-D16'),
});

export const reformPackageSchema = z.strictObject({
  schema: z.literal('normlab.norm-package/v1'),
  id: z
    .string()
    .min(1)
    .max(80)
    .regex(/^[A-Za-z][A-Za-z0-9_-]*$/),
  version,
  author: text(1, 200),
  review: z.literal('local-synthetic-fixture'),
  sourceKind: z.literal('synthetic'),
  source: z.strictObject({ id, content: text(1, 32768), digest: digestSchema }),
  sourceMappings: z
    .array(
      z.strictObject({
        ruleId: id,
        sourceId: id,
        anchor: z
          .string()
          .min(1)
          .max(96)
          .regex(/^[a-z0-9-]+$/),
        originRuleIds: z.array(id).max(12),
      }),
    )
    .min(4)
    .max(12),
  ir: reformIrSchema,
});

export const reformBundleSchema = z.strictObject({
  schema: z.literal('normlab.norm-bundle/v1'),
  id,
  package: reformPackageSchema,
  profile: reformProfileSchema,
  locks: z.strictObject({ packageDigest: digestSchema, profileDigest: digestSchema }),
  semanticDigest: digestSchema,
  provenanceDigest: digestSchema,
});

const finding = z.strictObject({ state: findingSchema, rationale: text(0, 2000) });
export const reformSnapshotInputSchema = z.strictObject({
  narrative: text(1, 6000),
  group,
  findings: z.strictObject({ M: finding, N: finding, E: finding }),
});
export const reformSnapshotSchema = reformSnapshotInputSchema.extend({
  schema: z.literal('normlab.snapshot/v2'),
  id: z.uuid(),
  caseId: id,
  revision: z.number().int().min(1).max(1000000),
  createdAt: instant,
  supersedes: z.uuid().nullable(),
  authority: z.literal('simulated-reviewer'),
  digest: digestSchema,
});

export const reformCompletedInputSchema = z.strictObject({
  group,
  M: z.boolean(),
  N: z.boolean(),
  E: z.boolean(),
});
export const reformOutcomeSchema = z.strictObject({
  qualification: group,
  prisonMonths: months,
  fineAmount: money,
  currency: z.literal('DEMO'),
});
const branchLedger = z.strictObject({
  ruleId: id,
  status: z.enum(['applied', 'inapplicable', 'excluded']),
  excludedBy: id.nullable(),
});
export const reformResultSchema = z.strictObject({
  schema: z.literal('normlab.decision-result/v2'),
  status: z.enum(['complete', 'conditional']),
  branches: z
    .array(
      z.strictObject({
        when: reformCompletedInputSchema,
        outcome: reformOutcomeSchema,
        ledger: z.array(branchLedger).min(4).max(12),
        steps: z
          .array(z.strictObject({ ruleId: id, beforeMonths: months, afterMonths: months }))
          .max(2),
      }),
    )
    .min(1)
    .max(8),
  ledger: z
    .array(z.strictObject({ ruleId: id, status: ruleStatus, excludedBy: id.nullable() }))
    .min(4)
    .max(12),
});

export const reformBundleRefSchema = z.strictObject({
  id,
  semanticDigest: digestSchema,
  provenanceDigest: digestSchema,
  profileDigest: digestSchema,
});
export const reformDomainSchema = z.strictObject({
  id: z.literal('D16'),
  profileId: z.literal(REFORM_PROFILE),
  groups: z.tuple([z.literal('K1'), z.literal('K2')]),
  predicates: z.tuple([z.literal('M'), z.literal('N'), z.literal('E')]),
  cardinality: z.literal(16),
  restrictions: z.array(z.string()).length(0),
});
const queryBase = {
  schema: z.literal('normlab.query/v2'),
  domain: reformDomainSchema,
  assumptions: z.array(text(1, 1000)).min(1).max(16),
};
export const reformQuerySchema = z.discriminatedUnion('kind', [
  z.strictObject({
    ...queryBase,
    kind: z.literal('decision'),
    snapshotDigest: digestSchema,
    model: reformBundleRefSchema,
  }),
  z.strictObject({
    ...queryBase,
    kind: z.literal('comparison'),
    baseline: reformBundleRefSchema,
    candidate: reformBundleRefSchema,
    mapping: z.literal('identity-typed-consequences/v1'),
    property: z.enum([
      'equivalence',
      'component-no-increase',
      'strict-reduction',
      'preserved-outside',
    ]),
    condition: z.strictObject({ M: z.boolean() }).nullable(),
    target: z.literal('prisonMonths'),
    preserve: preserved,
  }),
  z.strictObject({
    ...queryBase,
    kind: z.literal('property'),
    model: reformBundleRefSchema,
    property: z.literal('strict-M-mitigation'),
    target: z.literal('prisonMonths'),
    preserve: preserved,
  }),
]);

const comparisonRow = z.strictObject({
  input: reformCompletedInputSchema,
  baseline: reformOutcomeSchema,
  candidate: reformOutcomeSchema,
});
const pair = z.strictObject({
  before: reformCompletedInputSchema,
  after: reformCompletedInputSchema,
  baseline: reformOutcomeSchema,
  candidate: reformOutcomeSchema,
});
const certificateBase = { schema: z.literal('normlab.certificate/v2'), queryDigest: digestSchema };
export const reformCertificateSchema = z.discriminatedUnion('kind', [
  z.strictObject({ ...certificateBase, kind: z.literal('decision'), result: reformResultSchema }),
  z.strictObject({
    ...certificateBase,
    kind: z.literal('comparison'),
    result: z.strictObject({
      verdict: z.enum(['holds', 'counterexample']),
      method: z.enum(['corpus', 'exhaustive-finite-domain']),
      rows: z.array(comparisonRow).min(1).max(16),
      counterexample: comparisonRow.nullable(),
    }),
  }),
  z.strictObject({
    ...certificateBase,
    kind: z.literal('property'),
    result: z.strictObject({
      verdict: z.enum(['holds', 'counterexample']),
      method: z.enum(['corpus', 'exhaustive-finite-domain']),
      pairs: z.array(pair).min(1).max(8),
      counterexample: pair.nullable(),
    }),
  }),
]);

export const reformReceiptSchema = z.strictObject({
  payload: z.strictObject({
    schema: z.literal('normlab.receipt/v2'),
    id: z.uuid(),
    createdAt: instant,
    queryKind: z.enum(['decision', 'comparison', 'property']),
    bindings: z.strictObject({
      queryDigest: digestSchema,
      certificateDigest: digestSchema,
      resultDigest: digestSchema,
      statementDigest: digestSchema,
      assumptionsDigest: digestSchema,
      models: z
        .array(
          z.strictObject({
            role: z.enum(['model', 'baseline', 'candidate']),
            bundle: reformBundleRefSchema,
          }),
        )
        .min(1)
        .max(2),
    }),
    coverage: z.strictObject({
      domainDigest: digestSchema,
      kind: z.enum(['snapshot-completions', 'finite-domain', 'corpus']),
      status: z.enum(['declared-complete', 'partial']),
      declaredCardinality: z.number().int().min(1).max(16),
      coveredCardinality: z.number().int().min(0).max(16),
    }),
    verification: z.strictObject({
      status: z.enum(['verified', 'inconclusive', 'rejected', 'unsupported']),
      engine: z.literal('lean-kernel'),
      version: text(1, 200).nullable(),
      method: z.enum(['case-theorem', 'finite-domain-theorem']).nullable(),
      toolchainDigest: digestSchema.nullable(),
      axioms: z.array(z.string().min(1).max(96)).max(16),
      reason: text(1, 2000),
    }),
    issuer: digestSchema,
  }),
  signature: z.string().regex(/^[A-Za-z0-9+/]{86}==$/),
  publicKey: z.string().min(1).max(2048),
});

export type ReformProfile = z.infer<typeof reformProfileSchema>;
export type ReformRule = z.infer<typeof reformRuleSchema>;
export type ReformIR = z.infer<typeof reformIrSchema>;
export type ReformPackage = z.infer<typeof reformPackageSchema>;
export type ReformBundle = z.infer<typeof reformBundleSchema>;
export type ReformSnapshotInput = z.infer<typeof reformSnapshotInputSchema>;
export type ReformSnapshot = z.infer<typeof reformSnapshotSchema>;
export type ReformCompletedInput = z.infer<typeof reformCompletedInputSchema>;
export type ReformOutcome = z.infer<typeof reformOutcomeSchema>;
export type ReformResult = z.infer<typeof reformResultSchema>;
export type ReformQuery = z.infer<typeof reformQuerySchema>;
export type ReformCertificate = z.infer<typeof reformCertificateSchema>;
export type ReformReceipt = z.infer<typeof reformReceiptSchema>;

export const reformContractSchemas = {
  'semantic-profile': reformProfileSchema,
  'legal-ir': reformIrSchema,
  'norm-package': reformPackageSchema,
  'norm-bundle': reformBundleSchema,
  'snapshot-input': reformSnapshotInputSchema,
  snapshot: reformSnapshotSchema,
  'decision-result': reformResultSchema,
  query: reformQuerySchema,
  certificate: reformCertificateSchema,
  receipt: reformReceiptSchema,
};

export function exportedReformSchemas() {
  return Object.fromEntries(
    Object.entries(reformContractSchemas).map(([name, schema]) => [
      name,
      {
        ...z.toJSONSchema(schema, {
          target: 'draft-2020-12',
          unrepresentable: 'throw',
          reused: 'ref',
        }),
        $id: `urn:normlab:contract:v2:${name}`,
      },
    ]),
  );
}
