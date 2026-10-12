# Offline Stage 1 transport adapter v1

Slice 3 [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Imports saved provider v1 and retry v2 captures into the common
[offline envelope](OFFLINE_ENVELOPE_V1.md). No SDK client, credentials, inference,
resume or transport dispatch is constructed by this path.

## Commands

```bash
python3 -B -S evaluation/offline_adapters.py stage1 saved-capture-directory \
  --output .artifacts/stage1-bundle
python3 -B -S evaluation/offline_adapters.py verify .artifacts/stage1-bundle
python3 -B -S evaluation/offline_compare.py \
  .artifacts/stage1-bundle .artifacts/stage1-bundle \
  --output .artifacts/stage1-self-comparison
```

Without `--output`, import validates the in-memory envelope and prints counts.
Export creates an exclusive new directory. Invalid/unsupported input gives
exit 1 and a fixed diagnostic. Legacy retry v1 and historical wire-fixture
executor formats are unsupported; there is no heuristic fallback.

## Source and verification

`normlab.offline-stage1-source/v1` wraps the original indexed file tree:
root capture, split plan/jobs, and each available child plan/capture/turn.
Only referenced JSON files are read; adjacent `.env` files are not collected.
An existing child plan is retained even if the child capture is missing.
Every archived file keeps its original bytes in content-addressed artifacts.
Source paths must stay within the capture directory; bundle paths stay within
the bundle. Limits: 2 MiB per artifact, 64 MiB total, 4096 artifacts, 1024 tasks.
The supported frozen profiles currently contain 36 or 288 logical tasks.

The reader reconstructs the bounded archive in a private temporary directory
and calls the existing native **replay** functions, never their `run` functions.
It validates saved source/task digests, matched arm bindings and planned wire
requests, native turn invariants, model drift, retry order/backoff, permits,
call caps and pending suffixes. It then regenerates the entire projection and
requires equality with the saved envelope, including metrics and identities.
Changing derived statuses/attempts/counts and recomputing hashes cannot bypass
this check.

This verifies internal consistency of a saved plan and capture tree. It does
not regenerate that plan from the original corpus or authenticate a provider,
operator, source document or historical execution. Original manifest/parent/code
digests remain in the archived plan. The adapter does not claim independent
dataset verification from those digests alone.

Run identity is explicitly `legacy-bundle-derived`. The source wrapper binds
all archived files. `captureDigest` binds outer and child captures plus raw turns,
so changing a child response changes capture-set identity even when the outer
retry index bytes remain identical. `inferenceCallsExecuted: 0` refers to import
or verification; `saved-live` identifies the historical capture mode.

## Attempts and outcomes

Each logical task has one turn and an explicit array of transport attempts:
`normlab.offline-attempt/v1`. Retries remain attempts of that turn; they do not
become dialogue turns. An unexecuted task has an empty array. This differs from
legacy classification/S1.3, whose unavailable attempt history remains `null`.

An attempt records its parent turn, ordinal/derived ID, original and normalized
status, outer `finished` flag, known dispatch count, budget reservation,
raw turn/child capture/child plan/request references, error/exception classes,
backoff, returned model/request ID, usage, latency and unknown cost.
The original public response remains in the archived raw turn.

- Provider `sent` and unfinished retry entries become `unknown-sent-outcome`.
- An absent child has `dispatches: null` and a conservative budget reservation
  of 1; it is not evidence of an actual HTTP call.
- A completed child with an unfinished outer checkpoint keeps known model,
  request ID and usage, but exposes no accepted verdict.
- Returned model drift is `model-rejected`; raw child evidence remains available.
- A failed/unknown suffix is not dropped from the planned denominator.
- Illegal execution after an unknown outcome is rejected. No automatic resume
  or retry occurs while importing/reading a bundle.

The native plan lacks language metadata; `language` remains `null` rather than
being guessed from a case ID or source text.

## Counts and reference boundary

The report (`normlab.offline-stage1-report/v1`) preserves the native replay summary
and per-task first/final statuses and observed labels. Counts include:

- All planned tasks/questions, final and first status counts, raw attempt statuses.
- Reserved attempt entries and retries; known dispatches separately from unknown
  dispatch reservations. `attemptsStarted` follows the native index convention
  and includes reservations; it does not establish actual HTTP dispatch.
- Unknown outcomes and dispatched/reserved attempts without usage.
- Known input/output tokens summed **once per attempt**, including a completed
  child whose outer outcome is still unknown.

`turn.usage` describes the last available attempt; the bundle's known-token counts
sum all attempts, not just final turns. Known zero is not an estimate of missing
usage or cost. `cost` and case-level quality remain null.

This transport slice does **not import candidate labels or native scored reports**.
`reference` is null, `referenceStatus` is `not-evaluated`, and selected-reference
pass remains null. The comparator retains status/unmatched rows, but every
otherwise compatible Stage 1 pair remains `not-evaluated` for quality. Importing
sealed references/score views is a separate next slice; a successful replay
does not become evidence for the target quality percentage.

## Portable reader

Use the exact trusted reader revision that produced the bundle. Copy the 18
modules listed by `offline_stage1_source.READER_FILES` into `evaluation/`, and
the asset listed by `READER_ASSETS` into `server/`, preserving that layout.
Add `offline_compare.py` for comparison. No repository fixtures or SDK packages
are needed. The prompt asset is required by an eager import in the unchanged
legacy harness; the adapter records its digest explicitly.

Stage 1 verification requires those reader/native module and asset bytes to
match the bundle's adapter revision. It never loads or executes archived code
artifacts. Classification/S1.3 retain their existing five-module reader path;
comparison adds its own sixth module.

## Evidence and next step

[Executed checks and historical imports](OFFLINE_STAGE1_ADAPTER_2026-10-13.md).
Next: review this transport contract, then add independently versioned imports
of Stage 1 seals/references/score views before MLflow projection.
