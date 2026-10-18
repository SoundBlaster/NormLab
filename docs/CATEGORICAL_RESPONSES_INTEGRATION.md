# Ordinary Luna: categorical Responses integration

Task: [#149](https://github.com/SoundBlaster/NormLab/issues/149). Depends on
[SDK upgrade #148](https://github.com/SoundBlaster/NormLab/pull/148).

## Contract and scope

`evaluation/responses_smoke.py` connects the released Jev4Mellea 0.8.0
`ResponsesChoiceProvider` to the current bounded smoke runner. This is an
inspectable comparison entry point, not a new evaluation framework or a completed
quality experiment. Frozen Stage 1, native execution, archive/scorer and MLflow
contracts remain unchanged. This report format is not accepted by those readers.

Input is the same `{state, questions}` object accepted by the native smoke CLI,
restricted to one through three **Choice** questions. No Noul/Score conversion is
performed. All source text, candidate claims, definitions, instructions, labels
and criteria are preserved; expected answers must not be added to the state.
The SDK snapshots a task and places state in Responses input, question definitions
in instructions, and the allowed labels in a strict output JSON Schema.

The request wrapper is new and differs from historical Stage 1 Responses
serialization. Equal semantic input is not byte-identical wire input or a claim
of equivalent prompting. Re-running an old case with this wrapper is a new arm;
do not pool its responses with historical model-quality results.

## Dry-run and configuration

No SDK, credential access or network is required for dry-run:

```bash
python3 -B -S evaluation/responses_smoke.py \
  fixtures/providers/stage1-choice.json \
  --provider coreinfra-responses --reasoning-effort low
```

Presets are `coreinfra-responses` at
`https://hub.coreinfra.ai/openai/api/v1/responses` (`COREINFRA_API_KEY`) and
`openai-responses` at `https://api.openai.com/v1/responses` (`OPENAI_API_KEY`).
Both default to requested model `gpt-6-luna`, low reasoning and 1,024 output
tokens. Presets are configuration, not proof of current availability/account
access. `--endpoint-url`, `--model`, `--key-env`, `--key-file`, `--timeout`,
`--reasoning-effort` and `--max-output-tokens` allow explicit overrides. A new
public config can be supplied with `--config`:

```json
{
  "schema": "normlab.responses-config/v1",
  "id": "custom-luna",
  "api_format": "openai-responses",
  "endpoint_url": "https://gateway.example.com/custom/responses",
  "model": "vendor/luna",
  "key_env": "CUSTOM_PROVIDER_KEY",
  "timeout": 10,
  "reasoning_effort": "low",
  "max_output_tokens": 1024
}
```

Credential values are forbidden in config documents. The common endpoint/model/
credential-source validation is reused from the current native configuration;
this does not route Responses to Decisions. A config document may use JSON null
for `reasoning_effort` to omit that setting. CLI `none` sends the literal effort
`none`; neither case promises that the selected model supports it. Settings are
never silently removed after a provider error.

## Independent and batch dispatch

Default `--tactic independent` sends one fresh request per question, sequentially.
`--tactic batch` sends all configured questions in one shared-state request.
The cap must cover actual planned requests: for three questions use
`--max-calls 3` in independent mode or `--max-calls 1` in batch mode. No previous
response IDs, dialogue history, automatic retry or repair is used. The first
failure stops remaining requests. Batch answers are validated atomically; partial
answers are not salvaged.

After separate authorization of input, supplier and spending, an explicit live
command uses the current isolated provider environment:

```bash
"$PROVIDER_ENV/bin/python" evaluation/responses_smoke.py \
  fixtures/providers/stage1-choice.json \
  --provider coreinfra-responses --tactic independent --max-calls 1 \
  --live --output .artifacts/responses-choice-run
```

`$PROVIDER_ENV` is installed from `evaluation/requirements-providers-current.txt`
according to the local cache/build policy. No inference was performed for this
implementation. The call cap is not a monetary guarantee; spending limits and a
frozen semantic experiment remain separate requirements.

For a matched native single-question request, pass **the same input file** to
`evaluation/provider_smoke.py --provider coreinfra-jev` or
`--provider coreinfra-decisions`. Native smoke dispatches questions independently;
Responses batch is a different tactic, not a matched native batch implementation.

## Evidence

Dry-run emits `normlab.responses-choice-plan/v1`; execution emits
`normlab.responses-choice-smoke/v1`. The report records provider/settings,
dependency versions, question order, tactic, planned/actual requests, actual
request bodies and per-request latency/outcomes. `semanticTaskDigest` is SHA256
of UTF-8 JSON with sorted object keys, compact separators, unescaped Unicode and
no nonfinite values. It covers the complete original `{state, questions}`, not
the provider or tactic; order is recorded separately. Individual records bind
their selected question subset with the same digest rule.

Results preserve labels, requested/returned model, request ID, usage, adapter
revision and actual settings. Missing metadata stays null. Usage is per request;
batch usage is not copied onto each answer or multiplied by question count.
There are no fabricated confidence/probabilities, native threshold routing or
quality scores. A configured `indeterminate` label is an ordinary answer;
refusal, incomplete generation, malformed output, HTTP and transport failures
are failed records. HTTP authorization headers, exception text, raw response
bodies and the SDK's optional sensitive evidence are not serialized by this
runner. Reports include source-bearing requests and must be handled accordingly.

`fixtures/providers/stage1-choice.json` is an exact copy of the first task in
the frozen Stage 1 pilot: C002/R003. Its task digest is
`dedfab0c194443cb8523dfb05e614918981f15e45c03cbd0cf8c8f3eb76373e8`.
It includes an intentionally defective candidate, not a new reference label or
an extraction task. Its equality to the pinned planner's input is checked
offline; the legacy fixture/planner is unchanged.

## Verification and next experiment

Focused tests use the actual installed adapter/SDK with mock HTTP and real socket
and default transport calls forbidden. They cover native/CoreInfra/custom routes,
single/independent/batch mapping, metadata, exact source/question/criterion
preservation, SDK-free planning and failure handling. CI includes them in the
existing provider-contract job. Standing project testing authorization is
recorded in [the verification scope](EVALUATION_VERIFICATION_AUTHORIZATION.md).
Passing these checks establishes local integration behavior, not live provider
availability or semantic accuracy.

Local verification on 2026-10-18: **149 passed in 1.49 seconds** against installed
adapter 0.8.0 on Python 3.13.15: 41 categorical checks plus 108 existing current
provider/bridge/verifier/harness/Mellea checks. Real credential variables were
removed; transports and sockets were blocked except for supplied mock HTTP.
Ruff lint/format, Markdown/JSON/YAML formatting and whitespace checks passed.
The shared task validator has the same AST as the previous native validator.
Frozen/native source paths are unchanged. Full native archive/MLflow suites and
live availability were not rechecked by this narrow integration; GitHub CI and
independent review remain separate evidence.

Next: freeze one bounded matched native Choice / ordinary Responses probe using
the same task and record the new wire wrapper/settings. Reference quality and
the independent/batch/sequential experiment in [#69](https://github.com/SoundBlaster/NormLab/issues/69)
remain separate work. No further framework infrastructure is required here.
