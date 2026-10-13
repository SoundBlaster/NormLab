# Execution/resume contract: source audit and implementation handoff

Date: 2026-10-13 (Europe/Moscow).
Task: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Source snapshot: `0cd4fcd2344b0233b870c7fbe0bcd65291b4f005` (#89 merge).
[Proposed contract](EXECUTION_RESUME_CONTRACT_V1.md).

## Current behavior vs proposed common runtime

| Area                    | Source-backed current behavior                                                                                                             | Required delta; not implemented here                                                                                                         |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Permit                  | [Native permit validator][permit] binds plan digest, call cap, expiry and operator-confirmed external spending                             | Common permit additionally binds runtime run ID/provider scope; no approval inherited from old runs                                          |
| Before dispatch         | [Outer checkpoint][reserve] records unfinished attempt before invoking child; provider also checkpoints `sent` before transport            | Durable common journal/atomic artifact publication, writer lock and explicit commit-failure gate                                             |
| Writer durability       | [Native JSON writer][writer] bounds bytes and replaces a temporary file                                                                    | No fsync/directory flush or general append journal is established by this helper; implement/prove durability separately                      |
| Unknown suffix          | [Retry replay][unknown] forbids attempts after pending outcome; missing child consumes one possible dispatch                               | Keep default stop; explicit stop/adopt resolution must preserve original unknown checkpoint and charge                                       |
| Known transport failure | [Retry eligibility][retry] whitelists transient classes and rejects certificate failures                                                   | Reuse that policy as a versioned baseline; broader retries are different experiment semantics                                                |
| Deadlines               | Native run uses one process-local monotonic deadline, including backoff; suspend-aware behavior is not established here                    | Require verified suspend-aware clock capability, same host/boot/source/units and original deadline; reject unsupported continuity before I/O |
| Context                 | [Stage 1 adapter][adapter] preserves native logical task/request and unavailable language; [comparison][compare] checks context/provenance | Strict new dispatch requires exact public context; sequential/repair remain unsupported until separately implemented                         |
| Identity                | [Offline contract][identity] accepts derived legacy run identity; captures and score views have distinct bindings                          | Runtime UUID + capture revision needs a new verified source adapter, not relabeling old evidence                                             |
| S1.3                    | [Compiler][s13plan] produces logical jobs; [replay][s13replay] seals predictions before reference reads                                    | Logical question batches are not transport dispatch evidence; common attempt writer is still needed                                          |
| Registry                | [Projection][projection] excludes reference/view changes from capture parent; [intent ledger][registry] rejects ID/digest conflicts        | A changed journal/capture for the same execution needs versioned capture-revision keys; current importer must keep rejecting overwrite       |

The proposal does not grant existing runners new resume capability. It does not
claim HTTP idempotency, distributed execution, durable power-loss recovery,
independent human review or a provider-enforced monetary cap. Native replay and
SDK-free import remain observational; they cannot authorize a new network call.

## Three distinctions that must survive implementation

1. **Reservation vs observed dispatch:** a pre-dispatch crash can leave one
   charged slot without proof of an HTTP call. Conservative reservations must
   stay separate from measured dispatches. The new common policy never refunds a
   post-reservation slot from exception metadata alone; this stronger invariant
   must not silently reinterpret old native zero-dispatch/preflight records.
2. **Execution vs capture revision vs score view:** resume extends a journal,
   reconciliation changes its sealed revision, rescoring only changes a view.
   Current immutable MLflow capture parents cannot represent an in-place capture
   update. New projection/adapters must explicitly retain those identities and
   compare exact revisions, preserving unknown execution independence.
3. **Import recovery vs inference resume:** #89 recovery can safely repeat local
   artifact/registry writes. That does not establish that an uncertain provider
   request can safely be repeated or that an expired permit is current.

## Ordered implementation handoff within #77

| Slice | Deliverable                                                                                     | Required evidence before progressing                                                                                                                                                                                 |
| ----- | ----------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 5a    | Strict plan/run/event/resolution schemas, capability checks and SDK-free dry-run/journal replay | Reject unsupported policies, missing suspend-aware clock capability, wrong identity/context bindings, corrupt tails, counter/ordinal drift and stale decision head; authorized dispatches remain zero                |
| 5b    | Single-writer durable mock executor, reservation accounting and exact public request capture    | Fault injection around commit/dispatch/response/finalization/backoff; no hidden SDK retry, budget refund or event loss; usage once per attempt                                                                       |
| 5c    | Bounded resume and explicit stop/adopt resolution                                               | No unknown redispatch; limits/expiry preserved; suspension counts toward original deadline; expiry during sleep and clock source/epoch/units drift or regression stop dispatch; adoption validates original evidence |
| 5d    | Runtime/capture-revision adapter and registry projection version                                | Two sealed revisions preserve one execution lineage, remain distinct and cannot overwrite raw evidence; portable replay/compare/import work without network                                                          |
| 5e    | Separately authorized live smoke                                                                | Exact plan/run/provider permit, external spending declaration, calls/deadline/stop caps; capture and usage/unknown outcomes retained                                                                                 |

This is decomposition of the existing Issue, not a second ledger or new
authorization. No live request follows from completing a schema or mock gate.
The subsequent [5a implementation](EXECUTION_RECORDS_V1.md) freezes the closed
record/reader subset. Its later [offline runtime verification](EXECUTION_RECORD_VERIFICATION_2026-10-13.md)
records dedicated positive/mutation evidence and the intent/permit ordering fix.
This dated audit records the original proposal; gates 5b–5e remain required before
claiming a working common executor or completing #77.

## Validation in this documentation slice

Source inspection and static reference/consistency checks only. No code, fixture,
dependency pin or native behavior was changed. No tests added or run, no SDK
construction, inference, resume, registry import or deployment performed here.
Prettier/whitespace, 12 commit-pinned source anchors and 32 relative links passed.
Every pinned source was byte-compared with the base commit; the changed/untracked
file inventory contains only four documentation files. Proposed schema literals
have no existing matches in `evaluation/` or `fixtures/`. GitHub CI/review are
separate and pending at publication.

The MLflow acceptance criterion in #77 was checked after #89 merged with six
successful CI checks. Other acceptance remains open. This proposal records the
remaining protocol rather than claiming it has already been implemented.

## Review correction: suspension and resumed deadlines

Addressed [P2 review](https://github.com/SoundBlaster/NormLab/pull/90#discussion_r4260073708)
on 2026-10-13. Same-boot continuity alone does not guarantee elapsed suspension
is counted: the [Linux clock manual](https://man7.org/linux/man-pages/man3/clock_gettime.3.html)
distinguishes `CLOCK_MONOTONIC` from suspend-aware `CLOCK_BOOTTIME`.
The proposal now requires `same-host-boot-suspend-aware/v1`, binds clock
source/units/capability and readings, and rejects unsupported or changed clocks
before execution/resume. Gates 5a/5c explicitly require capability rejection and
suspension/deadline evidence. This updates the proposed contract only; no native
clock, executor or platform support was implemented or tested here.

Correction checks passed: Prettier/whitespace, all 32 relative links and 12
commit-pinned source anchors/byte comparisons; the PR still changes only its four
documentation files. The preceding head `1c74e4659f0b3b636e9df2817c1f9ca23dfdcdc2`
passed all six CI checks. Fresh CI/review of this correction remains separate.

[permit]: https://github.com/SoundBlaster/NormLab/blob/0cd4fcd2344b0233b870c7fbe0bcd65291b4f005/evaluation/stage1_provider_executor.py#L44
[reserve]: https://github.com/SoundBlaster/NormLab/blob/0cd4fcd2344b0233b870c7fbe0bcd65291b4f005/evaluation/stage1_retry_executor_v2.py#L224
[writer]: https://github.com/SoundBlaster/NormLab/blob/0cd4fcd2344b0233b870c7fbe0bcd65291b4f005/evaluation/stage1_provider_plan.py#L198
[unknown]: https://github.com/SoundBlaster/NormLab/blob/0cd4fcd2344b0233b870c7fbe0bcd65291b4f005/evaluation/stage1_retry_executor_v2.py#L306
[retry]: https://github.com/SoundBlaster/NormLab/blob/0cd4fcd2344b0233b870c7fbe0bcd65291b4f005/evaluation/stage1_retry_executor_v2.py#L151
[adapter]: https://github.com/SoundBlaster/NormLab/blob/0cd4fcd2344b0233b870c7fbe0bcd65291b4f005/evaluation/offline_stage1.py#L76
[compare]: https://github.com/SoundBlaster/NormLab/blob/0cd4fcd2344b0233b870c7fbe0bcd65291b4f005/evaluation/offline_compare.py#L161
[identity]: https://github.com/SoundBlaster/NormLab/blob/0cd4fcd2344b0233b870c7fbe0bcd65291b4f005/evaluation/offline_contract.py#L192
[s13plan]: https://github.com/SoundBlaster/NormLab/blob/0cd4fcd2344b0233b870c7fbe0bcd65291b4f005/evaluation/s13_offline.py#L93
[s13replay]: https://github.com/SoundBlaster/NormLab/blob/0cd4fcd2344b0233b870c7fbe0bcd65291b4f005/evaluation/s13_offline.py#L353
[projection]: https://github.com/SoundBlaster/NormLab/blob/0cd4fcd2344b0233b870c7fbe0bcd65291b4f005/evaluation/offline_mlflow_projection.py#L84
[registry]: https://github.com/SoundBlaster/NormLab/blob/0cd4fcd2344b0233b870c7fbe0bcd65291b4f005/evaluation/mlflow_registry.py#L83
