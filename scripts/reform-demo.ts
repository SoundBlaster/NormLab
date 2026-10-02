import { randomUUID } from 'node:crypto';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { parseArgs } from 'node:util';
import type { ReformBundle, ReformQuery, ReformSnapshot } from '../shared/reform-contracts.js';
import { renderReformExplanationMarkdown } from '../shared/reform-explanations.js';
import { decisionQuery } from '../server/reform-bindings.js';
import { explainReformExport } from '../server/reform-explanations.js';
import { digest } from '../server/hash.js';
import { getReformBundle } from '../server/reform-models.js';
import {
  comparisonQuery,
  getReformCounterexampleBundle,
  mitigationQuery,
  proposeReformQuery,
} from '../server/reform-queries.js';
import {
  exportReformArtifacts,
  ReformReceiptSigner,
  replayReformExport,
} from '../server/reform-receipts.js';

const { values } = parseArgs({ options: { out: { type: 'string' } } });
const output = resolve(
  values.out ??
    join(
      '.artifacts',
      `reform-demo-${new Date().toISOString().replaceAll(':', '-')}-${randomUUID().slice(0, 8)}`,
    ),
);
mkdirSync(dirname(output), { recursive: true });
// Each run creates its own directory; an existing export is never overwritten.
mkdirSync(output);
const signer = new ReformReceiptSigner();
writeFileSync(join(output, 'issuer-public.pem'), signer.publicKey, { flag: 'wx' });
const a = getReformBundle('A'),
  b = getReformBundle('B'),
  c = getReformBundle('C');
const d = getReformCounterexampleBundle();
const cases: {
  id: string;
  query: ReformQuery;
  bundles: ReformBundle[];
  snapshot?: ReformSnapshot;
}[] = [
  { id: 'AB-equivalence', query: comparisonQuery(a, b, 'equivalence'), bundles: [a, b] },
  ...(['component-no-increase', 'strict-reduction', 'preserved-outside'] as const).map(
    (property) => ({
      id: `AC-${property}`,
      query: comparisonQuery(a, c, property),
      bundles: [a, c],
    }),
  ),
  ...([a, b, c] as const).map((model, i) => ({
    id: `${['A', 'B', 'C'][i]}-strict-M-mitigation`,
    query: mitigationQuery(model),
    bundles: [model],
  })),
  {
    id: 'AD-preserved-outside-counterexample',
    query: comparisonQuery(a, d, 'preserved-outside'),
    bundles: [a, d],
  },
];
const snapshotContent = {
  schema: 'normlab.snapshot/v2' as const,
  id: randomUUID(),
  caseId: 'reform-demo-case',
  revision: 1,
  createdAt: new Date().toISOString(),
  supersedes: null,
  authority: 'simulated-reviewer' as const,
  narrative: 'Synthetic explanation demonstration',
  group: 'K1' as const,
  findings: {
    M: { state: 'established' as const, rationale: 'Synthetic M finding' },
    N: { state: 'not-established' as const, rationale: 'N remains open' },
    E: { state: 'refuted' as const, rationale: 'Synthetic E finding' },
  },
};
const snapshot: ReformSnapshot = { ...snapshotContent, digest: digest(snapshotContent) };
for (const [index, model] of [a, b, c].entries())
  cases.push({
    id: `${['A', 'B', 'C'][index]}-conditional-decision`,
    query: decisionQuery(snapshot, model),
    bundles: [model],
    snapshot,
  });
const excludedContent = {
  ...snapshotContent,
  id: randomUUID(),
  revision: 2,
  supersedes: snapshot.id,
  findings: {
    ...snapshotContent.findings,
    E: { state: 'established' as const, rationale: 'Synthetic exclusion finding' },
  },
};
const excludedSnapshot: ReformSnapshot = { ...excludedContent, digest: digest(excludedContent) };
cases.push({
  id: 'C-conditional-exclusion',
  query: decisionQuery(excludedSnapshot, c),
  bundles: [c],
  snapshot: excludedSnapshot,
});
const results = [];
for (const item of cases) {
  const certificate = proposeReformQuery(item.query, item.bundles, {}, item.snapshot);
  const receipt = await signer.issue(item.query, item.bundles, certificate, item.snapshot);
  const artifact = exportReformArtifacts(
    item.query,
    item.bundles,
    certificate,
    receipt,
    item.snapshot,
  );
  const content = `${JSON.stringify(artifact, null, 2)}\n`;
  const replay = await replayReformExport(content, signer.publicKey);
  if (!replay.current) throw new Error(`${item.id}: ${replay.reason}`);
  const file = `${item.id}.json`;
  writeFileSync(join(output, file), content, { flag: 'wx' });
  const explanation = await explainReformExport(artifact, signer.publicKey);
  if (!explanation.evidence.current) throw new Error(`${item.id}: explanation replay failed`);
  const explanationJson = `${item.id}.explanation.json`,
    explanationMarkdown = `${item.id}.explanation.md`;
  writeFileSync(join(output, explanationJson), `${JSON.stringify(explanation, null, 2)}\n`, {
    flag: 'wx',
  });
  writeFileSync(join(output, explanationMarkdown), renderReformExplanationMarkdown(explanation), {
    flag: 'wx',
  });
  const verdict =
    certificate.kind === 'decision' ? certificate.result.status : certificate.result.verdict;
  results.push({
    id: item.id,
    file,
    queryDigest: digest(item.query),
    statementDigest: receipt.payload.bindings.statementDigest,
    toolchainDigest: receipt.payload.verification.toolchainDigest,
    verdict,
    counterexample: certificate.kind === 'decision' ? null : certificate.result.counterexample,
    coverage: receipt.payload.coverage,
    method: receipt.payload.verification.method,
    axioms: receipt.payload.verification.axioms,
    replay,
    explanationJson,
    explanationMarkdown,
    explanationDigest: explanation.explanationDigest,
  });
  console.log(
    `${item.id}: ${verdict}; ${receipt.payload.coverage.coveredCardinality}/${receipt.payload.coverage.declaredCardinality}; replay and explanation current`,
  );
}
writeFileSync(
  join(output, 'manifest.json'),
  `${JSON.stringify(
    {
      schema: 'normlab.reform-demo/v1',
      createdAt: new Date().toISOString(),
      issuer: digest(signer.publicKey),
      issuerKeyFile: 'issuer-public.pem',
      results,
    },
    null,
    2,
  )}\n`,
  { flag: 'wx' },
);
console.log(`Artifacts: ${output}`);
