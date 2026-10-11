# Stage 1: CoreInfra three-arm transport

Prepared 2026-10-11. Implementation and mock HTTP execution only; **zero live
Stage 1 requests**. Earlier small [compatibility probes](COREINFRA_LIVE_CHECK_2026-10-11.md)
verified the selected API routes, not this full Russian verifier task.

## New revision and matched inputs

`stage1_provider_plan.py` layers a separate provider experiment over the frozen
historical comparison manifest. It verifies that manifest, its source/code pins,
review disposition and source/candidate/definition/convention hashes using the
original compiler. Historical files/captures/source pins remain unchanged.

The new manifest is
[`stage1-coreinfra-v1/experiment.json`](../fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json).
Each source/candidate/repeat supplies exactly the same semantic task to:

| Arm | Exact endpoint | Client |
| --- | --- | --- |
| Jev `jev-1.13.0` | `https://hub.coreinfra.ai/typesafe/api/v1/systemone` | TypeSafeProvider, adapter 0.4.0 |
| Luna Decisions `gpt-6-luna` | `https://hub.coreinfra.ai/openai/api/v1/decisions` | OpenAIProvider, adapter 0.4.0 |
| Ordinary Luna `gpt-6-luna` | `https://hub.coreinfra.ai/openai/api/v1/responses` | Direct httpx2, Low + strict JSON Schema |

One Choice is asked per request. The SDK question name `classification` maps to
the semantic `overall` verdict. Responses gets the complete canonical task and
returns `{"overall":"compatible|incompatible|indeterminate"}`. These wire
representations are not byte-identical, but candidate text, definitions,
conventions, instructions and criteria are shared. No reviewer labels are read.
There is no previous-response/conversation ID, tools, repair or extra prompt.
Responses sets `stream=false`, `store=false`, Low reasoning and 1024 maximum
output tokens. Decisions/TypeSafe expose no equivalent output ceiling here;
this is not an equal-token/cost-budget comparison.

The historical case/record/repeat order is retained. The three-arm order rotates
per semantic context, balancing each position: four appearances per position per
arm in pilot; 32 in corpus. All three contexts are fresh, even for identical input.

| Profile | Cases / records | Repeats | Calls per arm | Total cap | Wall budget |
| --- | --- | --- | --- | --- | --- |
| `pilot` | C002, C008 / 4 | 3 | 12 | **36** | 1350 s |
| `corpus` | 16 / 32 | 3 | 96 | **288** | 10800 s |

Corpus includes pilot cases; these are not additional independent observations.
Repeats measure variability and are not independent cases. Shared semantic input
limit is 32768 UTF-8 bytes. Concurrency is one. Plans authorize zero paid calls.

## CLI

```bash
# SDK-free planning, no keys/network/output.
python3 -S evaluation/stage1_provider_executor.py \
  fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json

# Actual SDK request construction with MockTransport, no credential lookup/network.
.tools/provider-evaluation-0.4/bin/python evaluation/stage1_provider_executor.py \
  fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json \
  --mock-output .artifacts/new-stage1-mock

# Recompile the pinned plan and replay without SDKs, credentials or network.
python3 -S evaluation/stage1_provider_executor.py \
  fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json \
  --replay .artifacts/new-stage1-mock
```

`--profile corpus` selects the larger schedule. `--max-mock-calls 2` rehearses a
partial run. `--mock-fault http|transport|malformed|model-drift|request-mismatch|interrupt` and
`--mock-fault-slot N` inject a fault at a zero-based slot; model drift must be
injected after that arm has already completed once. `interrupt` stops after the
sent checkpoint so replay can report unknown outcome; `request-mismatch`
exercises rejection before dispatch. Fixture labels cycle by
schedule position without opening annotations. They are not model predictions.

Exit 0 means complete execution/replay or a valid dry-run; 3 means a valid partial
run; 2 means a configuration/artifact/operation error. Diagnostics omit exception
text, URLs, HTTP error bodies and credentials.

