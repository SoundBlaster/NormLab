# Slice 5c: mock continuation verification

Date: 2026-10-14 (Europe/Moscow). Task:
[#77](https://github.com/SoundBlaster/NormLab/issues/77).
Base: `7843936f44ad794860edcbea928a5199bf42fe30` (#93).
Contract: [mock continuation v1](MOCK_RESUME_V1.md).

## Local checks

| Check                                          | Result                                                                                                        |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Dedicated 5c suite, Python 3.14.8 / macOS      | 20/20 methods with fault/mutation subtests, 2.764s                                                            |
| Dedicated 5c suite, Python 3.10.19 / macOS     | 20/20, 2.813s                                                                                                 |
| Complete SDK-free offline suite, Python 3.14.8 | 135/135 in 125.651s                                                                                           |
| Ruff lint/format                               | All 99 Python files pass                                                                                      |
| AST / source preservation / Markdown           | Seven modules parsed; 101/103 existing evaluation files unchanged; 44 relative links resolve; Prettier passes |
| GitHub CI and independent PR review            | Separate gates; pending publication                                                                           |
| Inference / provider requests / deployment     | None                                                                                                          |

Reproduction from repository root:

```bash
python -B -S -m unittest discover -s evaluation -p test_offline_mock_resume.py -v
python -B -S -m unittest discover -s evaluation -p 'test_offline_*.py' -v
ruff check --select E4,E7,E9,F,I evaluation
ruff format --check evaluation
```

## Observed behavior

- Created execution and an interrupted completed prefix continue only unstarted
  work. Original v1 snapshot bytes and event prefix survive unchanged; execution
  identity, completed outcomes and charges retain their prior values. Each
  continuation has a new invocation UUID and a durable head-bound request.
- Retry continues at ordinal 2 with the same exact request bytes and a new
  derived attempt ID. Tests observe only the remaining 1-second backoff, including
  when simulated downtime already exceeds it. Neither ordinal 1 nor completed
  tasks are dispatched again.
- Authorization expiry during backoff stops with no new mock call. A new request
  can resume the clean stop within the original deadline. Crossing the original
  deadline after the invocation marker stops without dispatch.
- Reducing lifetime dispatch caps to 1, interrupting after completion and opening
  another invocation never resets that reservation. Raising the cap rejects;
  retaining it produces a verified `budget-exhaustion` stop. Old requests reject
  after their head changes.
- Unknown reservations block resume. Explicit stop retains the unknown attempt,
  all accounting and its resolution history, and finishes without a mock call.
  The resulting unknown stop cannot be reopened by resume.
- Explicit response-backed adoption commits the original attempt without a new
  reservation/call. An unstarted suffix remains unstarted until a separately
  requested continuation; adoption of the last completed task can finalize.
- Stop/adoption authorization is rechecked at its applying event. Expiry after
  the invocation marker leaves an unapplied control record and the original
  unknown reservation. Fresh authorization can later resolve it.
- Caller mutation after reservation cannot extend the copied request's expiry;
  a now-expired reservation stays unknown with zero new calls.

## Faults, mutations and filesystem checks

- Thirteen migration/authorization/invocation/reservation/response/terminal/stop
  fault points include before/after atomic replacement. Inspection sees the old
  or fully published new authority. Reservations remain unknown across uncertain
  outcomes; orphan artifacts never cause automatic adoption.
- Four adoption fault points cover before application, terminal file flush,
  terminal replacement and after adoption. Before replacement the attempt stays
  unknown; after replacement completion is retained and finalization needs no
  repeat dispatch.
- Four independent subprocess `os._exit(86)` scenarios cover reservation flush,
  reservation publication, saved response and committed terminal. An independently
  flushed mock-call trace distinguishes calls from committed outcomes. Unknown
  attempts are never resent.
- An independent process holds the exclusive writer lock after its invocation
  commit. Both a reader and another writer reject until release; the child then
  completes. The CLI inspect path runs with writes denied by the existing test
  helper. CLI apply and hard-exit children deny sockets, subprocess creation and
  provider SDK imports using the active guard covered by the original 5b suite.
- Rejected request changes cover execution/plan/checkpoint/head, action,
  elapsed/UTC/expiry, every original clock field and cap growth. Invalid requests
  leave the captured directory bytes unchanged and invoke no mock transport.
- Rehashed event mutations cover invocation IDs, clock regression, retry ordinal,
  reservation charges, misplaced control evidence and fabricated budget/expiry
  stops. Rehashed control-artifact cap growth is also rejected.
- Rehashed outcome changes cover model, provider request ID, request/context
  digests, synthetic usage and absent response/result. Coordinately rehashed
  nested response attempt IDs and result normalizers reject against the frozen
  codec. A modified result at its old content address also rejects. These are
  consistency checks on unsigned evidence, not source/writer authentication.
- Symlink, FIFO and oversized retained inventory entries reject before checkpoint
  mutation. Original 5b and strict 5a tests remain in the complete offline suite.

## Implementation and evidence boundaries

Five new Python files separate shared mock normalization/event construction,
versioned read/replay, explicit continuation writer, CLI and regression checks.
Two existing 5b modules share the codec/schedule and bounded replay cache; their
v1 behavior remains covered by the existing tests. No native runner/scorer,
provider dependency, frozen fixture or strict 5a schema/replay implementation is
changed. The existing Stage 1 CI discovery command includes the new module.

Every accepted v2 report keeps zero inference calls/authorized provider dispatches,
false live-readiness/host-clock/code/provider/semantic-quality flags and null
actual cost. Clock continuity is checked **only for supplied simulated clock
observations**. Operator authorization data are not attested. Process-crash and
barrier ordering evidence does not establish physical power-loss durability,
hostile/remote filesystem safety or semantic/model quality.

Next after review: **5d runtime export/registry integration with capture revision
identity**. Real host clock/epoch, current authorization attestation, provider
normalization/transport and separately authorized live smoke remain later gates.
The broader #77 task remains open with its full acceptance incomplete.
