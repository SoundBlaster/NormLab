# Native safe suffix resume: v1

Date: 2026-10-16 (Europe/Moscow). Ledger:
[#77](https://github.com/SoundBlaster/NormLab/issues/77).

Update 2026-10-18: [continuation consumers v3](CONTINUATION_CONSUMERS_V3.md)
connect resumed captures to portable archives, selected-question scoring and local
MLflow. The original execution/resume modules remain unchanged.

Explicit single-worker continuation preserves the original UUID, task/turn/attempt
identities, requests, model acceptance, reservations, deadline, permit and history.
Implementation and offline checks do not authorize a live experiment.

## Eligible states

| Source                                                                                 | Behavior                                                        |
| -------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Created checkpoint without reservations                                                | Continue the unreserved schedule                                |
| Interruption after a committed terminal outcome                                        | Continue the pending suffix                                     |
| Clean `operator-stop` with pending work                                                | Reopen only that stop in the derived projection                 |
| Eligible terminal transport failure with recorded backoff                              | Continue its next ordinal after the remaining original backoff  |
| Reservation without terminal commit, including saved orphan response                   | Reject; preserve the unknown and its charge                     |
| Native `stopped-with-unknown` control                                                  | Reject; stop does not permit skipping or resending unknown work |
| Terminal failure, usage violation, expired original permit/deadline or no pending task | Reject                                                          |

An old one-attempt transport failure has no recorded schedule retry/backoff
decision and is not retroactively eligible. Continuation uses the frozen schedule
policy: at most three attempts per turn, exact same request, eligible recorded
transient transport failures only, 1–1.5 / 2–2.5 second backoff. No hidden repair,
fallback, certificate-error retry or HTTP/output/model-failure retry is introduced.

## Explicit authorization and unchanged bounds

`normlab.native-resume-request/v1` binds the exact UUID, plan digest, original
checkpoint digest, current checkpoint digest and raw journal head. It contains a
fresh invocation UUID, operator assertion/expiry, non-increasing aggregate caps,
confirmation of the original currency ceiling and credential **environment names**
for every arm. Stage 1 names must match its verified frozen provider lineage.
Credential values never belong in these files or reports.

`prepare` only reads. `apply` separately requires the exact canonical request
digest confirmation. The operator assertion is not a signature or identity
attestation. Resume cannot increase the previous effective caps, discard past
charges, extend the frozen deadline or replace/renew the original permit. A new
invocation authorization can expire earlier; the original permit remains required.
Ceilings that leave no room for another reservation reject before new publication.
Later exhaustion of a narrower invocation ceiling records a conservative
`operator-stop`, retaining cumulative charges.

Current Linux `CLOCK_BOOTTIME`, original host/boot epoch, nonregressing clock/UTC,
original deadline and both authorization bounds are checked before publication
and around reservation/key lookup/transport I/O. Restart downtime and suspension
consume the original deadline. Transport timeout includes invocation expiry and
the original per-attempt ceiling. Unsupported hosts and reboot reject. A saved
capability is not current execution authority; exact in-flight cancellation is
not claimed.

## Existing claim, lock and immutable base

Resume verifies the original owner-private local claim's exact UUID, plan, permit
and canonical output path. The resolved output root itself must also be a directory
owned by the current effective user with no group/other permission bits; this is
rechecked at every current authority gate, including immediately before dispatch.
Missing, partial, permissive, symlinked or mismatched
claims reject. It never creates, deletes, renews or resets a claim. A copied/moved
directory cannot consume the original output's claim. The existing exclusive
writer lock serializes local invocations; shared reader locks block mutation.
This is local POSIX coordination, not distributed execution consensus.

Before the first continuation changes `checkpoint.json`, a normal immutable native
archive is durably published under `native-resume-base/`. It retains the exact
original checkpoint and verified source capture. A matching committed base can be
reused after interruption; incomplete/mismatched archives reject without repair or
overwrite. Writer inventory/publication bounds include both trees.

`normlab.native-resume-checkpoint/v1` retains the original raw journal prefix and
adds versioned invocation/effect events. Invocations reference their immutable
request; effects bind that invocation. The new reader checks raw hashes/order,
request/head bindings, clocks, caps, exact context, normalized response/model
history and attempt ordinals. Its derived v1 replay projection omits invocation
markers and reopens only clean operator stops; historical raw events are intact.

Invocation and reservation commit durably before key lookup/transport. Exit after
reservation leaves the attempt unknown, even with response files. Exit after
terminal commit allows a new explicit request for safe remaining work. Once an
invocation commits, its old request rejects even if nothing was dispatched.
Inspect the committed state after missing acknowledgement; nothing auto-restarts.

Original native producer modules and fixtures remain unchanged. Continuation has
separate code pins covering the complete local import closure, native producer
dependencies and archive reader/export logic. A changed dependency rejects an
existing continuation; incomplete earlier preview pin sets are not migrated or
accepted implicitly. Execution also requires original runtime/dependency pins.
Offline inspection does not attest the recorded producer runtime. Existing native
export/archive/score/import readers reject the new checkpoint. Continuation-aware
consumers and unknown-stop application to resumed captures remain subsequent work.
The original base archive remains ordinary historical evidence.

## Reports and commands

`inspect` never samples time, reads keys/claims, dispatches, writes or repairs. It
retains cumulative reservations, usage, failures, unknown billing/dispatches,
first/final outcomes, the planned denominator and invocation IDs, and reports zero
new inference and `executionReady=false`. `apply` additionally reports newly
invoked dispatches and authorized new reservations for this invocation. Its
`inferenceCallsExecuted` is null if a new terminal transport outcome has unknown
dispatch evidence. Historical uncertainty remains in cumulative counters.
CLI apply errors use null call counters because a dispatch may have happened;
exception text/credentials are never printed. No semantic quality or enforced
dollar-budget claim is made.

```bash
# Authorization/caps are operator metadata; keys.json maps arm IDs to env names.
python3 -B -S evaluation/native_resume_cli.py prepare /path/to/native-capture \
  --authorization /path/to/authorization.json \
  --expires-at '<current UTC expiry no later than original permit>' \
  --key-environments /path/to/keys.json \
  --caps /path/to/non-increasing-caps.json > /path/to/resume-request.json

# Review the request, then compute its canonical SHA-256 separately.
PYTHONPATH=evaluation python3 -B -S -c \
  'import json; from pathlib import Path; from offline_bundle import canonical, sha; print(sha(canonical(json.loads(Path("/path/to/resume-request.json").read_bytes()))))'

# Requires original supported Linux host/boot, claim, permit and current bounds.
python3 -B -S evaluation/native_resume_cli.py apply /path/to/native-capture \
  /path/to/resume-request.json --confirm-request-digest '<reviewed-digest>'

python3 -B -S evaluation/native_resume_cli.py inspect /path/to/native-capture
```

## Verification boundary and next step

`evaluation/test_offline_native_resume.py` uses synthetic native producer captures,
fake clocks/HTTP, real local claims, publication fault injection and actual child
process exits. Existing SDK-free offline CI includes it automatically. These are
process-crash checks, not arbitrary power-loss, provider availability or semantic
accuracy evidence. Local verification uses per-checkout TB5 cache/temp/log paths.
See [verification authorization](EVALUATION_VERIFICATION_AUTHORIZATION.md).

Next: continuation-aware archive/score/import consumers with exact capture-revision
bindings. Adoption requires independently committed attempt-correlated producer
receipts. Live smoke requires separate bounded authorization.

## Local verification record

| Check                                                                       | Result                                                       |
| --------------------------------------------------------------------------- | ------------------------------------------------------------ |
| Focused SDK-free resume scenarios, Python 3.14.8                            | 24 passed, 16.024 s                                          |
| Same scenarios, Python 3.10.19                                              | 24 passed, 18.051 s                                          |
| Final complete SDK-free offline suite, Python 3.14.8                        | 326 passed, 160.130 s                                        |
| Native producer source/fixtures                                             | All 22 modules and tracked fixtures unchanged from `507210a` |
| Ruff lint/format                                                            | Passed, 169 Python files                                     |
| Prettier, relative Markdown links, digest example syntax, staged whitespace | Passed; 155 relative links                                   |

Coverage includes six archive/invocation publication boundaries, four actual
child-process exits, four generic wire protocols, Stage 1 pilot/corpus denominators
of 36/288 tasks, clean restarts, narrowed cumulative caps, backoff/ordinals/retry
exhaustion, model drift, usage violations, claim/path/permission/lock/symlink
rejection, clock/UTC/expiry changes before dispatch, unknown/orphan rejection,
changed runtime pins and rehashed control/event mutations. Initial development
runs exposed an unsupported metadata-read path, a missing import and a missing
test fixture helper; these were corrected before the recorded final runs.
No provider calls, real credential lookup, production registry writes or deployment
were performed. GitHub CI/review are separate evidence tracked in the PR/ledger.

## Review follow-up — 2026-10-18

Both P2 findings in PR #135 were confirmed and corrected. Current authority gates
now require the resolved output directory itself to be owned by the effective user
and have no group/other permission bits. Regression cases reject group/world
write permissions, a simulated foreign owner and permission changes immediately
before dispatch; an existing reservation remains charged and unknown.

Continuation pins now cover 54 local modules: the native archive producer set,
archive reader/export functions and the complete statically discovered local import
closure. A regression checks closure coverage and simulates byte drift of every
pinned module, verifying changed hashes and read-only rejection of an existing
checkpoint. Original native producer files and fixtures remain unchanged.

| Check                                          | Result                |
| ---------------------------------------------- | --------------------- |
| Focused SDK-free scenarios, Python 3.14.8      | 27 passed, 18.923 s   |
| Focused SDK-free scenarios, Python 3.10.19     | 27 passed, 22.093 s   |
| Complete SDK-free offline suite, Python 3.14.8 | 329 passed, 175.941 s |

Ruff lint/format (169 Python files), Prettier, documentation links/digest example
syntax and staged whitespace checks passed. Verification used TB5 per-checkout
cache/temp/log paths; no provider requests or real credentials were used.
Current-head CI/review remain separately tracked in PR #135 and Issue #77.
