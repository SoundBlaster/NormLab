# Provider configuration

Prepared 2026-10-11. Configuration support is separate from live compatibility
and semantic accuracy. The initial configuration update made no live calls. A subsequent authorized
[local compatibility check](COREINFRA_LIVE_CHECK_2026-10-11.md) verified Jev
Noul/Choice/Score and ordinary Luna Responses. After correcting the application
base to `/openai/api/v1`, all three Luna Decisions primitives also completed;
one preceding Choice attempt failed before an HTTP status.

## API format and supplier

The current smoke integration uses `mellea-jev-adapter==0.9.0` (Python 3.11+)
through `evaluation/provider_runtime.py` and
[`requirements-providers-current.txt`](../evaluation/requirements-providers-current.txt).
Mellea remains 0.8.0; TypeSafe SDK 0.7.5, OpenAI 3.31.0 and httpx2 2.13.1
are pinned to the checked revisions. These are selected package pins, not a
complete transitive dependency lock. Existing models/presets are unchanged;
`--model` selects another operator-approved model explicitly.

The historical Stage 1 environment remains on adapter **0.4.0** using
[`requirements-providers.txt`](../evaluation/requirements-providers.txt).
Its source-pinned `provider_config.py`, plans, captures and fixtures are unchanged.
The SDK-free native execution runner uses its own wire adapter and does not
load Jev4Mellea. Updating this SDK integration does not change native normalization
or upgrade historical runs.

A provider is an explicit combination of API format, full HTTPS endpoint, model,
credential source and timeout. The hostname or model name does not select a protocol.

| Python preset         | API format           | Full endpoint                                        | Key environment variable |
| --------------------- | -------------------- | ---------------------------------------------------- | ------------------------ |
| `typesafe`            | `typesafe-systemone` | `https://api.typesafe.ai/v1/systemone`               | `TYPESAFE_API_KEY`       |
| `openai`              | `openai-decisions`   | `https://api.openai.com/v1/decisions`                | `OPENAI_API_KEY`         |
| `coreinfra-jev`       | `typesafe-systemone` | `https://hub.coreinfra.ai/typesafe/api/v1/systemone` | `COREINFRA_API_KEY`      |
| `coreinfra-decisions` | `openai-decisions`   | `https://hub.coreinfra.ai/openai/api/v1/decisions`   | `COREINFRA_API_KEY`      |

The operator-provided CoreInfra documentation identifies `/openai/api/v1`
as the application API base for Responses/Chat Completions; `/codex/api/v1`
is the Codex agent route with agent-specific model catalogue. It does not
explicitly list Decisions. The Decisions resource was subsequently live-checked under the application
base: Noul/Choice/Score completed with HTTP 200 on the synthetic example.
This verifies the checked calls, not every model/account or future availability. Override it with the supplier-confirmed full URL when needed.
Native endpoints also require account/model access; presets do not prove access.
`endpoint_url` is passed to the released adapter unchanged, without appending
`/v1`, `/systemone` or `/decisions`. OpenAI Decisions is different from Responses
and Chat Completions. A different URL cannot convert protocols.

## Local smoke CLI

Create a separate environment; preserve environments used for historical runs:

```bash
# Choose an isolated path according to your local build/cache policy.
export PROVIDER_ENV=/absolute/path/to/provider-evaluation-0.9
python3.13 -m venv "$PROVIDER_ENV"
"$PROVIDER_ENV/bin/python" -m pip install -r evaluation/requirements-providers-current.txt
"$PROVIDER_ENV/bin/python" -m pip check
```

Dry-run validates public configuration and input without importing the SDK,
reading credentials, creating output or making network requests:

```bash
python3 evaluation/provider_smoke.py fixtures/providers/smoke.json --provider typesafe --max-calls 3
python3 evaluation/provider_smoke.py fixtures/providers/smoke.json --provider openai --max-calls 3
python3 evaluation/provider_smoke.py fixtures/providers/smoke.json --provider coreinfra-jev --max-calls 3
python3 evaluation/provider_smoke.py fixtures/providers/smoke.json --provider coreinfra-decisions --max-calls 3
python3 evaluation/provider_smoke.py fixtures/providers/smoke.json --config fixtures/providers/custom.json --max-calls 3
```

