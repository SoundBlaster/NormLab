"""Fresh one-attempt durable native boundary; no scheduler, retry or resume."""

import copy
import os
import platform
import re
import sys
from pathlib import Path
from types import SimpleNamespace

from execution_checkpoint import (
    DurableWriter,
    SnapshotStore,
    bounded_read,
    build_checkpoint,
    reader_lock,
)
from execution_live_authority import claim_run
from execution_live_gate import LinuxClock, current_gate
from execution_live_http import NativeHTTP
from execution_live_wire import adapter_revision, metadata, normalized
from execution_mock_codec import make_event
from execution_outcomes import answer_schema
from execution_plan import MAX_JOURNAL_BYTES, Store, prepare
from execution_replay import replay
from offline_bundle import MAX_BYTES, canonical, object_keys, require, sha

MODULES = (
    "execution_live_authority.py",
    "execution_live_gate.py",
    "execution_live_http.py",
    "execution_live_wire.py",
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


def checkpoint(intent, events, store):
    # Reuse its state derivation/replay validation, never persist mock schema/flags.
    derived = build_checkpoint(intent, events, store, sha(canonical(requirements())))
    return {
        "schema": "normlab.live-checkpoint/v1",
        "intentDigest": sha(canonical(intent)),
        "codePins": requirements(),
        "run": derived["run"],
        "journal": derived["journal"],
    }


def inspect_live(output):
    """Historical replay is read-only and never grants current clock/dispatch authority."""
    with reader_lock(output):
        raw_intent = bounded_read(Path(output) / "intent.json", MAX_BYTES)
        saved = Store.decode_json(
            bounded_read(Path(output) / "checkpoint.json", MAX_JOURNAL_BYTES)
        )
        object_keys(saved, "schema intentDigest codePins run journal")
        require(
            saved["schema"] == "normlab.live-checkpoint/v1"
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
        installed_pins(plan)
        replay(SnapshotStore(output, intent, []))
        expected = checkpoint(intent, saved["journal"], store)
        require(canonical(saved) == canonical(expected), "Regenerated live checkpoint")
        report = replay(SnapshotStore(output, saved["run"], saved["journal"]))
        report["nativeBoundary"] = {
            "mode": "fresh-one-attempt/v1",
            "resumeSupported": False,
            "historicalReplayOnly": True,
        }
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


def run_once(input_directory, output, confirmation, key_environment, *, hook=None):
    """Real entrypoint. Tests patch factories; production exposes no fake-clock option."""
    require(
        isinstance(key_environment, str)
        and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key_environment),
        "Credential environment reference",
    )
    source = Store(input_directory)
    require(
        not Path(output).resolve().is_relative_to(source.root),
        "Live output outside immutable input",
    )
    plan = prepare(source)
    installed_pins(plan)
    intent = source.json("run.json")
    require(
        intent["evidenceKind"] == "live-capture" and intent["predecessor"] is None,
        "Fresh live run",
    )
    require(
        source.json("journal.json") == [] and intent["state"] == "created",
        "Fresh empty journal; no resume",
    )
    replay(source)
    confirmation = copy.deepcopy(confirmation)
    clock = LinuxClock()
    sample = clock.sample()
    current_gate(plan, intent, source, confirmation, sample)
    claim_run(intent, source.root, output)
    events, run, last_sample = [], intent, sample
    task, arm = (
        plan["tasks"][0],
        next(a for a in plan["arms"] if a["id"] == plan["tasks"][0]["armId"]),
    )
    questions = answer_schema(source.value(plan["pins"]["outputSchema"]))
    with DurableWriter(output, hook) as writer:
        writer.publish("plan.json", source.read("plan.json"), phase="plan")
        for name, raw in source.files.items():
            if name.startswith("artifacts/"):
                writer.put(raw, phase="input")
        writer.publish("intent.json", canonical(intent), phase="intent")
        writer.publish(
            "checkpoint.json",
            canonical(checkpoint(intent, events, Store(writer.root))),
            phase="initial",
            replace=True,
        )

        def commit(kind, outcome=None, reason=None):
            nonlocal run, events, last_sample
            fresh = clock.sample()
            require(
                fresh["epoch"] == intent["clock"]["epoch"]
                and fresh["clockNs"] >= last_sample["clockNs"]
                and fresh["observedAt"] >= last_sample["observedAt"],
                "Commit clock continuity",
            )
            event_clock = SimpleNamespace(
                value=fresh["clockNs"], timestamp=lambda: fresh["observedAt"]
            )
            event = make_event(
                intent, events, event_clock, plan, kind, outcome=outcome, reason=reason
            )
            candidate = checkpoint(intent, [*events, event], Store(writer.root))
            writer.publish(
                "checkpoint.json", canonical(candidate), phase=kind, replace=True
            )
            run, events, last_sample = candidate["run"], candidate["journal"], fresh

        def check():
            nonlocal last_sample
            fresh = clock.sample()
            checked = current_gate(
                plan,
                run,
                Store(writer.root),
                confirmation,
                fresh,
                last_sample=last_sample,
                reserve=False,
            )
            last_sample = fresh
            return checked["timeoutNs"]

        writer.hook("before-reservation")
        current_gate(
            plan,
            run,
            Store(writer.root),
            confirmation,
            clock.sample(),
            last_sample=last_sample,
        )
        commit("attempt-reserved")
        writer.hook("after-reservation")
        check()
        secret = os.environ.get(key_environment)
        require(isinstance(secret, str) and secret, "Credential unavailable")
        writer.hook("before-transport-construction")
        transport = NativeHTTP()
        writer.hook("before-dispatch")
        reply = transport.dispatch(source.artifact(task["request"]), secret, check)
        writer.hook("after-dispatch")
        saved, blobs = classify(reply, task, arm, questions)
        for raw in blobs:
            writer.put(raw, phase="response")
        ref = writer.put(canonical(saved), phase="outcome")
        writer.hook("after-response")
        commit("attempt-terminal", outcome=ref)
        writer.hook("after-terminal")
        # This capability deliberately stops after one attempt, including an
        # eligible transport failure. A future scheduler may implement retries.
        commit("run-stopped", reason="operator-stop")
    return inspect_live(output)
