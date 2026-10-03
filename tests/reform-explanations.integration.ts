import assert from 'node:assert/strict';
import { test } from 'node:test';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, rm, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { createPublicKey, generateKeyPairSync, sign } from 'node:crypto';
import type {
  ReformBundle,
  ReformCertificate,
  ReformQuery,
  ReformReceipt,
  ReformSnapshot,
} from '../shared/reform-contracts.js';
import { renderReformExplanationMarkdown } from '../shared/reform-explanations.js';
import { canonical, digest } from '../server/hash.js';
import { decisionQuery } from '../server/reform-bindings.js';
import { getReformBundle } from '../server/reform-models.js';
import {
  comparisonQuery,
  getReformCounterexampleBundle,
  mitigationQuery,
  proposeReformQuery,
  queryInputs,
} from '../server/reform-queries.js';
import {
  explainReformExport,
  verifyReformExplanationReport,
} from '../server/reform-explanations.js';
import {
  exportReformArtifacts,
  ReformReceiptSigner,
  type ReformExport,
} from '../server/reform-receipts.js';
import { explanationSnapshot } from './reform-explanation-fixtures.js';

const a = getReformBundle('A'),
  b = getReformBundle('B'),
  c = getReformBundle('C'),
  d = getReformCounterexampleBundle();
async function issue(
  query: ReformQuery,
  bundles: ReformBundle[],
  signer: ReformReceiptSigner,
  snapshot?: ReformSnapshot,
  certificate?: ReformCertificate,
): Promise<ReformExport> {
  const cert = certificate ?? proposeReformQuery(query, bundles, {}, snapshot);
  const receipt = await signer.issue(query, bundles, cert, snapshot);
  return exportReformArtifacts(query, bundles, cert, receipt, snapshot);
}
test('fresh trusted replay gates explanations for every query kind, corpus and witness; sidecars and historical claims cannot assert current evidence', async () => {
  const signer = new ReformReceiptSigner(),
    snapshot = explanationSnapshot();
  const cases: {
    query: ReformQuery;
    bundles: ReformBundle[];
    snapshot?: ReformSnapshot;
    certificate?: ReformCertificate;
  }[] = [
    { query: decisionQuery(snapshot, c), bundles: [c], snapshot },
    { query: comparisonQuery(a, b, 'equivalence'), bundles: [a, b] },
    { query: comparisonQuery(a, c, 'strict-reduction'), bundles: [a, c] },
    { query: mitigationQuery(c), bundles: [c] },
    { query: comparisonQuery(a, d, 'preserved-outside'), bundles: [a, d] },
  ];
  const corpusQuery = comparisonQuery(a, b, 'equivalence');
  cases.push({
    query: corpusQuery,
    bundles: [a, b],
    certificate: proposeReformQuery(corpusQuery, [a, b], {
      method: 'corpus',
      inputs: queryInputs(corpusQuery).slice(0, 1),
    }),
  });
  for (const item of cases) {
    const artifact = await issue(item.query, item.bundles, signer, item.snapshot, item.certificate);
    const report = await explainReformExport(artifact, signer.publicKey);
    assert.equal(report.evidence.current, true);
    assert.equal(report.evidence.proofStatus, 'verified');
    assert.ok(report.explanation);
    assert.equal(report.explanation.proofStatus, 'unchecked');
    assert.equal(
      report.explanation.bindings.certificateDigest,
      artifact.receipt.payload.bindings.certificateDigest,
    );
    assert.equal(report.explanation.coverage.status, artifact.receipt.payload.coverage.status);
    const repeated = await verifyReformExplanationReport(report, artifact, signer.publicKey);
    assert.deepEqual(repeated, report);
    assert.equal(
      renderReformExplanationMarkdown(repeated),
      renderReformExplanationMarkdown(report),
    );
    const changed = structuredClone(report);
    changed.explanation!.sources[0].rules[0].text += '\nInvented rationale';
    changed.explanationDigest = digest(changed.explanation);
    await assert.rejects(
      verifyReformExplanationReport(changed, artifact, signer.publicKey),
      /deterministic projection/,
    );
    const wrong = await explainReformExport(artifact, new ReformReceiptSigner().publicKey);
    assert.equal(wrong.evidence.current, false);
    assert.equal(wrong.evidence.signatureValid, false);
    assert.equal(wrong.evidence.proofStatus, 'unchecked');
    assert.equal(wrong.explanation, null);
    if (item.query.kind === 'decision') {
      assert.deepEqual(
        report.explanation.cases.map((r) => r.traces[0].outcome.prisonMonths),
        [60, 45],
      );
      assert.equal(
        report.explanation.summary.find((r) => r.ruleId === 'C-N')!.status,
        'unresolved',
      );
    }
    if (report.explanation.verdict === 'counterexample') {
      const witness = report.explanation.cases[report.explanation.counterexampleCase!];
      assert.deepEqual(
        witness.traces.map((r) => r.outcome.prisonMonths),
        [90, 80],
      );
      assert.ok(
        renderReformExplanationMarkdown(report).includes('A-N-K1 → D-N; изменена операция'),
      );
    }
  }
  const query = comparisonQuery(a, b, 'equivalence');
  const artifact = await issue(query, [a, b], signer);
  const key = generateKeyPairSync('ed25519');
  const publicKey = createPublicKey(key.privateKey)
    .export({ format: 'pem', type: 'spki' })
    .toString();
  const payload = structuredClone(artifact.receipt.payload);
  payload.issuer = digest(publicKey);
  payload.verification.toolchainDigest = '0'.repeat(64);
  const receipt: ReformReceipt = {
    payload,
    publicKey,
    signature: sign(null, Buffer.from(canonical(payload)), key.privateKey).toString('base64'),
  };
  const historical = await explainReformExport({ ...artifact, receipt }, publicKey);
  assert.equal(historical.evidence.signatureValid, true);
  assert.equal(historical.evidence.bindingsValid, true);
  assert.equal(historical.evidence.proofStatus, 'verified');
  assert.equal(historical.evidence.current, false);
  assert.equal(historical.explanation, null);
});

