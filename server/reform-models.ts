import { readFileSync } from 'node:fs';
import {
  REFORM_PROFILE,
  reformBundleSchema,
  reformPackageSchema,
  reformProfileSchema,
  type ReformBundle,
  type ReformIR,
  type ReformPackage,
} from '../shared/reform-contracts.js';
import { parseSupportedReformIR, ReformContractError } from '../shared/reform-semantics.js';
import { digest } from './hash.js';

export const reformProfile = reformProfileSchema.parse({
  schema: 'normlab.semantic-profile/v1',
  id: REFORM_PROFILE,
  version: '1.0.0',
  groups: ['K1', 'K2'],
  predicates: ['M', 'N', 'E'],
  completion: 'all-findings-terminal',
  openFindings: ['unreviewed', 'not-established'],
  order: ['baseline', 'exclusions', 'M', 'N'],
  arithmetic: 'exact-rational-reject-non-integral',
  currency: 'DEMO',
  maxRules: 12,
  maxBranches: 8,
});

export function validateReformPackage(value: unknown): ReformPackage {
  const pkg = reformPackageSchema.parse(value);
  parseSupportedReformIR(pkg.ir);
  if (pkg.source.digest !== digest(pkg.source.content))
    throw new ReformContractError('invalid', 'Source digest mismatch');
  if (
    JSON.stringify(pkg.sourceMappings.map((m) => m.ruleId)) !==
    JSON.stringify(pkg.ir.rules.map((r) => r.id))
  )
    throw new ReformContractError('invalid', 'Missing, repeated or reordered source mapping');
  for (const mapping of pkg.sourceMappings) {
    if (
      mapping.sourceId !== pkg.source.id ||
      !pkg.source.content.includes(`### ${mapping.ruleId}\n`) ||
      mapping.anchor !== mapping.ruleId.toLowerCase() ||
      new Set(mapping.originRuleIds).size !== mapping.originRuleIds.length
    )
      throw new ReformContractError('invalid', 'Invalid source mapping');
  }
  return pkg;
}

export function lockReformPackage(value: unknown): ReformBundle {
  const pkg = validateReformPackage(value);
  return reformBundleSchema.parse({
    schema: 'normlab.norm-bundle/v1',
    id: `${pkg.id}-${pkg.version.replaceAll('.', '_')}`,
    package: pkg,
    profile: reformProfile,
    locks: { packageDigest: digest(pkg), profileDigest: digest(reformProfile) },
    semanticDigest: digest({ profile: reformProfile, ir: pkg.ir }),
    provenanceDigest: digest({
      id: pkg.id,
      version: pkg.version,
      author: pkg.author,
      review: pkg.review,
      sourceKind: pkg.sourceKind,
      source: pkg.source,
      sourceMappings: pkg.sourceMappings,
    }),
  });
}

export function validateReformBundle(value: unknown): ReformBundle {
  const bundle = reformBundleSchema.parse(value);
  const expected = lockReformPackage(bundle.package);
  if (digest(bundle) !== digest(expected))
    throw new ReformContractError('invalid', 'Bundle lock or digest mismatch');
  return bundle;
}

type FixtureModel = {
  role: 'A' | 'B' | 'C';
  provisions: (ReformIR['rules'][number] & { sourceRef: string; originIds: string[] })[];
};
const fixtureRoot = new URL('../fixtures/reform-v1/', import.meta.url);
const plan = JSON.parse(readFileSync(new URL('fixture.json', fixtureRoot), 'utf8')) as {
  schema: string;
  models: FixtureModel[];
};
if (plan.schema !== 'normlab.reform-fixture-plan/v1') throw new Error('Unsupported fixture plan');
const source = readFileSync(new URL('source.md', fixtureRoot), 'utf8');
const registry = plan.models.map((model) => {
  const pkg: ReformPackage = {
    schema: 'normlab.norm-package/v1',
    id: `reform-${model.role}`,
    version: '0.1.0',
    author: 'NormLab synthetic laboratory',
    review: 'local-synthetic-fixture',
    sourceKind: 'synthetic',
    source: { id: 'reform-source', content: source, digest: digest(source) },
    sourceMappings: model.provisions.map((rule) => ({
      ruleId: rule.id,
      sourceId: 'reform-source',
      anchor: rule.id.toLowerCase(),
      originRuleIds: rule.originIds,
    })),
    ir: {
      schema: 'normlab.legal-ir/v2',
      profileId: REFORM_PROFILE,
      scope: 'synthetic-reform-D16',
      rules: model.provisions.map(({ id, groups, mandatory, applyCount, operation }) => ({
        id,
        groups,
        mandatory,
        applyCount,
        operation,
      })),
    },
  };
  for (const rule of model.provisions)
    if (rule.sourceRef !== `source.md#${rule.id.toLowerCase()}`)
      throw new Error('Fixture source reference mismatch');
  return { role: model.role, bundle: lockReformPackage(pkg) };
});
if (
  registry.length !== 3 ||
  JSON.stringify(registry.map((r) => r.role).sort()) !== JSON.stringify(['A', 'B', 'C'])
)
  throw new Error('Fixture must contain A/B/C exactly once');
const knownRuleIds = new Set(
  registry.flatMap((r) => r.bundle.package.ir.rules.map((rule) => rule.id)),
);
for (const { bundle } of registry)
  for (const mapping of bundle.package.sourceMappings)
    if (mapping.originRuleIds.some((id) => !knownRuleIds.has(id)))
      throw new Error('Unknown fixture origin');

export function getReformBundle(role: 'A' | 'B' | 'C'): ReformBundle {
  const entry = registry.find((item) => item.role === role);
  if (!entry) throw new ReformContractError('unsupported', 'Unknown fixture model');
  return structuredClone(entry.bundle);
}