The custom JSON contains only public fields. Supply overrides with
`--api-format`, `--endpoint-url`, `--model`, `--key-env`, `--provider-id` and
`--timeout`. The example `gateway.example.com` is a placeholder.
CLI output includes adapter version as runtime metadata; config input accepts
only schema/id/api_format/endpoint_url/model/key_env and optional timeout.

After separately authorizing the supplier, input and spending, run explicitly:

```bash
"$PROVIDER_ENV/bin/python" evaluation/provider_smoke.py \
  fixtures/providers/smoke.json --provider coreinfra-jev --max-calls 3 \
  --live --output .artifacts/coreinfra-jev-smoke
```

Only the selected environment variable is read; there is no credential fallback.
Alternatively `--key-file /absolute/private/file` selects a regular file with no
group/other permissions and at most 8192 bytes. Never put keys in config JSON,
URLs, command arguments, reports or git. API keys are inserted into Bearer auth.
The URL must use HTTPS, a DNS host, port 443 and a plain path without credentials,
query or fragment. This operator-only Python CLI is **not** the hosted Docker
public-address egress sandbox; it can reach operator-configured DNS destinations.

Each Noul/Choice/Score question makes one request for either API format, up to
three, with no automatic batching, retries, redirects, provider fallback or
ambient environment proxy. Timeout is per SDK HTTP operation, not an end-to-end
deadline. A request cap is not a currency cap. Set a supplier spending limit.

Every attempt reserves its slot before sending. The new private output directory
contains checkpointed `report.json` (`normlab.provider-smoke/v2`): actual request bodies, HTTP status, timing,
normalized results, returned model, request ID, usage and dependency versions.
Headers, keys and error bodies are excluded. Input narratives and model results
are sensitive; use synthetic inputs and protect output. On the first failure,
remaining questions stay `not-executed`; there is no automatic resume. A crashed
attempt can remain `sent`. Exit 0 means all primitives completed, 3 means incomplete
execution. This smoke report has no semantic labels or quality score and does not
replace the frozen Stage 1 executor/capture/replay protocol. Version 2 retains
the 0.7 typed usage metadata, including `cost_usd` when supplied; unknown cost
remains null. The top-level `cost` is not an inferred total. Existing v1 reports
stay historical. Images are not accepted by this text-only CLI, despite optional
image support in the upstream adapter.

## Historical evaluation compatibility

Existing v1 manifests, captures, labels and source SHA pins remain unchanged.
The legacy ProxyAPI factory accepts checked runtime adapters 0.3.0, 0.4.0, 0.7.0, 0.8.0 and 0.9.0; its frozen
provider metadata still describes the original 0.3.0 manifest. Actual runtime
versions are recorded separately in `capture.dependencies`. Do not interpret
new captures as identical experimental conditions. New provider exploration uses
this CLI and its distinct `normlab.provider-smoke/v2` report. Construct current
configs with `provider_runtime.configuration`; the current factory rejects a
historical config rather than misreporting its adapter version. Frozen Stage 1
executors intentionally retain their 0.4.0 version checks. That is an archived
execution constraint, not evidence of an SDK wire incompatibility. An exact
historical re-execution can use the archived profile; ordinary current use and CI
need only 0.9.0.

CI installs one current 0.9.0 SDK environment for the current smoke, copied bridge,
verifier replay and Mellea contracts. The frozen Stage 1 retry tests use an
explicit mock-only compatibility probe: it substitutes the current factory and
allows only the declared 0.4.0 / recorded 0.9.0 version pair in two version equalities.
It retains actual dependency metadata and denies live execution/network. It does
not make old captures/permits valid under a new execution runtime.
See the [0.9.0 direct categorical integration](CATEGORICAL_EVALUATE_INTEGRATION.md).
The [0.8.0 upgrade report](JEV_ADAPTER_0_8_UPGRADE_2026-10-18.md) remains historical evidence.
The [0.7.0 compatibility report](JEV_ADAPTER_0_7_UPGRADE_2026-10-15.md) remains historical evidence.

