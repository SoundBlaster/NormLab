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
