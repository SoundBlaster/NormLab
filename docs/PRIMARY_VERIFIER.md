# Primary current verifier: ordinary Luna Low

Decision: 2026-10-19 MSK. Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
User approved ordinary Luna Low as the main route and retaining Jev experimentally.

## Current default

`evaluation/categorical_smoke.py` now defaults to `coreinfra-responses` when neither
`--provider` nor `--config` is supplied. It uses the existing released adapter's
`ResponsesChoiceProvider` and direct `CategoricalRequirement.evaluate()` bridge.

| Setting                 | Primary route                                              |
| ----------------------- | ---------------------------------------------------------- |
| API                     | Ordinary Responses, strict JSON Schema categorical output  |
| Endpoint                | `https://hub.coreinfra.ai/openai/api/v1/responses`         |
| Requested model         | `gpt-6-luna`                                               |
| Reasoning               | `low`                                                      |
| Output cap              | 1024 tokens, including reasoning                           |
| Credential source       | `COREINFRA_API_KEY`, read only for explicit live execution |
| Tactic                  | Independent fresh request per question                     |
| Caller policy           | Required explicit label→accept/reject/review mapping       |
| Confidence/distribution | Absent for ordinary Responses; never synthesized           |

```bash
# SDK-free planning only: no credential or network access.
python3 -B -S evaluation/categorical_smoke.py   fixtures/providers/stage1-choice.json   --policy fixtures/providers/choice-policy.json --max-calls 1

# Explicit experimental Jev; native primitive smoke also stays available.
python3 -B -S evaluation/categorical_smoke.py   fixtures/providers/stage1-choice.json --provider coreinfra-jev   --policy fixtures/providers/choice-policy.json --max-calls 1
```

An explicit native/Responses `--config` keeps its selected family and endpoint.
Native Decisions and direct-provider presets remain supported. A failed Responses
call stays an operational failure, with no automatic Jev fallback, repair or retry.
The existing CLI bounds each invocation only; a later corpus experiment must freeze
its full schedule, aggregate budget, controls, stopping rule and authorization.

The package name Jev4Mellea remains because that library also implements ordinary
Responses. Selecting its Responses provider does not invoke the Jev model. Historical
native plans, captured evidence, pins, model configurations and replay are unchanged.

## Hosted application profile

The TypeScript gateway already defaults to ordinary Responses classification,
`gpt-6-luna` and low reasoning. This change does not need a hosted adapter rewrite.
Python verification and hosted discovery/classification are distinct tasks and wire
wrappers; a passing candidate-verifier control does not validate full UI extraction.

For an operator selecting CoreInfra, these are public gateway settings:

```dotenv
NORMLAB_INFERENCE_CLASSIFIER=openai
NORMLAB_OPENAI_MODEL=gpt-6-luna
NORMLAB_OPENAI_BASE_URL=https://hub.coreinfra.ai/openai/api/v1
NORMLAB_OPENAI_RESPONSES_ENDPOINT_URL=https://hub.coreinfra.ai/openai/api/v1/responses
```

Base/full endpoint values must also reach egress, as described in the
[hosted runbook](HOSTED_INFERENCE.md). The existing protected file supplied through
`NORMLAB_OPENAI_API_KEY_FILE` must contain the selected supplier's key; no credential
value belongs in this profile or browser. Actual deployment/secret changes are not
part of this delivery. Existing explicit operator overrides still take precedence.

Hosted discovery/classification keep their existing stage-specific output limits;
the Python categorical 1024-token cap is not copied to extraction. Inference remains
opt-in, statements remain model proposals pending human confirmation and source
editing keeps its existing invalidation/revision rules.

## Evidence and decision limits

- [Four-control comparison](BRIDGE_SEMANTIC_PROBE_2026-10-18.md): Jev2/4,
  Decisions3/4, ordinary Luna Low4/4 candidate agreement. These are four controls
  over three authored texts, not a general quality ranking.
- [Jev instruction ablation](JEV_QUOTE_AUTHORITY_RETRY_2026-10-18.md): final2/4
  for baseline and extra quote-authority instruction,0/4 label changes.
- [Jev source-language comparison](RU_EN_SOURCE_LANGUAGE_2026-10-19.md):2/3 RU
  and EN,0/3 label changes; English narrative did not rescue wrong acceptance.

This is a reversible engineering default supported by observed failures in the
current Jev task. Jev's general capability and the error's root cause remain open.
Further Jev diagnosis is deferred in Issue145 until a new version or explicit
request warrants revisiting it. No adapter or historical result is deleted.

Ordinary Luna must still be evaluated on diverse development narratives, including
negation, attribution, multiple episodes, uncertainty, source ambiguity, unsupported
claims and human correction. Existing controls are DEV, not untouched holdout or
independent human gold. Development review/quality:#65; final pipeline selection:#80;
untouched evaluation:#81. This default does not complete those gates.

## Verification scope and next step

The current user request approves switching and checking the existing evaluation
pipeline; standing focused offline regression authorization is recorded in
[EVALUATION_VERIFICATION_AUTHORIZATION](EVALUATION_VERIFICATION_AUTHORIZATION.md).
Check default SDK-free planning, explicit native/config selection, released SDK
serialization, label-policy/evidence preservation and operational failure without
fallback, with real provider credentials absent and sockets/default transports denied.

No new live inference is authorized by changing a default. Previous experiments
are complete and their unused retry allowances are not reused. Next: prepare one
small fixed development slice from the existing reviewed corpus, freeze the Luna
configuration/task/rubric and propose a separate bounded live permit. Keep full
output semantic review and manual correction burden separate from control agreement.

Actual local verification on 2026-10-19: **112 focused offline tests passed** on
Python 3.13.15 / adapter 0.9.0, with real provider-key variables removed. Existing
fixtures deny sockets and default HTTP transports; SDK HTTP uses synthetic responses.
Four primary-default control dry-runs and explicit native config checks are recorded
in [verification evidence](evidence/luna-primary-2026-10-19/verification.json).
These checks establish routing and integration behavior. A live development quality
assessment, full local suite, hosted deployment and independent review are separate.
