# Stage 1 network retries, revision 1

`evaluation/stage1_retry_executor.py` adds an explicit outer retry policy over the
frozen three-provider planner and single-attempt executor. The old no-retry CLI,
manifests, source pins, scorer and captures are unchanged. New retry-plan and
retry-capture schemas distinguish this strategy from historical measurements.
This is a sequential local evaluation runner, not a hosted-service retry change.

## Policy

- **Three attempts maximum per semantic job**: one initial dispatch and up to two
  retries. Every attempt uses a fresh client and the exact same planned request.
  This applies equally to Jev, Luna Decisions and ordinary Luna Low.
- Retry only a recorded `transport-error` whose sanitized exception chain includes
  ConnectError/ConnectTimeout, ReadError/ReadTimeout, WriteError/WriteTimeout,
  RemoteProtocolError or SSLEOFError. Certificate verification errors block retry.
  Unrecognized errors fail closed; they are not assumed transient.
- Exponential backoff with jitter: **1–1.5 seconds**, then **2–2.5 seconds**.
  Mock execution records the lower-bound delay without sleeping.
- HTTP errors, including 429/503, invalid answers, refusal/schema failures,
  request mismatch and model drift are not retried by this policy. There is no
  fallback provider/model or prompt repair. SDK/HTTP internal retries stay zero.
- Process interruption with an unknown attempt outcome stops without resume.
  Interruption during backoff is separately recorded and also stops.

A received network error does not prove the provider never processed or billed
the request. Retrying may therefore pay for duplicate work; the user has explicitly
requested network retries, and every potentially dispatched attempt counts.
No idempotency/deduplication guarantee is claimed for these provider endpoints.

## Aggregate budget and deadline

The global `maxCalls` counts **attempts, not successful jobs**. A cap of 12 allows
at most 12 potentially dispatched requests including retries. It may complete
fewer than four semantic contexts across the three arms. On exhausted attempts,
the whole run stops and preserves the unused semantic suffix.

Pilot has 36 jobs and a maximum schedule ceiling of 108 dispatches; corpus has
288 jobs and a ceiling of 864. These ceilings authorize **zero live requests**.
An explicit permit can set a smaller aggregate cap. Old plan-bound permits do
not match the new retry-plan digest. The child permit is derived from the approved
aggregate permit, retains its spending declaration/expiry and allows only one
dispatch; the outer runner enforces the aggregate cap.

The original wall-time budget applies across jobs, retries and backoff. Checks run
before attempts, before sleeping and after completion. HTTP operation timeouts
remain bounded; synchronous phases may cumulatively overrun the wall budget.
This is not a hard in-flight cancellation guarantee. Monetary enforcement remains
an externally configured operator assertion, not a locally enforced currency cap.

## Capture and replay

Each attempt has its own original-format child capture and split planned job.
The wrapper binds the original plan, retry policy and code hashes, records the
ordered job/attempt IDs, exception-class whitelist and selected backoff, then
checkpoints before execution and after the outcome. Auth headers, exception
messages, URLs from exception text and raw HTTP error bodies are excluded.

Observation temporarily wraps httpx2's transport and response-byte iterator to
record sanitized exception classes while preserving exception propagation. It is
restored in `finally`; this design is for the **single-threaded local CLI only**,
not shared concurrent workers. Exception metadata in a crash may be incomplete.

Replay recompiles the retry plan, validates child requests/responses with the
historical replay, checks attempt ordering/backoff/eligibility and verifies the
aggregate cap. Logical-job status and per-arm dispatch totals are separate: a
job that recovers counts once as completed while both dispatches remain visible.
Missing/pending outcomes are conservatively counted and reported as unknown.
No replay imports SDKs, reads credentials or performs network calls. Hashes are
local integrity checks, not signatures or trusted timestamps.

The previous candidate-label scorer accepts canonical no-retry captures only;
do not feed it the wrapper index or discard failed attempts when assessing the
new strategy. A retry-aware scoring projection is a separate follow-up.

## CLI

```bash
# New retry-plan digest, no SDK/key/network; authorized calls remain zero.
python3 -B -S evaluation/stage1_retry_executor.py \
  fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json

# Real SDK control flow, mock transport, no credential lookup.
.tools/provider-evaluation-0.4/bin/python -B evaluation/stage1_retry_executor.py \
  fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json \
  --mock-output .artifacts/new-retry-mock --mock-scenario recover \
  --max-mock-calls 37

python3 -B -S evaluation/stage1_retry_executor.py \
  fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json \
  --replay .artifacts/new-retry-mock

# Explicit live permit bound to the NEW retry-plan digest, not the old pilot digest.
.tools/provider-evaluation-0.4/bin/python -B evaluation/stage1_retry_executor.py \
  fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json \
  --live-output .artifacts/new-retry-live --permit /absolute/private/permit.json
```

Select corpus with `--profile corpus` in planning/execution/replay. Output paths
must be new. Exit 0 is complete/dry-run, 3 a valid partial capture, 2 rejection.
KeyboardInterrupt retains the process interruption exit; replay can still inspect
the checkpoint. Mock scenarios: recover, exhaust, http, invalid, interrupt,
backoff-interrupt. The HTTP scenario injects 503 and demonstrates no HTTP retry.

## Evidence

Local CLI rehearsals used SDK 0.4.0 mock HTTP with `COREINFRA_API_KEY` removed
from subprocess environments. All nine captures were replayed with Python -B -S:

| Scenario | Mock dispatches | Stop |
| --- | ---: | --- |
| Complete pilot | 36 | complete |
| First failure then recovery | 37 | complete |
| All three attempts fail | 3 | retries-exhausted |
| HTTP 503 | 1 | provider-error |
| Malformed output | 1 | invalid-output |
| Recovery needs a second slot, cap one | 1 | budget-exhaustion |
| Cap zero | 0 | budget-exhaustion |
| Interrupted attempt | 1 | unknown-sent-outcome |
| Interrupted backoff | 1 | interrupted-during-backoff |

These are local control-flow rehearsals, not a new automatic CI suite or live
provider reliability/quality evidence. No paid calls were made for this change.
Next: add a retry-aware terminal-result scoring projection, then authorize a small
live comparison with an aggregate attempt cap and preserve first-attempt reliability.
