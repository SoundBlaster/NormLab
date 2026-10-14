"""Single-worker scripted mock execution; no SDK, credentials, network or resume."""

import copy
from datetime import timedelta

from execution_checkpoint import (
    DurableWriter,
    build_checkpoint,
    inspect_checkpoint,
)
from execution_mock_codec import make_event, model_rejected, normalize_mock
from execution_outcomes import TERMINAL, answer_schema, answers, retryable
from execution_plan import Store, charge, new_run, prepare
from execution_records import (
    ERROR_CLASSES,
    PREFIX,
    attempt_id,
    integer,
    items,
    utc,
)
from offline_bundle import MAX_BYTES, canonical, object_keys, require, sha

SCRIPT_SCHEMA = "normlab.mock-script/v1"


def validate_script(script, plan, store):
    object_keys(script, "schema clock tasks")
    require(script["schema"] == SCRIPT_SCHEMA, "Mock script schema")
    object_keys(script["clock"], "startNs utcStart stepNs")
    integer(script["clock"]["startNs"])
    integer(script["clock"]["stepNs"], 1000)
    utc(script["clock"]["utcStart"])
    items(script["tasks"], 1)
    require(len(script["tasks"]) == len(plan["tasks"]), "Mock script task denominator")
    definitions = answer_schema(store.value(plan["pins"]["outputSchema"]))
    arms = {arm["id"]: arm for arm in plan["arms"]}
    models, reachable = {}, True
    for scripted, task in zip(script["tasks"], plan["tasks"]):
        object_keys(scripted, "key attempts")
        require(scripted["key"] == task["key"], "Mock script task order")
        items(scripted["attempts"], 1, 3)
        arm = arms[task["armId"]]
        for ordinal, spec in enumerate(scripted["attempts"], 1):
            object_keys(spec, "status model answers errorClass statusCode latencyNs")
            require(
                spec["status"] in TERMINAL | {"unknown-outcome"},
                "Scripted mock outcome",
            )
            require(
                isinstance(spec["model"], str) and 0 < len(spec["model"]) <= 1024,
                "Mock model",
            )
            integer(spec["latencyNs"])
            require(
                spec["latencyNs"] <= arm["timeoutNs"],
                "Simulated latency exceeds request timeout",
            )
            if spec["status"] == "completed":
                answers(
                    {
                        "schema": PREFIX + "answers/v1",
                        "normalizer": arm["adapter"],
                        "answers": spec["answers"],
                    },
                    task,
                    arm,
                    definitions,
                )
            else:
                require(
                    spec["answers"] is None,
                    "Only completed mock responses contain answers",
                )
            if spec["status"] == "transport-failed":
                require(
                    spec["errorClass"] in ERROR_CLASSES,
                    "Sanitized mock transport class",
                )
            else:
                require(spec["errorClass"] is None, "No hidden mock transport error")
            if spec["status"] == "http-failed":
                integer(spec["statusCode"], 400)
                require(spec["statusCode"] <= 599, "Mock HTTP failure status")
            else:
                require(spec["statusCode"] is None, "No mock failure HTTP status")
            eligible = retryable(
                {
                    "status": spec["status"],
                    "errorClasses": [spec["errorClass"]] if spec["errorClass"] else [],
                },
                ordinal,
            )
            require(
                eligible == (ordinal < len(scripted["attempts"])),
                "Mock script must cover exactly the frozen retry path",
            )
            rejected = model_rejected(spec["model"], arm, models)
            if spec["status"] == "model-rejected":
                require(
                    rejected,
                    "Mock model rejection requires unaccepted or drifted model",
                )
            if reachable:
                if spec["status"] == "completed" and not rejected:
                    models.setdefault(arm["id"], spec["model"])
                elif not eligible:
                    reachable = False
    return script


