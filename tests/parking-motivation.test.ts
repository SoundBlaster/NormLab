import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { ParkingContributionSchema } from '../ontology/parking-pilot/motivation/generated/schemas.js';
import {
  consumeMotivation,
  createMotivationRequest,
  motivationDigest,
  type MotivationProposal,
} from '../server/parking-motivation.js';
import {
  buildMotivationPlan,
  checkMotivationArtifacts,
  exportMotivationPlan,
  loadMotivationDataset,
  motivationChoiceTask,
  scoreMotivationResponses,
} from '../scripts/parking-motivation.js';

const dataset = loadMotivationDataset();
function sample(index = 0) {
  return {
    input: structuredClone(dataset.inputs[index]!),
    proposal: structuredClone(dataset.references[index]!.reference),
    request: createMotivationRequest(dataset.inputs[index]!),
  };
}
function parse(proposal: unknown, request = sample().request) {
  return consumeMotivation(JSON.stringify(proposal), request);
}

test('24 frozen references anchor; imported generic concepts and generated shape are pinned', () => {
  checkMotivationArtifacts();
  assert.equal(dataset.inputs.length, 24);
  assert.equal(
    ParkingContributionSchema.safeParse({
      $type: 'nlmot:ParkingContribution',
      contributionKey: 'c1',
    }).success,
    true,
  );
  assert.equal(
    ParkingContributionSchema.safeParse({ $type: 'nlmot:ParkingContribution' }).success,
    false,
  );
  assert.deepEqual(buildMotivationPlan(), buildMotivationPlan());
});

test('quotes use exact UTF-16 anchors, preserving a source speaker independently of actor', () => {
  const { input, proposal, request } = sample(21);
  const result = parse(proposal, request);
  assert.equal(result.ok, true);
  if (!result.ok) return;
  const support = result.proposal.hypotheses[0]!.positiveSupport[0]!;
  assert.equal(input.sourceText.slice(support.startOffset, support.endOffset), support.quote);
  assert.equal(support.startOffset, input.sourceText.indexOf(support.quote));
  assert.notEqual(
    support.startOffset,
    Array.from(input.sourceText.slice(0, support.startOffset)).length,
  );
  const letter = sample(12),
    letterResult = parse(letter.proposal, letter.request);
  assert.equal(letterResult.ok, true);
  if (!letterResult.ok) return;
  assert.equal(letterResult.proposal.hypotheses[0]!.actorId, 'a1');
  assert.equal(letterResult.proposal.hypotheses[0]!.positiveSupport[0]!.speakerId, 'letter_1');
  assert.equal(letterResult.semanticRelevanceVerified, false);
});

test('repeated quotes require an explicit valid occurrence; normalization is not performed', () => {
  const { proposal, request } = sample(20);
  const s = proposal.hypotheses[0]!.positiveSupport[0]!;
  delete s.occurrence;
  assert.deepEqual(parse(proposal, request), { ok: false, code: 'ambiguous_quote' });
  s.occurrence = 99;
  assert.deepEqual(parse(proposal, request), { ok: false, code: 'invalid_occurrence' });
  s.occurrence = 1;
  assert.equal(parse(proposal, request).ok, true);
  s.quote = 'Я  спешил.';
  assert.deepEqual(parse(proposal, request), { ok: false, code: 'quote_not_found' });
});

test('unsupported guesses and model authority/physical/norm fields are rejected', () => {
  const { proposal, request } = sample();
  proposal.hypotheses[0]!.positiveSupport = [];
  assert.equal(parse(proposal, request).ok, false);
  const valid = sample().proposal;
  for (const field of [
    'bindings',
    'reviewState',
    'sourceTruthVerified',
    'snapshots',
    'delta',
    'findings',
    'sanction',
  ])
    assert.equal(parse({ ...valid, [field]: true }, request).ok, false, field);
  assert.equal(
    parse({ ...valid, hypotheses: [{ ...valid.hypotheses[0], operatorAuthor: 'a1' }] }, request).ok,
    false,
  );
});

