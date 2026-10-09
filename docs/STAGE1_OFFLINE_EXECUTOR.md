# Stage 1: offline executor and replay

## Scope

`evaluation/stage1_executor.py` rehearses the frozen
[comparison protocol](STAGE1_COMPARISON_PROTOCOL.md) with public synthetic wire
responses. This is the first implementation slice of the executor. **No live
transport exists in this runner**: no SDK, HTTP client, credential lookup or live
flag. The protocol still authorizes **zero paid calls**.

The reusable parser in `evaluation/stage1_wire.py` covers representative
Jev/Decisions Choice and Luna Responses JSON
Schema bodies, including refusal, incomplete output and malformed distributions.
Fixtures give Jev a synthetic body `id`; a future real Jev transport must obtain
the request ID from `x-typesafe-request-id`. These fixtures do not establish SDK
or gateway interoperability.

## Reproduce

From the repository root, using Python 3.9+:

```bash
# Dry run: compile the pinned plan; no files, credentials or network.
python3 evaluation/stage1_executor.py \
  fixtures/parking-pilot/stage1-comparison-v1/experiment.json

# A new directory is required. This consumes synthetic fixture slots only.
python3 evaluation/stage1_executor.py \
  fixtures/parking-pilot/stage1-comparison-v1/experiment.json \
  --mock-output .artifacts/stage1-offline-pilot

# Recompile the pinned plan and validate stored requests, bodies and states.
python3 evaluation/stage1_executor.py \
  fixtures/parking-pilot/stage1-comparison-v1/experiment.json \
  --replay .artifacts/stage1-offline-pilot

# Exercise a stop after two consumed fixture slots.
python3 evaluation/stage1_executor.py \
  fixtures/parking-pilot/stage1-comparison-v1/experiment.json \
  --mock-output .artifacts/stage1-offline-cap-two --max-fixture-calls 2
```

Use `--profile corpus` or `--profile decisions-pilot` for the other schedules.
No flag allows increasing the frozen profile cap. An existing capture directory
is never overwritten or resumed. Run tests with:

```bash
python3 -m unittest discover -s evaluation -p 'test_stage1*.py'
```

## Capture contract

- `plan.json`, split planned job files and a plan summary come from the unchanged
  planner. Replay compares the reconstructed export with a freshly compiled plan.
- `capture.json` binds the plan digest, fixture digest, executor/parser source hashes,
  fixture cap, stop reason and ordered hashes of all turn files.
- Each turn binds the full job digest, exact public request, consumption count,
  state, HTTP status, successful raw body, normalized result and local latency.
- Each JSON artifact is bounded by 2 MiB. Accepted response bodies have a stricter
  1 MiB bound to leave room for request and capture metadata.
- Counts include every planned job, including failed and unexecuted suffixes.
  `fixtureCalls` and `networkCalls` are separate; the latter is always zero here.
- Successful bodies are replayed through the same parser. HTTP error and malformed
  response bodies, exception messages and authorization headers are not serialized.

State transitions are `not-executed → sent → completed/failed`. A consumed slot
and public request are checkpointed **before** fixture consumption. A surviving
`sent` checkpoint has an unknown outcome and stops replay; it cannot be resumed.
Replay rejects contradictory states, changed requests, altered normalized results,
executed jobs after a stop and returned model drift within an arm.

Files use atomic replacement individually. The directory is not a transactional
database: interruption between replacing a turn and its index may cause a digest
mismatch, which fails closed. Hashes detect accidental changes relative to the
index; they are not signatures and cannot authenticate a maliciously rewritten
bundle. Capture source hashes deliberately reject executor version drift.

## Limits and evidence

Offline caps and pre/post monotonic deadline checks are exercised. A synchronous
fixture parser is not forcibly interrupted mid-parse. This is **not a hard wall
deadline guarantee for future network calls**. The frozen transport timeout and
monetary cap cannot be verified without that future transport.

The demo cycles labels by schedule position, never opening reviewer labels. All
confidences, model IDs, token counts and latencies are synthetic/local rehearsal
data. No semantic scorer or critical-error-free rate is inferred from them.
`actualCost` and `criticalErrorFreeRate` remain null.

Recorded [offline summaries](../fixtures/parking-pilot/stage1-offline-executor-v1/summaries.json):

| Profile | Fixture slots completed | Network calls | Stop |
| --- | ---: | ---: | --- |
| pilot | 24 | 0 | none |
| corpus | 192 | 0 | none |
| decisions-pilot | 12 | 0 | none |

These 228 mock slots test control flow only. CI's existing Stage 1 discovery
pattern includes the new executor tests automatically.

## Next gates

1. Repair the four active P1 findings in the [PR inspection](OPEN_PR_REVIEW_2026-10-10.md).
2. Add a separate real transport with exact frozen wire bodies, Jev header IDs,
   disabled retries/redirects, sanitized errors and bounded responses. Exercise
   that actual client path through a mock HTTP transport before any live call.
3. Bind an explicit live execution permit to the plan digest, confirm pricing and
   monetary enforcement, and exercise timeout/unknown-outcome behavior. Keep the
   current offline runner and historical evidence unchanged.
4. After live opt-in, perform bounded compatibility probes, then the 24-call pilot.
   Seal predictions before loading candidate labels; report failures and abstentions
   in the planned denominator, without promoting labels to expert ground truth.
