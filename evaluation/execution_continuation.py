"""Versioned mock continuation replay; exact original evidence is never rewritten."""

import copy
from pathlib import Path

from execution_checkpoint import (
    CHECKPOINT,
    bounded_read,
    build_checkpoint,
    load_checkpoint,
    reader_lock,
    replay_snapshot,
)
from execution_mock import SimulatedClock, validate_script
from execution_mock_codec import normalize_mock, reference
from execution_outcomes import retryable
from execution_plan import MAX_JOURNAL_BYTES, Store, charge, prepare
from execution_records import (
    MAX_EVENTS,
    PREFIX,
    authorization,
    caps,
    integer,
    items,
    run_id,
    utc,
)
from offline_bundle import (
    MAX_BYTES,
    MAX_TOTAL_BYTES,
    canonical,
    object_keys,
    require,
    sha,
)

CHECKPOINT_V2 = "normlab.mock-checkpoint/v2"
CONTROL_SCHEMA = "normlab.mock-continuation-request/v1"
EVENT_FIELDS = "schema id runId invocationId sequence previousDigest type taskId turnId attemptId ordinal clockNs observedAt request budgetDelta outcome stopReason"
MAX_INVOCATIONS = 128


def cursor(report):
    for index, task in enumerate(report["taskOutcomes"]):
        final = task["final"]
        if final is None:
            return index, 1
        if final["status"] != "completed":
            ordinal = len(task["attemptIds"])
            require(
                retryable(final, ordinal) and type(final["backoffNs"]) is int,
                "Non-retryable terminal outcome cannot resume",
            )
            return index, ordinal + 1
    return len(report["taskOutcomes"]), 1


def completed_models(plan, report):
    models = {}
    for task, saved in zip(plan["tasks"], report["taskOutcomes"]):
        if saved["final"] is not None and saved["final"]["status"] == "completed":
            models.setdefault(task["armId"], saved["final"]["model"])
    return models


