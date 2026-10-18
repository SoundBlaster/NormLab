# Stop an unknown attempt after native resume

Date: 2026-10-18 (Europe/Moscow). Ledger:
[#77](https://github.com/SoundBlaster/NormLab/issues/77).

Update 2026-10-18: [final stop-control consumers v4](STOP_CONTROL_CONSUMERS_V4.md)
provide a separate portable archive/scorer/MLflow path. This document retains
the local v1 control contract; frozen generic v1/v2/v3 consumers remain closed.

This additive control closes a resumed execution with exactly one reserved attempt
without a committed terminal outcome. It does **not** learn that outcome, release
its charge, adopt an orphan response or permit another dispatch. The original 57
[continuation v3 producer files](CONTINUATION_CONSUMERS_V3.md) remain unchanged.
Separate modules, CLI and schemas preserve closed existing readers.

## Request and application

`normlab.resumed-stop-request/v1` binds the exact original run UUID/plan, current
resumed checkpoint digest, capture revision, raw journal head and single unknown
attempt ID. Only `stop` is supported. The operator supplies a fresh explicit
assertion and expiry; `apply` separately confirms the canonical request SHA-256.
An assertion is not authenticated operator identity or a signature.

`prepare` is read-only and obtains no clock, claim, key or transport. `apply`
requires an existing owner-private output directory and exclusive writer lock.
It reuses the original unknown-stop policy for exact binding, authorization,
same host/boot/source clock capability and nonregressing clock/UTC. The current
stop assertion must still be unexpired. Closing an unknown after the original
inference deadline is allowed: it does not renew that deadline, permit, caps or
inference authority. Time/expiry and root permissions are checked again before
publication.

Fresh-native, mock and clean/finished resumed sources reject. The exact already
committed request repeats idempotently without obtaining current clock or
inference authority; another decision cannot replace it. [Safe resume](NATIVE_SAFE_RESUME_V1.md)
rejects both the unknown source and new stop checkpoint.

## Immutable history and durable decision

Before replacing `checkpoint.json`, publish a complete immutable package under
`native-resumed-stop-base/`. Its `capture/` is an unchanged strict
`normlab.runtime-archive/v3`, retaining the raw resumed checkpoint, every
invocation/attempt and embedded original base. Its `artifacts/` separately copies
all content-addressed root artifact blobs absent from that capture. A closed
`normlab.resumed-stop-evidence/v1` manifest in `evidence.json` binds their exact
paths, lengths, hashes, original capture/head and producer pins. These bytes are
explicitly `unattributed-uncommitted-artifacts`, `adopted=false`: no attempt or
provider provenance is inferred from orphan content. Unpublished `.pending-*`
writer temporaries are excluded; the whole source inventory still bounds them.
The confirmed stop-request artifact is separately bound by the final control.
Root source bytes are preserved and archived orphan bytes remain unadopted. Reservations,
cumulative charges, first/final outcomes, unknown usage and planned task denominator
retain their original values.

The writer bounds the combined source, nested archive, request and control
inventory before publication. Matching complete bases can be reused; partial or
mismatched directories reject without overwrite or repair. Regular-file/symlink
checks and the existing local POSIX lock serialize writers. The request commits
before the control frame. The final checkpoint is atomically replaced and its
directory flushed. Interruption before commit leaves the original unknown
checkpoint; interruption after replacement leaves a verifiable stop decision.
Process-exit checks do not establish arbitrary power-loss safety.
The outer package marker commits only after the strict capture and orphan bytes
are flushed. A complete inner capture without this outer marker is not reusable.

`normlab.resumed-stop-checkpoint/v1` binds the request, original capture/head,
immutable base archive ID and pre-stop evidence ID, observed clock sample and all 59 producer pins: frozen
57 plus the two new control/CLI modules. Its resolution ID hashes those fields.
Read-only `inspect` verifies the v3 archive, original and archived orphan inventories/bytes, root source bytes, request, recorded
sample and regenerated frame. It retains `unknownAttemptIds` and
`unknownDispatchAttempts`, reporting `controlState=stopped-with-unknown`, zero new
dispatch/inference and no resume/adoption/execution capability. A copied tree can
be inspected after deletion of its original path; saved fields grant no execution
authority there. Unsigned hashes/pins establish consistency, not producer, clock
or operator authenticity.
`native_resumed_stop.read_base(path)` verifies the standalone package and returns
its strict capture, evidence manifest and orphan bytes, even after deletion of
the original run. Retaining only its inner `capture/` intentionally loses this
extra uncommitted evidence; retain the entire pre-stop package instead.

## CLI

```bash
# Read-only proposal; authorization.json is an operator assertion, not a key.
python3 -B -S evaluation/native_resumed_stop_cli.py prepare /path/to/resumed-run \
  --attempt-id '<exact unknown attempt ID>' \
  --authorization /path/to/authorization.json \
  --expires-at '<current UTC stop authorization expiry>' > /path/to/stop-request.json

# Review the request and calculate its canonical SHA-256 separately.
PYTHONPATH=evaluation python3 -B -S -c \
  'import json; from pathlib import Path; from offline_bundle import canonical, sha; print(sha(canonical(json.loads(Path("/path/to/stop-request.json").read_bytes()))))'

# Requires the supported original Linux host/boot and current stop assertion.
python3 -B -S evaluation/native_resumed_stop_cli.py apply /path/to/resumed-run \
  /path/to/stop-request.json --confirm-request-digest '<reviewed-digest>'

# Historical read-only inspection: no current authority/clock/key lookup.
python3 -B -S evaluation/native_resumed_stop_cli.py inspect /path/to/resumed-run
```

## Verification boundary and next step

Focused/full SDK-free regression uses synthetic captures and fake HTTP/clocks,
network/key/claim guards, full 288-task histories, active locks,
expiry/epoch/regression checks, partial/competing/rehashed decisions, publication
faults and actual local process exits. Verification authorization is
[recorded separately](EVALUATION_VERIFICATION_AUTHORIZATION.md). Results are
recorded below after execution, with CI/review separately in the PR/ledger.

Local results on 2026-10-18:

| Check                                           | Result                                          |
| ----------------------------------------------- | ----------------------------------------------- |
| Focused resumed-stop, Python 3.14.8             | 12/12; 20.242 s                                 |
| Focused resumed-stop, Python 3.10.19            | 12/12; 21.665 s                                 |
| Full SDK-free offline regression, Python 3.14.8 | 355/355; 200.943 s                              |
| Ruff lint/format                                | 177 Python files pass                           |
| Original v3 producers                           | All 57 files byte-identical to base `86efe1c`   |
| New producer closure                            | 59 pinned files cover local control/CLI imports |
| Prettier, links, digest example, whitespace     | Pass; 152 relative Markdown links               |

Tests include six publication fault boundaries, two actual child process exits,
all 59 producer-pin drift cases, source deletion/copy inspection, clock and
permission rechecks, and the full corpus denominator. Cache/temp/log output uses
the verified per-checkout TB5 paths. No provider calls or real credentials.

### Review follow-up — 2026-10-18

P2 [4306185149](https://github.com/SoundBlaster/NormLab/pull/142#discussion_r4306185149)
identified that strict v3 captures omit unreferenced response/outcome blobs.
The pre-stop package now retains those bytes separately, binds them by an outer
evidence manifest/ID and verifies both the source and archived inventories. A
base-only copy remains readable after deletion of the original run; orphan data
still grants no attempt correlation, outcome adoption or billing certainty.

Focused final regression: 15/15 on Python 3.14.8 (28.760 s) and 15/15 on Python
3.10.19 (32.212 s). New cases cover original/archived orphan deletion or mutation,
added blobs, rehashed manifest changes, independent package portability and four
outer publication faults. Existing fault checks caught unpublished stop-request
temporaries interfering with matching-base reuse; only published content-addressed
blobs enter the orphan inventory, with pending files still subject to aggregate
writer bounds. All 57 frozen producers and the 59-file pin closure are preserved;
Ruff lint/format for all 177 Python files pass. Full final SDK-free regression and
new-head CI results are recorded separately in PR #142 and Issue #77.

This slice supports local stop application/inspection and its portable embedded
pre-stop base. The separate [v4 consumer](STOP_CONTROL_CONSUMERS_V4.md) now supports
final-control archive/scorer/MLflow inputs with the exact control and stable
execution parent. Generic v1/v2/v3 consumers still reject final controls.
Correlated outcome adoption and bounded live smoke remain separate work; no real
provider requests, credentials, production registry writes or deployment occur.
