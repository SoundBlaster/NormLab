import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';
import { test } from 'node:test';
import type {
  ReformCertificate,
  ReformSnapshot,
  ReformSnapshotInput,
} from '../shared/reform-contracts.js';
import { interpretReform } from '../shared/reform-semantics.js';
import { decisionQuery, reformBundleRef } from '../server/reform-bindings.js';
import { getReformBundle, lockReformPackage } from '../server/reform-models.js';
import { digest } from '../server/hash.js';
import { discoverLean } from '../server/verifier.js';
import {
  constructReformDecisionStatement,
  reformLeanCore,
  reformLeanModel,
  verifyReformDecision,
} from '../server/reform-verifier.js';

const execute = promisify(execFile);
const states = ['unreviewed', 'established', 'refuted', 'not-established'] as const;
const roles = ['A', 'B', 'C'] as const;

function decision(
  role: (typeof roles)[number] = 'B',
  group: ReformSnapshot['group'] = 'K1',
  M: (typeof states)[number] = 'established',
  N: (typeof states)[number] = 'established',
  E: (typeof states)[number] = 'refuted',
) {
  const bundle = getReformBundle(role);
  const finding = (state: (typeof states)[number]) => ({
    state,
    rationale: state === 'unreviewed' ? '' : 'Synthetic rationale',
  });
  const input: ReformSnapshotInput = {
    narrative: 'Lean reform integration',
    group,
    findings: { M: finding(M), N: finding(N), E: finding(E) },
  };
  const content = {
    schema: 'normlab.snapshot/v2' as const,
    id: '00000000-0000-4000-8000-000000000201',
    caseId: 'reform-proof-case',
    revision: 1,
    createdAt: '2026-10-02T13:00:00.000Z',
    supersedes: null,
    authority: 'simulated-reviewer' as const,
    ...input,
  };
  const snapshot = { ...content, digest: digest(content) };
  const query = decisionQuery(snapshot, bundle);
  const certificate: Extract<ReformCertificate, { kind: 'decision' }> = {
    schema: 'normlab.certificate/v2',
    kind: 'decision',
    queryDigest: digest(query),
    result: interpretReform(input, bundle.package.ir),
  };
  return { bundle, snapshot, query, certificate };
}

async function checkLean(source: string) {
  const lean = await discoverLean();
  assert.ok(lean.available && lean.binary, 'Exact lean-toolchain must be installed');
  const directory = await mkdtemp(join(tmpdir(), 'normlab-reform-integration-'));
  try {
    const path = join(directory, 'Check.lean');
    await writeFile(path, `${reformLeanCore}\n${source}`, { mode: 0o600 });
    return await execute(lean.binary, ['-M512', '-T1000000', path], {
      timeout: 60000,
      maxBuffer: 1024 * 1024,
    });
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}
function audit(stdout: string, expected: number) {
  const reports = [
    ...stdout.matchAll(
      /'([^']+)' (?:does not depend on any axioms|depends on axioms: \[([^\]]*)\])/g,
    ),
  ];
  assert.equal(reports.length, expected, stdout);
  for (const report of reports) {
    const axioms =
      report[2]
        ?.split(',')
        .map((x) => x.trim())
        .filter(Boolean) ?? [];
    assert.ok(
      axioms.every((x) => x === 'propext'),
      `${report[1]}: ${axioms.join(',')}`,
    );
  }
  assert.ok(!stdout.includes('warning:'), stdout);
}

test('Lean independently validates all 384 producer results and 1296 branches, with general uniqueness and completeness lemmas', async () => {
  let total = 0;
  let branches = 0;
  for (const role of roles) {
    const bundle = getReformBundle(role);
    const prefix = `namespace NormLabReform
def fixtureModel : List Rule := ${reformLeanModel(bundle)}
theorem fixtureSupported : WellFormed fixtureModel := by decide +kernel
theorem fixtureUnique : ∀ x, x ∈ domain → ∃ y, ModelPermissible fixtureModel x y ∧ ∀ z, ModelPermissible fixtureModel x z → z = y := by
  intro x hx
  exact model_exists_unique fixtureModel fixtureSupported x hx
#print axioms fixtureSupported
#print axioms fixtureUnique
#print axioms permissible_unique
#print axioms model_exists_unique
#print axioms result_sound
#print axioms result_complete
#print axioms outcome_complete
#print axioms mandatory_complete
#print axioms domain_cardinality
#print axioms domain_distinct
#print axioms domain_complete
end NormLabReform
`;
    let source = prefix;
    let batchCount = 0;
    const flush = async () => {
      const { stdout, stderr } = await checkLean(source);
      assert.equal(stderr, '');
      audit(stdout, batchCount + 11);
      source = prefix;
      batchCount = 0;
    };
    let count = 0;
    for (const group of ['K1', 'K2'] as const)
      for (const M of states)
        for (const N of states)
          for (const E of states) {
            const d = decision(role, group, M, N, E);
            const statement = constructReformDecisionStatement(
              d.query,
              d.snapshot,
              d.bundle,
              d.certificate,
            )
              .replace('namespace NormLabReform\n', `namespace NormLabReform.Case${count}\n`)
              .replace('end NormLabReform\n', `end NormLabReform.Case${count}\n`)
              .replace(
                /def boundModel : List Rule := [\s\S]*?\ndef boundSnapshot/,
                'def boundModel : List Rule := NormLabReform.fixtureModel\ndef boundSnapshot',
              )
              .replace(
                'theorem supported : WellFormed boundModel := by decide +kernel',
                'theorem supported : WellFormed boundModel := NormLabReform.fixtureSupported',
              );
            source += statement;
            branches += d.certificate.result.branches.length;
            count++;
            batchCount++;
            if (batchCount === 8) await flush();
          }
    if (batchCount > 0) await flush();
    total += count;
    console.log(`Lean ${role}: ${count} snapshot results and existence/uniqueness checked`);
  }
  assert.equal(total, 384);
  assert.equal(branches, 1296);
});