class Capture:
    def __init__(self, root):
        self.root = Path(root)
        self.raw = bounded_read(self.root / "checkpoint.json", MAX_JOURNAL_BYTES)
        self.checkpoint = Store.decode_json(self.raw)
        self.base_raw = (
            self.raw
            if self.checkpoint.get("schema") == CHECKPOINT
            else bounded_read(self.root / "checkpoint-v1.json", MAX_JOURNAL_BYTES)
        )
        self.base, self.base_report = load_checkpoint(root, snapshot_raw=self.base_raw)
        self.base_digest = sha(self.base_raw)
        self.store = Store(root)
        metadata = {
            "checkpoint.json": self.raw,
            "intent.json": bounded_read(self.root / "intent.json", MAX_BYTES),
            "mock-script.json": bounded_read(self.root / "mock-script.json", MAX_BYTES),
        }
        if self.raw != self.base_raw:
            metadata["checkpoint-v1.json"] = self.base_raw
        self.store.files.update(metadata)
        self.store.total = sum(map(len, metadata.values()))
        require(self.store.total <= MAX_TOTAL_BYTES, "Continuation byte cap")
        self.plan = prepare(self.store)
        self.intent = Store.decode_json(metadata["intent.json"])
        self.script = validate_script(
            Store.decode_json(metadata["mock-script.json"]), self.plan, self.store
        )
        self.events = self.checkpoint["journal"]
        if self.checkpoint["schema"] == CHECKPOINT:
            self.projected = copy.deepcopy(self.events)
            self.report = self.base_report
            self.limits = dict(self.plan["caps"])
            self.invocations = []
        else:
            object_keys(
                self.checkpoint,
                "schema baseDigest intentDigest scriptDigest run journal",
            )
            require(
                self.checkpoint["schema"] == CHECKPOINT_V2
                and self.checkpoint["baseDigest"] == self.base_digest,
                "Continuation schema/base binding",
            )
            run, self.report, self.projected, self.limits, self.invocations = (
                self.derive(self.events)
            )
            require(
                self.checkpoint == self.frame(self.events, run),
                "Derived continuation checkpoint binding",
            )

    def projection(self, events):
        checkpoint = build_checkpoint(
            self.intent, events, self.store, self.base["scriptDigest"]
        )
        return replay_snapshot(self.store, checkpoint["run"], events)

    def run_view(self, events, report):
        run = copy.deepcopy(self.intent)
        run.update({key: report[key] for key in ("state", "stopReason", "counts")})
        run["journalHead"] = events[-1]["id"] if events else None
        run["lastClockNs"] = (
            events[-1]["clockNs"] if events else run["clock"]["startNs"]
        )
        return run

    def frame(self, events, run):
        return {
            "schema": CHECKPOINT_V2,
            "baseDigest": self.base_digest,
            "intentDigest": self.base["intentDigest"],
            "scriptDigest": self.base["scriptDigest"],
            "run": run,
            "journal": events,
        }

    def prefix_report(self, projected, raw_events):
        report = self.projection(projected)
        if report["state"] == "finished":
            stopped = next(
                event
                for event in reversed(raw_events)
                if event["type"] == "run-stopped"
            )
            report["stopReason"] = stopped["stopReason"]
        return report

    def request_check(self, request, events, report, limits, projected):
        object_keys(
            request,
            "schema runId planDigest checkpointDigest journalHead action clock nowNs observedAt caps expiresAt authorization attemptId outcome",
        )
        require(request["schema"] == CONTROL_SCHEMA, "Continuation request schema")
        prior_raw = (
            self.base_raw
            if len(events) == len(self.base["journal"])
            else canonical(self.frame(events, self.run_view(events, report)))
        )
        require(
            request["runId"] == self.intent["id"]
            and request["planDigest"] == self.intent["planDigest"]
            and request["checkpointDigest"] == sha(prior_raw)
            and request["journalHead"] == (events[-1]["id"] if events else None),
            "Request exact execution/plan/checkpoint/head",
        )
        require(
            request["action"] in {"resume", "stop", "adopt-saved-outcome"},
            "Continuation action",
        )
        require(
            request["clock"] == self.intent["clock"],
            "Clock source/epoch/units/deadline continuity",
        )
        integer(request["nowNs"])
        previous = events[-1]["clockNs"] if events else self.intent["clock"]["startNs"]
        require(request["nowNs"] >= previous, "Clock reading regression")
        clock = SimulatedClock(self.script["clock"])
        clock.value = request["nowNs"]
        require(
            clock.timestamp() == request["observedAt"],
            "Exact simulated clock/UTC mapping",
        )
        authorization(request["authorization"])
        observed, authorized, expires = (
            utc(request["observedAt"]),
            utc(request["authorization"]["authorizedAt"]),
            utc(request["expiresAt"]),
        )
        require(
            authorized <= observed < expires,
            "Current continuation authorization validity",
        )
        if events:
            require(
                authorized >= utc(events[-1]["observedAt"]),
                "Fresh authorization for current head",
            )
        caps(request["caps"])
        require(
            all(request["caps"][key] <= value for key, value in limits.items()),
            "Continuation cannot increase effective caps",
        )
        require(
            all(
                request["caps"][key] >= consumed
                for key, consumed in report["counts"]["reserved"].items()
            ),
            "Continuation caps must cover already-reserved totals",
        )
        if request["action"] == "resume":
            require(
                request["attemptId"] is None and request["outcome"] is None,
                "Resume has no adoption target",
            )
            require(
                not report["unknownAttemptIds"],
                "Unknown attempt cannot be redispatched",
            )
            require(
                report["state"] != "finished"
                or report["stopReason"] == "operator-stop",
                "Finished execution cannot resume",
            )
            index, _ = cursor(report)
            require(
                index == len(self.plan["tasks"])
                or request["nowNs"] < self.intent["clock"]["deadlineNs"],
                "Original deadline expired",
            )
        else:
            require(
                report["state"] == "paused-unknown"
                and request["attemptId"] in report["unknownAttemptIds"],
                "Resolution targets original paused unknown attempt",
            )
            if request["action"] == "stop":
                require(request["outcome"] is None, "Stop has no adopted outcome")
            else:
                self.adoption(request, report, projected)

    def adoption(self, request, report, projected):
        reserved = next(
            event
            for event in projected
            if event["type"] == "attempt-reserved"
            and event["attemptId"] == request["attemptId"]
        )
        index = next(
            i
            for i, task in enumerate(self.intent["tasks"])
            if task["taskId"] == reserved["taskId"]
        )
        task = self.plan["tasks"][index]
        arm = next(arm for arm in self.plan["arms"] if arm["id"] == task["armId"])
        ordinal = reserved["ordinal"]
        spec = self.script["tasks"][index]["attempts"][ordinal - 1]
        expected, blobs = normalize_mock(
            spec,
            task,
            arm,
            request["attemptId"],
            ordinal,
            completed_models(self.plan, report),
        )
        require(
            expected["response"] is not None,
            "Adoption requires saved response-backed mock evidence",
        )
        require(
            self.store.value(request["outcome"]) == expected,
            "Adoption exact response/model/result/usage normalization",
        )
        for _, raw in blobs:
            require(
                self.store.artifact(reference(raw)) == raw,
                "Original mock response/result bytes",
            )
        return index, ordinal

    def derive(self, events):
        items(events, maximum=MAX_EVENTS)
        prefix_length = len(self.base["journal"])
        require(
            events[:prefix_length] == self.base["journal"],
            "Original 5b journal prefix preserved",
        )
        projected = copy.deepcopy(self.base["journal"])
        limits, invocations = dict(self.plan["caps"]), []
        ids = {self.intent["id"], self.intent["initialInvocationId"]}
        current, control_ref, invocation = None, None, None
        applied = False
        head = events[prefix_length - 1]["id"] if prefix_length else None
        last_clock = (
            events[prefix_length - 1]["clockNs"]
            if prefix_length
            else self.intent["clock"]["startNs"]
        )
        last_utc = events[prefix_length - 1]["observedAt"] if prefix_length else None
        for index in range(prefix_length, len(events)):
            event = events[index]
            object_keys(event, EVENT_FIELDS + " control")
            require(
                event["schema"] == PREFIX + "event/v2", "Continuation event version"
            )
            integer(event["sequence"], 1)
            require(
                event["sequence"] == index + 1
                and event["previousDigest"] == head
                and event["runId"] == self.intent["id"],
                "Raw continuation event chain",
            )
            require(
                event["id"]
                == sha(canonical({k: v for k, v in event.items() if k != "id"})),
                "Raw continuation event identity",
            )
            integer(event["clockNs"])
            require(
                event["clockNs"] >= last_clock
                and (last_utc is None or utc(event["observedAt"]) >= utc(last_utc)),
                "Continuation elapsed/UTC regression",
            )
            clock = SimulatedClock(self.script["clock"])
            clock.value = event["clockNs"]
            require(
                clock.timestamp() == event["observedAt"],
                "Continuation exact simulated timestamp",
            )
            kind = event["type"]
            if kind == "invocation-started":
                require(
                    len(invocations) < MAX_INVOCATIONS, "Continuation invocation cap"
                )
                run_id(event["invocationId"])
                require(
                    event["invocationId"] not in ids,
                    "Fresh continuation invocation UUID",
                )
                require(
                    all(
                        event[key] is None
                        for key in (
                            "taskId",
                            "turnId",
                            "attemptId",
                            "ordinal",
                            "request",
                            "outcome",
                            "stopReason",
                        )
                    )
                    and event["budgetDelta"] == {key: 0 for key in limits},
                    "Invocation marker fields",
                )
                caps(event["budgetDelta"])
                current = self.store.value(event["control"])
                report = self.prefix_report(projected, events[:index])
                self.request_check(current, events[:index], report, limits, projected)
                require(
                    event["clockNs"] == current["nowNs"]
                    and event["observedAt"] == current["observedAt"],
                    "Invocation observation binding",
                )
                if current["action"] == "resume" and report["state"] == "finished":
                    require(
                        projected[-1]["type"] == "run-stopped"
                        and projected[-1]["stopReason"] == "operator-stop",
                        "Only clean operator stop can be cleared",
                    )
                    projected.pop()
                limits, control_ref, invocation, applied = (
                    dict(current["caps"]),
                    event["control"],
                    event["invocationId"],
                    False,
                )
                ids.add(invocation)
                invocations.append(
                    {
                        "id": invocation,
                        "action": current["action"],
                        "checkpointBefore": current["checkpointDigest"],
                        "journalHeadBefore": current["journalHead"],
                        "attemptId": current["attemptId"],
                        "applied": current["action"] == "resume",
                        "adoptionValidated": False,
                    }
                )
            else:
                require(
                    current is not None and event["invocationId"] == invocation,
                    "Effect requires current authorized invocation",
                )
                require(
                    kind
                    in {
                        "attempt-reserved",
                        "attempt-observed",
                        "attempt-terminal",
                        "run-stopped",
                    },
                    "Continuation effect kind",
                )
                if current["action"] == "stop":
                    require(
                        utc(event["observedAt"]) < utc(current["expiresAt"]),
                        "Stop authorization expired before application",
                    )
                    require(
                        not applied
                        and kind == "run-stopped"
                        and event["stopReason"] == "unknown-outcome",
                        "Stop resolution cannot dispatch or clear unknown",
                    )
                    applied = True
                elif current["action"] == "adopt-saved-outcome":
                    if not applied:
                        require(
                            utc(event["observedAt"]) < utc(current["expiresAt"]),
                            "Adoption authorization expired before application",
                        )
                        require(
                            kind == "attempt-terminal"
                            and event["attemptId"] == current["attemptId"]
                            and event["outcome"] == current["outcome"],
                            "Adoption reconciles only its original attempt/outcome",
                        )
                        self.adoption(current, self.projection(projected), projected)
                        applied = True
                    else:
                        require(
                            kind == "run-stopped"
                            and event["stopReason"] in {"complete", "terminal-failure"},
                            "Adoption cannot implicitly continue execution",
                        )
                if event["control"] is not None:
                    require(
                        current["action"] == "resume"
                        and kind == "run-stopped"
                        and event["stopReason"] == "operator-stop"
                        and event["control"] == control_ref
                        and utc(event["observedAt"]) >= utc(current["expiresAt"]),
                        "Authorization-expiry stop evidence",
                    )
                if kind == "attempt-reserved":
                    require(
                        current["action"] == "resume"
                        and utc(current["authorization"]["authorizedAt"])
                        <= utc(event["observedAt"])
                        < utc(current["expiresAt"]),
                        "Reservation within current authorization",
                    )
                    prior = self.projection(projected)
                    task = next(
                        task
                        for task, ids_ in zip(self.plan["tasks"], self.intent["tasks"])
                        if ids_["taskId"] == event["taskId"]
                    )
                    require(
                        all(
                            prior["counts"]["reserved"][key] + value <= limits[key]
                            for key, value in charge(self.plan, task).items()
                        ),
                        "All past charges stay within continuation caps",
                    )
                if applied:
                    invocations[-1]["applied"] = True
                    invocations[-1]["adoptionValidated"] = (
                        current["action"] == "adopt-saved-outcome"
                    )
                normalized = {
                    key: value for key, value in event.items() if key != "control"
                }
                if kind == "run-stopped" and event["stopReason"] == "budget-exhaustion":
                    prior = self.projection(projected)
                    pending, _ = cursor(prior)
                    require(
                        pending < len(self.plan["tasks"]),
                        "Budget stop requires pending work",
                    )
                    next_charge = charge(self.plan, self.plan["tasks"][pending])
                    require(
                        any(
                            prior["counts"]["reserved"][key] + value > limits[key]
                            for key, value in next_charge.items()
                        ),
                        "Effective continuation cap exhaustion",
                    )
                    normalized["stopReason"] = "operator-stop"
                normalized.update(
                    schema=PREFIX + "event/v1",
                    invocationId=self.intent["initialInvocationId"],
                    sequence=len(projected) + 1,
                    previousDigest=projected[-1]["id"] if projected else None,
                )
                normalized["id"] = sha(
                    canonical({k: v for k, v in normalized.items() if k != "id"})
                )
                projected.append(normalized)
                if event["outcome"] is not None:
                    self.store.value(event["outcome"])
            head, last_clock, last_utc = (
                event["id"],
                event["clockNs"],
                event["observedAt"],
            )
        require(invocations, "Version 2 requires an explicit invocation")
        report = self.prefix_report(projected, events)
        run = self.run_view(events, report)
        report.update(
            schema="normlab.mock-continuation-replay/v1",
            journalHead=head,
            lastObservedAt=last_utc,
        )
        report["mockExecution"] = {
            "checkpointSchema": CHECKPOINT_V2,
            "scriptDigest": self.base["scriptDigest"],
            "baseCheckpointDigest": self.base_digest,
            "clockSimulated": True,
            "clockContinuityChecked": True,
            "authorizationAttested": False,
            "durabilityPolicy": "posix-fsync-atomic-checkpoint/v1",
            "resumeSupported": True,
            "effectiveCaps": limits,
            "invocations": invocations,
            "committedMockOutcomes": sum(
                event["type"] == "attempt-terminal" for event in projected
            ),
            "resolvedUnknownAttemptIds": [
                entry["attemptId"]
                for entry in invocations
                if entry["applied"] and entry["action"] != "resume"
            ],
            "continuationStopReason": "authorization-expired"
            if events[-1]["type"] == "run-stopped" and events[-1]["control"] is not None
            else report["stopReason"],
        }
        return run, report, projected, limits, invocations


def inspect_continuation(root):
    with reader_lock(root):
        return Capture(root).report


def continuation_request(
    root,
    *,
    action,
    now_ns,
    expires_at,
    operator_authorization,
    attempt=None,
    outcome=None,
    limits=None,
):
    """Prepare data for explicit operator approval; never saves or grants live authority."""
    with reader_lock(root):
        capture = Capture(root)
        clock = SimulatedClock(capture.script["clock"])
        clock.value = now_ns
        return {
            "schema": CONTROL_SCHEMA,
            "runId": capture.intent["id"],
            "planDigest": capture.intent["planDigest"],
            "checkpointDigest": sha(capture.raw),
            "journalHead": capture.events[-1]["id"] if capture.events else None,
            "action": action,
            "clock": copy.deepcopy(capture.intent["clock"]),
            "nowNs": now_ns,
            "observedAt": clock.timestamp(),
            "caps": dict(capture.limits if limits is None else limits),
            "expiresAt": expires_at,
            "authorization": operator_authorization,
            "attemptId": attempt,
            "outcome": outcome,
        }
