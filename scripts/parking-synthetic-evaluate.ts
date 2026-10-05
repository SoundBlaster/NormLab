import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { basename, resolve } from 'node:path';
import { reviewStatementSchema, reviewStatementIssues } from '../shared/parking-review.js';
import { writeBaselineArtifactManifest } from './baseline-artifact-manifest.js';

const dataset = resolve('fixtures/parking-pilot/synthetic-v1');
const corpusPath = resolve(dataset, 'manifest.json');
const labelsPath = resolve(dataset, 'reviewer-expectations.json');
const demoExampleQuotes = new Set([
  'В Туле машина стояла с 09:00',
  'Я оплатил парковку',
  'я не оплатил парковку',
]);
const [outputArgument, ...runArguments] = process.argv.slice(2);
if (!outputArgument || runArguments.length === 0) {
  throw new Error(
    'Usage: npm run parking:evaluate:synthetic -- <new-report-directory> <extraction-run-directory...>',
  );
}

const output = resolve(outputArgument);
mkdirSync(resolve(output, '..'), { recursive: true });
mkdirSync(output);
const sha256 = (value: string | Buffer) => createHash('sha256').update(value).digest('hex');
const corpus = JSON.parse(readFileSync(corpusPath, 'utf8')) as {
  schema: string;
  version: number;
  status: string;
  caseCount: number;
  realIncidentCount: number;
  cases: {
    id: string;
    sourceFile: string;
    sourceDigest: string;
    family: string;
    splitGroup: string;
    labelsFile: string;
    inputFile: string;
  }[];
};
const labels = JSON.parse(readFileSync(labelsPath, 'utf8')) as {
  schema: string;
  status: string;
  cases: {
    id: string;
    required: {
      predicate: string;
      stance: 'asserted' | 'denied' | 'unknown';
      quote: string;
      startOffset: number;
      endOffset: number;
    }[];
    forbidden: [string, 'asserted' | 'denied' | 'unknown'][];
    expectedGaps: { field: string; reason: string; status: string; purpose: string }[];
    reviewFocus: string;
  }[];
};

if (
  corpus.status !== 'development-not-holdout' ||
  corpus.realIncidentCount !== 0 ||
  labels.status !== 'candidate-not-expert-approved' ||
  corpus.cases.length !== corpus.caseCount
)
  throw new Error('Synthetic corpus status or case-count contract changed.');

const labelById = new Map(labels.cases.map((label) => [label.id, label]));
if (labelById.size !== corpus.cases.length || corpus.cases.some((item) => !labelById.has(item.id)))
  throw new Error('Corpus manifest and reviewer expectations have different case IDs.');

for (const item of corpus.cases) {
  const source = readFileSync(resolve(dataset, item.sourceFile), 'utf8');
  if (sha256(source) !== item.sourceDigest) throw new Error(`Corpus source drift: ${item.id}`);
  const label = labelById.get(item.id)!;
  for (const required of label.required) {
    const quote = source.slice(required.startOffset, required.endOffset);
    if (quote !== required.quote) throw new Error(`Candidate expectation anchor drift: ${item.id}`);
  }
}

function verifyManifest(directory: string) {
  const path = resolve(directory, 'artifact-manifest.json');
  if (!existsSync(path)) throw new Error(`Missing artifact-manifest.json: ${directory}`);
  const manifest = JSON.parse(readFileSync(path, 'utf8')) as {
    schema: string;
    signed: boolean;
    entries: { path: string; sha256: string }[];
  };
  if (manifest.schema !== 'normlab.baseline-artifacts/v1' || manifest.signed !== false)
    throw new Error(`Unsupported artifact manifest: ${directory}`);
  const verified = new Set<string>();
  for (const entry of manifest.entries) {
    const file = resolve(directory, entry.path);
    if (!file.startsWith(`${directory}/`) || !existsSync(file))
      throw new Error(`Unsafe or missing artifact path: ${entry.path}`);
    if (sha256(readFileSync(file)) !== entry.sha256)
      throw new Error(`Artifact digest mismatch: ${basename(directory)}/${entry.path}`);
    verified.add(entry.path);
  }
  return { digest: sha256(readFileSync(path)), verified };
}

