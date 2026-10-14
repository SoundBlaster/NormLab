# Explicit mock continuation and resolution: slice 5c

Date: 2026-10-14. Task: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Base: `7843936f44ad794860edcbea928a5199bf42fe30` (#93).
Extends [5b mock execution](MOCK_EXECUTION_V1.md); the strict
[5a replay contract](EXECUTION_RECORDS_V1.md) remains unchanged.

## Scope and commands

This is **offline mock continuation**, using the built-in scripted transport and
an explicitly supplied observation of the original **simulated** clock.
It neither verifies the current host clock nor attests an operator identity.
It does not authorize live inference or load provider SDKs/credentials.

```bash
python -B -S evaluation/execution_resume_cli.py inspect /path/to/execution
python -B -S evaluation/execution_resume_cli.py apply /path/to/execution /path/to/reviewed-request.json
```

Python 3.10+, local POSIX filesystem and cooperating processes are required.
`inspect` accepts original v1 and continuation v2 checkpoints, performs no writes,
and rejects during an active writer. Exit 0 is structural consistency, including
paused/failed executions; exit 2 is sanitized rejection. Existing 5b and native
readers do not silently acquire v2 support.

## Request and explicit authorization

Closed request schema `normlab.mock-continuation-request/v1`:

| Fields                            | Meaning                                                                                                      |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `schema`, `runId`, `planDigest`   | Same original execution and plan                                                                             |
| `checkpointDigest`, `journalHead` | Exact current checkpoint bytes and raw event head                                                            |
| `action`                          | `resume`, `stop` or `adopt-saved-outcome`                                                                    |
| `clock`                           | Original complete clock declaration, including epoch, units, source and deadline                             |
| `nowNs`, `observedAt`             | Nonregressing simulated elapsed observation and its exact UTC mapping                                        |
| `caps`                            | Absolute lifetime caps, each covering already-reserved totals and no greater than the previous effective cap |
| `authorization`                   | 5a operator ID/reference/authorized-at record, explicitly supplied for this head                             |
| `expiresAt`                       | UTC expiration, later than observation; checked again before each reservation/dispatch                       |
| `attemptId`, `outcome`            | Null for resume; original unknown attempt for resolution; artifact reference only for adoption               |

`authorizedAt <= observedAt < expiresAt`, with authorization no earlier than the
previous committed observation. This validates supplied **data**, not a real
identity, signature, wall clock or credential. Reusing a request after a committed
invocation rejects its stale checkpoint/head. Each invocation receives a fresh
UUID; execution/task/turn/attempt identities retain their original derivation.
Stop/adoption also require unexpired authorization at their applying event. If
expiry follows the invocation marker, that marker stays saved but the resolution
does not apply; a fresh request can resolve the still-unknown attempt.

The Python builder prepares data for explicit review; it never writes or grants
live authority:

```python
import sys

sys.path.insert(0, "evaluation")
from execution_continuation import continuation_request

request = continuation_request(
    "/path/to/execution",
    action="resume",
    now_ns=1_100_000_000,  # Choose an observation on this run's simulated clock.
    expires_at="2026-01-01T00:00:20.100000Z",
    operator_authorization={
        "operatorId": "synthetic-reviewer",
        "authorizationRef": "f" * 64,
        "authorizedAt": "2026-01-01T00:00:00.100000Z",
    },
)
```

These sample times/reference are synthetic and only fit the fixture clock. For
resolution, supply the original `attempt` ID, and for adoption its saved `outcome`
reference. Review all fields before saving/applying the request. The executor
copies the supplied request, preventing caller mutation from extending its caps
or expiration after validation.

## Continuation and unknown outcomes

- Resume schedules only the unstarted suffix or the next already eligible retry.
  Completed attempts are never repeated. Frozen retry whitelist and three-attempt
  ceiling remain in force; request bytes and ordinal derivation remain unchanged.
- Retry waits only the remaining lower-bound backoff, subtracting simulated time
  since the prior terminal event. Caps, elapsed time and original deadline never
  restart. Expiration during backoff stops without a new reservation.
- A clean `operator-stop`, including authorization expiry, can continue with a
  fresh head-bound authorization, within the original deadline. Complete,
  terminal-failure, deadline, budget-exhaustion and unknown-resolution stops are
  final. A completed suffix may be finalized without dispatch after deadline.
- Any reserved attempt without a terminal outcome blocks resume. `stop` records
  the explicit unknown resolution, preserves the unknown ID and all charges,
  then ends the execution. It does not claim a successful response.
- `adopt-saved-outcome` accepts only response-backed evidence that exactly matches
  the frozen mock script and shared normalization codec: original attempt,
  request/context, returned model, response/result bytes, normalized answers,
  request ID and zero synthetic usage. Rehashing changed content is insufficient.
  Response-less failures/unknown outcomes cannot be adopted on this path.
- Adoption appends a terminal event for the original reservation, without a new
  charge or transport call. It finalizes a completed run or terminal failure;
  otherwise it leaves the suffix untouched. Continuing that suffix needs another
  fresh request. Orphan files are never adopted automatically.

## Durable versioned checkpoint

Before the first continuation marker, the writer preserves the **exact original
v1 checkpoint bytes** in immutable `checkpoint-v1.json`. The original intent,
script, artifacts and v1 event prefix remain intact. The mutable authority is
`checkpoint.json`, now a closed v2 record:

```text
{schema: "normlab.mock-checkpoint/v2", baseDigest, intentDigest,
 scriptDigest, run, journal}
```

New events use `normlab.execution-event/v2`, adding nullable `control` to the 5a
fields. An `invocation-started` marker references the durable request artifact,
charges zero and binds its new invocation ID to this exact head. Subsequent
effects belong to that invocation. Publication retains the 5b exclusive lock,
file/directory fsync, atomic checkpoint replacement and poisoned-writer policy.
Interrupted migration/request publication leaves harmless bounded orphan files;
retry validates an existing original snapshot before reuse.

The v2 reader validates the raw chain, controls, clock/cap continuity and adoption
proof, then creates an **in-memory validation projection** for unchanged 5a replay.
It omits invocation markers, normalizes invocation IDs/event hashes and clears
only explicitly resumed clean stops. A proven exhaustion of reduced caps maps
internally to `operator-stop` because 5a knows only original plan caps; the raw
journal and public report retain `budget-exhaustion`. Stored evidence is never
rewritten to fit that projection.

Ordinary artifacts remain bounded at 2 MiB, checkpoints at 16 MiB, inventory at
4096 retained/published entries including directories, 64 MiB file bytes, journal
at 8192 events and continuation invocations at 128. Directory entries contribute
zero bytes but occupy publication capacity throughout the writer lifetime.
Symlinks, FIFO and oversized retained files reject before mutation. Process-crash
checks establish atomic visibility and dispatch barriers, not physical power-loss
guarantees or protection from adversarial local directory rewriting.

## Evidence and next gate

The [verification report](MOCK_RESUME_VERIFICATION_2026-10-14.md) distinguishes
mock calls from inference. New v2 reports expose invocation history, effective
caps, explicit resolutions, `clockContinuityChecked: true` and
`authorizationAttested: false`. `runtimeClockVerified`, `codePinsVerified`,
`providerWireValidated`, `executionReady` and `semanticQualityEvidence` remain
false; `actualCost` stays null and inference/authorized dispatch counts stay zero.

Next: **5d capture-revision-aware runtime export/registry integration**. Before
any separately authorized 5e live smoke, implement real host clock/epoch and
current authorization verification, native provider normalization and transport.
The broader #77 acceptance remains incomplete.
