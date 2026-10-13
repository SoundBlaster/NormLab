# Execution records 5a: offline runtime verification

Date: 2026-10-13. Task: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Base: `c25b8b3ac01f511bcb8ab4fbac129dd0c92b719c` (merged #91 reader and #58).
Contract: [execution records v1](EXECUTION_RECORDS_V1.md).

## Result and scope

Dedicated coverage consists of 33 unittest methods with positive cases and
mutation subtests. All pass on Python 3.10.19 and 3.14.8 on macOS. The complete
stdlib-only offline suite passes 94/94 on Python 3.14.8, including the 61 existing
export, comparison, Stage 1/reference and MLflow projection checks.

One production defect was reproduced and corrected: the intent factory required
a live permit before allocating the execution UUID that the permit must bind.
No provider requests, credentials, inference, deployment or real MLflow SDK
integration were involved. This verifies the read-only 5a subset, not an executor,
resume implementation, provider compatibility or semantic model quality.

## Reproduction

From the repository root, with Python 3.10+ and no third-party dependencies:

```bash
python -B -S -m unittest discover -s evaluation -p 'test_offline_execution*.py' -v
python -B -S -m unittest discover -s evaluation -p 'test_offline_*.py' -v
```

The dedicated tests are
[record/replay scenarios](../evaluation/test_offline_execution_records.py) and
[boundary scenarios](../evaluation/test_offline_execution_boundaries.py), using
[independent synthetic construction](../evaluation/execution_test_support.py).
The existing Stage 1 CI command already discovers both test modules. Fresh CI is
separate from these local results and is recorded on the verification PR.

Fixtures are generated under a temporary directory outside the repository. Test
construction independently derives hashes, IDs, journal chains and expected
summaries; it does not call production replay or counter helpers to build the
expected record. Fixtures labelled `live-capture` are synthetic declarations
with an `example.invalid` endpoint and historical synthetic permits; they are
not live evidence or current authorization.

CLI subprocesses use `-B -S`, a minimal environment without inherited credentials,
and audit guards installed before importing the reader. Guards deny socket use,
child processes, provider SDK/HTTP client imports, file writes/mutations and
reviewer-label reads. Planning additionally denies reads of run/journal/resolution
files. Positive controls deliberately trigger each network/process/SDK/write/
label guard. Rejection assertions exclude guard `AssertionError` so a blocked
side effect cannot masquerade as a successful input-validation test. Accepted
cases also compare every fixture file's hash before and after reading.

These audit hooks are regression controls for this Python path, not an OS sandbox
or a general security boundary against arbitrary native code.

## Covered behavior

| Area                     | Positive evidence                                                                                                                                        | Rejection / conservative evidence                                                                                                                                      |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Plan                     | `plan` equals `dry-run`; all four supported protocol subsets; exact ordered three-question request; custom public HTTPS endpoint                         | Rebound unsupported policies/types, context/history/settings/model/question/label drift, structured credentials; planning cannot read execution or authorization files |
| Identity / permit        | Fresh distinct execution/invocation UUIDs; allocate intent, then bind permit; empty mock/live-shaped captures                                            | Saved live capture without permit; live permit in mock; plan/run/provider-scope binding, boolean caps, expiry and authorization order drift                            |
| Journal                  | Complete mock and live-shaped captures; explicit first/final outcomes; two-attempt recovery and three-attempt exhaustion                                 | Rehashed sequence/task/turn/ordinal/invocation/delta/refund/clock drift, repeated reservation, events after stop, unsupported resume                                   |
| Denominator / accounting | 288 synthetic tasks produce 288 outcomes, 288 reservations, 864 questions and 4,896 known input tokens; three questions charge usage once per attempt    | Saved summary overrides; reservation caps/permit minima; unknown suffix cannot disappear after recounting and rehashing                                                |
| Unknown / usage          | Unresolved reservation pauses; partial known usage retained; null observed dispatch stays unknown; usage above ceilings retained and prevents later work | False dispatch with positive/null usage; observations losing known usage, model or request identity; later work after an unknown reservation                           |
| Failure / retry          | HTTP, invalid output, refusal, model rejection and transport failures retain evidence and stop                                                           | Certificate retry, short backoff, early retry reservation, out-of-range answers, normalizer drift and completed model drift                                            |
| Clock / expiry           | Last valid reservation before deadline; terminal evidence after deadline or permit expiry retained; simulated elapsed-time jump stops work               | Unsupported clock source/capability/units/epoch shape, changed deadline, reservation at deadline, UTC/elapsed regressions and reservation before authorization         |
| Resolution               | Bound stop/adoption preflight preserves paused state and returns `applied: false`, `adoptionValidated: false`                                            | Stale journal head, wrong attempt/run/action, missing or tampered adoption evidence, old authorization and completed-attempt target                                    |
| Input / portability      | Copied stdlib reader outside repository; cached original bytes; journal above ordinary 2 MiB limit accepted below separate 16 MiB journal cap            | Duplicate/nonfinite/invalid-encoding JSON, malformed tail, artifact drift, leaf/parent symlink, FIFO, oversized files; controlled file-count/total-byte bounds         |

Coordinated mutations update the affected content-addressed artifacts, plan
digest, task/turn/attempt IDs, journal chain and derived summary where applicable.
Their rejection therefore exercises semantic record invariants beyond stale
hash detection. Hashes still prove consistency only, not authenticity.

The shared accepted-case assertions require zero authorized dispatches and zero executed
inference calls; false runtime-clock/code/provider verification and execution-ready
flags; null actual cost; missing execution capabilities and no semantic-quality
evidence. Rejections return exit 2, sanitized JSON stderr and no source text,
paths, credentials or traceback. Valid paused/failed captures remain acceptable
inputs; acceptance is not a claim that those captures completed successfully.

## Defect: allocating an intent before binding a permit

Before the correction, the new lifecycle regression failed at `new_run()`:

```text
ValueError: Mock/live permit separation
```

The UUID was allocated inside the helper but could not be returned without an
already bound live permit. The normal sequence could not be constructed through
the public helper:

1. Allocate an in-memory intent and obtain its execution UUID.
2. Prepare the permit for that UUID, exact plan and provider scope.
3. Bind the permit before validating a saved live capture.

The narrow correction permits an unbound in-memory live intent. The unchanged
replay gate still rejects a missing permit, and mock intents still reject live
permits at factory and replay. The regression verifies both the rejection before
binding and acceptance after binding; UUID generation remains fresh per call.
No schema version, cap, wire format or replay authorization rule changed.

## Local validation

- Dedicated 5a suite: 33/33 on Python 3.10.19 and 3.14.8.
- Complete stdlib offline suite: 94/94 on Python 3.14.8.
- Ruff lint/format: all 90 evaluation Python files pass.
- Syntax for the factory and three new test/support modules, Markdown formatting,
  33 relative links and whitespace checks pass.
- Byte comparison against the base: 86 of 87 pre-existing evaluation Python files
  are unchanged; the sole production delta is the intent factory. All 95 other
  tracked evaluation files, including native runners/scorers and requirements,
  are unchanged. No fixture or dependency pin change is included.

## Remaining gates

This run does not attest the current host/boot clock, actual suspension behavior,
code/dependency pins, provider normalization, writer atomicity/durability, process
locking or crash recovery. Clock jumps here are synthetic recorded readings.
File-count/total-byte boundaries use reduced test constants; ordinary/journal
file-size boundaries use the actual limits. The 288-task test is synthetic
accounting evidence, not a benchmark or provider run. Native frozen fixtures,
runners, scorers and pins are unchanged.

After review, next is **5b: durable single-writer mock execution and fault
injection** around reservation commit, dispatch, response, finalization and
backoff. Gates 5c–5e, runtime capture-revision export/registry integration and the
remaining #77 acceptance criteria stay outstanding. No live request is authorized
by passing this offline gate.