test('scope/kind and unknown actor/speaker identifiers cannot be supplied by the model', () => {
  for (const patch of [
    { episodeId: 'e2' },
    { contributionId: 'ghost' },
    { contributionKind: 'action' },
    { actorId: 'ghost' },
  ]) {
    const { proposal, request } = sample();
    Object.assign(proposal.hypotheses[0]!, patch);
    assert.equal(parse(proposal, request).ok, false);
  }
  const { proposal, request } = sample();
  proposal.hypotheses[0]!.positiveSupport[0]!.speakerId = 'ghost';
  assert.deepEqual(parse(proposal, request), { ok: false, code: 'unknown_speaker' });
});

test('negative-only and contested support survive; missing motive does not create opposition', () => {
  const denied = sample(3),
    conflict = sample(4),
    absent = sample(1);
  for (const item of [denied, conflict, absent])
    assert.equal(parse(item.proposal, item.request).ok, true);
  assert.equal(denied.proposal.hypotheses[0]!.positiveSupport.length, 0);
  assert.equal(denied.proposal.hypotheses[0]!.negativeSupport.length, 1);
  assert.equal(conflict.proposal.hypotheses[0]!.positiveSupport.length, 1);
  assert.equal(conflict.proposal.hypotheses[0]!.negativeSupport.length, 1);
  assert.equal(absent.proposal.hypotheses.length, 0);
});

test('unknown actor and nonhuman actor remain source-only without physical promotion', () => {
  for (const index of [13, 14, 15, 16, 17, 18]) {
    const item = sample(index),
      result = parse(item.proposal, item.request);
    assert.equal(result.ok, true);
    if (!result.ok) continue;
    assert.equal(result.physicalEnrichmentPerformed, false);
    assert.equal(result.sourceTruthVerified, false);
    assert.equal(result.reviewState, 'unreviewed');
  }
  assert.equal(sample(13).proposal.hypotheses[0]!.actorId, null);
});

test('request input, contract/schema and bindings tampering are detected', () => {
  for (const mutation of [
    (r: ReturnType<typeof createMotivationRequest>) => {
      r.modelInput.input.sourceText += 'x';
    },
    (r: ReturnType<typeof createMotivationRequest>) => {
      r.modelInput.instructions += 'x';
    },
    (r: ReturnType<typeof createMotivationRequest>) => {
      r.bindings.contractDigest = '0'.repeat(64);
    },
    (r: ReturnType<typeof createMotivationRequest>) => {
      r.modelInput.input.context.actors[0]!.label = 'Другой';
    },
  ]) {
    const { proposal, request } = sample();
    mutation(request);
    assert.deepEqual(parse(proposal, request), { ok: false, code: 'binding_mismatch' });
  }
  assert.deepEqual(consumeMotivation('{', sample().request), { ok: false, code: 'invalid_json' });
});

test('duplicate hypotheses/support and malformed supplied grounding are rejected', () => {
  const { proposal, request, input } = sample();
  proposal.hypotheses.push(structuredClone(proposal.hypotheses[0]!));
  assert.deepEqual(parse(proposal, request), { ok: false, code: 'duplicate_id' });
  proposal.hypotheses.pop();
  proposal.hypotheses[0]!.positiveSupport.push(
    structuredClone(proposal.hypotheses[0]!.positiveSupport[0]!),
  );
  assert.deepEqual(parse(proposal, request), { ok: false, code: 'duplicate_support' });
  input.context.contributions[0]!.episodeId = 'ghost';
  assert.throws(() => createMotivationRequest(input), /unknown_episode/);
});

test('score keeps provider/protocol/missing outcomes separate from reference edges', () => {
  const plan = buildMotivationPlan();
  const responses = plan.requests.slice(0, 6).map(({ id, request }, index) => ({
    id,
    requestId: request.bindings.requestId,
    status: 'completed' as const,
    raw: JSON.stringify(dataset.references[index]!.reference),
  }));
  responses[1]!.raw = '{';
  responses[2]!.requestId = 'wrong-request';
  const report = scoreMotivationResponses(plan, {
    schema: 'normlab.parking-motivation-responses/v1',
    planDigest: plan.planDigest,
    responses: [
      ...responses,
      {
        id: 'M07',
        requestId: plan.requests[6]!.request.bindings.requestId,
        status: 'provider_error',
      },
      {
        id: 'M08',
        requestId: plan.requests[7]!.request.bindings.requestId,
        status: 'transport_unknown',
      },
    ],
  });
  assert.deepEqual(report.statuses, {
    anchored: 4,
    rejected: 1,
    request_mismatch: 1,
    provider_error: 1,
    transport_unknown: 1,
    missing_output: 16,
  });
  assert.equal(report.semanticAccuracyMeasured, false);
  assert.equal(report.anchorEdges.extra, 0);
});

