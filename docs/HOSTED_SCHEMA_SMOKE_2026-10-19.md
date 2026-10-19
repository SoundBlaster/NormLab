# CoreInfra hosted schema smoke — DEV017

2026-10-19. Related: [#70](https://github.com/SoundBlaster/NormLab/issues/70),
[merged contract](HOSTED_DISCOVERY_SUBJECT_CONTRACT.md).

## Frozen protocol

User requested «Готовить и проверяй» after the proposed short live CoreInfra schema
check. One original DEV017 from the development slice, unchanged source bytes.
Run the merged production hosted entry point with ordinary Luna Low, discovery
then classification, through `https://hub.coreinfra.ai/openai/api/v1/responses`.
The earlier failing capture used Medium and the old contract: this is a Low
compatibility smoke, not an effort-only comparison or a reproduction of Medium.

- Maximum **2 aggregate HTTP attempts**, no retries, repair, judge or fallback.
- 120s per provider operation; 300s case and series deadline; stop first
  failure, unknown outcome, source/runtime drift or cap. If extra classification
  batches would exceed the cap, stop without sending them.
- Existing user-reported external account ceiling **$4**, not independently
  verified; token usage retained, price/cost unknown. The runner enforces request
  count/time, not dollar billing.
- `COREINFRA_API_KEY` from environment; no Keychain access, secret persistence,
  deployment or additional cases. Private capture/build output on verified TB5.

Freeze [plan](evidence/hosted-schema-smoke-2026-10-19/plan.json),
[runtime/source authority](evidence/hosted-schema-smoke-2026-10-19/authority.json),
[supervisor](evidence/hosted-schema-smoke-2026-10-19/driver.mjs) and
[preparation](evidence/hosted-schema-smoke-2026-10-19/prepare.mjs) before dispatch.
Supervisor is a narrow derivative of the earlier one-off hosted driver; no
application/framework changes or installs. Original evidence remains immutable.

## Expected checks and interpretation

1. Actual discovery request has strict JSON Schema, ID `type`/`pattern` and no
   `maxLength`. Record HTTP status, completed/refused/protocol/local outcome.
2. Preserve full source quote about app/SMS failure and unsuccessful payment.
   Domain subject is an explicitly supported person/vehicle ID, not a channel;
   valid syntax alone does not prove a correct referent or actor role.
3. Inspect full output: payment denial, technical-cause wording, episode context,
   quoted anchors and pending human review. No invented vehicle or legal result.
4. Save all attempts/raw responses/known and unknown usage; replay the exact
   captured response sequence with network forbidden. Publish a hashed evidence
   archive only after scanning every payload for reflected credentials.

A completed response demonstrates acceptance of this exact request and this
sample's local outcome. It does not prove provider enforcement of every regex,
independent human gold, accuracy, general quality improvement or causal effect.
An unexpected response stops the series; do not repair it or spend unused calls
on another case. Further inference needs a new agreed scope.

## Execution

Pending at protocol freeze. Results will be appended after the bounded run.

## Observed result

Execution freeze `292d8ccff525ffe4e4e8ecd4c946f3ddd8c89a4f`, started
2026-10-19 08:04:34 UTC. **2/2 HTTP200/completed**, both returned
`gpt-6-luna`; **13.448s** series /13.424s pipeline. No retries, unknown
usage, failed or extra requests. The authorized2-attempt series is exhausted.

| Resource                              | Discovery | Classification | Total |
| ------------------------------------- | --------: | -------------: | ----: |
| Input tokens                          |       514 |          1,199 | 1,713 |
| Output tokens                         |       363 |            369 |   732 |
| Reasoning tokens (included in output) |       270 |            201 |   471 |

Provider reported cached input0 both stages, cache-write input0/1,196.
Price/billing unavailable; USD cost remains null.

Actual request used the frozen strict schema with only `type`/`pattern` on
subject/episode IDs. CoreInfra accepted it, and the returned sample completed
local validation. This establishes acceptance of this exact request, not
provider enforcement of all pattern constraints.

### Full expected/actual review

Original source, unchanged:

> В Москве я стоял на городской парковке. Приложение и СМС не работали, оплатить парковку не удалось.

Both full source sentences were preserved as exact quoted fragments. All five
model proposals use `vehicle_1`, `episode_1`, `speaker=narrator` and remain
`pending`/`unreviewed`; no user confirmation or legal calculation occurred.

| Expected check                                               | Actual response                                                                       | Interpretation                                                                 |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Valid domain ID, no channel text as subject                  | Both subjects `vehicle_1`                                                             | Syntax passes; vehicle not explicit in source, actor/reference review required |
| Moscow claim retained                                        | `inMoscow/asserted`: «Событие происходило в Москве.»                                  | Source-supported location                                                      |
| City parking retained                                        | `cityParking/asserted`: «Место названо городской парковкой.»                          | Source-supported place                                                         |
| Avoid invented automobile                                    | `placement/asserted`: «Автомобиль находился на парковке.»                             | Candidate implicit-vehicle inference; do not accept automatically              |
| Unsuccessful payment preserved                               | `payment/denied`: «Оплатить конкретную парковку не удалось.»                          | Negation preserved                                                             |
| Technical failure retained without stronger causal assertion | `paymentComplexity/asserted`: «Оплата не прошла из-за неработающих приложения и СМС.» | Facts retained, «из-за» strengthens implicit causal relation; review required  |
| Exact quotations, pending human review                       | All5 statement anchors /2 fragment offsets exact; all pending                         | Parser/provenance checks pass, not semantic approval                           |

**Disposition: operational pass, semantic review needed.** The vehicle and
causality observations are same-agent candidate concerns, not independent gold
or an accuracy score. Do not infer that higher effort, new wording or the schema
caused a quality improvement; this is one Low sample under a changed contract.

## Verification and next step

[Offline replay](evidence/hosted-schema-smoke-2026-10-19/replay.json) reproduced
the complete result and calls from2 captured responses, excluding only new
statement UUIDs and latency. Global fetch forbidden, injected archived bytes only,
key removed from environment:0 new provider calls.5 statement anchors and2
fragment offsets checked. Actual wire schema keys/strict flag/Low effort checked.

[Candidate review](evidence/hosted-schema-smoke-2026-10-19/candidate-review.json),
[all-attempt observations](evidence/hosted-schema-smoke-2026-10-19/observations.json),
[raw evidence archive](evidence/hosted-schema-smoke-2026-10-19/evidence.zip).
Historical Low/Medium archives and the saved failed response remain unchanged.

Next: decide how to represent first-person parking narratives without an
explicit vehicle and how to keep causal summaries within the literal source.
Do this offline with source-bound examples; no extra inference or framework
expansion is implied.
