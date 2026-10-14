# Native live boundary: offline verification

Date: 2026-10-14. Task: [Issue 77](https://github.com/SoundBlaster/NormLab/issues/77).
Base: `901be94d032e68a34a47923803d8ee85ed6e7ef7`.
Contract: [native live boundary v1](NATIVE_LIVE_BOUNDARY_V1.md).

## Implemented scope

Three additive layers: current Linux clock/local operator-confirmation gate;
stdlib native HTTPS/public-wire normalizer; fresh one-attempt durable kernel/CLI.
Existing mock producers, 5a replay rules and mock-only archive/MLflow readers are
unchanged. The kernel stops after one known attempt and leaves all remaining tasks
visible; it implements no scheduler, automatic retry, native resume or fallback.

## Local evidence

- Python 3.10.19 focused SDK-free suite: **16/16 passed**.
- Python 3.14.8 full SDK-free discovery: **245/245 passed** in 139.597 s.
- Ruff 0.15.0 exact CI selection `E4,E7,E9,F,I`: passed.
- Ruff formatting: **143** Python files passed.
- No package dependencies or CI jobs added. Existing discovery includes these tests.
- All **144** pre-existing files under `evaluation/` are byte-identical to the base.

The tests use a synthetic clock and fake HTTPS factories, including explicit
socket-denying guards. The fake clock can exercise suspension/expiry/continuity
branches but does not prove the physical host's suspension behavior. No TypeSafe,
OpenAI, Mellea or MLflow SDK is needed. Offline CLI subprocess guards reject SDK
imports and network construction. No real API key is read or written.

Commands:

```bash
python3.14 -B -S -m unittest discover -s evaluation -p 'test_offline_*.py' -v
```

Focused command from `evaluation/`:

```bash
python -B -S -m unittest test_offline_live_gate test_offline_live_wire \
  test_offline_live_kernel -v
```

## Covered boundaries

- Exact current run/plan/permit/invocation/spending confirmation, positive external
  ceiling, permit time window, frozen deadline, source/epoch/units/capability and
  nondecreasing clock/UTC. Mock permits and exhausted caps reject. Mac cannot fall
  back to an ordinary monotonic clock.
- Four representative protocol replies: TypeSafe Noul/Choice/Score, OpenAI
  Decisions Predicate/Choice/Score and structured Chat/Responses answers. Malformed
  coverage, duplicate names, boolean probabilities, changed legend, truncated
  completion and adapter drift reject. Optional usage remains null.
- HTTP control flow sends one ordered planned body and does not follow 302.
  Provider errors/malformed bytes retain only digest/size; key-bearing projection
  fields are discarded and reasoning payloads omitted.
- The fake dispatch reads the already published reservation checkpoint before
  returning. Injection before reserve commit produces zero reservations/calls;
  injection after reservation, dispatch, response save or before terminal commit
  preserves a charged unknown reservation. Injection after terminal preserves
  the committed outcome. Inspection cannot dispatch/resume.
- Expiry after reservation and unavailable credential produce no transport
  construction. Changed pins/confirmation or output aliases inside inputs reject
  before publication. Existing execution directories are never reopened.
- HTTP, transport, model and output failures remain separate terminal categories;
  each triggers exactly one fake dispatch and no retry/fallback. Usage is counted
  once despite three questions. The unexecuted suffix remains in the denominator.
- Source bytes are unchanged. Saved checkpoint counter edits reject regeneration;
  successful outputs contain no fixture key. Read-only reports retain false
  execution/semantic-quality flags and no cost estimate.

## Limits and next work

These results establish offline control flow, not SDK/live interoperability,
model quality, physical suspend behavior, signed operator identity or enforced
USD spending. POSIX file/directory fsync and atomic checkpoint are not power-loss
proof. DNS/in-flight cancellation is not guaranteed to stop exactly at deadline.
The same-clock check is local kernel capability inspection, not remote attestation.

Stage 1 plan migration, scheduler/retries, native resume and live archive consumers
are pending. A live smoke needs a separately frozen plan, current authorization and
bounded spending declaration; this implementation run authorized zero inference.
GitHub CI/review is separate evidence recorded on the PRs/ledger after publication.
