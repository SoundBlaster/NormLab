"""Single-worker native schedule; durable attempts, bounded retries, no resume."""

import copy
import os
import re
import time
from pathlib import Path
from types import SimpleNamespace

import execution_live_kernel as kernel
from execution_checkpoint import DurableWriter
from execution_decisions import permit_caps
from execution_mock_codec import make_event
from execution_outcomes import answer_schema, retryable
from execution_plan import Store, charge, prepare
from execution_records import backoff_bounds, utc
from execution_replay import replay
from offline_bundle import canonical, require

MODE = "stage1-bounded-schedule/v1"


def run_schedule(input_directory, output, confirmation, *, hook=None):
    return run_boundary(input_directory, output, confirmation, schedule=True, hook=hook)


def run_boundary(
    input_directory,
    output,
    confirmation,
    *,
    schedule=False,
    key_environment=None,
    hook=None,
):
    require(type(schedule) is bool, "Explicit native execution mode")
    source = Store(input_directory)
    require(
        not Path(output).resolve().is_relative_to(source.root),
        "Live output outside immutable input",
    )
    plan = prepare(source)
    kernel.installed_pins(plan)
    if schedule:
        from execution_stage1_plan import verify_stage1

        plan, original = verify_stage1(source)
        keys = {arm: p["keyEnvironment"] for arm, p in original["providers"].items()}
    else:
        keys = {arm["id"]: key_environment for arm in plan["arms"]}
    require(
        all(
            isinstance(key, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key)
            for key in keys.values()
        ),
        "Credential environment reference",
    )
    intent = source.json("run.json")
    require(
        intent["evidenceKind"] == "live-capture"
        and intent["predecessor"] is None
        and source.json("journal.json") == []
        and intent["state"] == "created",
        "Fresh empty live intent; no resume",
    )
    replay(source)
    confirmation = copy.deepcopy(confirmation)
    clock = kernel.LinuxClock()
    sample = clock.sample()
    kernel.current_gate(plan, intent, source, confirmation, sample)
    kernel.claim_run(intent, source.root, output)
    limits, permit = permit_caps(plan, intent, source)
    events, run, last_sample = [], intent, sample
    position, ordinal, invoked = 0, 1, 0
    models = {}
    questions = answer_schema(source.value(plan["pins"]["outputSchema"]))
    mode = MODE if schedule else None
    attempt_deadline = None
    with DurableWriter(output, hook) as writer:
        writer.publish("plan.json", source.read("plan.json"), phase="plan")
        for name, raw in source.files.items():
            if name.startswith("artifacts/"):
                writer.put(raw, phase="input")
        writer.publish("intent.json", canonical(intent), phase="intent")

        def publish(kind):
            nonlocal run
            candidate = kernel.checkpoint(intent, events, Store(writer.root), mode=mode)
            writer.publish(
                "checkpoint.json", canonical(candidate), phase=kind, replace=True
            )
            run = candidate["run"]

        publish("initial")

        def fresh_clock():
            nonlocal last_sample
            fresh = clock.sample()
            require(
                fresh["epoch"] == intent["clock"]["epoch"]
                and fresh["clockNs"] >= last_sample["clockNs"]
                and utc(fresh["observedAt"]) >= utc(last_sample["observedAt"]),
                "Commit clock continuity",
            )
            previous, last_sample = last_sample, fresh
            return fresh, previous

        def commit(kind, outcome=None, reason=None):
            fresh, _ = fresh_clock()
            event_clock = SimpleNamespace(
                value=fresh["clockNs"], timestamp=lambda: fresh["observedAt"]
            )
            event = make_event(
                intent,
                events,
                event_clock,
                plan,
                kind,
                task_index=min(position, len(plan["tasks"]) - 1),
                ordinal=ordinal,
                outcome=outcome,
                reason=reason,
            )
            events.append(event)
            publish(kind)

        def check():
            fresh, previous = fresh_clock()
            gate = kernel.current_gate(
                plan,
                run,
                Store(writer.root),
                confirmation,
                fresh,
                last_sample=previous,
                reserve=False,
                task_index=position,
            )
            timeout = gate["timeoutNs"]
            if schedule and attempt_deadline is not None:
                timeout = min(timeout, attempt_deadline - fresh["clockNs"])
                require(timeout > 0, "Original attempt deadline expired")
            return timeout

        def stop_if_limited():
            fresh, previous = fresh_clock()
            # A clock rollback is rejected above even when the run is stopping.
            if fresh["clockNs"] >= intent["clock"]["deadlineNs"]:
                commit("run-stopped", reason="deadline")
                return True
            if utc(fresh["observedAt"]) >= utc(permit["expiresAt"]):
                # v1 journal has no permit-expired reason; explicit conservative stop.
                commit("run-stopped", reason="operator-stop")
                return True
            required = charge(plan, plan["tasks"][position])
            if any(
                run["counts"]["reserved"][k] + n > limits[k]
                for k, n in required.items()
            ):
                commit("run-stopped", reason="budget-exhaustion")
                return True
            kernel.current_gate(
                plan,
                run,
                Store(writer.root),
                confirmation,
                fresh,
                last_sample=previous,
                task_index=position,
            )
            return False

        while position < len(plan["tasks"]):
            if schedule and stop_if_limited():
                break
            task = plan["tasks"][position]
            arm = next(a for a in plan["arms"] if a["id"] == task["armId"])
            writer.hook("before-reservation")
            fresh, previous = fresh_clock()
            kernel.current_gate(
                plan,
                run,
                Store(writer.root),
                confirmation,
                fresh,
                last_sample=previous,
                task_index=position,
            )
            attempt_deadline = fresh["clockNs"] + arm["timeoutNs"]
            commit("attempt-reserved")
            writer.hook("after-reservation")
            check()
            secret = os.environ.get(keys[arm["id"]])
            require(isinstance(secret, str) and secret, "Credential unavailable")
            writer.hook("before-transport-construction")
            transport = kernel.NativeHTTP()
            writer.hook("before-dispatch")
            invoked += 1
            reply = transport.dispatch(source.artifact(task["request"]), secret, check)
            writer.hook("after-dispatch")
            saved, blobs = kernel.classify(reply, task, arm, questions)
            if (
                saved["status"] in {"completed", "invalid-output"}
                and saved["model"] is not None
                and arm["id"] in models
                and models[arm["id"]] != saved["model"]
            ):
                saved.update(status="model-rejected", result=None)
            if schedule and retryable(saved, ordinal):
                saved["backoffNs"] = backoff_bounds(ordinal)[0]
            for raw in blobs:
                writer.put(raw, phase="response")
            ref = writer.put(canonical(saved), phase="outcome")
            writer.hook("after-response")
            commit("attempt-terminal", outcome=ref)
            terminal_clock = events[-1]["clockNs"]
            writer.hook("after-terminal")
            if not schedule:
                commit("run-stopped", reason="operator-stop")
                break
            if any(
                count is not None and count > arm["requestCaps"][key]
                for key, count in saved["usage"].items()
            ):
                commit("run-stopped", reason="usage-ceiling-exceeded")
                break
            if saved["status"] == "completed":
                models[arm["id"]] = saved["model"]
                position, ordinal = position + 1, 1
                if position == len(plan["tasks"]):
                    commit("run-stopped", reason="complete")
                    break
            elif retryable(saved, ordinal):
                ordinal += 1
                target = terminal_clock + saved["backoffNs"]
                while last_sample["clockNs"] < target:
                    if stop_if_limited():
                        break
                    time.sleep(
                        min(
                            0.25,
                            max(0, target - last_sample["clockNs"]) / 1_000_000_000,
                        )
                    )
                if run["state"] == "finished":
                    break
            else:
                commit("run-stopped", reason="terminal-failure")
                break
    report = kernel.inspect_live(output)
    report.update(
        operation="run-schedule" if schedule else "run-once",
        dispatchAttemptsInvoked=invoked,
        inferenceCallsExecuted=None
        if report["unknownDispatchAttempts"]
        else report["counts"]["observedDispatches"],
        authorizedDispatches=report["counts"]["reserved"]["dispatches"],
    )
    return report
