"""Native checkpoint/normalization kernel and one-attempt compatibility entrypoint."""

import platform
import sys
from pathlib import Path

from execution_checkpoint import (
    SnapshotStore,
    bounded_read,
    build_checkpoint,
    reader_lock,
)
from execution_live_authority import claim_run as claim_run
from execution_live_gate import LinuxClock as LinuxClock
from execution_live_gate import current_gate as current_gate
from execution_live_http import NativeHTTP as NativeHTTP
from execution_live_wire import adapter_revision, metadata, normalized
from execution_plan import MAX_JOURNAL_BYTES, Store, prepare
from execution_replay import replay
from offline_bundle import MAX_BYTES, canonical, object_keys, require, sha

MODULES = (
    "execution_live_authority.py",
    "execution_live_gate.py",
    "execution_live_http.py",
    "execution_live_wire.py",
    "execution_stage1_protocol.py",
    "execution_stage1_plan.py",
    "execution_stage1_bind.py",
    "execution_live_scheduler.py",
    "stage1_provider_plan.py",
    "plan_stage1_comparison.py",
    "harness.py",
    "provider_config.py",
    "execution_live_kernel.py",
    "execution_live_cli.py",
    "execution_checkpoint.py",
    "execution_mock_codec.py",
    "execution_decisions.py",
    "execution_records.py",
    "execution_plan.py",
    "execution_replay.py",
    "execution_outcomes.py",
    "offline_bundle.py",
)


def requirements():
    return {
        "code": {
            name: sha(Path(__file__).with_name(name).read_bytes()) for name in MODULES
        },
        "dependencies": {
            "python-stdlib-runtime": sha(
                canonical(
                    {
                        "implementation": platform.python_implementation(),
                        "version": sys.version,
                    }
                )
            )
        },
        "adapter": adapter_revision(),
    }


def installed_pins(plan):
    expected = requirements()
    require(
        plan["pins"]["code"] == expected["code"]
        and plan["pins"]["dependencies"] == expected["dependencies"],
        "Frozen native code/runtime pins",
    )
    require(
        all(a["adapter"] == expected["adapter"] for a in plan["arms"]),
        "Frozen native adapter pins",
    )


def checkpoint(intent, events, store, *, mode=None):
    # Reuse its state derivation/replay validation, never persist mock schema/flags.
    derived = build_checkpoint(intent, events, store, sha(canonical(requirements())))
    result = {
        "schema": "normlab.live-checkpoint/v1"
        if mode is None
        else "normlab.live-checkpoint/v2",
        "intentDigest": sha(canonical(intent)),
        "codePins": requirements(),
        "run": derived["run"],
        "journal": derived["journal"],
    }
    if mode is not None:
        require(mode == "stage1-bounded-schedule/v1", "Native schedule mode")
        result["mode"] = mode
    return result


def inspect_live(output):
    """Historical replay is read-only and never grants current clock/dispatch authority."""
    with reader_lock(output):
        raw_intent = bounded_read(Path(output) / "intent.json", MAX_BYTES)
        saved = Store.decode_json(
            bounded_read(Path(output) / "checkpoint.json", MAX_JOURNAL_BYTES)
        )
        mode = saved.get("mode")
        object_keys(
            saved,
            "schema intentDigest codePins run journal"
            + (" mode" if mode is not None else ""),
        )
        require(
            saved["schema"]
            == (
                "normlab.live-checkpoint/v1"
                if mode is None
                else "normlab.live-checkpoint/v2"
            )
            and saved["intentDigest"] == sha(raw_intent),
            "Live checkpoint/intent binding",
        )
        intent = Store.decode_json(raw_intent)
        require(
            intent["evidenceKind"] == "live-capture" and intent["predecessor"] is None,
            "Fresh live intent only",
        )
        store = Store(output)
        plan = prepare(store)
        if mode is not None:
            from execution_stage1_plan import verify_stage1

            verify_stage1(store)
        installed_pins(plan)
        replay(SnapshotStore(output, intent, []))
        expected = checkpoint(intent, saved["journal"], store, mode=mode)
        require(canonical(saved) == canonical(expected), "Regenerated live checkpoint")
        require(
            mode is not None
            or sum(e["type"] == "attempt-reserved" for e in saved["journal"]) <= 1,
            "One-attempt checkpoint denominator",
        )
        verify_normalization(plan, intent, saved["journal"], store, mode=mode)
        report = replay(SnapshotStore(output, saved["run"], saved["journal"]))
        report["nativeBoundary"] = {
            "mode": mode or "fresh-one-attempt/v1",
            "resumeSupported": False,
            "historicalReplayOnly": True,
        }
        report["operation"] = "inspect"
        report["dispatchAttemptsInvoked"] = 0
        return report


