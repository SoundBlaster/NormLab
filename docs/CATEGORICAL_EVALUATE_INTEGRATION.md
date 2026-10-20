# Jev4Mellea 0.9.0: direct categorical evaluation

Prepared 2026-10-18. Ledger: [NormLab #153](https://github.com/SoundBlaster/NormLab/issues/153).
Upstream: [released v0.9.0](https://github.com/SoundBlaster/Jev4Mellea/releases/tag/v0.9.0).

## Scope

The current Python SDK profile now pins `mellea-jev-adapter==0.9.0`.
Mellea 0.8.0, TypeSafe SDK 0.7.5, OpenAI 3.31.0 and httpx2 2.13.1 remain selected
pins, not a complete transitive dependency lock. Previous environments and reports
are historical; create a dedicated environment for the new profile.

`categorical_runtime.py` connects TypeSafe Choice, OpenAI Decisions Choice and
ordinary Responses through `CategoricalRequirement.evaluate()` directly.
Native wrappers borrow the underlying provider; the NormLab context manager owns
its lifetime. No generation Backend or sampling strategy is involved.

The task builder returns a snapshot of the supplied state and questions, including
the original typed candidate. It does not derive a new `{candidate, reference}`
task from free text. The bridge returns the original task/result/decision binding.
This avoids Mellea sampling strategies catching review/errors after earlier
attempts. Direct `evaluate()` returns review as data and propagates operational
exceptions; the smoke CLI catches those only to write an explicit failed record.

## Explicit consumer policy

The CLI requires a separate public policy file, for example
[`choice-policy.json`](../fixtures/providers/choice-policy.json):

```json
{
  "schema": "normlab.categorical-policy/v1",
  "questions": {
    "overall": {
      "compatible": "accept",
      "incompatible": "reject",
      "indeterminate": "review"
    }
  }
}
```

Every question and every allowed label must have an explicit mapping. Missing,
extra or invalid mappings fail before credentials, output creation or dispatch.
The mapping is application acceptance policy, not the expected answer for an
individual case, and is never added to model input. There is no default numerical
confidence threshold or assumption that a particular category must mean accept.

For a multi-question Responses batch, the group outcome is review if any question
requires review; otherwise reject if any question rejects; otherwise accept.
Every per-question outcome remains visible in `questionDecisions`, so review does
not erase a rejected question. Independent calls have separate decisions and no
implied whole-run semantic acceptance verdict. This aggregation is a current
NormLab consumer policy, not an upstream universal rule.

For the supplied Stage1 fixture, the source is «Я не оплатил парковку.», while the
typed candidate incorrectly asserts actual payment. Its predeclared candidate
reference is `incompatible`. Under this example policy an `incompatible` model
answer becomes reject: the proposed fact should not be accepted as compatible.
This is not a judgment about a fine or an independent human-gold annotation.

## SDK-free dry-run

As of 2026-10-19, the default current categorical route is **ordinary Luna Low
through CoreInfra Responses**. Native Jev and Decisions require an explicit
provider or config. This is a provisional engineering choice; see
[primary verifier](PRIMARY_VERIFIER.md) for evidence and remaining quality gates.

From the repository root:

```bash
# Primary route: ordinary Luna Low, no provider flag needed.
python3 -B -S evaluation/categorical_smoke.py fixtures/providers/stage1-choice.json \
  --policy fixtures/providers/choice-policy.json --max-calls 1

# Explicit experimental native routes.
python3 -B -S evaluation/categorical_smoke.py fixtures/providers/stage1-choice.json \
  --provider coreinfra-jev --policy fixtures/providers/choice-policy.json --max-calls 1

python3 -B -S evaluation/categorical_smoke.py fixtures/providers/stage1-choice.json \
  --provider coreinfra-decisions --policy fixtures/providers/choice-policy.json --max-calls 1

python3 -B -S evaluation/categorical_smoke.py fixtures/providers/stage1-choice.json \
  --provider coreinfra-responses --policy fixtures/providers/choice-policy.json --max-calls 1
```

Dry-run imports no SDK/Mellea, reads no credentials, creates no output and sends
no requests. It reports the semantic task digest, exact policy, provider/model,
planned calls, tactic and `evaluationMethod: CategoricalRequirement.evaluate`.
The native `typesafe` / `openai` and ordinary `openai-responses` presets also work.
Presets do not attest access or model availability.

`--config` accepts the existing public native provider or Responses config schema.
Their explicit `api_format` selects the family. Exact endpoint, model, key
environment variable and timeout overrides work for native/custom suppliers.
`--reasoning-effort` and `--max-output-tokens` apply only to Responses; supplying
them for native decisions is an error. Credentials are never valid config fields.

## Explicit opt-in execution

Use an isolated Python 3.11+ environment installed from
`evaluation/requirements-provider-tests.txt` (or the current provider profile
without test dependencies). Follow local cache/build placement rules.
After separately authorizing input, provider and spending:

```bash
"$PROVIDER_ENV/bin/python" evaluation/categorical_smoke.py \
  fixtures/providers/stage1-choice.json \
  --policy fixtures/providers/choice-policy.json --max-calls 1 \
  --live --output /absolute/private/new-categorical-capture
```

The selected environment variable supplies the key; a protected `--key-file`
may be selected instead. Existing exact HTTPS endpoint validation and sensitive
output rules from [provider configuration](PROVIDER_CONFIGURATION.md) apply.
The key must belong to that endpoint's supplier.

`independent` (default) dispatches one question per request, at most three under
the explicit total `--max-calls` cap. `--tactic batch` uses one real shared-state
Responses request; a multi-question native batch fails before dispatch. One native
question may use either tactic with exactly one request. No hidden question loop
is advertised as a batch.

Each HTTP slot is checkpointed before sending. An operational failure stops the
remaining questions; there is no retry, repair, escalation, fallback or resume.
Unknown token usage/cost stays null. A call cap is not a currency cap; a provider
spending limit and a separate experiment authorization are still needed. HTTP
timeouts remain per operation, not an end-to-end deadline.

Exit 0 means all evaluations completed, including semantic reject/review outcomes.
Exit 3 means incomplete/failed execution; exit 2 means invalid CLI input/config.

## Evidence report

The new private capture uses `normlab.categorical-evaluation-smoke/v1`, reusing
existing bounded request recording. It includes the exact policy, task digest,
question order, provider config, actual dependency metadata, request payloads,
HTTP status, reserved calls and timings.

Each completed result includes:

| Field                      | Meaning                                                    |
| -------------------------- | ---------------------------------------------------------- |
| `answers`                  | Actual category labels for the unchanged task              |
| `decision.outcome`         | Caller policy: accept, reject or review                    |
| `decision.reason`          | Identifies the explicit label policy; not an LLM rationale |
| `decision.score`           | Null; this consumer policy selects no numerical score      |
| `questionDecisions`        | Label-policy outcome for every question                    |
| `native_results`           | Original normalized Choice evidence, or null for Responses |
| Model / request ID / usage | Actual available SDK metadata; missing stays null          |

For native models, `native_results` retains selected label, native confidence,
distribution, model, request ID and usage without conflating confidence with
selected-label probability. Per-answer usage is not summed into a request total.
For ordinary models there is no fabricated confidence/distribution. Optional raw
response bodies, auth headers and exception text are excluded from this report.
Task narratives and predictions remain sensitive even without credentials.

An authorization/HTTP/transport/protocol error is `status: failed`, with error type
and available status code, `result: null`, and subsequent tasks not executed.
It is not a semantic reject or review. `semanticQualityEvidence` remains false:
completed evaluation and policy acceptance do not establish semantic accuracy.

## Compatibility and verification

Historical Stage1 profiles, plans, fixtures, source hashes and native SDK-free
execution remain unchanged. The copied ProxyAPI factory adds 0.9.0 to its checked
runtime allowlist while retaining the original historical metadata. The mock-only
legacy compatibility probe compares planned 0.4.0 to actual current 0.9.0, records
that difference and continues to forbid live execution. Existing primitive and
Responses-only CLI/report contracts remain available unchanged.

Local evidence on Python 3.13.15 with actual installed adapter 0.9.0:

- Clean isolated installation and `pip check` succeeded.
- 191 focused offline checks passed: bridge outcomes, native evidence, Responses
  independent/batch, pre-dispatch validation, SDK-free CLI, failure propagation,
  existing smoke/ProxyAPI/capture/replay/Mellea compatibility contracts.
- Seven mock-only legacy compatibility checks passed, exercising 332 mock
  invocations with planned adapter 0.4.0 and actual adapter 0.9.0. Version gates
  were narrowly bypassed 332 / 1821 times as recorded by the existing probe;
  network calls remained zero. This is not authority for historical live execution.
- Ruff 0.15.0 lint and formatting checks passed across the evaluation directory;
  Prettier checked the changed CI YAML and policy JSON. Frozen Stage1 source,
  historical requirements and fixtures have no diff from the branch base.
- Network/default HTTP transports were denied in the new integration checks;
  provider HTTP was synthetic. No live inference or deployment was performed.

GitHub CI and review are separate evidence and are tracked in #153/the PR.
The next experiment must freeze its routing policy and budget before inference;
this implementation does not establish calibrated thresholds or escalation gains.