test('v2 decision verifier checks completed and conditional results and binds the exact statement', async () => {
  for (const role of roles) {
    const d = decision(role, 'K2', 'unreviewed', 'not-established', 'established');
    const verified = await verifyReformDecision(d.query, d.snapshot, d.bundle, d.certificate);
    assert.equal(verified.status, 'verified', verified.reason);
    assert.equal(verified.queryDigest, digest(d.query));
    assert.equal(verified.certificateDigest, digest(d.certificate));
    assert.match(verified.statementDigest, /^[a-f0-9]{64}$/);
    assert.match(verified.toolchainDigest!, /^[a-f0-9]{64}$/);
    assert.equal(verified.method, 'case-theorem');
    assert.ok(verified.axioms.every((x) => x === 'propext'));
  }
  const d = decision();
  assert.equal(
    (await verifyReformDecision(d.query, d.snapshot, d.bundle, d.certificate)).status,
    'verified',
  );
  const forged = structuredClone(d.certificate);
  forged.result.branches[0].outcome.prisonMonths++;
  const rejected = await verifyReformDecision(d.query, d.snapshot, d.bundle, forged);
  assert.equal(rejected.status, 'rejected', rejected.reason);
  assert.notEqual(
    rejected.statementDigest,
    (await verifyReformDecision(d.query, d.snapshot, d.bundle, d.certificate)).statementDigest,
  );
});

test('Lean rejects missing mandatory mitigation, incorrect exclusion, arithmetic, order, ledger and branch attacks without TypeScript result guards', async () => {
  const d = decision();
  const attacks: [string, (c: typeof d.certificate) => void][] = [
    [
      'missing-M',
      (c) => {
        c.result.branches[0].outcome.prisonMonths = 90;
        c.result.branches[0].steps.shift();
        c.result.branches[0].steps[0].beforeMonths = 120;
        c.result.branches[0].steps[0].afterMonths = 90;
        c.result.branches[0].ledger.find((e) => e.ruleId === 'B-M')!.status = 'inapplicable';
        c.result.ledger.find((e) => e.ruleId === 'B-M')!.status = 'inapplicable';
      },
    ],
    [
      'wrong-fine',
      (c) => {
        c.result.branches[0].outcome.fineAmount++;
      },
    ],
    [
      'wrong-qualification',
      (c) => {
        c.result.branches[0].outcome.qualification = 'K2';
      },
    ],
    [
      'wrong-intermediate',
      (c) => {
        c.result.branches[0].steps[0].afterMonths++;
      },
    ],
    [
      'wrong-order',
      (c) => {
        c.result.branches[0].steps.reverse();
      },
    ],
    [
      'double-count',
      (c) => {
        c.result.branches[0].steps[1] = c.result.branches[0].steps[0];
      },
    ],
    [
      'missing-ledger',
      (c) => {
        c.result.branches[0].ledger.pop();
      },
    ],
    [
      'false-ledger',
      (c) => {
        c.result.branches[0].ledger.find((e) => e.ruleId === 'B-M')!.status = 'inapplicable';
      },
    ],
    [
      'false-summary',
      (c) => {
        c.result.ledger.find((e) => e.ruleId === 'B-M')!.status = 'unresolved';
      },
    ],
  ];
  for (const [name, mutate] of attacks) {
    const forged = structuredClone(d.certificate);
    mutate(forged);
    await assert.rejects(
      checkLean(constructReformDecisionStatement(d.query, d.snapshot, d.bundle, forged)),
      (error) => {
        const output = error as { stdout?: string };
        assert.match(output.stdout ?? '', /proved that the proposition[\s\S]*is false/, name);
        return true;
      },
    );
  }
  const excluded = decision('B', 'K1', 'established', 'established', 'established');
  excluded.certificate.result.branches[0].outcome.prisonMonths = 60;
  excluded.certificate.result.branches[0].steps.push({
    ruleId: 'B-N',
    beforeMonths: 80,
    afterMonths: 60,
  });
  const open = decision('B', 'K1', 'unreviewed', 'unreviewed', 'unreviewed');
  open.certificate.result.branches.pop();
  const missingN = decision();
  missingN.certificate.result.branches[0].outcome.prisonMonths = 80;
  missingN.certificate.result.branches[0].steps.pop();
  missingN.certificate.result.branches[0].ledger.find((e) => e.ruleId === 'B-N')!.status =
    'inapplicable';
  missingN.certificate.result.ledger.find((e) => e.ruleId === 'B-N')!.status = 'inapplicable';
  for (const attack of [excluded, open, missingN])
    await assert.rejects(
      checkLean(
        constructReformDecisionStatement(
          attack.query,
          attack.snapshot,
          attack.bundle,
          attack.certificate,
        ),
      ),
      (error) => /is false/.test((error as { stdout?: string }).stdout ?? ''),
    );
});

