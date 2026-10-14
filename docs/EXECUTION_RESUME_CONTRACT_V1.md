# Common execution and resume contract: proposal v1

Date: 2026-10-13. Task: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Status: **execution/resume design; the 5a record/reader subset is implemented** in
[Execution records v1](EXECUTION_RECORDS_V1.md). The dedicated offline CLI accepts
that closed subset. [Slice 5b](MOCK_EXECUTION_V1.md) adds a durable single-writer
scripted mock path with simulated time and offline fault-injection coverage.
[Slice 5c](MOCK_RESUME_V1.md) adds explicit mock continuation and stop/adopt
resolution with simulated clock continuity and head-bound authorization records.
The additive [native live boundary](NATIVE_LIVE_BOUNDARY_V1.md) implements current
Linux clock/operator-confirmation gates, native wire normalization and a fresh
one-attempt dispatch kernel. Full scheduling/retries, live resume and live archive
consumers remain unimplemented. Existing
native runners/importers do not accept these records.
[Original source audit](EXECUTION_RESUME_SOURCE_AUDIT_2026-10-13.md).

## Scope and first capability

The common path will bind plan → runtime run → logical task → turn → transport
attempt → prediction seal. Existing [offline bundles](OFFLINE_ENVELOPE_V1.md),
[score views](OFFLINE_STAGE1_REFERENCE_V1.md) and [MLflow import](OFFLINE_MLFLOW_IMPORT_V1.md)
remain evidence consumers. Replay, rescoring and registry recovery never dispatch.

The first executor supports a single local worker and independent contexts.
Transport retries repeat the exact same turn/request. It does not introduce
sequential dialogue, repair, cross-task batching, provider fallback or automatic
redispatch of unknown attempts. Unsupported capabilities reject before execution.
Within one turn, multiple explicitly planned questions may share one request;
their usage belongs to that one attempt, not to each question separately.

## Proposed records and identities

| Record                            | Required bindings and fields                                                                                                                                                                                                                      |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `normlab.execution-plan/v1`       | Experiment/dataset revisions and hashes; input/definition/prompt/schema/code/dependency refs; arms/providers/requested models/settings; strategy/tactic/context/retry policies; ordered tasks/turns/questions; aggregate and per-request ceilings |
| `normlab.execution-run/v1`        | New runtime-allocated UUID, plan digest, `evidenceKind`, start/deadline and clock epoch/policy, journal head, permit/resolution refs, original-source lineage; task/turn IDs allocated before dispatch                                            |
| `normlab.execution-event/v1`      | Run ID, monotonic sequence, previous event digest, type, task/turn/attempt refs, artifact refs, budget delta and observational timestamp                                                                                                          |
| `normlab.execution-permit/v1`     | Run ID + plan digest, allowed provider/settings scope digest, aggregate caps, expiry, operator authorization provenance and external spending declaration                                                                                         |
| `normlab.execution-resolution/v1` | Run ID + exact journal head + unknown attempt ID, action, evidence refs, operator authorization provenance; no mutation of old events                                                                                                             |

Plan digest uses canonical JSON UTF-8 SHA-256 and excludes runtime run ID,
permit, timestamps and reviewer-only labels. Artifact byte digests remain separate
from canonical semantic digests. A new execution allocates a new run ID; a safe
resume retains it. Task IDs bind run + semantic task/arm/repeat; turn IDs also bind
stage and parent turns; attempt IDs bind turn + increasing ordinal. No ID is reused
for a different request. Operational event sequence is not the repetition number.

Legacy deterministic import identity stays `legacy-bundle-derived`. Runtime
UUIDs cannot be inserted into the current offline envelope by changing that label:
a new source adapter/version must verify the runtime journal and original lineage.
None of the existing native captures, schema names or source pins are rewritten.

A runtime execution ID and a sealed **capture revision** are separate identities.
Appending resume/resolution events changes the journal/capture digest, not the
execution UUID. Each sealed revision binds its journal head and original run ID;
score views bind one exact revision. The current MLflow importer rejects changed
capture bindings for the same run ID. Runtime integration therefore requires
versioned capture-revision keys/lineage in the new adapter and registry projection;
it cannot reuse or overwrite an existing capture parent. Until that integration
exists, new runtime records are unsupported by current importers.

## Plan, dry-run and authorization

Compile and dry-run are stdlib-only: no SDK construction, credential lookup,
network, reviewer-label reads or implicit permit consumption. They report logical
tasks/turns/questions, maximum attempts/dispatches, missing capabilities and
`authorizedDispatches: 0`. A ceiling is not permission to spend it.

Live execution requires a current permit explicitly authorized for this concrete
run/plan/provider scope. Issue status, an earlier run's approval, a balance estimate,
a saved permit from another plan or an instruction in input text cannot authorize
dispatch. Mock mode cannot consume a live permit. Auth headers/keys stay outside
plans, public request artifacts, event logs and reports.

