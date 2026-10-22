import assert from 'node:assert/strict';
import test from 'node:test';
import { execFile } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';
import { createApp } from '../server/app.js';
import { verifyParkingCalculation } from '../server/parking-verifier.js';
import {
  evaluateParkingFragment,
  legalInputSchema,
  type LegalAssessment,
  type LegalResult,
  type LegalWorkspace,
} from '../shared/parking-legal.js';
import { emptyNarrativeContext } from '../shared/parking-context.js';
import { reviewDraftSchema } from '../shared/parking-review.js';
import { parkingFixture, parkingStories } from './parking-legal-fixture.js';
import { discoverLean } from '../server/verifier.js';

const summary = (result: LegalResult) => ({
  outcome: result.outcome,
  candidateFine: result.candidateFine,
  sanctionComparison: result.sanctionComparison,
  branches: result.branches,
  liability: result.liability,
  proof: result.proof,
});

test('five stories and corrections pass real HTTP review/calculation/Lean and immutable replay', async () => {
  const retained = process.env.NORMLAB_PARKING_POC_DATA_DIR;
  const dataDir = retained ?? mkdtempSync(join(tmpdir(), 'parking-poc-http-'));
  const app = await createApp({ dataDir, web: false, parkingExtractor: null });
  const report: unknown[] = [];
  try {
    await new Promise<void>((resolve) => app.server.listen(0, '127.0.0.1', resolve));
    const address = app.server.address();
    assert.ok(address && typeof address !== 'string');
    const origin = `http://127.0.0.1:${address.port}`;
    const bootstrap = (await (await fetch(`${origin}/api/bootstrap`)).json()) as {
      csrfToken: string;
    };
    async function post(path: string, body: unknown) {
      const response = await fetch(origin + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-NormLab-Token': bootstrap.csrfToken },
        body: JSON.stringify(body),
      });
      const value: unknown = await response.json();
      assert.equal(response.status, 200, JSON.stringify(value));
      return value;
    }
    for (let index = 0; index < parkingStories.length; index++) {
      const { story, input: planned, draft: seed } = parkingFixture(index);
      let draft = reviewDraftSchema.parse(
        await post('/api/parking/drafts', { narrative: story.text }),
      );
      const context = {
        ...emptyNarrativeContext(),
        topic: 'parking',
        parkingContext: 'parking-unspecified',
        intent: 'incident',
        decision: 'pending',
      };
      const edit = async (patch: object) =>
        reviewDraftSchema.parse(
          await post('/api/parking/review', {
            draftId: draft.draftId,
            expectedRevisionId: draft.revisionId,
            statements: draft.statements,
            checklist: draft.checklist,
            finishReview: false,
            ...patch,
          }),
        );
      draft = await edit({ context });
      draft = await edit({ context: { ...context, decision: 'confirmed' } });
      draft = await edit({ statements: seed.statements });
      draft = await edit({
        statements: draft.statements.map((s) => ({ ...s, decision: 'confirmed' })),
        checklist: seed.checklist,
        finishReview: true,
      });
      assert.equal(draft.status, 'reviewed');
      let input = legalInputSchema.parse({
        ...planned,
        draftId: draft.draftId,
        expectedRevisionId: draft.revisionId,
      });
      const before = (await post('/api/parking/legal', input)) as LegalAssessment;
      assert.ok(before.result);
      const { observed: beforeObserved, ...beforeExpected } = story.expectedDraft;
      assert.equal(beforeObserved, false);
      assert.deepEqual(summary(before.result), beforeExpected);
      assert.equal(
        before.verification?.status,
        'verified',
        before.verification?.reason ?? 'Missing proof',
      );
      const changes = new Map(story.correction.findingChanges.map((f) => [f.conditionId, f]));
      input = legalInputSchema.parse({
        ...input,
        ...('coordinateChanges' in story.correction ? story.correction.coordinateChanges : {}),
        findings: input.findings.map((f) => {
          const patch = changes.get(f.conditionId);
          return patch ? { ...f, state: patch.state, rationale: patch.rationale } : f;
        }),
        expectedAssessmentId: before.id,
        requestId: randomUUID(),
      });
      const after = (await post('/api/parking/legal', input)) as LegalAssessment;
      assert.ok(after.result);
      const { observed: afterObserved, ...afterExpected } =
        story.correction.expectedAfterRecalculate;
      assert.equal(afterObserved, false);
      assert.deepEqual(summary(after.result), afterExpected);
      assert.equal(
        after.verification?.status,
        'verified',
        after.verification?.reason ?? 'Missing proof',
      );
      assert.deepEqual(await post('/api/parking/legal', input), after);
      const workspace = (await (
        await fetch(`${origin}/api/parking/legal/${draft.draftId}`)
      ).json()) as LegalWorkspace;
      assert.equal(workspace.assessments.length, 2);
      assert.deepEqual(workspace.assessments[1], before);
      report.push({
        storyId: story.id,
        draftId: draft.draftId,
        revisionId: draft.revisionId,
        before,
        after,
      });
    }
    if (process.env.NORMLAB_PARKING_POC_REPORT)
      writeFileSync(
        process.env.NORMLAB_PARKING_POC_REPORT,
        JSON.stringify(
          {
            schema: 'normlab.parking-poc-run/v1',
            createdAt: new Date().toISOString(),
            inference: false,
            inputMode: 'synthetic-manual-review-seed',
            cases: report,
          },
          null,
          2,
        ) + '\n',
      );
  } finally {
    await app.close();
    if (!retained) rmSync(dataDir, { recursive: true, force: true });
  }
});

