# Primary current decision verifier: Liquid D1 Ultra

Decision: 2026-10-21 MSK. Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
The user requested using D1 Ultra instead of Jev for the current experiments.
This is a reversible provider selection. Small development controls do not
establish a model ranking or complete the pipeline quality gates.

## Current categorical CLI default

`evaluation/categorical_smoke.py` selects `liquid-d1-ultra` when neither
`--provider` nor `--config` is supplied. It uses the installed adapter 0.9.0's
System One Choice provider and direct `CategoricalRequirement.evaluate()` bridge.

| Setting                    | Selected route                                                                 |
| -------------------------- | ------------------------------------------------------------------------------ |
| Provider identity          | `liquid-d1-ultra`                                                              |
| Wire format                | `typesafe-systemone`: named `state` / `questions`, Choice answer map           |
| Actual supplier / endpoint | Liquid, `https://api.liquid.ai/decisions/v1/systemone`                         |
| Requested model            | `d1-ultra`                                                                     |
| Credential source          | `LIQUID_API_KEY`, or explicit protected `--key-file`; live execution only      |
| Tactic                     | Independent request per question, explicit total call cap                      |
| Consumer policy            | Required label → accept/reject/review mapping                                  |
| Evidence                   | Native confidence and probabilities retained separately; no synthesized scores |

The API-family name describes serialization. It does not send a request to
TypeSafe or identify D1 as Jev. The capture records Liquid's exact provider
ID, endpoint and model. Historical `provider_config.py`, frozen plans, references
and captures retain their original values. The current runtime owns the added preset.

```bash
# SDK-free plan: no credentials, network or output capture.
python3 -B -S evaluation/categorical_smoke.py fixtures/providers/stage1-choice.json \
  --policy fixtures/providers/choice-policy.json --max-calls 1

# Equivalent explicit public configuration, containing no credential values.
python3 -B -S evaluation/categorical_smoke.py fixtures/providers/stage1-choice.json \
  --config fixtures/providers/liquid-d1-ultra-config.json \
  --policy fixtures/providers/choice-policy.json --max-calls 1

# Explicit alternative for comparison; still dry-run.
python3 -B -S evaluation/categorical_smoke.py fixtures/providers/stage1-choice.json \
  --provider coreinfra-responses \
  --policy fixtures/providers/choice-policy.json --max-calls 1
```

Existing `typesafe`, `coreinfra-jev`, Decisions and Responses selections remain
available through explicit `--provider` or `--config`. A failed D1 call stays an
operational failure. It never silently selects Jev, Luna or a different key.
The CLI stops subsequent questions after failure and performs no retries.
`--reasoning-effort` and generation-token settings require an explicit Responses
route; they are not D1 settings. No model call occurs without `--live`.

Set the key only in the caller's protected environment or an existing private
file. Do not put its value in tracked configuration, CLI arguments or logs.
This change does not retrieve a key, transfer a CoreInfra spending cap to Liquid,
authorize a new paid run or reuse allowances from completed experiments.

## Discovery, hosted service and historical defaults

Luna remains the separate full-text discovery/extraction route. This selection
changes the current **Python decision evaluation CLI**. The hosted TypeScript
gateway's existing ordinary Luna profile and the deployed service are separate;
no hosted Liquid adapter, secret installation or deployment is included here.
Users of the hosted UI continue to use its configured provider.

The earlier [ordinary Luna Low decision](https://github.com/SoundBlaster/NormLab/blob/400b56c5303b434948918f59c76b3be8009ccae0/docs/PRIMARY_VERIFIER.md)
is retained in Git. Its `coreinfra-responses` route remains explicit. The low-level
primitive `provider_smoke.py` keeps its existing `typesafe` default; use
`--provider liquid-d1-ultra` there to select Liquid deliberately. Frozen Stage 1
runners continue using their pinned configurations, without a hidden migration.

## Evidence and practical limits

- [Paired questions and answers](JEV_D1_COMPARISON_2026-10-21.md): on the same
  ten returned overall inputs, Jev matched 8/10 candidate references and D1 9/10.
  Two Jev network unknowns are excluded from that semantic denominator.
- Both models accepted the wrong narrator attribution in P04b. Direct TypeSafe
  repeated that Jev defect. Selecting D1 alone does not solve the shared error.
- On two separate narrow origin questions, both models matched 2/2 candidate
  references. Question and input projection changed together; this is a diagnostic
  result on familiar texts, not independent holdout performance.
- D1 calls so far exercise Choice. The current integration replays actual Liquid
  response bodies through the released SDK under synthetic transport. It does
  not imply live evidence for other primitive types or hosted extraction quality.
- Liquid captures had no request ID. The SDK only reports an ID when its expected
  header is present; no ID is invented. Normalized SDK usage preserves input/output
  tokens but does not preserve Liquid's extra `usage.cost` field. CLI monetary cost
  remains unknown; raw historical provider captures retain that field separately.
- Native confidence and P(selected) are distinct and have not been calibrated as
  correctness probabilities. Pending human review and existing caller policy remain.

Issue [#145](https://github.com/SoundBlaster/NormLab/issues/145) retains Jev's
separate diagnosis; its broader deferred scope is not automatically resumed.
Development review [#65](https://github.com/SoundBlaster/NormLab/issues/65), final
pipeline selection [#80](https://github.com/SoundBlaster/NormLab/issues/80) and
untouched evaluation [#81](https://github.com/SoundBlaster/NormLab/issues/81)
remain separate acceptance gates.

## Verification and next step

Focused offline verification follows the standing
[verification authorization](EVALUATION_VERIFICATION_AUTHORIZATION.md): SDK-free
default/config planning, exact endpoint/model/key selection, installed-SDK replay
of both captured Liquid origin answers, preservation of confidence/usage/policy,
explicit alternative routes and operational failure without retry or fallback.
Real sockets/default HTTP transports are forbidden by the fixtures; keys in those
checks are synthetic. New CI/review evidence belongs to the current PR head.

Local result: **208 offline provider-contract tests passed**, including both
captured D1 origin replies and no-retry/no-fallback error scenarios, with real
provider-key variables removed. Ruff and Prettier passed. See
[verification summary](evidence/liquid-primary-2026-10-21.json). No new provider
requests, dependency installation, application build or deployment ran.

Next: review this provisional provider switch and the paired answer report. A
subsequent quality experiment needs its own frozen tasks, protocol and authorization.
