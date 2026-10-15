"""Allocate a fresh Linux-host intent from an explicit local authorization file."""

from pathlib import Path

import execution_live_kernel as kernel
from execution_checkpoint import DurableWriter
from execution_decisions import permit_caps
from execution_plan import Store, new_run
from execution_records import caps, scope_digest
from execution_replay import replay
from execution_stage1_plan import verify_stage1
from offline_bundle import canonical, object_keys, require, sha


def bind_stage1(compiled, output, authorization):
    source = Store(compiled)
    plan, _ = verify_stage1(source)
    kernel.installed_pins(plan)
    require(
        not Path(output).resolve().is_relative_to(source.root),
        "Fresh input outside compiled plan",
    )
    object_keys(
        authorization, "schema planDigest caps expiresAt authorization externalSpending"
    )
    require(
        authorization["schema"] == "normlab.stage1-native-authorization/v1"
        and authorization["planDigest"] == sha(canonical(plan)),
        "Exact authorization plan",
    )
    caps(authorization["caps"])
    sample = kernel.LinuxClock().sample()
    clock = {
        k: sample[k] for k in ("policy", "source", "units", "suspendAware", "epoch")
    }
    clock.update(
        startNs=sample["clockNs"], deadlineNs=sample["clockNs"] + plan["wallTimeNs"]
    )
    intent = new_run(plan, clock, evidence_kind="live-capture")
    permit = {
        k: authorization[k]
        for k in (
            "planDigest",
            "caps",
            "expiresAt",
            "authorization",
            "externalSpending",
        )
    }
    permit.update(
        schema="normlab.execution-permit/v1",
        runId=intent["id"],
        scopeDigest=scope_digest(plan),
    )
    with DurableWriter(output) as writer:
        writer.publish("plan.json", source.read("plan.json"), phase="bind-plan")
        for name, raw in source.files.items():
            if name.startswith("artifacts/"):
                writer.put(raw, phase="bind-artifact")
        intent["permit"] = writer.put(canonical(permit), phase="permit")
        store = Store(writer.root)
        permit_caps(plan, intent, store)
        confirmation = {
            "runId": intent["id"],
            "planDigest": intent["planDigest"],
            "permitDigest": intent["permit"]["sha256"],
            "invocationId": intent["initialInvocationId"],
            "externalCeilingMicros": permit["externalSpending"]["ceilingMicros"],
        }
        kernel.current_gate(plan, intent, store, confirmation, sample)
        writer.publish("run.json", canonical(intent), phase="bind-intent")
        writer.publish("journal.json", canonical([]), phase="bind-journal")
        replay(Store(writer.root))
    return {
        "schema": "normlab.stage1-native-bind/v1",
        "confirmation": confirmation,
        "authorizedDispatches": 0,
        "inferenceCallsExecuted": 0,
        "executionReady": False,
        "semanticQualityEvidence": False,
    }
