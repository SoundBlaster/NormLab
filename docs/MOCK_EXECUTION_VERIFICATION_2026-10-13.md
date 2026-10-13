# Slice 5b: mock execution verification

Date: 2026-10-13. Task: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Base: `ce88fd0472bd9f0718cf8c11cd96001883970e87` (#92).
Contract: [durable mock execution v1](MOCK_EXECUTION_V1.md).

## Local results

| Check                                          | Result                                               |
| ---------------------------------------------- | ---------------------------------------------------- |
| Dedicated 5b suite, Python 3.14.8 / macOS      | 19/19 methods with mutation/fault subtests           |
| Dedicated 5b suite, Python 3.10.19 / macOS     | 19/19 in 2.263s                                      |
| Complete SDK-free offline suite, Python 3.14.8 | 113/113 in 133.665s; includes all 94 previous checks |

```bash
python -B -S -m unittest discover -s evaluation -p test_offline_mock_execution.py -v
python -B -S -m unittest discover -s evaluation -p 'test_offline_*.py' -v
```

[Test module](../evaluation/test_offline_mock_execution.py) uses independently
constructed 5a synthetic input fixtures. CLI execution and hard-exit subprocesses
deny network, child-process and provider SDK use through active audit hooks;
positive controls trigger each guard. Inspection additionally runs under the
5a write/label-read guards and compares file hashes before/after. Tests of local
file/lock behavior intentionally allow the writer's filesystem operations.

These are Python regression guards, not an OS sandbox against arbitrary native
code. Synthetic answers are prescribed test data, not model quality evidence.
No real provider calls, credentials, paid inference, real MLflow SDK import or
deployment occurred.

## Fault and barrier evidence

| Scenario group                                | Evidence                                                                                                                                                                                                                                                                                            |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Eight reservation interruption points         | Before reservation, before write/flush, after file flush, after replace/directory flush, after reservation and before dispatch. Actual mock call count stays zero. Before atomic replace the old empty checkpoint survives; afterward the charged unknown checkpoint is visible.                    |
| Fifteen response/terminal/finalization points | After mock call, during response/result/outcome publication, before/after terminal commit and before/after final stop publication. Charge remains one; uncommitted outcome artifacts do not produce a completed prediction.                                                                         |
| Six hard process exits                        | `os._exit(86)` bypasses Python cleanup after reservation-temp flush, reservation, dispatch, response, terminal or during backoff. An independently flushed test trace distinguishes actual mock calls from journal reservations. New execution in the same directory rejects; inspection is stable. |
| Actual storage errors                         | Injected `OSError` from `os.fsync` before reservation-file durability and after checkpoint replace/before directory durability. Both produce zero mock calls. A writer with a failed publication is unusable.                                                                                       |
| Barrier ordering                              | A checked mock dispatch observes the already committed reservation. File flush precedes replace, directory flush precedes dispatch, initial checkpoint precedes internal transport-construction phase.                                                                                              |
| Actual independent process                    | A child holds the writer lock at pre-dispatch. Inspection from another process rejects with `BlockingIOError`; a second writer cannot reopen the existing output. Releasing the child permits exactly one mock attempt and a valid complete checkpoint.                                             |

Hard-exit evidence tests process failure, not a physical power cut. Atomic replace
is a visibility point; a failure before directory flush can leave the complete
new checkpoint visible without a successful durability acknowledgement. No
subsequent dispatch occurs in that failed writer. Power-loss behavior, filesystem/
controller durability, remote filesystems and hostile directory mutation remain
unverified.

## Functional coverage

- All four public wire subsets complete with exact original request bytes. Source
  mutation after copying cannot change the bytes used by mock transport.
- Noul/Choice/Score answer order, types and values match the pinned schema. Model
  identity drift becomes explicit `model-rejected`; response evidence remains.
- Transient failure then completion uses two distinct attempt IDs and byte-identical
  requests; three failures exhaust the frozen ceiling. Certificate, HTTP, invalid
  output, refusal and model failures stop; unknown outcome preserves the suffix.
- Each of dispatch/question/input-token/output-token caps is tested at zero and
  exactly one reservation. Unstarted task denominator remains complete. Synthetic
  usage is zero and never refunds conservative token reservations.
- Simulated deadline during backoff forbids the next attempt; deadline after
  reservation but before dispatch retains a charge with zero mock calls.
- Invalid script/answers/latency/retry path or non-built-in transport reject before
  output creation. Existing directory cannot be overwritten or implicitly resumed.
- Changed view, intent/script bytes, missing journal suffix, malformed checkpoint
  and checkpoint symlink reject. FIFO/symlink script inputs reject without blocking.
  Reduced file-count/total-byte writer limits reject before publishing extra data.
- Accepted reports retain zero authorized/executed inference calls, false live
  readiness/clock/code/provider verification, null actual cost and no semantic
  quality evidence. The mock clock and unsupported resume are explicit.

## Scope and next step

5b adds three stdlib production modules and one test module. The 5a reader/replay,
all native runners/scorers, dependency pins, historical fixtures, offline-envelope
and MLflow contracts remain unchanged. The existing Stage 1 CI discovery includes
these tests; fresh GitHub CI/review are separate and recorded on the PR.

Static validation passed: Ruff lint/format all 94 evaluation Python files, syntax
for four new modules, Prettier, 43 relative links and whitespace. Byte comparisons
against the base confirm all 99 pre-existing evaluation files (90 Python files)
are unchanged.

This establishes the local mock writer and conservative process-interruption
behavior. It does not implement current host/boot clock attestation, live
authorization/transport, provider normalization, resume/adoption, prediction-seal
export or runtime/capture-revision registry integration. #77 remains OPEN.

Next after review: **5c bounded resume and explicit stop/adopt resolution**, with
clock/authorization verification, remaining caps and original deadline preserved.

## Review correction: preflight model-rejection evidence

Addressed [P2](https://github.com/SoundBlaster/NormLab/pull/93#discussion_r4263701538).
An accepted model without prior same-arm drift cannot be explicitly labelled
`model-rejected`. Previously that inconsistency failed only during terminal
replay, after output creation/reservation/mock dispatch. The regression reproduced
four unexpected output directories before the correction.

Preflight now shares the runtime model-rejection predicate and tracks only
reachable completed models per arm. Five negative cases (first attempt, unchanged
model, transport-only history, another arm and an unreachable suffix) reject with
no output directory or mock calls. Explicit accepted-model drift remains valid;
the existing unaccepted-model and automatic completed-response drift cases pass.
Dedicated suite: 21/21 on Python 3.14.8 (3.711s) and 3.10.19 (2.467s).
Complete SDK-free offline suite: 115/115 on Python 3.14.8 in 136.716s. Ruff
lint/format all 94 Python files, syntax for both changed modules, Markdown
formatting, six relative links and whitespace pass. These extend the original
results above; fresh GitHub CI/review remain separate.