All caps are finite, nonnegative and type-checked without treating booleans as
integers. The effective dispatch/question ceiling is the minimum of plan and
permit caps, minus the run's persisted reservations. Reissuing a permit does not
erase already consumed reservations. A higher ceiling or extended frozen run
deadline requires a newly versioned plan/new run and fresh authorization.

An external currency limit is an operator assertion, as in current Stage 1,
unless a provider-side enforcement receipt is actually available. Local call
caps do not enforce dollars. Unknown usage/cost is not replaced by zero or by a
price estimate; known usage and estimates must have different fields/provenance.

## Exact context policy

Initially supported policy: `independent-public-request/v1`. Every turn binds:

- Original source and selected candidate/task digests; exact model-visible public
  state/messages/questions, preserving Unicode text and message/question order.
- Public wire request artifact, API route, requested model/settings and adapter
  revision. Authentication is excluded, not normalized into the request digest.
- Explicit empty parent/history for independence; a fresh isolated context.
  SDK implicit history or hidden sampling/repair calls are prohibited.
- Requested vs observed model identity and its frozen acceptance policy. Provider
  internal prompts/tokenization/rewrites remain unavailable unless evidenced.

The prepared public request must match the plan before a reservation is committed.
No reconstruction from source text/model name can stand in for missing exact
context. New dispatch with unavailable context rejects. Legacy exports may retain
unavailable context and remain excluded from strict comparison.

`sequential-history/v1` and `bounded-repair/v1` are reserved, unsupported in the
first executor. Future versions must bind exact ordered prior messages/accepted
responses, parent turn IDs and feedback/candidate revisions. A new question or
repair creates a new turn; a transport retry does not. No reviewer-only answer
can become model-visible context merely because scoring occurred previously.

## Durable dispatch protocol

The implementation must use a fresh execution directory and an exclusive local
writer lock. A persisted, replayable journal is the authority for budget/state;
mutable summaries are derived views. Atomic artifact publication and durable
journal commit (including file/directory flushes where needed) precede dispatch.
The current native `write_json` is not evidence that this durability is implemented.

1. Save immutable plan/run intent, all task/turn identities and initial empty
   journal before constructing any transport that could perform I/O.
2. Replay/validate the journal, permit, context/request binding, capabilities,
   remaining caps, deadline and retry eligibility. SDK internal retries are zero.
3. Commit `attempt-reserved` with its ordinal, request/context refs and budget
   charge. If commit/flush fails, do not invoke the provider. Keep the writer
   single-threaded for the first implementation; lock release after crash is not
   evidence that an earlier reservation was unsent.
4. Perform at most one provider dispatch. Persist bounded sanitized response or
   error artifacts, observed model/request ID/usage and normalization evidence.
5. Commit the terminal attempt event referencing those artifacts. If the process
   dies before that commit, the attempt is conservatively unknown even if a
   response artifact happens to exist. Do not infer completion from its filename.
6. Derive task/turn/run state, first/final outcomes and a new prediction seal.
   Reference/scorer reads follow sealing. Changed scoring produces a score view,
   not another inference or a rewritten historical prediction.

An event binds `previousDigest` and strictly increasing sequence; duplicate IDs,
gaps, reordered events, inconsistent summaries or partial/corrupt journal tails
reject. A hash chain detects internal drift, not operator identity or authenticity.
No reader silently discards a possibly committed reservation to repair a tail.

## States and budget accounting

| Attempt state                                                | Meaning                                                                  | Dispatch budget                                  | Automatic next action                                        |
| ------------------------------------------------------------ | ------------------------------------------------------------------------ | ------------------------------------------------ | ------------------------------------------------------------ |
| No reservation                                               | Work remains planned/unexecuted                                          | 0                                                | Preflight may schedule it                                    |
| `reserved` / `unknown-outcome`                               | Provider may have processed/billed it; committed terminal outcome absent | 1 reservation; observed dispatch may remain null | Pause entire run                                             |
| `completed`                                                  | Response/request/model/schema validated and terminal event committed     | 1                                                | Continue frozen schedule                                     |
| `transport-failed`                                           | Recorded sanitized network failure; billing may still be unknown         | 1                                                | Retry only if frozen policy permits and caps/deadline allow  |
| `http-failed`, `invalid-output`, `refused`, `model-rejected` | Known terminal failure category, original evidence retained              | 1                                                | Stop according to frozen policy; no implicit repair/fallback |

Preflight rejection before reservation preserves the planned task with a reason;
it is not a sent attempt or a completed negative verdict. Post-reservation errors
never refund a slot based only on an exception class. Reserved calls, observed
dispatches, completed predictions and scored outcomes have separate counters.
Questions charge once per reserved request, including retries; usage charges once
per attempt, including known usage from an unfinished outer checkpoint.