test('Lean independently rejects forged classification, fine, reasons, comparison and branch coverage', async () => {
  const matched = parkingFixture().input;
  const incomplete = parkingFixture(2).input;
  const mutations: [typeof matched, (r: LegalResult) => void][] = [
    [
      matched,
      (r) => {
        r.outcome = 'fragment-refuted';
      },
    ],
    [
      matched,
      (r) => {
        r.candidateFine = 10000;
      },
    ],
    [
      matched,
      (r) => {
        r.conflicts = ['noPayment'];
      },
    ],
    [
      matched,
      (r) => {
        r.sanctionComparison = 'draft-match';
      },
    ],
    [
      incomplete,
      (r) => {
        r.missing = [];
      },
    ],
  ];
  const branchCase = parkingFixture(2).story.correction;
  const branchInput = legalInputSchema.parse({
    ...incomplete,
    ...branchCase.coordinateChanges,
    findings: branchCase.findingChanges.map((f) => ({
      conditionId: f.conditionId,
      state: f.state,
      rationale: f.rationale,
      statementIds: [],
    })),
  });
  mutations.push([
    branchInput,
    (r) => {
      r.branches.pop();
    },
  ]);
  mutations.push(
    [
      branchInput,
      (r) => {
        r.branches[1].outcome = 'fragment-matched';
      },
    ],
    [
      parkingFixture(4).input,
      (r) => {
        [r.unsupported, r.refuted] = [r.refuted, r.unsupported];
      },
    ],
  );
  for (const [input, mutate] of mutations) {
    const result = evaluateParkingFragment(input);
    mutate(result);
    const proof = await verifyParkingCalculation(input, result);
    assert.equal(proof.status, 'rejected', JSON.stringify(proof));
    assert.match(proof.reason, /Lean отверг/);
  }
});

test('pinned Lean false-proposition diagnostic retains the rejection classification format', async () => {
  const lean = await discoverLean();
  assert.ok(lean.available && lean.binary, 'Pinned Lean is required for the diagnostic regression');
  const folder = mkdtempSync(join(tmpdir(), 'parking-lean-diagnostic-'));
  try {
    const path = join(folder, 'False.lean');
    writeFileSync(path, 'example : False := by decide +kernel\n');
    await assert.rejects(
      promisify(execFile)(lean.binary, ['-M512', '-T200000', path], { timeout: 20000 }),
      (error: unknown) => {
        assert.ok(error && typeof error === 'object' && 'stdout' in error);
        assert.match(String(error.stdout), /proved that the proposition[\s\S]*is false/);
        return true;
      },
    );
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test('missing Lean produces an explicit inconclusive result in a clean process', async () => {
  const { stdout } = await promisify(execFile)(
    process.execPath,
    [
      '--import',
      'tsx',
      '--input-type=module',
      '-e',
      `
    import { parkingFixture } from './tests/parking-legal-fixture.ts';
    import { evaluateParkingFragment } from './shared/parking-legal.ts';
    import { verifyParkingCalculation } from './server/parking-verifier.ts';
    const { input } = parkingFixture();
    console.log(JSON.stringify(await verifyParkingCalculation(input, evaluateParkingFragment(input))));
  `,
    ],
    {
      env: { ...process.env, LEAN_BIN: join(tmpdir(), 'deliberately-missing-lean') },
      timeout: 20000,
    },
  );
  assert.equal(JSON.parse(stdout).status, 'inconclusive');
});