class SimulatedClock:
    """Deterministic test clock, explicitly not host/boot/suspension attestation."""

    def __init__(self, definition):
        self.definition = definition
        self.value = definition["startNs"]

    def timestamp(self):
        delta = (self.value - self.definition["startNs"]) // 1000
        return (
            utc(self.definition["utcStart"]) + timedelta(microseconds=delta)
        ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def advance(self, delta):
        integer(delta)
        integer(self.value + delta)
        self.value += delta


class MockTransport:
    """One deterministic local invocation; no retries or imports behind dispatch."""

    def __init__(self):
        self.calls = []

    def dispatch(self, request_bytes, attempt, spec):
        self.calls.append({"attemptId": attempt, "requestBytes": request_bytes})
        return copy.deepcopy(spec)


class MockExecution:
    def __init__(self, writer, plan, script, intent, *, transport=None):
        self.writer, self.plan, self.script, self.intent = writer, plan, script, intent
        self.clock = SimulatedClock(script["clock"])
        self.script_digest = sha(canonical(script))
        self.events = []
        self.transport = transport
        self.models = {}

    def commit(self, kind, *, task_index=0, ordinal=1, outcome=None, reason=None):
        event = make_event(
            self.intent,
            self.events,
            self.clock,
            self.plan,
            kind,
            task_index=task_index,
            ordinal=ordinal,
            outcome=outcome,
            reason=reason,
        )
        events = [*self.events, event]
        checkpoint = build_checkpoint(
            self.intent, events, Store(self.writer.root), self.script_digest
        )
        phase = {
            "attempt-reserved": "reserved",
            "attempt-terminal": "terminal",
            "attempt-observed": "observed",
            "run-stopped": "stop",
        }[kind]
        self.writer.publish(
            "checkpoint.json", canonical(checkpoint), phase=phase, replace=True
        )
        self.events = events
        self.clock.advance(self.script["clock"]["stepNs"])

    def current(self):
        checkpoint = build_checkpoint(
            self.intent, self.events, Store(self.writer.root), self.script_digest
        )
        return checkpoint["run"]

    def stop_before_reservation(self, task):
        if self.clock.value >= self.intent["clock"]["deadlineNs"]:
            return "deadline"
        reserved = self.current()["counts"]["reserved"]
        if any(
            reserved[key] + value > self.plan["caps"][key]
            for key, value in charge(self.plan, task).items()
        ):
            return "budget-exhaustion"
        return None

    def save_outcome(self, spec, index, ordinal):
        task = self.plan["tasks"][index]
        arm = next(arm for arm in self.plan["arms"] if arm["id"] == task["armId"])
        saved, blobs = normalize_mock(
            spec,
            task,
            arm,
            attempt_id(self.intent["tasks"][index]["turnId"], ordinal),
            ordinal,
            self.models,
        )
        if saved["status"] == "completed":
            self.models.setdefault(arm["id"], spec["model"])
        for phase, raw in blobs:
            self.writer.put(raw, phase=phase)
        return saved, self.writer.put(canonical(saved), phase="outcome")

    def dispatch_allowed(self):
        return self.clock.value < self.intent["clock"]["deadlineNs"]

    def wait_backoff(self, delay):
        self.writer.hook("before-backoff")
        self.clock.advance(delay // 2)
        self.writer.hook("during-backoff")
        self.clock.advance(delay - delay // 2)
        self.writer.hook("after-backoff")

    def execute(self):
        initial = build_checkpoint(
            self.intent, [], Store(self.writer.root), self.script_digest
        )
        self.writer.publish(
            "checkpoint.json", canonical(initial), phase="initial", replace=True
        )
        self.writer.hook("before-transport-construction")
        if self.transport is None:
            self.transport = MockTransport()
        require(
            type(self.transport) is MockTransport,
            "Only built-in mock transport is supported",
        )
        self.execute_schedule()

    def execute_schedule(self, start_index=0, start_ordinal=1):
        for index, (task, scripted) in enumerate(
            zip(self.plan["tasks"], self.script["tasks"])
        ):
            if index < start_index:
                continue
            for ordinal, spec in enumerate(scripted["attempts"], 1):
                if index == start_index and ordinal < start_ordinal:
                    continue
                reason = self.stop_before_reservation(task)
                if reason:
                    self.commit("run-stopped", reason=reason)
                    return
                self.writer.hook("before-reservation")
                self.commit("attempt-reserved", task_index=index, ordinal=ordinal)
                self.writer.hook("after-reservation")
                if not self.dispatch_allowed():
                    return  # Charged reservation remains unknown; never dispatch after deadline.
                self.writer.hook("before-dispatch")
                request_bytes = Store(self.writer.root).artifact(task["request"])
                returned = self.transport.dispatch(
                    request_bytes,
                    attempt_id(self.intent["tasks"][index]["turnId"], ordinal),
                    spec,
                )
                self.clock.advance(returned["latencyNs"])
                self.writer.hook("after-dispatch")
                saved, ref = self.save_outcome(returned, index, ordinal)
                self.writer.hook("after-response")
                if saved["status"] == "unknown-outcome":
                    self.commit(
                        "attempt-observed",
                        task_index=index,
                        ordinal=ordinal,
                        outcome=ref,
                    )
                    return
                self.writer.hook("before-terminal")
                self.commit(
                    "attempt-terminal", task_index=index, ordinal=ordinal, outcome=ref
                )
                self.writer.hook("after-terminal")
                if saved["status"] == "completed":
                    break
                if not retryable(saved, ordinal):
                    self.commit("run-stopped", reason="terminal-failure")
                    return
                self.wait_backoff(saved["backoffNs"])
        self.writer.hook("before-finalization")
        self.commit("run-stopped", reason="complete")
        self.writer.hook("after-finalization")


def run_mock(input_directory, output, script, *, hook=None, transport=None):
    require(type(script) is dict, "Mock script object")
    require(
        transport is None or type(transport) is MockTransport,
        "Only built-in mock transport",
    )
    source = Store(input_directory)
    plan = prepare(source)
    script = copy.deepcopy(validate_script(script, plan, source))
    raw_script = canonical(script)
    require(len(raw_script) <= MAX_BYTES, "Mock script byte cap")
    clock = {
        "policy": plan["clockPolicy"],
        "source": "linux:CLOCK_BOOTTIME",
        "units": "nanoseconds",
        "suspendAware": True,
        "epoch": sha(canonical({"mockClock": script["clock"]})),
        "startNs": script["clock"]["startNs"],
        "deadlineNs": script["clock"]["startNs"] + plan["wallTimeNs"],
    }
    intent = new_run(plan, clock, evidence_kind="mock")
    with DurableWriter(output, hook) as writer:
        writer.publish("plan.json", source.read("plan.json"), phase="plan")
        for name, raw in source.files.items():
            if name.startswith("artifacts/"):
                writer.put(raw, phase="input")
        writer.publish("intent.json", canonical(intent), phase="intent")
        writer.publish("mock-script.json", raw_script, phase="script")
        execution = MockExecution(writer, plan, script, intent, transport=transport)
        execution.execute()
    return inspect_checkpoint(output)
