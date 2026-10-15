"""Explicit single-writer native suffix continuation; no unknown redispatch."""

import copy
import os
import time
from types import SimpleNamespace

import execution_live_kernel as kernel
from execution_mock_codec import make_event
from execution_outcomes import answer_schema, retryable
from execution_plan import charge
from execution_records import backoff_bounds, utc
from native_resume_authority import verify_claim
from native_resume_capture import BASE, ResumeCapture, cursor, inspect_resume
from native_stop_resolution import StopWriter
from offline_bundle import (
    MAX_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    canonical,
    require,
    sha,
)
from runtime_archive_export import export_archive
from runtime_archive_format import prepare_archive
from runtime_archive_reader import read_archive
from runtime_export import prepare_export


class NativeResume:
    def __init__(self, writer, capture, request):
        self.writer, self.capture, self.request = writer, capture, request
        self.plan, self.intent = capture.plan, capture.intent
        self.events = copy.deepcopy(capture.events)
        self.report = copy.deepcopy(capture.report)
        self.run = capture.saved["run"]
        self.position, self.ordinal = cursor(self.report)
        self.clock = None
        self.last_sample = {
            "clockNs": self.run["lastClockNs"],
            "observedAt": self.report["lastObservedAt"]
            or capture.permit["authorization"]["authorizedAt"],
        }
        self.models = {}
        for task, saved in zip(self.plan["tasks"], self.report["taskOutcomes"]):
            if saved["final"] is not None and saved["final"]["status"] == "completed":
                self.models.setdefault(task["armId"], saved["final"]["model"])
        self.questions = answer_schema(
            capture.store.value(self.plan["pins"]["outputSchema"])
        )
        self.attempt_deadline = None
        self.invoked = 0

    def fresh(self):
        sample = self.clock.sample()
        # A real current capability is checked even when publishing a stop after expiry.
        require(
            canonical(
                {
                    key: sample[key]
                    for key in ("policy", "source", "units", "suspendAware", "epoch")
                }
            )
            == canonical(
                {
                    key: self.intent["clock"][key]
                    for key in ("policy", "source", "units", "suspendAware", "epoch")
                }
            )
            and type(sample["clockNs"]) is int
            and sample["clockNs"] >= self.last_sample["clockNs"]
            and utc(sample["observedAt"]) >= utc(self.last_sample["observedAt"]),
            "Native resume current clock/UTC capability continuity",
        )
        previous, self.last_sample = self.last_sample, sample
        return sample, previous

    def gate(self, sample, previous, *, reserve):
        self.capture.observation(
            self.request,
            sample,
            last_clock=previous["clockNs"],
            last_utc=previous["observedAt"],
        )
        verify_claim(self.intent, self.writer.root)
        confirmation = {
            "runId": self.intent["id"],
            "planDigest": self.intent["planDigest"],
            "permitDigest": self.intent["permit"]["sha256"],
            "invocationId": self.intent["initialInvocationId"],
            "externalCeilingMicros": self.request["externalCeilingMicros"],
        }
        result = kernel.current_gate(
            self.plan,
            self.run,
            self.capture.store,
            confirmation,
            sample,
            last_sample=previous,
            reserve=reserve,
            task_index=self.position,
        )
        required = (
            charge(self.plan, self.plan["tasks"][self.position])
            if reserve
            else {key: 0 for key in self.request["caps"]}
        )
        require(
            all(
                self.run["counts"]["reserved"][key] + value <= self.request["caps"][key]
                for key, value in required.items()
            ),
            "Current native resume effective ceilings",
        )
        remaining = min(
            result["timeoutNs"],
            int(
                (
                    utc(self.request["expiresAt"]) - utc(sample["observedAt"])
                ).total_seconds()
                * 1_000_000_000
            ),
        )
        if self.attempt_deadline is not None and not reserve:
            remaining = min(remaining, self.attempt_deadline - sample["clockNs"])
        require(remaining > 0, "Original native attempt timeout expired")
        return remaining

    def check(self):
        sample, previous = self.fresh()
        return self.gate(sample, previous, reserve=False)

    def commit(self, kind, *, outcome=None, reason=None, control=None):
        sample, previous = self.fresh()
        if kind in {"invocation-started", "attempt-reserved"}:
            self.gate(sample, previous, reserve=kind == "attempt-reserved")
        event = make_event(
            self.intent,
            self.events,
            SimpleNamespace(
                value=sample["clockNs"], timestamp=lambda: sample["observedAt"]
            ),
            self.plan,
            kind,
            task_index=min(self.position, len(self.plan["tasks"]) - 1),
            ordinal=self.ordinal,
            outcome=outcome,
            reason=reason,
            invocation=self.request["invocationId"],
            control=control,
            version=2,
        )
        events = [*self.events, event]
        report, _, _, _ = self.capture.derive(events)
        frame = self.capture.frame(events, report)
        self.writer.publish(
            "checkpoint.json", canonical(frame), phase=kind, replace=True
        )
        self.events, self.report, self.run = events, report, frame["run"]
        self.capture.store.files.pop("checkpoint.json", None)

    def limited(self):
        sample, previous = self.fresh()
        reason = None
        if sample["clockNs"] >= self.intent["clock"]["deadlineNs"]:
            reason = "deadline"
        elif utc(sample["observedAt"]) >= utc(self.request["expiresAt"]):
            reason = "operator-stop"
        elif any(
            self.run["counts"]["reserved"][key] + value > self.request["caps"][key]
            for key, value in charge(
                self.plan, self.plan["tasks"][self.position]
            ).items()
        ):
            # Narrower invocation caps may stop before the original permit caps.
            reason = "operator-stop"
        if reason is not None:
            self.commit("run-stopped", reason=reason)
            return True
        self.gate(sample, previous, reserve=True)
        return False

    def execute(self):
        kernel.installed_pins(self.plan)
        self.capture.request_check(
            self.request, self.events, self.report, self.capture.limits
        )
        require(
            self.request["invocationId"] not in self.capture.invocations,
            "Fresh unused native invocation",
        )
        self.clock = kernel.LinuxClock()
        sample, previous = self.fresh()
        self.gate(sample, previous, reserve=True)
        if self.capture.archive_id is None:
            planned = prepare_archive(prepare_export(self.capture.snapshot))
            exists = (self.writer.root / BASE).exists()
            require(
                len(self.writer.inventory)
                + (0 if exists else planned.index["totals"]["publishedEntries"])
                + 3
                <= MAX_FILES
                and sum(self.writer.inventory.values())
                + (
                    0
                    if exists
                    else planned.index["totals"]["contentBytes"]
                    + len(planned.index_bytes)
                )
                + 3 * MAX_BYTES
                <= MAX_TOTAL_BYTES,
                "Native resume combined archive/publication bounds",
            )
            if not exists:
                export_archive(planned, self.writer.root / BASE, hook=self.writer.hook)
            archive = read_archive(self.writer.root / BASE)
            require(
                archive.index == planned.index, "Existing immutable resume base binding"
            )
            self.capture.archive_id = archive.index["archiveId"]
            self.writer.inventory_check()
            self.writer.hook("after-resume-base")
        ref = self.writer.put(canonical(self.request), phase="resume-request")
        self.commit("invocation-started", control=ref)
        self.writer.hook("after-invocation")
        if self.ordinal > 1:
            previous = next(
                event
                for event in reversed(self.capture.projected)
                if event["type"] == "attempt-terminal"
            )
            saved = self.capture.store.value(previous["outcome"])
            self.wait(previous["clockNs"] + saved["backoffNs"])
        while (
            self.position < len(self.plan["tasks"])
            and self.report["state"] != "finished"
        ):
            if self.limited():
                break
            task = self.plan["tasks"][self.position]
            arm = next(a for a in self.plan["arms"] if a["id"] == task["armId"])
            self.writer.hook("before-reservation")
            self.attempt_deadline = self.last_sample["clockNs"] + arm["timeoutNs"]
            self.commit("attempt-reserved")
            self.writer.hook("after-reservation")
            self.check()
            secret = os.environ.get(self.request["keyEnvironments"][arm["id"]])
            require(isinstance(secret, str) and secret, "Credential unavailable")
            self.writer.hook("before-transport-construction")
            self.check()
            transport = kernel.NativeHTTP()
            self.writer.hook("before-dispatch")
            self.check()
            self.invoked += 1
            reply = transport.dispatch(
                self.capture.store.artifact(task["request"]), secret, self.check
            )
            self.writer.hook("after-dispatch")
            saved, blobs = kernel.classify(reply, task, arm, self.questions)
            if (
                saved["status"] in {"completed", "invalid-output"}
                and saved["model"] is not None
                and arm["id"] in self.models
                and self.models[arm["id"]] != saved["model"]
            ):
                saved.update(status="model-rejected", result=None)
            if retryable(saved, self.ordinal):
                saved["backoffNs"] = backoff_bounds(self.ordinal)[0]
            for raw in blobs:
                self.writer.put(raw, phase="response")
            outcome = self.writer.put(canonical(saved), phase="outcome")
            self.writer.hook("after-response")
            self.commit("attempt-terminal", outcome=outcome)
            self.writer.hook("after-terminal")
            self.attempt_deadline = None
            if self.report["usageCeilingExceeded"]:
                self.commit("run-stopped", reason="usage-ceiling-exceeded")
                break
            if saved["status"] == "completed":
                self.models[arm["id"]] = saved["model"]
                self.position, self.ordinal = self.position + 1, 1
                if self.position == len(self.plan["tasks"]):
                    self.commit("run-stopped", reason="complete")
                    break
            elif retryable(saved, self.ordinal):
                target = self.events[-1]["clockNs"] + saved["backoffNs"]
                self.ordinal += 1
                self.wait(target)
            else:
                self.commit("run-stopped", reason="terminal-failure")
                break

    def wait(self, target):
        while self.last_sample["clockNs"] < target:
            if self.limited():
                return
            time.sleep(
                min(0.25, max(0, target - self.last_sample["clockNs"]) / 1_000_000_000)
            )


def resume_native(root, request, *, confirm_request_digest, hook=None):
    request = copy.deepcopy(request)
    require(
        confirm_request_digest == sha(canonical(request)),
        "Current exact native resume request confirmation",
    )
    with StopWriter(root, hook) as writer:
        execution = NativeResume(writer, ResumeCapture(writer.root), request)
        execution.execute()
    report = inspect_resume(root)
    report.update(
        operation="resume",
        dispatchAttemptsInvoked=execution.invoked,
        inferenceCallsExecuted=None
        if any(
            event["type"] == "attempt-terminal"
            and execution.capture.store.value(event["outcome"])["dispatchObserved"]
            is None
            for event in execution.events[len(execution.capture.events) :]
        )
        else execution.invoked,
        authorizedDispatches=report["counts"]["reserved"]["dispatches"]
        - execution.capture.report["counts"]["reserved"]["dispatches"],
    )
    return report
