import { z } from 'zod';
import { readFileSync } from 'node:fs';
import { digestSchema } from '../shared/domain.js';
import {
  labModelRoles,
  labQueries,
  type LabModelRole,
  type LabQueryId,
} from '../shared/reform-lab.js';
import { reformMetricAnnotationsSchema } from '../shared/reform-metrics.js';
import { MAX_EXPERIMENT_BYTES, MAX_EXPERIMENT_ITEMS } from '../shared/reform-transfer.js';
import { reformReceiptSchema } from '../shared/reform-contracts.js';
import { digest } from './hash.js';
import { getReformBundle } from './reform-models.js';
import {
  comparisonQuery,
  mitigationQuery,
  getReformCounterexampleBundle,
} from './reform-queries.js';
import {
  exportReformArtifacts,
  reformExportSchema,
  verifyReformReceiptSignature,
  type ReformExport,
} from './reform-receipts.js';
import { measureReformExport, projectReformMetrics } from './reform-metrics.js';

const itemSchema = z.strictObject({
  artifact: reformExportSchema,
  annotations: reformMetricAnnotationsSchema.nullable(),
});
const lockSchema = z.strictObject({
  artifactDigest: digestSchema,
  annotationsDigest: digestSchema.nullable(),
  bundleDigests: z.array(digestSchema).min(1).max(2),
  queryDigest: digestSchema,
  certificateDigest: digestSchema,
  statementDigest: digestSchema,
  verification: reformReceiptSchema.shape.payload.shape.verification,
});
export const portableExperimentSchema = z.strictObject({
  schema: z.literal('normlab.experiment/v1'),
  createdAt: z.iso.datetime({ precision: 3 }),
  issuer: digestSchema,
  items: z.array(itemSchema).min(1).max(MAX_EXPERIMENT_ITEMS),
  manifest: z.strictObject({
    format: z.literal('synthetic-reviewed-reform/v1'),
    runtime: z.strictObject({
      leanToolchain: z.string().min(1).max(100),
      nodeEngine: z.string().min(1).max(100),
      dependencyLockDigest: digestSchema,
    }),
    locks: z.array(lockSchema).min(1).max(MAX_EXPERIMENT_ITEMS),
  }),
});
export type PortableExperiment = z.infer<typeof portableExperimentSchema>;
export const importedExperimentSchema = z.strictObject({
  id: digestSchema,
  importedAt: z.iso.datetime({ precision: 3 }),
  trustedPublicKey: z.string().min(1).max(16384),
  experiment: portableExperimentSchema,
});
export type ImportedExperiment = z.infer<typeof importedExperimentSchema>;
const runtimeLocks = {
  leanToolchain: readFileSync(new URL('../lean-toolchain', import.meta.url), 'utf8').trim(),
  nodeEngine: JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')).engines
    .node as string,
  dependencyLockDigest: digest(
    JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8')),
  ),
};
const reviewedAnnotations = reformMetricAnnotationsSchema.parse(
  JSON.parse(
    readFileSync(new URL('../fixtures/reform-v1/metric-annotations.json', import.meta.url), 'utf8'),
  ),
);

export function describePortableArtifact(artifact: ReformExport): {
  title: string;
  modelRole: LabModelRole | null;
  queryId: LabQueryId | null;
} {
  const query = artifact.query;
  if (query.kind === 'decision') {
    const role = labModelRoles.find((role) => getReformBundle(role).id === query.model.id);
    if (!role) fail('Unsupported decision model');
    return {
      title: `Модель ${role} · snapshot #${artifact.snapshot!.revision}`,
      modelRole: role,
      queryId: null,
    };
  }
  const a = getReformBundle('A'),
    b = getReformBundle('B'),
    c = getReformBundle('C');
  for (const entry of labQueries) {
    const candidate = entry.id.startsWith('AB-')
      ? b
      : entry.id.startsWith('AD-')
        ? getReformCounterexampleBundle()
        : c;
    const expected = entry.id.endsWith('strict-M-mitigation')
      ? mitigationQuery(getReformBundle(entry.id[0] as LabModelRole))
      : comparisonQuery(
          a,
          candidate,
          entry.id === 'AB-equivalence'
            ? 'equivalence'
            : entry.id === 'AC-component-no-increase'
              ? 'component-no-increase'
              : entry.id === 'AC-strict-reduction'
                ? 'strict-reduction'
                : 'preserved-outside',
        );
    if (digest(expected) === digest(query))
      return { title: entry.title, modelRole: null, queryId: entry.id };
  }
  fail('Unsupported query, scope or model roles');
}