def classify(reply, task, arm, questions):
    response, blobs, result = reply["response"], [], None
    model, rid, usage = None, None, {"inputTokens": None, "outputTokens": None}
    status = "transport-failed" if response is None else "invalid-output"
    response_ref = None
    if response is not None:
        raw = canonical(response)
        response_ref = {
            "path": f"artifacts/{sha(raw)}.blob",
            "sha256": sha(raw),
            "bytes": len(raw),
        }
        blobs.append(raw)
        try:
            model, rid, usage = metadata(response, arm["protocol"])
            if 400 <= response["httpStatus"] <= 599:
                status = "http-failed"
            elif response["httpStatus"] == 200 and model is not None:
                if model not in arm["acceptedModels"]:
                    status = "model-rejected"
                else:
                    value = normalized(response, task, arm, questions)
                    raw = canonical(value)
                    result = {
                        "path": f"artifacts/{sha(raw)}.blob",
                        "sha256": sha(raw),
                        "bytes": len(raw),
                    }
                    blobs.append(raw)
                    status = "completed"
        except (ValueError, TypeError, KeyError, OverflowError, UnicodeError):
            status = "invalid-output"
    saved = {
        "schema": "normlab.execution-outcome/v1",
        "status": status,
        "requestDigest": task["request"]["sha256"],
        "contextDigest": task["context"]["sha256"],
        "model": model,
        "providerRequestId": rid,
        "dispatchObserved": True if response is not None else None,
        "usage": usage,
        "response": response_ref,
        "result": result,
        "errorClasses": [reply["errorClass"]] if response is None else [],
        "backoffNs": None,
        "statusCode": response["httpStatus"] if status == "http-failed" else None,
    }
    return saved, blobs


def verify_normalization(plan, intent, events, store, *, mode):
    """Re-derive response-backed outcomes; unsigned consistency, not API authenticity."""
    from execution_outcomes import answer_schema, retryable
    from execution_records import backoff_bounds

    questions = answer_schema(store.value(plan["pins"]["outputSchema"]))
    tasks = {ids["taskId"]: task for ids, task in zip(intent["tasks"], plan["tasks"])}
    models = {}
    for event in events:
        if event["type"] != "attempt-terminal":
            continue
        saved = store.value(event["outcome"])
        task = tasks[event["taskId"]]
        arm = next(a for a in plan["arms"] if a["id"] == task["armId"])
        if saved["response"] is None:
            require(
                saved["status"] == "transport-failed"
                and saved["dispatchObserved"] is None
                and saved["model"] is None
                and saved["providerRequestId"] is None
                and saved["usage"] == {"inputTokens": None, "outputTokens": None},
                "Native transport observation shape",
            )
            expected_delay = (
                backoff_bounds(event["ordinal"])[0]
                if mode is not None and retryable(saved, event["ordinal"])
                else None
            )
            require(
                saved["backoffNs"] == expected_delay, "Native retry delay derivation"
            )
            continue
        expected, _ = classify(
            {"response": store.value(saved["response"]), "errorClass": None},
            task,
            arm,
            questions,
        )
        if (
            expected["status"] in {"completed", "invalid-output"}
            and expected["model"] is not None
            and arm["id"] in models
            and models[arm["id"]] != expected["model"]
        ):
            expected.update(status="model-rejected", result=None)
        require(
            canonical(saved) == canonical(expected),
            "Re-derived native response normalization",
        )
        if expected["status"] == "completed":
            models[arm["id"]] = expected["model"]


def run_once(input_directory, output, confirmation, key_environment, *, hook=None):
    """One-attempt compatibility entrypoint over the shared durable boundary."""
    from execution_live_scheduler import run_boundary

    return run_boundary(
        input_directory,
        output,
        confirmation,
        key_environment=key_environment,
        hook=hook,
    )
