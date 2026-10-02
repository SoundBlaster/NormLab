import { randomUUID } from 'node:crypto';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { parseArgs } from 'node:util';
import type { ReformBundle, ReformQuery } from '../shared/reform-contracts.js';
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
const cases: { id: string; query: ReformQuery; bundles: ReformBundle[] }[] = [
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
const results = [];
for (const item of cases) {
  const certificate = proposeReformQuery(item.query, item.bundles);
  const receipt = await signer.issue(item.query, item.bundles, certificate);
  const artifact = exportReformArtifacts(item.query, item.bundles, certificate, receipt);
  const content = `${JSON.stringify(artifact, null, 2)}\n`;
  const replay = await replayReformExport(content, signer.publicKey);
  if (!replay.current) throw new Error(`${item.id}: ${replay.reason}`);
  const file = `${item.id}.json`;
  writeFileSync(join(output, file), content, { flag: 'wx' });
  if (certificate.kind === 'decision') throw new Error('Unexpected demo query kind');
  results.push({
    id: item.id,
    file,
    queryDigest: digest(item.query),
    statementDigest: receipt.payload.bindings.statementDigest,
    toolchainDigest: receipt.payload.verification.toolchainDigest,
    verdict: certificate.result.verdict,
    counterexample: certificate.result.counterexample,
    coverage: receipt.payload.coverage,
    method: receipt.payload.verification.method,
    axioms: receipt.payload.verification.axioms,
    replay,
  });
  console.log(
    `${item.id}: ${certificate.result.verdict}; ${receipt.payload.coverage.coveredCardinality}/${receipt.payload.coverage.declaredCardinality}; replay current`,
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
