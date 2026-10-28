# Parking motivation development set v1

24 authored Russian sources, with operator-supplied actor/episode/contribution
context. This is the first **motivation-after-grounding** slice. It does not test
unassisted entity/event extraction, physical observation truth, liability or
whole-case completeness. References are authored in the same change, without
independent adjudication. No models have been run on this set.

`inputs.json` is model-facing source/context only. `reviewer-only.json` contains
anchor/scope expectations, explanatory notes and one semantic candidate check
per case. It must never be concatenated into a model prompt. `manifest.json`
fixes both byte hashes and case order before inference. IDs M01–M24 cover:

| Cases   | Main distinction                                                                  |
| ------- | --------------------------------------------------------------------------------- |
| M01–M04 | explicit, absent, unknown and explicitly denied motive                            |
| M05–M08 | opposed sources, multiple motives, desired/failed outcome, unrealized plan        |
| M09–M12 | owner/driver/payer, different actions, episodes and vehicles                      |
| M13–M14 | first person in a letter; unresolved actor                                        |
| M15–M18 | AI, community, machine and natural phenomenon; intention optional                 |
| M19–M20 | omission/downstream movement; technical obstacle without legal conclusion         |
| M21–M24 | repeated quote, UTF-16, injected instructions, different motives without conflict |

Use `npm run parking:motivation -- export NEW_DIRECTORY`. The CLI writes:

- `generator/Mxx.json`: source/context, instructions and response schema only;
- `verifier/Mxx.json`: Choice task with source/context and a candidate attribution;
- `verifier/policy.json`: explicit accept/reject/review routing;
- `reviewer-only/`: reference answers, never sent to models;
- `plan.json`: local request bindings, exact dataset and task fingerprints.

Each verifier file has one question and works with the existing offline planner:

```sh
python -B -S evaluation/check_parking_motivation_plan.py NEW_DIRECTORY
python -B evaluation/categorical_smoke.py NEW_DIRECTORY/verifier/M01.json \
  --policy NEW_DIRECTORY/verifier/policy.json --max-calls 1
```

There is no `--live` in this preparation step. Native D1 and a generative model
perform different tasks; no combined ranking is defined. A future execution
requires explicit provider/model/settings and call/time/cost authorization.
Preserve the plan and all attempts, usage and errors. Do not forward the entire
export directory to a model.

For offline generator scoring, prepare this local capture envelope:

```json
{
  "schema": "normlab.parking-motivation-responses/v1",
  "planDigest": "copy from plan.json",
  "responses": [
    {
      "id": "M01",
      "requestId": "copy the M01 request bindings.requestId",
      "status": "completed",
      "raw": "exact model response text"
    }
  ]
}
```

Other statuses are `provider_error`, `transport_unknown`, `missing_content`
(without `raw`). Omitted cases become `missing_output`; malformed proposals are
`rejected`; foreign request IDs are `request_mismatch`. Duplicate/unknown case
captures or a changed plan fail the scoring operation. The envelope does not
authenticate provenance of a capture: keep transport/provider evidence separately.

`score PLAN_DIRECTORY RESPONSES_JSON` reports set agreement on evidence edges:
actor + episode + contribution + kind + support polarity + speaker + exact UTF-16
range. Missing/provider/rejected outputs are listed separately and excluded from
that conditional edge metric; always report coverage alongside it. Empty
reference cases have a separate `emptyReferenceMatched` indicator. Questions,
free motive summaries, source authenticity and semantic completeness are not
scored. Two wrong summaries can share correct anchors; use the separate semantic
candidate task and human review. No result here is independent human-gold accuracy.

All candidates remain unreviewed and source-only. No states, empty Delta,
physical event registration, legal findings or sanction are manufactured.