function locks(items: PortableExperiment['items']) {
  return items.map(({ artifact, annotations }) => ({
    artifactDigest: digest(artifact),
    annotationsDigest: annotations ? digest(annotations) : null,
    bundleDigests: artifact.bundles.map(digest),
    queryDigest: digest(artifact.query),
    certificateDigest: digest(artifact.certificate),
    statementDigest: artifact.receipt.payload.bindings.statementDigest,
    verification: artifact.receipt.payload.verification,
  }));
}
function fail(message: string): never {
  throw new Error(message);
}

// Manifest integrity is separate from issuer trust and fresh proof verification.
export function validatePortableExperiment(value: unknown, trustedPublicKey: string) {
  const parsed = portableExperimentSchema.parse(value);
  // Reserve one byte for the trailing newline used by both download and CLI.
  if (Buffer.byteLength(JSON.stringify(parsed), 'utf8') + 1 > MAX_EXPERIMENT_BYTES)
    fail('Experiment exceeds the 2 MiB limit');
  if (parsed.issuer !== digest(trustedPublicKey)) fail('Trusted issuer does not match experiment');
  if (digest(parsed.manifest.runtime) !== digest(runtimeLocks))
    fail('Experiment runtime/dependency locks differ from this release');
  if (digest(parsed.manifest.locks) !== digest(locks(parsed.items)))
    fail('Experiment manifest does not match artifacts, annotations or toolchain locks');
  const registry = [
    ...(['A', 'B', 'C'] as const).map(getReformBundle),
    getReformCounterexampleBundle(),
  ];
  const seen = new Set<string>();
  const snapshots = new Map<string, string>();
  for (const { artifact, annotations } of parsed.items) {
    const id = digest(artifact);
    if (seen.has(id)) fail('Repeated artifact in experiment');
    seen.add(id);
    if (artifact.snapshot) {
      const hash = digest(artifact.snapshot);
      const previous = snapshots.get(artifact.snapshot.id);
      if (previous && previous !== hash) fail('Conflicting snapshot identities in experiment');
      snapshots.set(artifact.snapshot.id, hash);
    }
    if (!verifyReformReceiptSignature(artifact.receipt, trustedPublicKey))
      fail('Untrusted or invalid artifact signature');
    // This release imports only the exact reviewed registry, including synthetic model D.
    for (const bundle of artifact.bundles) {
      const known = registry.find((b) => b.id === bundle.id);
      if (!known || digest(known) !== digest(bundle))
        fail('Unknown model/version or altered locked bundle');
    }
    exportReformArtifacts(
      artifact.query,
      artifact.bundles,
      artifact.certificate,
      artifact.receipt,
      artifact.snapshot ?? undefined,
    );
    describePortableArtifact(artifact);
    // Annotation claims are unsigned. Accept only the reviewed fixture sidecar in this release.
    if (annotations && digest(annotations) !== digest(reviewedAnnotations))
      fail('Unknown or altered reviewed source annotations');
    projectReformMetrics(
      artifact.query,
      artifact.bundles,
      artifact.certificate,
      artifact.snapshot ?? undefined,
      annotations,
    );
  }
  return parsed;
}

export function packPortableExperiment(
  input: { artifact: ReformExport; annotations: unknown }[],
  trustedPublicKey: string,
): PortableExperiment {
  const items = input.map((item) => itemSchema.parse(item));
  return validatePortableExperiment(
    {
      schema: 'normlab.experiment/v1',
      createdAt: new Date().toISOString(),
      issuer: digest(trustedPublicKey),
      items,
      manifest: {
        format: 'synthetic-reviewed-reform/v1',
        runtime: runtimeLocks,
        locks: locks(items),
      },
    },
    trustedPublicKey,
  );
}

export async function replayPortableExperiment(value: unknown, trustedPublicKey: string) {
  // Clone and validate every item before starting a proof or accepting any record.
  const experiment = validatePortableExperiment(value, trustedPublicKey);
  const reports = [];
  for (const item of experiment.items)
    reports.push(await measureReformExport(item.artifact, trustedPublicKey, item.annotations));
  return {
    experiment,
    reports,
    current: reports.every((report) => report.evidence.current),
  };
}

export function parsePortableExperiment(text: string): PortableExperiment {
  if (Buffer.byteLength(text, 'utf8') > MAX_EXPERIMENT_BYTES)
    fail('Experiment exceeds the 2 MiB limit');
  return portableExperimentSchema.parse(JSON.parse(text));
}