function scoreRun(argument: string) {
  const directory = resolve(argument);
  const { digest: manifestDigest, verified } = verifyManifest(directory);
  const runManifestPath = resolve(directory, 'run-manifest.json');
  if (!verified.has('run-manifest.json') || !existsSync(runManifestPath))
    throw new Error(`Missing verified run-manifest.json: ${directory}`);
  const runManifest = existsSync(runManifestPath)
    ? (JSON.parse(readFileSync(runManifestPath, 'utf8')) as {
        schema?: string;
        model?: string;
        provider?: string;
        pipeline?: string;
        records?: {
          caseId: string;
          status: string;
          returnCode: number | null;
          error: string | null;
          elapsedSeconds?: number;
        }[];
      })
    : null;
  if (runManifest?.schema !== 'normlab.synthetic-extraction-run/v1')
    throw new Error(`Unsupported run manifest: ${directory}`);
  const runRecords = new Map((runManifest?.records ?? []).map((record) => [record.caseId, record]));
  for (const [name, sourcePath] of [
    ['dataset-manifest.json', corpusPath],
    ['reviewer-expectations.json', labelsPath],
  ] as const) {
    const snapshot = resolve(directory, name);
    if (!verified.has(name) || !existsSync(snapshot))
      throw new Error(`Missing verified dataset snapshot: ${name}`);
    if (sha256(readFileSync(snapshot)) !== sha256(readFileSync(sourcePath)))
      throw new Error(`Dataset snapshot differs from scorer inputs: ${name}`);
  }

  const cases = corpus.cases.map((item) => {
    const label = labelById.get(item.id)!;
    const source = readFileSync(resolve(dataset, item.sourceFile), 'utf8');
    const inputName = `${item.id}.input.json`;
    const outputName = `${item.id}.output.json`;
    const inputPath = resolve(directory, inputName);
    const outputPath = resolve(directory, outputName);
    const record = runRecords.get(item.id);
    let extractionError: string | null = record?.error ?? null;
    let inputValid = false;
    let statements: ReturnType<typeof reviewStatementSchema.parse>[] = [];
    let quarantineCount = 0;
    let structuralPass = false;
    let outputDigest: string | null = null;
    let discoveryOutcome: string | null = null;
    let discoveredFragmentCount: number | null = null;
    let classificationCalls: number | null = null;
    let modelError: string | null = null;

    if (!verified.has(inputName) || !existsSync(inputPath)) {
      extractionError ??= 'case-input-not-in-run-manifest';
    } else {
      const inputBytes = readFileSync(inputPath);
      if (sha256(inputBytes) !== sha256(readFileSync(resolve(dataset, item.inputFile)))) {
        extractionError ??= 'input-differs-from-pinned-synthetic-corpus';
      } else {
        const input = JSON.parse(inputBytes.toString()) as {
          narrative: string;
          sourceDigest: string;
        };
        if (
          sha256(input.narrative) !== item.sourceDigest ||
          input.sourceDigest !== item.sourceDigest
        )
          extractionError ??= 'input-source-digest-mismatch';
        else inputValid = true;
      }
    }

    if (!verified.has(outputName) || !existsSync(outputPath)) {
      extractionError ??= 'extraction-output-missing';
    } else {
      const raw = readFileSync(outputPath);
      outputDigest = sha256(raw);
      try {
        const payload = JSON.parse(raw.toString()) as {
          schema?: string;
          sourceDigest?: string;
          error?: string | null;
          statements?: unknown[];
          quarantine?: unknown[];
          latencyMs?: number;
          fragments?: unknown[];
          calls?: { stage: string; output: string }[];
        };
        if (payload.schema !== 'normlab.langextract-statements/v1')
          throw new Error('unsupported-extraction-schema');
        if (payload.sourceDigest !== item.sourceDigest) throw new Error('source-digest-mismatch');
        statements = (payload.statements ?? []).map((value) => reviewStatementSchema.parse(value));
        quarantineCount = payload.quarantine?.length ?? 0;
        discoveredFragmentCount = payload.fragments?.length ?? 0;
        classificationCalls =
          payload.calls?.filter((call) => call.stage === 'classification').length ?? 0;
        modelError = payload.error ?? null;
        const discoveryOutput = payload.calls?.find((call) => call.stage === 'discovery')?.output;
        if (discoveryOutput) {
          try {
            const parsed = JSON.parse(discoveryOutput) as { extractions?: unknown[] };
            const extractions = (parsed.extractions ?? []) as { statement?: unknown }[];
            discoveryOutcome = !extractions.length
              ? 'empty-response'
              : extractions.every(
                    (extraction) =>
                      typeof extraction.statement === 'string' &&
                      demoExampleQuotes.has(extraction.statement),
                  )
                ? 'demo-example-copy'
                : 'no-exact-anchored-fragments';
          } catch {
            discoveryOutcome = 'unparseable-response';
          }
        } else discoveryOutcome = 'discovery-call-missing';
        const issues = statements.flatMap((statement) => reviewStatementIssues(statement, source));
        if (payload.error) extractionError ??= payload.error;
        if (issues.length) extractionError ??= `invalid-statements:${issues.join('; ')}`;
        if (quarantineCount) extractionError ??= `quarantined-statements:${quarantineCount}`;
        structuralPass =
          inputValid &&
          !payload.error &&
          statements.length > 0 &&
          !issues.length &&
          !quarantineCount;
      } catch (error) {
        extractionError ??= error instanceof Error ? error.message : String(error);
      }
    }

    const missing = label.required.filter((required) => {
      const prefix = `nlinput:${required.predicate}`;
      return !statements.some(
        (statement) =>
          statement.predicate === prefix &&
          statement.stance === required.stance &&
          statement.startOffset <= required.startOffset &&
          statement.endOffset >= required.endOffset,
      );
    });
    const forbidden = label.forbidden.filter(([predicate, stance]) =>
      statements.some(
        (statement) =>
          statement.predicate === `nlinput:${predicate}` && statement.stance === stance,
      ),
    );
    const assertionProbePass = structuralPass && missing.length === 0 && forbidden.length === 0;
    return {
      id: item.id,
      family: item.family,
      splitGroup: item.splitGroup,
      status:
        record?.status ?? (outputDigest ? 'output-present-without-run-record' : 'not-attempted'),
      elapsedSeconds: record?.elapsedSeconds ?? null,
      sourceDigest: item.sourceDigest,
      outputDigest,
      extractionError,
      modelError,
      discoveryOutcome,
      discoveredFragmentCount,
      classificationCalls,
      structuralPass,
      statementCount: statements.length,
      quarantineCount,
      requiredProbeCount: label.required.length,
      requiredMatchedCount: label.required.length - missing.length,
      missingRequired: missing.map(({ predicate, stance, quote }) => ({
        predicate,
        stance,
        quote,
      })),
      forbiddenMatches: forbidden.map(([predicate, stance]) => ({ predicate, stance })),
      assertionProbePass,
      expectedGaps: {
        status: label.expectedGaps.length
          ? 'not-evaluated-output-contract-has-no-gap-field'
          : 'not-applicable',
        candidateCount: label.expectedGaps.length,
        fields: label.expectedGaps.map((gap) => gap.field),
      },
      legalSufficiency: 'not-evaluated',
      semanticReview: 'pending',
      reviewFocus: label.reviewFocus,
    };
  });

  const familyNames = [...new Set(cases.map((item) => item.family))];
  const familyMetrics = Object.fromEntries(
    familyNames.map((family) => {
      const members = cases.filter((item) => item.family === family);
      return [
        family,
        {
          caseCount: members.length,
          attemptedCases: members.filter((item) => item.outputDigest !== null).length,
          structuralPasses: members.filter((item) => item.structuralPass).length,
          assertionProbePasses: members.filter((item) => item.assertionProbePass).length,
        },
      ];
    }),
  );
  const attemptedCases = cases.filter((item) => item.outputDigest !== null).length;
  const targetQualityStatus = 'not-evaluated-candidate-labels-and-gap-detection-unscored';

  return {
    name: basename(directory),
    model: runManifest.model,
    provider: runManifest.provider,
    pipeline: runManifest.pipeline,
    runManifestDigest: existsSync(runManifestPath) ? sha256(readFileSync(runManifestPath)) : null,
    artifactManifestDigest: manifestDigest,
    metrics: {
      totalCases: cases.length,
      attemptedCases,
      unattemptedCases: cases.length - attemptedCases,
      structuralPasses: cases.filter((item) => item.structuralPass).length,
      structuralPassRate: cases.filter((item) => item.structuralPass).length / cases.length,
      assertionProbePasses: cases.filter((item) => item.assertionProbePass).length,
      assertionProbePassRate: cases.filter((item) => item.assertionProbePass).length / cases.length,
      requiredProbes: cases.reduce((sum, item) => sum + item.requiredProbeCount, 0),
      requiredProbesMatched: cases.reduce((sum, item) => sum + item.requiredMatchedCount, 0),
      forbiddenInferenceMatches: cases.reduce((sum, item) => sum + item.forbiddenMatches.length, 0),
      casesWithEmptyDiscoveryResponse: cases.filter(
        (item) => item.discoveryOutcome === 'empty-response',
      ).length,
      casesWithUnanchoredDiscoveryOnly: cases.filter(
        (item) => item.discoveryOutcome === 'no-exact-anchored-fragments',
      ).length,
      casesEchoingDemoExample: cases.filter((item) => item.discoveryOutcome === 'demo-example-copy')
        .length,
      casesReachingClassification: cases.filter((item) => (item.classificationCalls ?? 0) > 0)
        .length,
      extractionErrors: Object.fromEntries(
        [
          ...new Set(
            cases.map((item) => item.modelError).filter((value): value is string => value !== null),
          ),
        ].map((error) => [error, cases.filter((item) => item.modelError === error).length]),
      ),
      casesWithCandidateGaps: cases.filter((item) => item.expectedGaps.candidateCount > 0).length,
      gapScoredCases: 0,
      targetQualityStatus,
      targetQualityRate: null,
    },
    familyMetrics,
    cases,
  };
}

