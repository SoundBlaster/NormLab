# Native unknown-outcome stop: v1

Date: 2026-10-16 (Europe/Moscow). Ledger:
[#77](https://github.com/SoundBlaster/NormLab/issues/77).

Update 2026-10-18: [final stop-control consumers v4](STOP_CONTROL_CONSUMERS_V4.md)
add a separate portable archive/scorer/MLflow path for this control, preserving
unknowns and the frozen v1 execution contract.

This is the first native reconciliation slice after the
[native checkpoint/archive consumers](LIVE_RUNTIME_ARCHIVE_V2.md). It implements
an explicit local **stop** decision for a native capture paused on one unknown
attempt. It makes zero provider calls. Safe suffix resume, unknown redispatch and
saved-response adoption are not implemented by this slice.

## Why adoption is unavailable

The existing native executor durably reserves an attempt, then saves an outcome
before committing its terminal event. A crash in between leaves orphan bytes.
Those outcome records bind request/context and normalized response metadata, but
do not include an independently committed receipt tying the saved outcome to the
specific attempt. A valid response alone cannot prove that correlation when the
same request can occur across retries/repetitions. The mock adoption code has its
scripted attempt binding; that does not supply native provider evidence.

Therefore `adopt-saved-outcome` and `resume` requests reject. A future adoption
slice needs a versioned native producer with attempt-correlated receipt publication
and its own crash/replay evidence. No response is adopted by filename or by an
operator guessing the answer. Source orphan files remain unchanged.

## Request and authorization

`normlab.native-stop-request/v1` binds all of:

- Original execution UUID and plan digest.
- Exact checkpoint digest, journal head and full native capture revision.
- The original single unknown attempt; action is exactly `stop`.
- Operator assertion `{operatorId, authorizationRef, authorizedAt}` and expiry.

`prepare_stop`/CLI `prepare` only read and validate; they neither sample a clock
nor apply a decision. `apply_stop` requires an independent exact canonical request
digest confirmation. This is a trusted local operator assertion, not a signature
or proof of identity.

Application checks the current Linux `CLOCK_BOOTTIME` capability and original
host/boot epoch, nonregressing clock and UTC readings, and current stop-authorization
validity. It samples again after archival work and checks immediately before
publication. Saved clock declarations do not authorize application. Unsupported
hosts, epoch changes, clock regression and expired authorization reject.

The original inference deadline or permit may have expired: closing an unknown
does not require additional inference permission. The operation cannot extend
those bounds, create a permit, reset charges or authorize dispatch.

## Durable publication

The operation acquires the existing exclusive source writer lock. An active
writer or shared reader blocks mutation. Before changing the current checkpoint:

1. Verify the original native capture with installed trusted readers.
2. Prepare a normal immutable native runtime archive of that exact snapshot.
3. Publish it durably under `native-stop-base/`, including its normal archive
   commit marker and byte-identical `source/checkpoint.json`.
4. Save the content-addressed stop request in the original artifacts directory.
5. Recheck current clock/authorization and atomically publish the new
   `normlab.native-stop-checkpoint/v1` at the root `checkpoint.json`.

The existing fsync/file/atomic-replace primitives are reused. File, entry and total
byte bounds account for the existing source plus archived base and new decision.
No historical plan, intent, journal event, outcome or orphan is edited or deleted.
The former checkpoint remains byte-identical inside the verified base archive.
The new control checkpoint has its own derived resolution ID and code pin.

Failure before the final checkpoint replacement leaves the original unknown
checkpoint current. A fully committed matching base archive can be reused after
an interruption; an incomplete/mismatched base rejects without repair or overwrite.
After replacement, inspection can validate the decision even if the applying
process did not acknowledge completion. Reapplying the exact same request returns
`already-applied`, performs no writes and needs no fresh clock sample. A different
decision cannot overwrite the committed stop.

POSIX process-exit tests establish the observed process-crash boundaries; they do
not prove survival of arbitrary filesystem/device failure or sudden power loss.

## Read-only inspection and evidence

`inspect_stop`/CLI `inspect` verify the archived original capture, request/head
binding, recorded sample consistency and regenerated control checkpoint. They
never sample current time, look up credentials, construct transport, claim a run
or repair files. The report preserves:

- All original reservation charges and unknown usage/dispatch counts.
- The original unknown attempt, null final verdict and unexecuted suffix.
- Original deadline and task denominator, including the 288-task corpus.
- `sourceState=paused-unknown`, plus `controlState=stopped-with-unknown` and the
  separate `operatorStoppedAttemptIds` list. A stop does not clear an unknown.
- Zero newly invoked dispatch/inference, `executionReady=false`,
  `resumeSupported=false`, `adoptionSupported=false` and no semantic quality claim.

`localCaptureOnly=true`, `authorizationAttested=false` and
`recordedClockVerified=false` describe the read-only evidence boundary. Hashes
check internal consistency, not authenticity or global execution authority. Copies
of the same capture may have separate local decisions; this is not a distributed
revocation/consensus mechanism.

Original native readers/export/scorer/import entrypoints reject the new stop
checkpoint schema. They cannot ignore the decision and treat the updated root as
an unchanged native source. The `native-stop-base` archive remains an ordinary
verified immutable historical capture. A future resolution-aware consumer must
explicitly bind the decision revision; current consumers are not silently upgraded.

## CLI

All commands are SDK-free. Use the actual local native capture path; the source
must already have a valid native writer lock and paused-unknown checkpoint.
The authorization JSON is operator metadata, never an API credential.

```bash
python3 -B -S evaluation/native_stop_cli.py prepare /path/to/native-capture \
  --attempt-id '<unknown-attempt-id>' \
  --authorization /path/to/operator-authorization.json \
  --expires-at '2026-10-16T12:00:00.000000Z' > /path/to/new-stop-request.json

# Review the exact request, then compute its canonical digest:
PYTHONPATH=evaluation python3 -B -S -c \
  'import json; from pathlib import Path; from offline_bundle import canonical, sha; print(sha(canonical(json.loads(Path("/path/to/new-stop-request.json").read_bytes()))))'

# Explicit application requires the matching Linux host/boot and valid authorization.
python3 -B -S evaluation/native_stop_cli.py apply /path/to/native-capture \
  /path/to/new-stop-request.json --confirm-request-digest '<reviewed-digest>'

python3 -B -S evaluation/native_stop_cli.py inspect /path/to/native-capture
```

The date above is illustrative; application validates current validity and cannot
reuse an expired example. CLI errors expose only a category and zero-call flags.
Preparation/inspection do not require Linux clock capability.

## Verification and next slice

The offline regression file is `evaluation/test_offline_native_stop.py`; it is
included automatically in the existing CI `test_offline_*.py` step. It uses
synthetic native captures, fake clocks and fake original HTTP responses. Native
stop application/inspection deny transport, credentials and run-claim lookup.
Local build/test artifacts and supported caches use the verified TB5 checkout path.

Local verification on the implementation branch:

| Check                                                        | Result                                               |
| ------------------------------------------------------------ | ---------------------------------------------------- |
| Focused synthetic native stop cases, Python 3.14.8, SDK-free | 14 passed, 7.675 s                                   |
| Same focused cases, Python 3.10.19, SDK-free                 | 14 passed, 8.209 s                                   |
| Complete SDK-free offline regression, Python 3.14.8          | 302 passed, 173.213 s                                |
| Existing native producer source and tracked fixtures         | All 22 modules and fixtures unchanged from `2045dec` |
| Ruff lint/format, Prettier, relative Markdown links          | Passed; 164 Python files, 151 relative links         |

Coverage includes six injected publication boundaries, two actual process-exit
boundaries, repeated/competing decisions, wrong source/head/target/action, clock
epoch/UTC/expiry rejection, lock contention, symlink rejection, rehashed control
tampering, corrupt archived base, SDK-free CLI and the full 288-task corpus
denominator. The expanded fork test initially missed an `os` import; this was
corrected before the successful final focused/full runs. GitHub CI and review
remain separate evidence, tracked in the PR and ledger.

No live provider calls, paid inference, production registry writes or deployment
are part of this slice.

Next: native safe suffix resume with current head-bound authorization, preserved
deadline/caps/clock/model history and explicit local run-claim continuity. Unknown
work remains forbidden until a separately implemented reconciliation decision
supports it; stop is not permission to resend it.