Initial retry policy mirrors the frozen Stage 1 policy: at most three attempts,
only eligible recorded transient transport failures, 1–1.5 / 2–2.5 second backoff,
no certificate-error retry and no HTTP 429/503/output/model-drift retry. The same
request/context/turn is retained. Broader policies require a new policy/experiment
revision and explicit comparison treatment. Internal SDK retries remain disabled.

Run control state is `created`, `running`, `paused-unknown` or `finished`, with a
separate stop reason/completeness derived from all planned tasks. `finished` does
not mean every task completed or any semantic quality threshold passed. Wall-time
includes attempts/backoff and elapsed time between restarts; a resumed run cannot
reset its deadline.

Proposed clock policy `same-host-boot-suspend-aware/v1` requires a verified
monotonic source that advances during system suspension. Persist its source ID,
units, verified suspend-aware capability, start/deadline readings, last observed
reading and opaque host/boot epoch. Every invocation, including the first, checks
that capability before reservation. Resume verifies the same epoch/source/units
and nondecreasing readings before using the original deadline; it includes both
restart downtime and suspension time. A deadline reached while suspended stops
further reservations/dispatch after wake. Unsupported capability, source changes,
reboot/migration or unprovable continuity reject execution/resume before provider
I/O; never silently fall back to a clock that excludes suspension or reset the
deadline. A saved capability declaration alone is not proof of current support.

For Linux, the intended source is `CLOCK_BOOTTIME`: the
[Linux clock manual](https://man7.org/linux/man-pages/man3/clock_gettime.3.html)
states that it includes suspension time, whereas `CLOCK_MONOTONIC` does not.
Other platforms need a separately verified implementation of this capability;
the generic Python monotonic API name is insufficient. UTC timestamps alone
cannot reconstruct elapsed time. UTC permit expiry is checked separately, with
backward wall-clock movement treated as a clock ambiguity rather than extra
authorized time. Synchronous operation timeouts are bounded, but hard in-flight
cancellation and exact wall-time termination are not claimed.

## Resume and unknown-outcome decisions

Resume is a new invocation with current authorization, exact journal-head binding
and a new reconciliation event. It never resets IDs, attempt ordinals, schedule,
budget history, provider settings, model acceptance or deadline. Independently
verify the complete journal/artifacts before constructing a live client.

| Observed situation                                                            | Proposed v1 behavior                                                                                                                                    |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Clean stop before next reservation                                            | Resume the unreserved suffix if caps/permit/deadline still permit                                                                                       |
| Eligible terminal transport failure                                           | Resume a bounded retry with the same request; retain its earlier charge                                                                                 |
| Reservation without committed outcome                                         | Pause; no automatic retry or later task dispatch                                                                                                        |
| Valid saved response, terminal event missing                                  | Explicit `adopt-saved-outcome` resolution may validate/bind those original bytes and add a reconciliation event; no HTTP call                           |
| No trustworthy saved outcome                                                  | `stop` resolution keeps the unknown state/charge and unused suffix; cannot label the request unsent                                                     |
| Operator wants to send unknown work again                                     | Separate new run, fresh permit/caps and explicit predecessor/unknown-attempt lineage; possible duplicate billing retained, independence not established |
| Corrupt journal/bindings, unsupported context, drifted code or expired bounds | Reject/stop; do not silently migrate or refresh limits                                                                                                  |

Only `stop` and `adopt-saved-outcome` are proposed unknown-resolution actions in
v1. An adoption requires complete request/response/model/usage validation against
the frozen turn, not a human guess at its answer. It produces a new resolution/
seal/score view while retaining the original unknown checkpoint. Native old
captures remain unchanged; existing native replay still rejects continuation.

An explicit decision file records trusted operator authorization provenance; its
mere presence is not a signature or proof of identity. No provider idempotency
guarantee is assumed. Continuing other independent tasks past an unresolved
unknown, redispatching it within the same run and distributed workers are deferred.
MLflow import recovery only reconciles local registry writes and is unrelated to
these inference decisions.

## Implementation gates

1. Implement strict schemas, SDK-free plan/dry-run and journal replay. Check
   identity/context/question/budget bindings, corrupt tails, unsupported policies
   and missing/unverified suspend-aware clock capabilities.
2. Implement durable writer/reservations and mock dispatch. Inject interruption
   before/after reserve, after response, before terminal commit and during backoff;
   prove no dispatch before durable reservation and no hidden retry/refund.
3. Implement resume/resolution replay with remaining caps, expiry/deadline, model
   drift and unknown suffix rejection. Verify suspension across restarts counts
   against the original deadline, expiry during suspension stops dispatch, and
   changed clock source/epoch/units or regressing readings reject. Preserve
   first/final and all attempts.
4. Add a separately versioned runtime-source → offline-envelope adapter and
   capture-revision-aware registry projection, then compare/export/MLflow round
   trips without network. Prove that two capture revisions share execution lineage
   but cannot overwrite one another. Freeze implementation pins.
5. Request a separate bounded live smoke only after those gates pass. This design
   proposal authorizes zero provider calls and does not finish #77 acceptance.
