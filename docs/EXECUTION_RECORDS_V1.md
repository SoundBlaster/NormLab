# Common execution records v1: offline slice 5a

Date: 2026-10-13. Task: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Base: `b3fab570e95d356bd6c177ebad0142ba84be4b41` (#90).

Implements the closed record/reader subset of the
[execution/resume design](EXECUTION_RESUME_CONTRACT_V1.md). These are executable
Python validators, with exact required fields and no additional fields, rather
than a dependency on a general JSON Schema engine. This read-only path has no
executor, durable writer, provider normalizer, current clock attestation or resume.
The separate [5b mock path](MOCK_EXECUTION_V1.md) adds local writer/reservation
behavior under simulated time; it grants no live execution capability.
Existing native readers/scorers/pins and offline-envelope/MLflow formats are
unchanged. Their adapters still reject these new runtime records.

## Commands and files

Python 3.10+. Commands read a local directory and print JSON to stdout:

```bash
python -B -S evaluation/execution_contract_cli.py plan /path/to/records
python -B -S evaluation/execution_contract_cli.py dry-run /path/to/records
python -B -S evaluation/execution_contract_cli.py replay /path/to/records
python -B -S evaluation/execution_contract_cli.py resolution /path/to/records
```

- `plan.json`: complete semantic plan, required by every command.
- `artifacts/<sha256>.blob`: byte-exact inputs, public request/context, output
  schema, outcomes, responses, normalized answers and optional permit/evidence.
  Each ref is exactly `{path, sha256, bytes}` and must match the saved bytes.
- `run.json`: immutable bindings plus a derived view checked against journal.
- `journal.json`: a complete JSON array of ordered events; no truncated-tail repair.
- `resolution.json`: read only by `resolution`, after full replay.

`plan` and `dry-run` are aliases. Neither allocates/persists a runtime ID nor reads
run/permit/resolution files. The Python helper `new_run()` allocates separate UUID4
execution/invocation IDs in memory for a previously prepared plan. It accepts a
clock declaration; it does not read or attest a clock or persist an intent.
For live intents, allocate the UUID with `permit=None`, then bind a permit to that
exact execution UUID and plan before replay. An unbound in-memory intent grants
no authority; saved live-capture replay rejects a missing permit. Mock intents
reject a live permit at both factory and replay boundaries.

Every result has `authorizedDispatches: 0` and `inferenceCallsExecuted: 0`.
`missingCapabilities` includes durable writer, dispatcher, clock attestation,
provider wire normalization and resume/resolution application. Clock/code/provider
verification flags remain false; semantic quality evidence is false and actual
cost is null. Exit 0 means accepted structural consistency, including a valid
paused/failed capture; exit 2 means rejection. It never means permission to execute.

There is no SDK import, environment/Keychain lookup, HTTP client, subprocess,
artifact write, reference-label reader or apply/resume command on this path.
Error output contains only the exception class and zero-call boundary, without
source text, paths, credentials or response bodies.

## Frozen fields

All names below are required, including nullable fields. Object key order is
irrelevant except where exact artifact bytes or wire question order are bound.
Arrays retain order. JSON must be UTF-8 with unique keys, finite numbers and valid
Unicode. Counts are actual integers, never booleans, in `[0, 2^63-1]` unless a
positive minimum is specified. Times are integer nanoseconds; UTC is exactly
`YYYY-MM-DDTHH:MM:SS.ffffffZ`. Digests are lowercase SHA-256 hex.

| Record                               | Exact fields                                                                                                                                          |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `normlab.execution-plan/v1`          | `schema experiment dataset strategy tactic pins arms tasks caps wallTimeNs contextPolicy retryPolicy clockPolicy`                                     |
| `normlab.execution-run/v1`           | `schema id initialInvocationId identityKind evidenceKind planDigest clock tasks permit predecessor journalHead lastClockNs state stopReason counts`   |
| `normlab.execution-event/v1`         | `schema id runId invocationId sequence previousDigest type taskId turnId attemptId ordinal clockNs observedAt request budgetDelta outcome stopReason` |
| `normlab.execution-permit/v1`        | `schema runId planDigest scopeDigest caps expiresAt authorization externalSpending`                                                                   |
| `normlab.execution-resolution/v1`    | `schema runId planDigest journalHead attemptId action evidence authorization`                                                                         |
| `normlab.execution-outcome/v1`       | `schema status requestDigest contextDigest model providerRequestId dispatchObserved usage response result errorClasses backoffNs statusCode`          |
| `normlab.execution-answer-schema/v1` | `schema questions`                                                                                                                                    |
| `normlab.execution-answers/v1`       | `schema normalizer answers`                                                                                                                           |

### Plan and request binding

- Revision objects: `{id, revision, sha256}` for experiment/dataset/strategy/tactic
  and each arm's adapter. These are pinned declarations, not proof of provenance.
- `pins`: `{definitions, prompt, outputSchema, code, dependencies}`. First three
  are artifact refs verified by bytes. Code/dependency maps contain nonempty
  name → digest entries; actual installed/executing revisions are not attested.
- Arm: `{id, provider, protocol, endpoint, model, acceptedModels, settings,
adapter, requestCaps, timeoutNs}`. Arm IDs and model labels are unique.
  Settings: `{temperature, reasoningEffort, maxOutputTokens}`; temperature is null
  or 0–2, effort is null/none/low/medium/high, output ceiling is positive.
- Supported public wire subsets: `typesafe-systemone/v1`, `openai-decisions/v1`,
  `openai-chat-completions/v1`, `openai-responses/v1`. Endpoints are configurable
  public HTTPS URLs without query/fragment/user credentials. This does not verify
  gateway availability, model support or provider protocol compatibility.
- Task: `{key, caseId, armId, repeat, stage, source, candidate, request, context,
questionIds}`. Source/candidate/request/context are byte refs. Semantic
  case/arm/repeat/stage coordinates and task keys are unique; task order is schedule.
- Request artifact: `{method, url, headers, body}`. POST, exact arm endpoint,
  only `Content-Type: application/json`, model and supported sampling/token fields
  exactly match the arm. Unplanned wire fields reject. Decision APIs bind ordered
  question keys/types; Chat binds saved messages, Responses binds saved input.
  Authentication-shaped structured fields reject; prose is never rewritten or
  guaranteed secret-free. Provider-specific prompt/result transformation remains
  unverified until a separately implemented normalizer/transport gate.
- Independent context artifact: `{policy, sourceDigest, candidateDigest,
requestDigest, questionIds, parentTurnIds, history}`. Digests/order must equal
  task refs; parents/history are empty. The exact request bytes are retained.
  This is declared source/request lineage, not proof that a provider saw it or
  that arbitrary prose correctly expresses the selected source/candidate.
- `contextPolicy = independent-public-request/v1`,
  `retryPolicy = stage1-transient-transport/v1`,
  `clockPolicy = same-host-boot-suspend-aware/v1`; other policies reject.

Every `caps`, `requestCaps` and `budgetDelta` object has exactly
`{dispatches, questions, inputTokens, outputTokens}`. Plan/permit caps are aggregate;
request caps bind one dispatch, maximum questions and token ceilings. A reservation
charges 1 dispatch, the turn's actual question count and both token ceilings,
without later refund. This conservative token reservation policy is new common
runtime policy; it must not reinterpret historical native token totals. Decision
APIs have no output-token wire setting in this subset: that ceiling is a local
declaration checked against saved known usage, not provider-side enforcement.

Dry-run reports logical task/turn/question counts, three maximum attempts per
turn and separate cap-limited upper bounds. These independent upper bounds are
not a promise that the full schedule is executable within every cap/deadline.

### Identity, run view and clock

Plan digest = canonical UTF-8 JSON SHA-256, excluding runtime/authorization/view
fields because they are not in the plan schema. Artifact hashes use original bytes.
Task ID = `identity("task", [runId, task])`; turn ID =
`identity("turn", [taskId, stage, []])`; attempt ID =
`identity("attempt", [turnId, ordinal])`. `identity` is the existing kind-prefixed
canonical SHA-256 helper. Run tasks contain exactly `{key, taskId, turnId}`.

Run identity is `runtime-allocated`; evidence is `mock` or `live-capture`, both
saved declarations. Predecessor is null or `{runId, unknownAttemptId, captureDigest}`
with a different execution UUID; external lineage/authenticity is not attested.
Permit is null for mock, an artifact ref for live-capture. Journal head starts null.

Clock: `{policy, source, units, suspendAware, epoch, startNs, deadlineNs}`.
Accepted source declaration is currently `linux:CLOCK_BOOTTIME`, units are
nanoseconds, suspendAware must be true, epoch is an opaque host/boot digest and
`deadlineNs = startNs + wallTimeNs`. Other source declarations or missing
capability reject. This whitelist does not attest current Linux/VM/host support;
runtime verification, same-boot checks after restart and simulated suspension
checks belong to later gates. This reader works on macOS without claiming a
macOS execution clock implementation.

Run counts: `{reserved, observedDispatches, knownInputTokens, knownOutputTokens,
unknownUsageAttempts}`. The reader recomputes them, state, stop reason, journal
head and last clock reading; saved summaries cannot override the journal.
`reserved` is a caps-shaped object. Replay additionally reports unknown dispatch
attempts, original unknown attempt IDs and first/final outcomes per planned task.
Unstarted/unknown predictions remain null; known usage sums retain a separate
unknown-attempt count. Multi-question requests charge usage once per attempt.

### Journal transitions

Event ID = canonical SHA-256 of the complete event excluding `id`;
`previousDigest` references the preceding event ID. Sequence starts at 1 with no
gaps. Every event binds execution and the initial invocation UUID; other
invocations/reconciliation events are unsupported in 5a. No events follow a stop.
Hash chains establish consistency, not signatures, execution or authorship.

- `attempt-reserved`: exact next task/turn/request/ordinal, null outcome/reason,
  exact positive reservation charge within effective plan/permit caps. Deadline
  and saved permit UTC validity are checked at this reservation.
- `attempt-observed`: requires the active reservation; zero budget delta;
  unknown-outcome artifact may retain partial usage/response/identity. It cannot
  complete the attempt or permit later work.
- `attempt-terminal`: requires that reservation; zero delta; an outcome is
  completed/transport-failed/http-failed/invalid-output/refused/model-rejected.
  Previously known usage/response/request identity cannot disappear or regress.
- `run-stopped`: null task/turn/attempt/ordinal/request/outcome, zero delta.
  Reasons: operator-stop/deadline/budget-exhaustion/terminal-failure/complete/
  unknown-outcome/usage-ceiling-exceeded, with corresponding evidence checks. An unresolved reservation
  permits only unknown-outcome stop. Completion requires the whole denominator.

A reservation without a terminal event at EOF → paused-unknown (or explicit finished/unknown
stop), retaining reservation and nullable observed dispatch. A second reservation
before a terminal event rejects. Resume/application of a resolution is unsupported;
a valid preflight never changes this rule or any prior journal bytes.

Transport retries retain request/context/turn, use ordinals 1–3 and only the
frozen transient-class whitelist. Certificate failures and all other statuses
cannot retry. Next reservation must follow saved bounded backoff (1–1.5 / 2–2.5 s).
Completed model identity stays stable per arm; drift requires model-rejected.
Wall-clock/elapsed regressions reject. Terminal evidence can arrive after expiry
or deadline; no later reservation may ignore either bound. Hard in-flight
cancellation and exact wall-time termination are not claimed.

### Outcomes, permits and resolution preflight

Outcome `dispatchObserved` is bool/null; usage is `{inputTokens, outputTokens}`
with nullable nonnegative integers. Known usage above a declared request ceiling
is retained, marks `usageCeilingExceeded` and forbids later reservations; it cannot
claim a normal complete stop. `dispatchObserved: false` requires explicitly zero
input/output usage; null or positive usage requires true/null dispatch evidence.
The reader rejects inconsistent records instead of rewriting their usage. Mock
outcomes explicitly contain false observed provider dispatch and zero provider
usage. Response/result are nullable artifact refs, errors a bounded sanitized
class list, backoff nullable nanoseconds and HTTP failure status 400–599 or null.
Completed outcomes require a response, accepted/stable model and normalized result;
live completion also requires an observed dispatch declaration.

Answer-schema questions are `{id, type, labels}` with unique IDs. Noul labels
are empty; choice/score labels contain at least two unique strings. Normalized
answers contain `{questionId, type, value}` in the planned order. Noul is in [0,1],
choice selects a label, score is in [0, numberOfLabels−1]. Result normalizer revision
must match the arm's adapter. No claim of native raw-response/normalization parity,
calibration, independent labels or semantic correctness follows from this check.

Permit scope hashes the entire ordered arm array. Effective caps are plan/permit
minima; all previous reservations stay charged. Authorization is
`{operatorId, authorizationRef, authorizedAt}` with a digest of trusted external
authorization provenance, not a signature. External spending is
`{currency: "USD", ceilingMicros, confirmationRef, provenance: "operator-asserted"}`;
local caps do not enforce a currency limit. Saved permit validity is checked at
captured reservations, not against today's clock or as current execution approval.

Resolution binds exact execution/plan/journal head and an original unknown attempt.
Authorization must not predate that head's UTC observation. Actions are `stop`
(empty evidence list) or `adopt-saved-outcome` (one hash-verified evidence ref).
The result always says `applied: false`, `adoptionValidated: false`, required gate
5c, and zero authorized dispatches. Adoption requires future full response/model/
usage normalization against the frozen turn; byte presence alone is insufficient.
New authorization cannot reset caps or extend the plan's frozen deadline.

## Bounds, validation and next gate

At most 1024 arms/tasks/questions per list, 8192 events, 4096 read files, 2 MiB per
ordinary file/artifact, 16 MiB journal and 64 MiB total read bytes. Public request
nesting is capped at 32. The reader caches original bytes, requires regular files,
rejects leaf/parent symlinks and uses bounded nonblocking reads. This does not
implement an atomic writer snapshot or protect against an adversary mutating
parent directories while reading. Writer locking/commit/flush evidence is gate 5b.

Initial implementation validation was static: syntax, import closure,
record-field consistency, Ruff, Markdown links/format, whitespace and
unchanged-native-source comparison. Dedicated tests were added in the subsequent
[offline runtime verification](EXECUTION_RECORD_VERIFICATION_2026-10-13.md).
They run CLI positives and rehashed mutations with network/process/provider SDK
and file-write guards, and are discovered by the existing Stage 1 CI offline step.
Local runtime results and fresh GitHub CI are separate evidence.

Static checks passed for all six new modules; all 81 existing evaluation Python
files remain byte-identical to the base. The transient retry whitelist and
three-attempt ceiling match the frozen baseline. Ruff lint/format passed for all
87 evaluation Python files. Documentation field tables match the validators.
No fixture, dependency, code pin or existing native contract changed.

The verification found and corrected the intent allocation/permit ordering bug;
the live replay permit requirement remains enforced. The subsequent
[5b implementation](MOCK_EXECUTION_V1.md) and its
[fault-injection report](MOCK_EXECUTION_VERIFICATION_2026-10-13.md) cover durable
single-writer mock checkpoints. Review of that slice and gates
5c–5e and the rest of #77 acceptance remain outstanding. Any later incompatible
record/policy change needs an explicit version/migration boundary.
