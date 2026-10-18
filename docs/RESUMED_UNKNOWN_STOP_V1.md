# Stop an unknown attempt after native resume

Date: 2026-10-18 (Europe/Moscow). Ledger:
[#77](https://github.com/SoundBlaster/NormLab/issues/77).

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

Before replacing `checkpoint.json`, publish a complete immutable
`normlab.runtime-archive/v3` under `native-resumed-stop-base/`. It retains the raw
resumed checkpoint, every invocation/attempt and embedded original base. Root
source bytes are preserved; orphan response files remain unadopted. Reservations,
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

`normlab.resumed-stop-checkpoint/v1` binds the request, original capture/head,
immutable base archive ID, observed clock sample and all 59 producer pins: frozen
57 plus the two new control/CLI modules. Its resolution ID hashes those fields.
Read-only `inspect` verifies the v3 archive, root source bytes, request, recorded
sample and regenerated frame. It retains `unknownAttemptIds` and
`unknownDispatchAttempts`, reporting `controlState=stopped-with-unknown`, zero new
dispatch/inference and no resume/adoption/execution capability. A copied tree can
be inspected after deletion of its original path; saved fields grant no execution
authority there. Unsigned hashes/pins establish consistency, not producer, clock
or operator authenticity.

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

This slice supports local stop application/inspection and its portable embedded
pre-stop base. The final control is **not yet** a runtime capture/archive/score or
MLflow input. Generic v1/v2/v3 consumers still reject it. A new versioned
stop-control consumer will preserve the exact control and stable execution parent.
Correlated outcome adoption and bounded live smoke remain separate work; no real
provider requests, credentials, production registry writes or deployment occur.