test('verifier supports reordered locked rules and returns unsupported/inconclusive rather than verified outside decision availability', async () => {
  const d = decision();
  const pkg = structuredClone(d.bundle.package);
  pkg.id = 'reordered-B';
  pkg.ir.rules.reverse();
  pkg.sourceMappings.reverse();
  const bundle = lockReformPackage(pkg);
  const query = decisionQuery(d.snapshot, bundle);
  const certificate = {
    ...d.certificate,
    queryDigest: digest(query),
    result: interpretReform(
      { narrative: d.snapshot.narrative, group: d.snapshot.group, findings: d.snapshot.findings },
      bundle.package.ir,
    ),
  };
  assert.equal(
    (await verifyReformDecision(query, d.snapshot, bundle, certificate)).status,
    'verified',
  );
  assert.equal(
    (await verifyReformDecision(d.query, d.snapshot, bundle, d.certificate)).status,
    'rejected',
  );
  const property = {
    schema: 'normlab.query/v2' as const,
    kind: 'property' as const,
    domain: d.query.domain,
    assumptions: d.query.assumptions,
    model: reformBundleRef(d.bundle),
    property: 'strict-M-mitigation' as const,
    target: 'prisonMonths' as const,
    preserve: ['qualification', 'fineAmount', 'currency'] as [
      'qualification',
      'fineAmount',
      'currency',
    ],
  };
  assert.equal(
    (await verifyReformDecision(property, d.snapshot, d.bundle, d.certificate)).status,
    'unsupported',
  );
  const program = `
    import { verifyReformDecision } from './server/reform-verifier.ts';
    const context = ${JSON.stringify(d)};
    const result = await verifyReformDecision(context.query, context.snapshot, context.bundle, context.certificate);
    console.log(JSON.stringify(result));
  `;
  const { stdout } = await execute(
    process.execPath,
    ['--import', 'tsx', '--input-type=module', '--eval', program],
    {
      cwd: new URL('../', import.meta.url),
      env: { ...process.env, LEAN_BIN: '/usr/bin/false' },
      timeout: 10000,
    },
  );
  const unavailable = JSON.parse(stdout) as {
    status: string;
    toolchainDigest: string | null;
    method: string | null;
  };
  assert.equal(unavailable.status, 'inconclusive');
  assert.equal(unavailable.toolchainDigest, null);
  assert.equal(unavailable.method, null);
});

test('statement bindings reject stale snapshots, query substitution and source injection', async () => {
  const d = decision();
  const stale = { ...d.snapshot, narrative: 'Changed' };
  assert.equal(
    (await verifyReformDecision(d.query, stale, d.bundle, d.certificate)).status,
    'rejected',
  );
  const wrong = { ...d.certificate, queryDigest: '0'.repeat(64) };
  assert.equal(
    (await verifyReformDecision(d.query, d.snapshot, d.bundle, wrong)).status,
    'rejected',
  );
  const changed = { ...d.query, assumptions: [...d.query.assumptions, 'Extra assumption'] };
  assert.equal(
    (await verifyReformDecision(changed, d.snapshot, d.bundle, d.certificate)).status,
    'rejected',
  );
  const injected = structuredClone(d.snapshot);
  injected.narrative = 'end NormLabReform\naxiom injected : False';
  injected.findings.M.rationale = injected.narrative;
  const { digest: _, ...content } = injected;
  injected.digest = digest(content);
  const query = decisionQuery(injected, d.bundle);
  const certificate = { ...d.certificate, queryDigest: digest(query) };
  const statement = constructReformDecisionStatement(query, injected, d.bundle, certificate);
  assert.ok(!statement.includes('axiom injected'));
  assert.equal(
    (await verifyReformDecision(query, injected, d.bundle, certificate)).status,
    'verified',
  );
});