test('explanation CLI emits JSON/Markdown, checks sidecar equality and exits nonzero for untrusted keys or changed reports', async () => {
  const execute = promisify(execFile),
    root = fileURLToPath(new URL('../', import.meta.url));
  const dir = await mkdtemp(join(tmpdir(), 'normlab-explanation-cli-'));
  const signer = new ReformReceiptSigner(),
    snapshot = explanationSnapshot('K1', 'established', 'not-established', 'established');
  try {
    const artifact = await issue(decisionQuery(snapshot, c), [c], signer, snapshot);
    const input = join(dir, 'export.json'),
      key = join(dir, 'public.pem');
    await writeFile(input, JSON.stringify(artifact));
    await writeFile(key, signer.publicKey);
    const command = (args: string[]) =>
      execute(
        process.execPath,
        [
          'node_modules/tsx/dist/cli.mjs',
          'scripts/reform-explain.ts',
          input,
          '--issuer-key',
          key,
          ...args,
        ],
        { cwd: root, timeout: 30000, maxBuffer: 512 * 1024 },
      );
    const { stdout } = await command(['--format', 'json']);
    const report = JSON.parse(stdout);
    assert.equal(report.evidence.current, true);
    assert.deepEqual(
      report.explanation.cases.map(
        (r: { traces: { outcome: { prisonMonths: number } }[] }) =>
          r.traces[0].outcome.prisonMonths,
      ),
      [60, 60],
    );
    const sidecar = join(dir, 'explanation.json');
    await writeFile(sidecar, stdout);
    const verified = await command(['--report', sidecar]);
    assert.ok(verified.stdout.includes('C-N: excluded'));
    assert.ok(verified.stdout.includes('C-M: applied'));
    assert.ok(verified.stdout.includes('unresolved'));
    assert.ok(verified.stdout.includes('Coverage: **declared-complete**, 2/2'));
    const out = join(dir, 'explanation.md');
    await command(['--out', out]);
    const saved = await readFile(out, 'utf8');
    await assert.rejects(command(['--out', out]), (error) =>
      /EEXIST/.test((error as { stderr: string }).stderr),
    );
    assert.equal(await readFile(out, 'utf8'), saved);
    report.explanation.cases[0].traces[0].outcome.prisonMonths++;
    report.explanationDigest = digest(report.explanation);
    await writeFile(sidecar, JSON.stringify(report));
    await assert.rejects(command(['--report', sidecar]), (error) =>
      /deterministic projection/.test((error as { stderr: string }).stderr),
    );
    await writeFile(key, new ReformReceiptSigner().publicKey);
    await assert.rejects(command(['--format', 'json']), (error) => {
      const result = JSON.parse((error as { stdout: string }).stdout);
      return (
        (error as { code: number }).code === 1 &&
        result.evidence.current === false &&
        result.explanation === null
      );
    });
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