const runs = runArguments.map(scoreRun);
const report = {
  schema: 'normlab.synthetic-parking-evaluation/v1',
  createdAt: new Date().toISOString(),
  dataset: {
    schema: corpus.schema,
    version: corpus.version,
    status: corpus.status,
    caseCount: corpus.caseCount,
    realIncidentCount: corpus.realIncidentCount,
    sourceManifestDigest: sha256(readFileSync(corpusPath)),
    expectationsStatus: labels.status,
    expectationsDigest: sha256(readFileSync(labelsPath)),
  },
  scoringPolicy: {
    requiredProbe:
      'predicate and stance match, and the anchored source span covers the candidate quote span',
    forbiddenProbe: 'exact predicate and stance pair appears in the extraction',
    caseAssertionProbePass:
      'valid non-empty extraction with no quarantine, no missing required probes, and no forbidden probe matches',
    denominator: 'all 40 cases, including missing outputs and provider/extractor failures',
    gapScoring: 'not evaluated because the extraction output contract contains no gaps field',
    limitations: [
      'Candidate expectations are not expert-approved gold and cover selected probes, not the full semantic graph.',
      'Cases are synthetic, clustered in eight contrast families, and include zero verified real incidents.',
      'The assertion-probe rate is not the 80% critical-error-free target and is not a population accuracy estimate.',
      'Legal sufficiency, event truth, disposition, and expected-gap detection are not scored.',
    ],
  },
  runs,
};

writeFileSync(resolve(output, 'report.json'), `${JSON.stringify(report, null, 2)}\n`);
writeFileSync(resolve(output, 'scorer-source.ts'), readFileSync(new URL(import.meta.url)));
writeFileSync(resolve(output, 'dataset-manifest.json'), readFileSync(corpusPath));
writeFileSync(resolve(output, 'reviewer-expectations.json'), readFileSync(labelsPath));
writeBaselineArtifactManifest(output);
for (const run of runs)
  console.log(
    `${run.name}: ${run.metrics.assertionProbePasses}/${run.metrics.totalCases} candidate assertion-probe passes; ${run.metrics.structuralPasses} structurally valid; target quality not evaluated`,
  );