The 0.8.0 SDK's `ResponsesChoiceProvider` is connected through the separate
[`responses_smoke.py` entry point](CATEGORICAL_RESPONSES_INTEGRATION.md) for
ordinary Luna and configurable Responses endpoints. It accepts unchanged Choice
tasks with explicit independent/batch dispatch and label-only result metadata.
The native `provider_smoke.py` CLI still exposes TypeSafe SystemOne and OpenAI
Decisions primitives. Neither path migrates frozen native Stage1 execution or
converts label-only responses into probability-based evidence.

The copied ProxyAPI bridge remains: besides routing it normalizes a body response
ID into the TypeSafe request-ID header. A generic System One endpoint setting
alone does not reproduce that compatibility layer.

## Direct categorical evaluation

`evaluation/categorical_smoke.py` connects native TypeSafe/OpenAI Choice and
ordinary Responses through the released 0.9.0 `CategoricalRequirement.evaluate()`
bridge. An explicit caller policy maps every category to accept/reject/review;
operational errors remain failed attempts. It preserves native distributions
when available and leaves ordinary-model confidence absent. No sampling, repair
or automatic fallback is used. See the [contract, dry-run and report fields](CATEGORICAL_EVALUATE_INTEGRATION.md).

## Hosted TypeScript gateway

The hosted path uses TypeScript adapters, independently of the Python package.
Set these public values **identically in gateway and egress**:

| Full endpoint variable                  | Fallback when absent                       |
| --------------------------------------- | ------------------------------------------ |
| `NORMLAB_OPENAI_RESPONSES_ENDPOINT_URL` | `NORMLAB_OPENAI_BASE_URL` + `/responses`   |
| `NORMLAB_OPENAI_DECISIONS_ENDPOINT_URL` | `NORMLAB_OPENAI_BASE_URL` + `/decisions`   |
| `NORMLAB_TYPESAFE_ENDPOINT_URL`         | `NORMLAB_TYPESAFE_BASE_URL` + `/systemone` |

Base URL defaults remain native OpenAI and TypeSafe. Explicit full endpoints
have precedence and can use different hosts. These settings are operator-only;
they are not accepted from browser/RPC requests. The egress allowlist derives
from the three validated destination authorities, retains DNS/public-address
checks and TLS port 443, and requires recreating **both** services after changes.
This repository does not alter the external Platform Compose deployment.

Discovery uses `NORMLAB_OPENAI_MODEL` and `NORMLAB_OPENAI_API_KEY_FILE`.
Set `NORMLAB_INFERENCE_CLASSIFIER=decisions` or `typesafe` for classification.
Decisions uses `NORMLAB_DECISIONS_MODEL` and optional
`NORMLAB_DECISIONS_API_KEY_FILE`; when that file setting is absent it deliberately
shares the OpenAI discovery key. An explicitly configured bad file fails startup.
TypeSafe uses `NORMLAB_TYPESAFE_MODEL` and `NORMLAB_TYPESAFE_API_KEY_FILE`.
Model aliases are bounded opaque identifiers, including vendor prefixes.
All keys must belong to the supplier of the selected endpoint.

For a separate Decisions supplier, mount its protected host file read-only at
`/run/secrets/normlab_decisions_api_key` and set
`NORMLAB_DECISIONS_API_KEY_FILE` to that path **in gateway only**. Egress and
NormLab never receive provider secrets. Existing secret validation applies;
see [hosted deployment and secret inventory](HOSTED_INFERENCE.md).

## Next evidence

Perform an authorized compatibility smoke for each actual supplier/path/model,
then integrate the selected provider into the bounded Stage 1 live transport.
Freeze runtime versions and use the same corpus, question/context policy and
budget for comparisons. Reachability, normalized answers and semantic accuracy
are separate results.