test('identical anchors are not evidence that an incorrect motive summary is correct', () => {
  const plan = buildMotivationPlan(),
    proposal = sample().proposal;
  proposal.hypotheses[0]!.motive.summary = 'Хотел купить космический корабль';
  const report = scoreMotivationResponses(plan, {
    schema: 'normlab.parking-motivation-responses/v1',
    planDigest: plan.planDigest,
    responses: [
      {
        id: 'M01',
        requestId: plan.requests[0]!.request.bindings.requestId,
        status: 'completed',
        raw: JSON.stringify(proposal),
      },
    ],
  });
  assert.equal(report.anchorEdges.precision, 1);
  assert.equal(report.cases[0]!.motiveSemantics, 'not-assessed');
  assert.equal(report.semanticAccuracyMeasured, false);
});

test('changed actor and evidence polarity cause a reference mismatch, not a truth verdict', () => {
  const plan = buildMotivationPlan(),
    proposal: MotivationProposal = sample(8).proposal;
  proposal.hypotheses[0]!.actorId = 'a2';
  proposal.hypotheses[0]!.negativeSupport = proposal.hypotheses[0]!.positiveSupport;
  proposal.hypotheses[0]!.positiveSupport = [];
  const report = scoreMotivationResponses(plan, {
    schema: 'normlab.parking-motivation-responses/v1',
    planDigest: plan.planDigest,
    responses: [
      {
        id: 'M09',
        requestId: plan.requests[8]!.request.bindings.requestId,
        status: 'completed',
        raw: JSON.stringify(proposal),
      },
    ],
  });
  assert.equal(report.anchorEdges.matched, 0);
  assert.equal(report.anchorEdges.extra, 1);
  assert.equal(report.anchorEdges.missing, 1);
});

test('archive plan/response mismatches and duplicate captures fail closed', () => {
  const plan = buildMotivationPlan();
  const empty = {
    schema: 'normlab.parking-motivation-responses/v1',
    planDigest: plan.planDigest,
    responses: [],
  };
  assert.throws(
    () => scoreMotivationResponses({ ...plan, inferencePerformed: true }, empty),
    /plan_mismatch/,
  );
  assert.throws(
    () => scoreMotivationResponses(plan, { ...empty, planDigest: 'wrong' }),
    /response_plan_mismatch/,
  );
  const response = {
    id: 'M01',
    requestId: plan.requests[0]!.request.bindings.requestId,
    status: 'missing_content',
  };
  assert.throws(
    () => scoreMotivationResponses(plan, { ...empty, responses: [response, response] }),
    /duplicate_response/,
  );
  assert.equal(scoreMotivationResponses(plan, empty).statuses.missing_output, 24);
  assert.notEqual(plan.planDigest, motivationDigest({ ...plan, verifier: {} }));
});

test('export is exclusive and model-facing files do not contain reviewer answers', () => {
  const directory = mkdtempSync(join(tmpdir(), 'normlab-motivation-'));
  try {
    const output = join(directory, 'plan');
    assert.equal(exportMotivationPlan(output).calls, 0);
    assert.throws(() => exportMotivationPlan(output), /EEXIST/);
    for (const input of dataset.inputs) {
      const generator = JSON.parse(
        readFileSync(join(output, 'generator', `${input.id}.json`), 'utf8'),
      );
      assert.deepEqual(Object.keys(generator).sort(), ['input', 'instructions', 'outputSchema']);
      const verifier = JSON.parse(
        readFileSync(join(output, 'verifier', `${input.id}.json`), 'utf8'),
      );
      assert.deepEqual(Object.keys(verifier).sort(), ['questions', 'state']);
      assert.deepEqual(
        verifier,
        motivationChoiceTask(
          input,
          dataset.references.find((r) => r.id === input.id)!.semanticCheck.candidate,
        ),
      );
      assert.equal('reference' in generator, false);
      assert.equal('expectedLabel' in verifier.state, false);
      assert.equal('reviewerNote' in verifier.state, false);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
