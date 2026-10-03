import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { ReformResult } from '../shared/reform-contracts.js';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { digest } from '../server/hash.js';
import { decisionQuery } from '../server/reform-bindings.js';
import { getReformBundle, lockReformPackage } from '../server/reform-models.js';
import {
  comparisonQuery,
  getReformCounterexampleBundle,
  mitigationQuery,
  proposeReformQuery,
  queryInputs,
} from '../server/reform-queries.js';
import {
  projectReformExplanation,
  validateReformExplanation,
  parseReformExplanationReport,
} from '../server/reform-explanations.js';
import {
  reformExplanationSchema,
  reformExplanationReportSchema,
  renderReformExplanationMarkdown,
  type ReformExplanation,
  type ReformExplanationReport,
} from '../shared/reform-explanations.js';
import { readReformFile } from '../scripts/reform-file.js';
import { explanationSnapshot, findingStates } from './reform-explanation-fixtures.js';

function renderFixture(explanation: ReformExplanation): ReformExplanationReport {
  // Rendering fixture only: this constructed metadata is not signature/proof evidence.
  return {
    schema: 'normlab.explanation-report/v1',
    artifactDigest: digest('render fixture'),
    explanationDigest: digest(explanation),
    explanation,
    evidence: {
      signatureValid: true,
      bindingsValid: true,
      current: true,
      proofStatus: 'verified',
      proofMethod: 'case-theorem',
      toolchainDigest: digest('render fixture'),
      reason: 'Rendering fixture; no signature or proof evidence',
    },
  };
}
test('all 384 snapshot/model explanations preserve every branch, ledger, numeric step and finding origin', () => {
  let count = 0,
    branches = 0;
  for (const role of ['A', 'B', 'C'] as const) {
    const model = getReformBundle(role);
    for (const group of ['K1', 'K2'] as const)
      for (const M of findingStates)
        for (const N of findingStates)
          for (const E of findingStates) {
            const snapshot = explanationSnapshot(group, M, N, E);
            const query = decisionQuery(snapshot, model);
            const cert = proposeReformQuery(query, [model], {}, snapshot);
            assert.equal(cert.kind, 'decision');
            const e = projectReformExplanation(query, [model], cert, snapshot);
            assert.equal(e.proofStatus, 'unchecked');
            assert.equal(e.cases.length, cert.result.branches.length);
            assert.deepEqual(e.findings, snapshot.findings);
            assert.deepEqual(
              e.summary.map(({ branches: _, ...entry }) => entry),
              cert.result.ledger,
            );
            for (const [i, row] of e.cases.entries()) {
              const trace = row.traces[0];
              const branch: ReformResult['branches'][number] = cert.result.branches[i];
              assert.deepEqual(trace.input, branch.when);
              assert.deepEqual(trace.outcome, branch.outcome);
              assert.deepEqual(
                trace.events.map(({ ruleId, status, excludedBy }) => ({
                  ruleId,
                  status,
                  excludedBy,
                })),
                branch.ledger,
              );
              assert.deepEqual(
                trace.events
                  .filter((e) => e.step !== null)
                  .map((e) => ({ ruleId: e.ruleId, ...e.step! })),
                branch.steps,
              );
              for (const event of trace.events)
                for (const c of event.conditions) {
                  assert.equal(c.value, branch.when[c.predicate]);
                  assert.equal(
                    c.origin,
                    ['established', 'refuted'].includes(snapshot.findings[c.predicate].state)
                      ? 'finding'
                      : 'completion',
                  );
                }
              branches++;
            }
            count++;
          }
  }
  assert.equal(count, 384);
  assert.equal(branches, 1296);
});
test('exclusion keeps M, equal outcomes retain open branches and source sections have exact addresses', () => {
  const model = getReformBundle('B'),
    snapshot = explanationSnapshot('K1', 'established', 'not-established', 'established');
  const query = decisionQuery(snapshot, model),
    cert = proposeReformQuery(query, [model], {}, snapshot);
  const e = projectReformExplanation(query, [model], cert, snapshot);
  assert.deepEqual(
    e.cases.map((c) => c.traces[0].outcome.prisonMonths),
    [80, 80],
  );
  assert.deepEqual(e.scope.openPredicates, ['N']);
  assert.equal(e.summary.find((r) => r.ruleId === 'B-N')!.status, 'unresolved');
  const second = e.cases[1].traces[0];
  assert.equal(second.events.find((r) => r.ruleId === 'B-N')!.reason, 'excluded-by-E');
  assert.equal(second.events.find((r) => r.ruleId === 'B-M')!.status, 'applied');
  assert.deepEqual(second.timeline, ['B-BASE-K1', 'B-X', 'B-M']);
  const reorderedPackage = structuredClone(model.package);
  reorderedPackage.ir.rules.reverse();
  reorderedPackage.sourceMappings.reverse();
  const reorderedModel = lockReformPackage(reorderedPackage);
  const reorderedQuery = decisionQuery(snapshot, reorderedModel);
  const reordered = projectReformExplanation(
    reorderedQuery,
    [reorderedModel],
    proposeReformQuery(reorderedQuery, [reorderedModel], {}, snapshot),
    snapshot,
  );
  assert.deepEqual(reordered.cases[1].traces[0].timeline, second.timeline);
  assert.deepEqual(reordered.cases[1].traces[0].outcome, second.outcome);
  for (const section of e.sources[0].rules) {
    assert.equal(
      section.text,
      model.package.source.content
        .split('\n')
        .slice(section.startLine - 1, section.endLine)
        .join('\n'),
    );
    assert.ok(section.text.startsWith(`### ${section.rule.id}\n`));
    assert.equal(section.text.split('\n').filter((l) => /^#{1,3} /.test(l)).length, 1);
    assert.deepEqual(
      section.originRuleIds,
      model.package.sourceMappings.find((m) => m.ruleId === section.rule.id)!.originRuleIds,
    );
  }
});
test('comparisons explain direct changes, propagated step values, preserved components and bound counterexamples', () => {
  const a = getReformBundle('A'),
    b = getReformBundle('B'),
    c = getReformBundle('C'),
    d = getReformCounterexampleBundle();
  const ab = comparisonQuery(a, b, 'equivalence');
  const eab = projectReformExplanation(ab, [a, b], proposeReformQuery(ab, [a, b]));
  assert.ok(eab.cases.every((r) => r.components.every((c) => !c.changed)));
  assert.ok(
    eab.cases.every((r) => r.ruleChanges.every((c) => !c.operationChanged && !c.stepValuesChanged)),
  );
  let rows = 0,
    pairs = 0;
  for (const property of [
    'component-no-increase',
    'strict-reduction',
    'preserved-outside',
  ] as const) {
    const query = comparisonQuery(a, c, property),
      cert = proposeReformQuery(query, [a, c]);
    const e = projectReformExplanation(query, [a, c], cert);
    assert.ok(e.cases.every((r) => r.relationSatisfied));
    assert.ok(
      e.cases.every((r) =>
        r.components.filter((c) => c.component !== 'prisonMonths').every((c) => !c.changed),
      ),
    );
    rows += e.cases.length;
    if (property === 'strict-reduction') {
      const row = e.cases.find((r) => r.traces[0].input.N && !r.traces[0].input.E)!;
      assert.equal(row.ruleChanges.find((c) => c.slot === 'M')!.operationChanged, true);
      const n = row.ruleChanges.find((c) => c.slot === 'N')!;
      assert.equal(n.operationChanged, false);
      assert.equal(n.stepValuesChanged, true);
    }
  }
  assert.equal(rows, 32);
  for (const model of [a, b, c]) {
    const query = mitigationQuery(model),
      cert = proposeReformQuery(query, [model]);
    const e = projectReformExplanation(query, [model], cert);
    assert.ok(e.cases.every((r) => r.ruleChanges.find((c) => c.slot === 'M')!.conditionsChanged));
    assert.ok(e.cases.every((r) => r.ruleChanges.every((c) => !c.operationChanged)));
    pairs += e.cases.length;
  }
  assert.equal(pairs, 24);
  const qd = comparisonQuery(a, d, 'preserved-outside'),
    cd = proposeReformQuery(qd, [a, d]);
  const ed = projectReformExplanation(qd, [a, d], cd);
  assert.equal(ed.counterexampleCase, 2);
  const witness = ed.cases[ed.counterexampleCase!];
  assert.equal(witness.relationSatisfied, false);
  assert.deepEqual(
    witness.traces.map((t) => t.outcome.prisonMonths),
    [90, 80],
  );
  assert.equal(witness.ruleChanges.find((c) => c.slot === 'N')!.operationChanged, true);
  const corpus = proposeReformQuery(ab, [a, b], { method: 'corpus', inputs: queryInputs(ab) });
  assert.equal(projectReformExplanation(ab, [a, b], corpus).coverage.status, 'partial');
});
test('projection rejects altered arithmetic, ledger, claims, locks and ambiguous source sections', () => {
  const model = getReformBundle('B'),
    snapshot = explanationSnapshot('K1', 'established', 'established', 'refuted');
  const query = decisionQuery(snapshot, model),
    cert = proposeReformQuery(query, [model], {}, snapshot);
  assert.equal(cert.kind, 'decision');
  for (const mutate of [
    (c: typeof cert) => {
      c.result.branches[0].steps[0].afterMonths++;
    },
    (c: typeof cert) => {
      c.result.branches[0].outcome.prisonMonths++;
    },
    (c: typeof cert) => {
      c.result.branches[0].ledger[0].status = 'inapplicable';
      c.result.ledger[0].status = 'inapplicable';
    },
  ]) {
    const candidate = structuredClone(cert);
    mutate(candidate);
    assert.throws(
      () => projectReformExplanation(query, [model], candidate, snapshot),
      /reconstruction/,
    );
  }
  const a = getReformBundle('A'),
    d = getReformCounterexampleBundle(),
    q = comparisonQuery(a, d, 'preserved-outside');
  const bad = proposeReformQuery(q, [a, d]);
  assert.equal(bad.kind, 'comparison');
  bad.result.verdict = 'holds';
  bad.result.counterexample = null;
  assert.throws(() => projectReformExplanation(q, [a, d], bad), /verdict/);
  const duplicate = structuredClone(model.package);
  duplicate.source.content += '\n### B-M\nDuplicate source\n';
  duplicate.source.digest = digest(duplicate.source.content);
  const relocked = lockReformPackage(duplicate),
    q2 = decisionQuery(snapshot, relocked);
  assert.throws(
    () =>
      projectReformExplanation(
        q2,
        [relocked],
        proposeReformQuery(q2, [relocked], {}, snapshot),
        snapshot,
      ),
    /Ambiguous source/,
  );
  const damaged = structuredClone(model);
  damaged.provenanceDigest = '0'.repeat(64);
  assert.throws(() => projectReformExplanation(query, [damaged], cert, snapshot), /lock or digest/);
});
test('explanation is deterministic, unchecked and cannot be rebound or modified without detection', () => {
  const model = getReformBundle('C'),
    snapshot = explanationSnapshot();
  const query = decisionQuery(snapshot, model),
    cert = proposeReformQuery(query, [model], {}, snapshot);
  const e = projectReformExplanation(query, [model], cert, snapshot);
  assert.deepEqual(projectReformExplanation(query, [model], cert, snapshot), e);
  validateReformExplanation(e, query, [model], cert, snapshot);
  for (const mutate of [
    (v: ReformExplanation) => {
      v.cases[0].traces[0].events[2].reason = 'trigger-false';
    },
    (v: ReformExplanation) => {
      v.sources[0].rules[0].text += ' invented';
    },
    (v: ReformExplanation) => {
      v.coverage.status = 'partial';
    },
    (v: ReformExplanation) => {
      v.bindings.queryDigest = '0'.repeat(64);
    },
  ]) {
    const changed = structuredClone(e);
    mutate(changed);
    assert.throws(
      () => validateReformExplanation(changed, query, [model], cert, snapshot),
      /exact inputs/,
    );
  }
  assert.equal(reformExplanationSchema.safeParse({ ...e, proofStatus: 'verified' }).success, false);
  assert.equal(reformExplanationSchema.safeParse({ ...e, arbitrary: 'unknown' }).success, false);
  const report = renderFixture(e);
  assert.equal(
    reformExplanationReportSchema.safeParse({
      ...report,
      evidence: { ...report.evidence, current: false },
    }).success,
    false,
  );
  assert.throws(() => parseReformExplanationReport(' '.repeat(512 * 1024 + 1)), /512 KiB/);
});
test('Markdown renders rationale, assumptions and source content as literal text with explicit evidence boundaries', () => {
  const pkg = getReformBundle('C').package;
  pkg.source.content = pkg.source.content.replace(
    '### C-M\n',
    '### C-M\n\n<img src=x onerror=alert(1)>\n```\n# injected\n```\n',
  );
  pkg.source.digest = digest(pkg.source.content);
  const model = lockReformPackage(pkg);
  const snapshot = explanationSnapshot();
  const { digest: _, ...content } = snapshot;
  content.findings.M.rationale =
    '<script>alert(1)</script> [phish](https://bad.invalid)\n# injected';
  const snap = { ...content, digest: digest(content) };
  const query = decisionQuery(snap, model);
  query.assumptions.push('[bad](javascript:alert(1))');
  const e = projectReformExplanation(
    query,
    [model],
    proposeReformQuery(query, [model], {}, snap),
    snap,
  );
  const md = renderReformExplanationMarkdown(renderFixture(e));
  assert.ok(md.includes('&lt;script&gt;'));
  assert.ok(!md.includes('rationale: <script>'));
  assert.ok(!md.includes('[bad](javascript:alert(1))'));
  assert.ok(md.includes('    <img src=x onerror=alert(1)>'));
  assert.ok(!md.split('\n').some((line) => line === '# injected'));
  assert.ok(md.includes('не имеют отдельного Lean proof'));
  assert.ok(md.includes('Открытые условия: N'));
});
test('CLI file boundary caps allocation, accepts UTF-8 and rejects directories, oversize and malformed UTF-8', () => {
  const dir = mkdtempSync(join(tmpdir(), 'normlab-explanation-files-'));
  try {
    const file = join(dir, 'text');
    writeFileSync(file, 'Привет');
    assert.equal(readReformFile(file, 12), 'Привет');
    assert.throws(() => readReformFile(file, 11), /within 11 bytes/);
    assert.throws(() => readReformFile(dir), /Expected a file/);
    writeFileSync(file, Buffer.from([0xff]));
    assert.throws(() => readReformFile(file), /encoded data/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
