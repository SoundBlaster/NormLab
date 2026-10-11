# Provider configuration

Prepared 2026-10-11. Configuration support is separate from live compatibility
and semantic accuracy. The initial configuration update made no live calls. A subsequent authorized
[local compatibility check](COREINFRA_LIVE_CHECK_2026-10-11.md) verified Jev
Noul/Choice/Score and ordinary Luna Responses; the expected Decisions path returned 404.

## API format and supplier

The Python evaluation dependency is pinned to `mellea-jev-adapter==0.4.0`.
A provider is an explicit combination of API format, full HTTPS endpoint, model,
credential source and timeout. The hostname or model name does not select a protocol.

| Python preset | API format | Full endpoint | Key environment variable |
| --- | --- | --- | --- |
| `typesafe` | `typesafe-systemone` | `https://api.typesafe.ai/v1/systemone` | `TYPESAFE_API_KEY` |
| `openai` | `openai-decisions` | `https://api.openai.com/v1/decisions` | `OPENAI_API_KEY` |
| `coreinfra-jev` | `typesafe-systemone` | `https://hub.coreinfra.ai/typesafe/api/v1/systemone` | `COREINFRA_API_KEY` |
| `coreinfra-decisions` | `openai-decisions` | `https://hub.coreinfra.ai/codex/api/v1/decisions` | `COREINFRA_API_KEY` |

The CoreInfra Decisions path is an expected configuration, **not live-verified**
by this update. Override it with the supplier-confirmed full URL when needed.
Native endpoints also require account/model access; presets do not prove access.
`endpoint_url` is passed to the released adapter unchanged, without appending
`/v1`, `/systemone` or `/decisions`. OpenAI Decisions is different from Responses
and Chat Completions. A different URL cannot convert protocols.

## Local smoke CLI

Create a separate environment; preserve environments used for historical runs:

```bash
python3 -m venv .tools/provider-evaluation-0.4
.tools/provider-evaluation-0.4/bin/python -m pip install -r evaluation/requirements-providers.txt
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
.tools/provider-evaluation-0.4/bin/python evaluation/provider_smoke.py \
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
contains checkpointed `report.json`: actual request bodies, HTTP status, timing,
normalized results, returned model, request ID, usage and dependency versions.
Headers, keys and error bodies are excluded. Input narratives and model results
are sensitive; use synthetic inputs and protect output. On the first failure,
remaining questions stay `not-executed`; there is no automatic resume. A crashed
attempt can remain `sent`. Exit 0 means all primitives completed, 3 means incomplete
execution. This smoke report has no semantic labels or quality score and does not
replace the frozen Stage 1 executor/capture/replay protocol.

## Historical evaluation compatibility

Existing v1 manifests, captures, labels and source SHA pins remain unchanged.
The legacy ProxyAPI factory accepts runtime adapter 0.3.0 or 0.4.0; its frozen
provider metadata still describes the original 0.3.0 manifest. Actual runtime
versions are recorded separately in `capture.dependencies`. Do not interpret
new captures as identical experimental conditions. New provider exploration uses
this CLI and its distinct `normlab.provider-smoke/v1` report.

The copied ProxyAPI bridge remains: besides routing it normalizes a body response
ID into the TypeSafe request-ID header. A generic System One endpoint setting
alone does not reproduce that compatibility layer.

## Hosted TypeScript gateway

The hosted path uses TypeScript adapters, independently of the Python package.
Set these public values **identically in gateway and egress**:

| Full endpoint variable | Fallback when absent |
| --- | --- |
| `NORMLAB_OPENAI_RESPONSES_ENDPOINT_URL` | `NORMLAB_OPENAI_BASE_URL` + `/responses` |
| `NORMLAB_OPENAI_DECISIONS_ENDPOINT_URL` | `NORMLAB_OPENAI_BASE_URL` + `/decisions` |
| `NORMLAB_TYPESAFE_ENDPOINT_URL` | `NORMLAB_TYPESAFE_BASE_URL` + `/systemone` |

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
