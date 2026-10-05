import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, existsSync, writeFileSync } from 'node:fs';
import { resolve, basename } from 'node:path';
import { execFileSync } from 'node:child_process';
import expectations from '../evaluation/expectations.json';
import {
  createParkingTypedRequest,
  consumeParkingTypedExtraction,
} from '../server/parking-typed-extraction.js';
import { reviewStatementSchema, reviewStatementIssues } from '../shared/parking-review.js';
import { writeBaselineArtifactManifest } from './baseline-artifact-manifest.js';

const output = resolve(process.argv[2] ?? 'experiments/parking-evaluation/2026-10-05');
mkdirSync(resolve(output, '..'), { recursive: true });
mkdirSync(output);
const sha256 = (value: string) => createHash('sha256').update(value).digest('hex');
const directories = process.argv.slice(3);
const inputs = directories.length
  ? directories
  : [
      'experiments/parking-baseline/2026-10-05-typed-quotes-gpt-oss-20b',
      'experiments/parking-baseline/2026-10-05-codex-gpt-6-luna-low',
    ];
type Assertion = { predicate: string; stance: string; aboutEpisode: string };
const runs = inputs.map((input) => {
  const directory = resolve(input);
  const manifest = JSON.parse(
    readFileSync(resolve(directory, 'artifact-manifest.json'), 'utf8'),
  ) as {
    entries: { path: string; sha256: string }[];
  };
  const verifiedArtifacts = new Set<string>();
  for (const entry of manifest.entries) {
    const file = resolve(directory, entry.path);
    if (
      !file.startsWith(`${directory}/`) ||
      createHash('sha256').update(readFileSync(file)).digest('hex') !== entry.sha256
    )
      throw new Error(`Artifact drift: ${entry.path}`);
    verifiedArtifacts.add(entry.path);
  }
  const requireArtifact = (path: string) => {
    if (!verifiedArtifacts.has(path))
      throw new Error(`Scored artifact missing from verified manifest: ${path}`);
  };
  const cases = expectations.cases.map((label) => {
    const source = readFileSync(
      resolve(`fixtures/parking-pilot/reference/${label.id}.source.txt`),
      'utf8',
    );
    const file = resolve(directory, `${label.id}.content.txt`),
      flatFile = resolve(directory, `${label.id}.output.json`);
    let assertions: Assertion[] = [],
      gate: boolean | null = false,
      error: unknown = null;
    let scope = 'ontology-graph',
      rawDigest: string | null = null,
      latencyMs: number | null = null;
    if (existsSync(file)) {
      requireArtifact(`${label.id}.content.txt`);
      requireArtifact(`${label.id}.request.json`);
      requireArtifact(`${label.id}.result.json`);
      const raw = readFileSync(file, 'utf8');
      rawDigest = sha256(raw);
      const binding = JSON.parse(
        readFileSync(resolve(directory, `${label.id}.request.json`), 'utf8'),
      ) as { bindings: { sourceDigest: string } };
      if (binding.bindings.sourceDigest !== sha256(source))
        throw new Error(`Source drift: ${label.id}`);
      const validation = consumeParkingTypedExtraction(
        raw,
        createParkingTypedRequest(`${label.id}-reference-v1`, source),
      );
      gate = validation.ok;
      error = validation.ok ? null : validation.issues;
      const parsed = JSON.parse(raw) as { assertions?: Assertion[] };
      assertions = Array.isArray(parsed.assertions) ? parsed.assertions : [];
      const result = JSON.parse(
        readFileSync(resolve(directory, `${label.id}.result.json`), 'utf8'),
      ) as { latencyMs: number };
      latencyMs = result.latencyMs;
    } else if (existsSync(flatFile)) {
      requireArtifact(`${label.id}.output.json`);
      scope = 'statement-proposal';
      const raw = readFileSync(flatFile, 'utf8');
      rawDigest = sha256(raw);
      const parsed = JSON.parse(raw) as {
        sourceDigest: string;
        statements: unknown[];
        error: unknown;
        quarantine: unknown[];
        latencyMs: number;
      };
      if (parsed.sourceDigest !== sha256(source)) throw new Error(`Source drift: ${label.id}`);
      const statements = parsed.statements.map((s) => reviewStatementSchema.parse(s));
      gate =
        !parsed.error &&
        statements.length > 0 &&
        !parsed.quarantine.length &&
        statements.every((s) => !reviewStatementIssues(s, source).length);
      error =
        parsed.error ||
        (!statements.length
          ? 'empty-extraction'
          : parsed.quarantine.length
            ? 'quarantined-extractions'
            : null);
      assertions = statements;
      latencyMs = parsed.latencyMs;
    } else error = 'not-attempted-or-provider-failure';
    const missing = label.required.filter(
      ([predicate, stance]) =>
        !assertions.some((a) => a.predicate === `nlinput:${predicate}` && a.stance === stance),
    );
    const unsupported = label.forbidden.filter(([predicate, stance]) =>
      assertions.some((a) => a.predicate === `nlinput:${predicate}` && a.stance === stance),
    );
    const opposing = assertions.filter((a) => a.predicate === 'nlinput:payment');
    const conflictPass =
      !('opposingPaymentSameEpisode' in label) ||
      opposing.some(
        (a) =>
          a.stance === 'asserted' &&
          opposing.some((b) => b.stance === 'denied' && b.aboutEpisode === a.aboutEpisode),
      );
    const criticalChecksPass =
      gate === true && !missing.length && !unsupported.length && conflictPass;
    return {
      caseId: label.id,
      sourceDigest: sha256(source),
      rawDigest,
      scope,
      gate,
      error,
      missing,
      unsupported,
      conflictPass,
      criticalChecksPass,
      latencyMs,
      semanticReview: 'pending',
      releaseEligible: false,
      humanReviewChecklist: label.review,
    };
  });
  return {
    name: basename(directory),
    artifactManifestDigest: existsSync(resolve(directory, 'artifact-manifest.json'))
      ? sha256(readFileSync(resolve(directory, 'artifact-manifest.json'), 'utf8'))
      : null,
    cases,
    metrics: {
      attempted_cases: cases.filter((c) => c.rawDigest).length,
      total_cases: cases.length,
      structure_pass_rate: cases.filter((c) => c.gate).length / cases.length,
      candidate_case_pass_rate: cases.filter((c) => c.criticalChecksPass).length / cases.length,
      semantic_review_pending: cases.length,
      target_case_pass_rate: expectations.targetCasePassRate,
    },
    releaseCasePassRate: null,
  };
});
const report = {
  schema: 'normlab.parking-evaluation-report/v1',
  createdAt: new Date().toISOString(),
  expectationsStatus: expectations.status,
  expectationsDigest: sha256(JSON.stringify(expectations)),
  scorerDigest: sha256(readFileSync(new URL(import.meta.url), 'utf8')),
  runs,
  notes: [
    'Candidate checks are incomplete semantic coverage, not expert approval.',
    'Graph and statement gates have different scopes; do not treat flat statement acceptance as graph validity.',
    'Provider failures remain in denominator.',
    'Raw assertions are inspected diagnostically even if graph gate rejects; they never become trusted proposals.',
  ],
};
writeFileSync(resolve(output, 'report.json'), `${JSON.stringify(report, null, 2)}\n`);
writeFileSync(resolve(output, 'scorer-source.ts'), readFileSync(new URL(import.meta.url)));
writeFileSync(resolve(output, 'expectations.json'), `${JSON.stringify(expectations, null, 2)}\n`);
writeBaselineArtifactManifest(output);
console.log(
  runs
    .map(
      (r) =>
        `${r.name}: structure ${r.metrics.structure_pass_rate}, candidate critical checks ${r.metrics.candidate_case_pass_rate}, release score pending`,
    )
    .join('\n'),
);
if (process.env.NORMLAB_MLFLOW_IMPORT === '1') {
  execFileSync(
    resolve('.tools/parking-evaluation/bin/python'),
    [resolve('evaluation/import_mlflow.py'), resolve(output, 'report.json')],
    { stdio: 'inherit' },
  );
}
