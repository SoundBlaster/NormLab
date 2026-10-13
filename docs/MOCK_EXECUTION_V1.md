# Durable single-writer mock execution: slice 5b

Date: 2026-10-13. Task: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Base: `ce88fd0472bd9f0718cf8c11cd96001883970e87` (#92).
Builds on [execution records 5a](EXECUTION_RECORDS_V1.md) and the
[execution/resume proposal](EXECUTION_RESUME_CONTRACT_V1.md).

## Scope

Implements a local POSIX single-writer **mock** executor with immutable exact
request artifacts, pre-dispatch reservations and atomic checkpoints. It invokes
only a built-in scripted Python transport. No provider SDK, HTTP client,
credentials, inference, live permit, resume/adoption, scorer/reference access or
registry integration is available on this path. Arbitrary transport/plugin
objects reject before creating an output directory.

The clock is a deterministic simulation, including simulated request latency and
backoff. It does not read or attest the host clock or suspension. The saved
`linux:CLOCK_BOOTTIME` field is the symbolic declaration required by the 5a mock
record subset, not evidence that macOS or this process implements that clock.
`runtimeClockVerified`, `providerWireValidated`, `codePinsVerified` and
`executionReady` stay false. Every CLI result grants and executes zero inference
calls. Passing this gate never authorizes a live request.

## Commands

Python 3.10+ on macOS/Linux, local filesystem with working POSIX locks, atomic
replace and file/directory `fsync`:

```bash
python -B -S evaluation/execution_mock_cli.py run /path/to/5a-input /path/to/fresh-output /path/to/mock-script.json
python -B -S evaluation/execution_mock_cli.py inspect /path/to/fresh-output
```

`5a-input` contains an already valid `plan.json` and its content-addressed public
artifacts. Only the plan and referenced bytes are copied; existing run/permit/
resolution or unrelated files are not imported. The output parent must exist;
the output directory itself must be absent. No overwrite, cleanup, automatic
retry of the command, reopening or continuation of an existing execution occurs.
Each new execution gets fresh execution/invocation UUIDs.

`inspect` is read-only and rejects while the writer holds its exclusive lock.
Exit 0 means structurally consistent saved mock evidence, including failed or
paused runs. Exit 2 is sanitized rejection; no exception message, source text,
path or credentials are printed. Process interruption can leave a partial fresh
directory without an initial checkpoint; inspection then rejects it.

## Script v1

Closed root shape: `{schema, clock, tasks}`, schema `normlab.mock-script/v1`.
Clock is `{startNs, utcStart, stepNs}`: nonnegative integer nanoseconds, exact 5a
UTC timestamp and integer step of at least 1000 ns. The epoch is derived from this
synthetic clock definition. Elapsed time advances after committed events, during
the scripted latency and during backoff; it does not measure storage/runtime
latency. Deadline remains `startNs + plan.wallTimeNs`.

Tasks are the complete ordered plan denominator, each `{key, attempts}`. Attempts
contain exactly `{status, model, answers, errorClass, statusCode, latencyNs}`.
There are 1–3 attempts, exactly covering the frozen eligible retry path; a script
cannot silently end at a retryable failure or add attempts after completion.

- Status: a 5a terminal category or `unknown-outcome`.
- `model`: nonempty string. A completed response with an unaccepted/drifted model
  becomes `model-rejected`, retaining the original scripted response.
  An explicit `model-rejected` status must already be justified during preflight:
  the model is unaccepted or differs from a prior reachable completion in the
  same arm. Transport failures and unexecuted suffixes do not establish drift.
- `answers`: ordered 5a normalized Noul/Choice/Score answers only for completion;
  otherwise null. Types, labels, scale and order must match the pinned schema.
- `errorClass`: one frozen sanitized class for transport failure, otherwise null.
- `statusCode`: integer 400–599 for HTTP failure, otherwise null.
- `latencyNs`: nonnegative integer, at most the arm's declared timeout.

The script is validated before output creation and stored as canonical JSON.
This is controlled test data, not a native provider response normalizer or proof
that a provider would return the supplied answers. See the
[reproducible test fixtures](../evaluation/test_offline_mock_execution.py).

## Durable layout and commit

| File                      | Meaning                                                                  |
| ------------------------- | ------------------------------------------------------------------------ |
| `plan.json`               | Original validated plan bytes, immutable                                 |
| `intent.json`             | Initial 5a mock run, immutable execution/invocation/task identities      |
| `mock-script.json`        | Frozen canonical script, immutable                                       |
| `artifacts/<sha256>.blob` | Original public input bytes and synthetic response/result/outcome bytes  |
| `checkpoint.json`         | Sole current authority: journal plus its consistent derived run view     |
| `.writer.lock`            | Exclusive advisory local writer lock; shared nonblocking inspection lock |

Checkpoint closed shape is `{schema, intentDigest, scriptDigest, run, journal}`,
schema `normlab.mock-checkpoint/v1`. Digests bind the immutable intent/script
bytes. `run` and `journal` retain the closed 5a schemas. All non-view run fields
must match the initial intent. The reader validates the initial empty intent and
then applies the unchanged strict 5a replay to the checkpoint's run/journal.
Saved summaries cannot replace derived counters.

The combined checkpoint avoids a crash window between independently updated
`run.json` and `journal.json`. Those two root files are deliberately not produced;
use the new inspector. Existing 5a/native/offline-envelope/MLflow readers are not
silently extended to this layout. Runtime export/registry integration is 5d.

Publication uses a same-directory exclusive temporary file, full write, file
flush and `fsync`, atomic publication, then directory `fsync`. Immutable names use
an exclusive hard-link publication; the checkpoint uses atomic replacement. The
fresh execution directory and its parent are also flushed. A local exclusive
`flock` is held for the writer lifetime. Errors during publication poison that writer
and abort execution; no dispatch follows a failed reservation barrier.

1. Copy/flush plan and all referenced bytes, initial intent and script.
2. Commit and replay-validate an empty checkpoint before constructing transport.
3. Check schedule, caps and simulated deadline; commit a validated reservation.
4. After the reservation's directory flush returns, invoke the built-in mock at
   most once with the exact copied public request bytes.
5. Publish/flush response, normalized result and outcome; commit the terminal
   event only after their artifacts are published.
6. Retain frozen retry/backoff, or stop; finalization is a separate checkpoint.

Atomic replacement is the visibility point. If publication fails after replace,
inspection can see the complete new checkpoint even though the writer did not
receive a successful durability acknowledgement. Before replace it sees the old
checkpoint. Both are validated; the failed writer never proceeds. Tests establish
process-crash behavior and barrier ordering, not physical power-loss guarantees,
storage-controller correctness, remote filesystem safety or writer attestation.

## Accounting and interruptions

All four caps are conservatively reserved once per attempt. Multiple questions
share one request; zero synthetic provider usage never refunds token reservations.
Mock outcomes declare false provider dispatch and zero provider usage. Committed
mock outcome count is separate from provider dispatches and from calls that may
have occurred before a crash.

A reservation without a terminal event remains `paused-unknown`. Orphan response,
result or outcome artifacts cannot establish completion. Unreferenced temporary
or artifact files are preserved for investigation, not adopted or deleted by the
reader. Unknown stops the whole schedule. Terminal transport failure can retry
only under the 5a whitelist/three-attempt ceiling, with deterministic lower-bound
1/2 second simulated backoff. Certificate/HTTP/output/model failures do not retry.

Caps and deadline are rechecked before each reservation. If the simulated deadline
is reached after reservation but before dispatch, the charge remains and no mock
call occurs. A terminal response may arrive after the deadline; later reservations
are forbidden. Deadline reached during backoff prevents the next attempt.

Published ordinary files are capped at 2 MiB, the combined checkpoint at 16 MiB,
the published inventory at 4096 files/64 MiB. In-progress temporary files add at
most one bounded publication buffer; retained crash evidence is not automatically
cleaned. Referenced artifacts, intent/script/checkpoint must be regular files;
symlinks/FIFO reject. The private directory and advisory locks assume cooperating
local processes, not an adversary rewriting directories under the reader.

## Verification and next gate

[Runtime verification](MOCK_EXECUTION_VERIFICATION_2026-10-13.md) records local
results and fault-injection scope. The existing Stage 1 offline CI command
discovers the new test module.

[Slice 5c](MOCK_RESUME_V1.md) extends this path through a new versioned reader and
explicit mock continuation/stop/adopt requests, preserving budgets/deadline.
The v1 5b command itself still never reopens an execution. Prediction-seal/export,
host clock/current authorization/code attestation and live transport remain
unimplemented. Next is **5d runtime export/registry integration**. #77 remains open.
