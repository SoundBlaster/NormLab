"""Current Linux clock and explicit local operator confirmation; no provider I/O."""

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from execution_checkpoint import bounded_read
from execution_decisions import permit_caps
from execution_plan import charge
from execution_records import CLOCK, integer, run_shape, utc
from offline_bundle import canonical, object_keys, require, sha


class LinuxClock:
    """Kernel BOOTTIME plus hashed host/boot identity; unsupported hosts reject."""

    def sample(self):
        require(
            sys.platform == "linux" and hasattr(time, "CLOCK_BOOTTIME"),
            "Linux CLOCK_BOOTTIME required",
        )
        boot = (
            bounded_read(Path("/proc/sys/kernel/random/boot_id"), 128).decode().strip()
        )
        require(str(UUID(boot)) == boot, "Canonical boot identity")
        machine = bounded_read(Path("/etc/machine-id"), 128).decode().strip()
        require(
            len(machine) == 32 and all(c in "0123456789abcdef" for c in machine),
            "Canonical host identity",
        )
        reading = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        integer(reading)
        return {
            "policy": CLOCK,
            "source": "linux:CLOCK_BOOTTIME",
            "units": "nanoseconds",
            "suspendAware": True,
            "epoch": sha(canonical([machine, boot])),
            "clockNs": reading,
            "observedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }


def current_gate(
    plan,
    run,
    store,
    confirmation,
    sample,
    *,
    last_sample=None,
    reserve=True,
    task_index=0,
):
    """An explicit invocation confirmation is required in addition to saved permit.

    Local trusted operator assertion, not an identity signature or dollar enforcement.
    Call again immediately after durable reservation, before transport/key lookup.
    """
    run_shape(run, plan)
    require(type(reserve) is bool, "Reservation gate mode")
    require(
        reserve or last_sample is not None, "Post-reservation clock baseline required"
    )
    require(run["evidenceKind"] == "live-capture", "Live gate cannot authorize mock")
    limits, permit = permit_caps(plan, run, store)
    object_keys(
        confirmation,
        "runId planDigest permitDigest invocationId externalCeilingMicros",
    )
    require(
        canonical(confirmation)
        == canonical(
            {
                "runId": run["id"],
                "planDigest": run["planDigest"],
                "permitDigest": run["permit"]["sha256"],
                "invocationId": run["initialInvocationId"],
                "externalCeilingMicros": permit["externalSpending"]["ceilingMicros"],
            }
        ),
        "Current exact run/plan/permit/invocation/spending confirmation",
    )
    integer(confirmation["externalCeilingMicros"], 1)
    object_keys(sample, "policy source units suspendAware epoch clockNs observedAt")
    require(
        canonical(
            {
                k: sample[k]
                for k in ("policy", "source", "units", "suspendAware", "epoch")
            }
        )
        == canonical(
            {
                k: run["clock"][k]
                for k in ("policy", "source", "units", "suspendAware", "epoch")
            }
        ),
        "Current same-host boot/source capability",
    )
    integer(sample["clockNs"])
    require(sample["clockNs"] >= run["lastClockNs"], "Current clock continuity")
    observed = utc(sample["observedAt"])
    if last_sample is not None:
        require(
            sample["clockNs"] >= last_sample["clockNs"]
            and observed >= utc(last_sample["observedAt"]),
            "Clock regression or wall-clock ambiguity",
        )
    require(sample["clockNs"] < run["clock"]["deadlineNs"], "Current deadline expired")
    require(
        utc(permit["authorization"]["authorizedAt"])
        <= observed
        < utc(permit["expiresAt"]),
        "Current permit expired or not yet valid",
    )
    integer(task_index)
    require(task_index < len(plan["tasks"]), "Current scheduled task index")
    task = plan["tasks"][task_index]
    required = charge(plan, task) if reserve else {k: 0 for k in limits}
    require(
        all(run["counts"]["reserved"][k] + n <= limits[k] for k, n in required.items()),
        "Current aggregate reservation ceilings",
    )
    arm = next(a for a in plan["arms"] if a["id"] == task["armId"])
    remaining = min(
        arm["timeoutNs"],
        run["clock"]["deadlineNs"] - sample["clockNs"],
        int((utc(permit["expiresAt"]) - observed).total_seconds() * 1_000_000_000),
    )
    integer(remaining, 1)
    return {"limits": limits, "timeoutNs": remaining, "sample": dict(sample)}