## Capture and replay

The new private directory contains the full split planned jobs, capture index
and one turn per planned job. Turn/index writes use atomic file replacement;
crashes between replacements can yield a hash mismatch and fail closed.

- Before HTTP dispatch, recorder verifies exact method, URL and parsed body
  against the plan, reserves one call and checkpoints `sent`.
- A request/model/body mismatch stops before dispatch. Every provider retry or
  unexpected extra call is rejected. Redirects and environment proxies are disabled.
- All failures and the unexecuted suffix remain in the planned denominator.
  Counts separate mock HTTP slots from potentially sent live requests.
- Accepted responses retain replayable public fields, model, normalized verdict,
  request ID, usage and latency. Jev's ID comes from `x-typesafe-request-id`;
  Decisions uses `x-request-id`; Responses uses its body ID.
- Authorization headers, raw error bodies and encrypted reasoning are excluded.
  Successful text/body data can still contain the narrative; use synthetic cases.
- Responses are bounded to 1 MiB; JSON artifacts to 2 MiB. Duplicate JSON keys,
  malformed distributions, refusal/incomplete output, unknown labels, missing
  coverage and returned-model drift reject the run. SDK results must agree with
  the independent parser's label/model/request ID.
- Replay verifies plan, hashes, source versions, permit/cap, job order, public
  requests, states, results and returned-model stability. It never invokes SDKs.
  Hashes are integrity checks, not signatures/authentication of an adversarial bundle.

`sent` without a final checkpoint means unknown outcome and possible spending;
replay reports this and no automatic resume exists. New outputs cannot overwrite
existing directories. Actual cost and semantic-quality metrics remain null.

## Live permit and spending

Live execution is explicitly separate:

```bash
.tools/provider-evaluation-0.4/bin/python evaluation/stage1_provider_executor.py \
  fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json \
  --live-output .artifacts/new-stage1-live --permit /absolute/private/permit.json
```

The checked-in `permit.example.json` is deliberately unusable: zero calls,
expired timestamp, no amount/pricing reference and no operator confirmation.
Create an authorized permit only after approving the actual plan digest, budget,
current pricing and supplier spending limit. Fields are:

- `planDigest`: exact digest printed by dry-run, not just experiment name.
- `maxCalls`: positive and no more than the selected profile cap.
- `expiresAt`: timezone-qualified timestamp; checked before execution/dispatch.
- `spending`: external-provider-limit, positive amount, ISO currency,
  pricing reference and explicit operator confirmation.

Only `COREINFRA_API_KEY` is selected by the supplied manifest. Custom providers
can use another explicit environment name and HTTPS endpoint in a new manifest;
there is no fallback key or supplier. All keys are checked before dispatch.

The runner enforces the call cap locally. The monetary limit is an **operator
assertion about a separately configured provider-side limit**; the runner cannot
verify or enforce that account setting or compute bills. It must not be described
as a local hard currency cap. A request can be charged even if its response fails.
There is no price estimate or default spend authorization in this implementation.
The local operator CLI is not the hosted Docker egress sandbox.

HTTP timeout is at most 30 seconds per operation, reduced to remaining wall time.
Monotonic checks run before calls, during response reading and after completion.
This synchronous transport is not a hard wall-clock kill: DNS/connect/TLS/write/read
phases can cumulatively overrun the wall budget. An overrun stops the run and
rejects the verdict. Do not claim hard in-flight cancellation or safe resume.

## Evidence and next step

Pilot and corpus mock HTTP captures/replay and failure rehearsals are summarized
in the fixture README. They establish the exercised control flow only. The full
verifier inputs have not reached CoreInfra in this change. No threshold/model
quality conclusion follows from the synthetic transport labels.

Next: authorize a small plan-bound live cap under a confirmed supplier spending
limit, execute and seal predictions, then run a separate candidate-label scorer.
The existing diagnostic labels are LLM-reviewed candidates, not expert ground truth.
