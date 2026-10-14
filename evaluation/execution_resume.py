"""Explicit authorized mock continuation; unknown work is never automatically resent."""

import copy
import fcntl
import os
import stat
from uuid import uuid4

from execution_checkpoint import CHECKPOINT, DurableWriter, bounded_read
from execution_continuation import (
    MAX_INVOCATIONS,
    Capture,
    completed_models,
    cursor,
    inspect_continuation,
)
from execution_mock import MockExecution, MockTransport
from execution_mock_codec import make_event
from execution_plan import MAX_JOURNAL_BYTES, charge
from execution_records import MAX_EVENTS, utc
from offline_bundle import MAX_BYTES, MAX_FILES, MAX_TOTAL_BYTES, canonical, require


class ContinuationWriter(DurableWriter):
    def __enter__(self):
        require(
            self.lock is None and not self.poisoned, "Fresh continuation writer handle"
        )
        self.root = self.root.resolve(strict=True)
        require(self.root.is_dir(), "Existing continuation directory")
        try:
            self.lock = os.open(
                self.root / ".writer.lock", os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
            )
            require(
                stat.S_ISREG(os.fstat(self.lock).st_mode), "Regular continuation lock"
            )
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for number, path in enumerate(self.root.rglob("*"), 1):
                require(number <= MAX_FILES, "Continuation inventory entry cap")
                require(not path.is_symlink(), "Continuation inventory symlink")
                if path.is_dir():
                    self.inventory[str(path.relative_to(self.root))] = 0
                    continue
                info = path.stat()
                require(stat.S_ISREG(info.st_mode), "Continuation regular inventory")
                name = str(path.relative_to(self.root))
                limit = (
                    MAX_JOURNAL_BYTES
                    if name in {"checkpoint.json", "checkpoint-v1.json"}
                    or (path.parent == self.root and path.name.startswith(".pending-"))
                    else MAX_BYTES
                )
                require(info.st_size <= limit, "Continuation inventory file cap")
                self.inventory[name] = info.st_size
                require(
                    len(self.inventory) <= MAX_FILES
                    and sum(self.inventory.values()) <= MAX_TOTAL_BYTES,
                    "Continuation inventory aggregate caps",
                )
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self


class ResumeExecution(MockExecution):
    def __init__(self, writer, capture, request, *, transport=None):
        super().__init__(
            writer, capture.plan, capture.script, capture.intent, transport=transport
        )
        self.capture, self.request = capture, request
        self.events = list(capture.events)
        self.models = completed_models(self.plan, capture.report)
        self.clock.value = request["nowNs"]
        self.invocation = str(uuid4())
        self.control = None

    def commit(self, kind, *, task_index=0, ordinal=1, outcome=None, reason=None):
        control = (
            self.control
            if kind == "invocation-started" or reason == "authorization-expired"
            else None
        )
        event = make_event(
            self.intent,
            self.events,
            self.clock,
            self.plan,
            kind,
            task_index=task_index,
            ordinal=ordinal,
            outcome=outcome,
            reason="operator-stop" if reason == "authorization-expired" else reason,
            invocation=self.invocation,
            control=control,
            version=2,
        )
        events = [*self.events, event]
        run, _, _, _, _ = self.capture.derive(events)
        phase = {
            "invocation-started": "invocation",
            "attempt-reserved": "reserved",
            "attempt-terminal": "terminal",
            "attempt-observed": "observed",
            "run-stopped": "stop",
        }[kind]
        self.writer.publish(
            "checkpoint.json",
            canonical(self.capture.frame(events, run)),
            phase=phase,
            replace=True,
        )
        self.events = events
        self.clock.advance(self.script["clock"]["stepNs"])

    def current(self):
        return self.capture.derive(self.events)[0]

    def dispatch_allowed(self):
        return super().dispatch_allowed() and utc(self.clock.timestamp()) < utc(
            self.request["expiresAt"]
        )

    def stop_before_reservation(self, task):
        if utc(self.clock.timestamp()) >= utc(self.request["expiresAt"]):
            return "authorization-expired"
        if self.clock.value >= self.intent["clock"]["deadlineNs"]:
            return "deadline"
        reserved = self.current()["counts"]["reserved"]
        if any(
            reserved[key] + value > self.request["caps"][key]
            for key, value in charge(self.plan, task).items()
        ):
            return "budget-exhaustion"
        return None

    def execute(self):
        self.capture.request_check(
            self.request,
            self.capture.events,
            self.capture.report,
            self.capture.limits,
            self.capture.projected,
        )
        require(
            len(self.events) < MAX_EVENTS
            and len(self.capture.invocations) < MAX_INVOCATIONS,
            "Continuation event/invocation bounds",
        )
        require(
            self.transport is None or type(self.transport) is MockTransport,
            "Only built-in mock transport",
        )
        if self.capture.checkpoint["schema"] == CHECKPOINT:
            path = self.writer.root / "checkpoint-v1.json"
            if "checkpoint-v1.json" in self.writer.inventory:
                require(
                    bounded_read(path, MAX_JOURNAL_BYTES) == self.capture.base_raw,
                    "Existing original snapshot drift",
                )
            else:
                self.writer.publish(
                    "checkpoint-v1.json", self.capture.base_raw, phase="base"
                )
        self.control = self.writer.put(canonical(self.request), phase="authorization")
        self.commit("invocation-started")
        self.writer.hook("after-invocation")
        if self.request["action"] == "stop":
            self.commit("run-stopped", reason="unknown-outcome")
            return
        if self.request["action"] == "adopt-saved-outcome":
            index, ordinal = self.capture.adoption(
                self.request, self.capture.report, self.capture.projected
            )
            self.writer.hook("before-adoption")
            self.commit(
                "attempt-terminal",
                task_index=index,
                ordinal=ordinal,
                outcome=self.request["outcome"],
            )
            self.writer.hook("after-adoption")
            _, report, _, _, _ = self.capture.derive(self.events)
            final = report["taskOutcomes"][index]["final"]
            if final["status"] != "completed":
                self.commit("run-stopped", reason="terminal-failure")
            elif all(
                task["final"] is not None and task["final"]["status"] == "completed"
                for task in report["taskOutcomes"]
            ):
                self.commit("run-stopped", reason="complete")
            return
        index, ordinal = cursor(self.capture.report)
        self.writer.hook("before-transport-construction")
        if self.transport is None:
            self.transport = MockTransport()
        if ordinal > 1:
            previous_id = self.capture.report["taskOutcomes"][index]["attemptIds"][-1]
            previous = next(
                event
                for event in reversed(self.capture.projected)
                if event["type"] == "attempt-terminal"
                and event["attemptId"] == previous_id
            )
            saved = self.capture.store.value(previous["outcome"])
            remaining = max(
                0, previous["clockNs"] + saved["backoffNs"] - self.clock.value
            )
            if remaining:
                self.wait_backoff(remaining)
        self.execute_schedule(index, ordinal)


def continue_mock(root, request, *, hook=None, transport=None):
    request = copy.deepcopy(request)
    require(
        transport is None or type(transport) is MockTransport,
        "Only built-in mock transport",
    )
    with ContinuationWriter(root, hook) as writer:
        capture = Capture(writer.root)
        execution = ResumeExecution(writer, capture, request, transport=transport)
        execution.execute()
    return inspect_continuation(root)
