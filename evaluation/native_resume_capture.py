"""Read-only native continuation replay; recorded authorization never grants I/O."""

import copy
import re
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from execution_checkpoint import (
    bounded_read,
    build_checkpoint,
    reader_lock,
    replay_snapshot,
)
from execution_decisions import permit_caps
from execution_live_kernel import verify_normalization
from execution_mock_codec import make_event
from execution_outcomes import retryable
from execution_plan import MAX_JOURNAL_BYTES, Store
from execution_records import (
    MAX_EVENTS,
    authorization,
    caps,
    integer,
    items,
    run_id,
    utc,
)
from offline_bundle import MAX_BYTES, canonical, object_keys, require, sha
from runtime_archive_format import pin_modules
from runtime_archive_reader import read_archive
from runtime_capture import RuntimeSnapshot
from runtime_live_capture import NativeCapture

REQUEST = "normlab.native-resume-request/v1"
CHECKPOINT = "normlab.native-resume-checkpoint/v1"
BASE = "native-resume-base"
MODE = "stage1-bounded-schedule/v1"
MODULES = (
    "native_resume_capture.py",
    "native_resume_authority.py",
    "native_resume_execution.py",
    "native_resume_cli.py",
    "native_stop_resolution.py",
    # Transitive local dependencies of the frozen native Stage1/compiler imports.
    "anchor.py",
    "classification_v3.py",
    "mellea_candidate.py",
    "offline_contract.py",
    "offline_score_contract.py",
    "offline_stage1.py",
    "offline_stage1_reference.py",
    "offline_stage1_scoring.py",
    "offline_stage1_source.py",
    "offline_task_contract.py",
    "proxyapi_config.py",
    "score_stage1_providers.py",
    "score_stage1_retries_v2.py",
    "stage1_provider_executor.py",
    "stage1_provider_wire.py",
    "stage1_retry_executor_v2.py",
    "stage1_wire_v2.py",
    "verifier_capture.py",
)


def code_pins():
    modules = (
        *MODULES,
        "runtime_archive_reader.py",
        "runtime_archive_export.py",
        *(name + ".py" for name in pin_modules("live-capture")),
    )
    return {name: sha(Path(__file__).with_name(name).read_bytes()) for name in modules}


def cursor(report):
    require(not report["unknownAttemptIds"], "Unknown reservation blocks native resume")
    require(not report["usageCeilingExceeded"], "Usage violation blocks native resume")
    for index, task in enumerate(report["taskOutcomes"]):
        final = task["final"]
        if final is None:
            return index, 1
        if final["status"] != "completed":
            ordinal = len(task["attemptIds"])
            require(
                retryable(final, ordinal) and type(final["backoffNs"]) is int,
                "Only a recorded eligible bounded retry may resume",
            )
            return index, ordinal + 1
    return len(report["taskOutcomes"]), 1


class ResumeCapture:
    """Caller holds a local writer/shared reader lock; no clock/key/claim lookup."""

    def __init__(self, root):
        self.root = Path(root)
        self.raw = bounded_read(self.root / "checkpoint.json", MAX_JOURNAL_BYTES)
        self.saved = Store.decode_json(self.raw)
        continued = self.saved.get("schema") == CHECKPOINT
        if continued:
            object_keys(self.saved, "schema baseArchiveId codePins run journal")
            archive = read_archive(self.root / BASE)
            self.base = NativeCapture(self.root / BASE / "source")
            self.snapshot = RuntimeSnapshot(self.base)
            require(
                archive.index["archiveId"] == self.saved["baseArchiveId"]
                and archive.files["capture.json"] == canonical(self.snapshot.manifest)
                and self.saved["codePins"] == code_pins(),
                "Native resume immutable base and installed continuation pins",
            )
            self.archive_id = archive.index["archiveId"]
        else:
            self.base = NativeCapture(self.root)
            self.snapshot = RuntimeSnapshot(self.base)
            self.archive_id = None
        self.intent, self.plan = self.base.intent, self.base.plan
        self.store = Store(self.root)
        for name in ("plan.json", "intent.json"):
            require(
                bounded_read(self.root / name, MAX_BYTES) == self.snapshot.files[name],
                "Unchanged original native resume input",
            )
        self.original_limits, self.permit = permit_caps(
            self.plan, self.intent, self.store
        )
        self.events = self.saved["journal"]
        if continued:
            self.report, self.projected, self.limits, self.invocations = self.derive(
                self.events
            )
            require(self.invocations, "Native resume checkpoint requires an invocation")
            require(
                canonical(self.saved)
                == canonical(self.frame(self.events, self.report)),
                "Regenerated native resume checkpoint",
            )
        else:
            self.report = self.base.report
            self.projected = copy.deepcopy(self.events)
            self.limits = dict(self.original_limits)
            self.invocations = []

    def binding(self, events=None, report=None):
        events = self.events if events is None else events
        report = self.report if report is None else report
        raw = (
            self.base.raw
            if len(events) == len(self.base.events)
            else canonical(self.frame(events, report))
        )
        return {
            "runId": self.intent["id"],
            "planDigest": self.intent["planDigest"],
            "baseCheckpointDigest": sha(self.base.raw),
            "checkpointDigest": sha(raw),
            "journalHead": events[-1]["id"] if events else None,
        }

    def request_check(self, request, events, report, limits):
        object_keys(
            request,
            "schema runId planDigest baseCheckpointDigest checkpointDigest journalHead action invocationId caps expiresAt authorization externalCeilingMicros keyEnvironments",
        )
        require(
            request["schema"] == REQUEST and request["action"] == "resume",
            "Native resume request schema/action",
        )
        require(
            all(
                request[key] == value
                for key, value in self.binding(events, report).items()
            ),
            "Exact resume run/plan/base/checkpoint/head binding",
        )
        run_id(request["invocationId"])
        require(
            request["invocationId"]
            not in {self.intent["id"], self.intent["initialInvocationId"]},
            "New native invocation UUID",
        )
        authorization(request["authorization"])
        previous = (
            report["lastObservedAt"] or self.permit["authorization"]["authorizedAt"]
        )
        require(
            utc(previous)
            <= utc(request["authorization"]["authorizedAt"])
            < utc(request["expiresAt"])
            <= utc(self.permit["expiresAt"]),
            "Fresh resume authorization inside original permit validity",
        )
        caps(request["caps"])
        require(
            all(
                report["counts"]["reserved"][key] <= request["caps"][key] <= value
                for key, value in limits.items()
            ),
            "Resume cannot increase caps or erase historical charges",
        )
        integer(request["externalCeilingMicros"], 1)
        require(
            request["externalCeilingMicros"]
            == self.permit["externalSpending"]["ceilingMicros"],
            "Original external spending declaration confirmation",
        )
        keys = request["keyEnvironments"]
        require(
            isinstance(keys, dict)
            and set(keys) == {a["id"] for a in self.plan["arms"]}
            and all(
                isinstance(key, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key)
                for key in keys.values()
            ),
            "Explicit credential environment names only",
        )
        if self.base.checkpoint.get("mode") is not None:
            # NativeCapture already verified full lineage with the read-only reader.
            # Do not demand this reader's Python digest for historical inspection.
            original = self.store.value(self.plan["pins"]["definitions"])["metadata"]
            require(
                keys
                == {
                    arm: p["keyEnvironment"] for arm, p in original["providers"].items()
                },
                "Frozen Stage1 credential references",
            )
        require(
            report["state"] != "finished" or report["stopReason"] == "operator-stop",
            "Only a clean native stop can resume",
        )
        index, _ = cursor(report)
        require(
            index < len(self.plan["tasks"]), "Native schedule has no pending suffix"
        )

    def observation(self, request, sample, *, last_clock, last_utc):
        object_keys(sample, "policy source units suspendAware epoch clockNs observedAt")
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
            ),
            "Current same Linux host/boot/source capability",
        )
        integer(sample["clockNs"])
        require(
            last_clock <= sample["clockNs"] < self.intent["clock"]["deadlineNs"]
            and utc(last_utc) <= utc(sample["observedAt"])
            and utc(self.permit["authorization"]["authorizedAt"])
            <= utc(sample["observedAt"])
            and utc(request["authorization"]["authorizedAt"])
            <= utc(sample["observedAt"])
            < utc(request["expiresAt"]),
            "Current resume clock/deadline/authorization continuity",
        )

    def projection(self, events):
        derived = build_checkpoint(
            self.intent, events, self.store, "native-resume-projection"
        )
        report = replay_snapshot(self.store, derived["run"], events)
        verify_normalization(self.plan, self.intent, events, self.store, mode=MODE)
        return report

    def frame(self, events, report):
        run = copy.deepcopy(self.intent)
        run.update(
            {
                key: copy.deepcopy(report[key])
                for key in ("state", "stopReason", "counts")
            }
        )
        run["journalHead"] = events[-1]["id"] if events else None
        run["lastClockNs"] = (
            events[-1]["clockNs"] if events else self.intent["clock"]["startNs"]
        )
        return {
            "schema": CHECKPOINT,
            "baseArchiveId": self.archive_id,
            "codePins": code_pins(),
            "run": run,
            "journal": events,
        }

    def derive(self, events):
        items(events, maximum=MAX_EVENTS)
        length = len(self.base.events)
        require(
            events[:length] == self.base.events,
            "Original native journal prefix unchanged",
        )
        projected = copy.deepcopy(self.base.events)
        report = copy.deepcopy(self.base.report)
        limits, invocations = dict(self.original_limits), []
        current = None
        last_clock = self.base.checkpoint["run"]["lastClockNs"]
        last_utc = (
            report["lastObservedAt"] or self.permit["authorization"]["authorizedAt"]
        )
        for index in range(length, len(events)):
            event = events[index]
            kind = event["type"]
            integer(event["clockNs"])
            require(
                event["clockNs"] >= last_clock
                and utc(event["observedAt"]) >= utc(last_utc),
                "Native continuation clock/UTC regression",
            )
            event_clock = SimpleNamespace(
                value=event["clockNs"], timestamp=lambda: event["observedAt"]
            )
            if kind == "invocation-started":
                require(len(invocations) < 128, "Native continuation invocation cap")
                current = self.store.value(event["control"])
                self.request_check(current, events[:index], report, limits)
                require(
                    current["invocationId"] not in invocations, "Invocation UUID reuse"
                )
                self.observation(
                    current,
                    {
                        **{
                            k: self.intent["clock"][k]
                            for k in (
                                "policy",
                                "source",
                                "units",
                                "suspendAware",
                                "epoch",
                            )
                        },
                        "clockNs": event["clockNs"],
                        "observedAt": event["observedAt"],
                    },
                    last_clock=last_clock,
                    last_utc=last_utc,
                )
                expected = make_event(
                    self.intent,
                    events[:index],
                    event_clock,
                    self.plan,
                    kind,
                    invocation=current["invocationId"],
                    control=event["control"],
                    version=2,
                )
                if report["state"] == "finished":
                    require(
                        projected[-1]["type"] == "run-stopped"
                        and projected[-1]["stopReason"] == "operator-stop",
                        "Only clean stop projection can reopen",
                    )
                    projected.pop()
                limits = dict(current["caps"])
                invocations.append(current["invocationId"])
            else:
                require(
                    current is not None
                    and kind in {"attempt-reserved", "attempt-terminal", "run-stopped"},
                    "Effect requires a native resume invocation",
                )
                if kind == "attempt-terminal":
                    # The current reservation is deliberately unknown until terminal commit.
                    task_index = next(
                        i
                        for i, ids_ in enumerate(self.intent["tasks"])
                        if ids_["taskId"] == event["taskId"]
                    )
                    ordinal = event["ordinal"]
                elif kind == "attempt-reserved":
                    task_index, ordinal = cursor(report)
                else:
                    task_index, ordinal = 0, 1
                expected = make_event(
                    self.intent,
                    events[:index],
                    event_clock,
                    self.plan,
                    kind,
                    task_index=min(task_index, len(self.plan["tasks"]) - 1),
                    ordinal=ordinal,
                    outcome=event["outcome"],
                    reason=event["stopReason"],
                    invocation=current["invocationId"],
                    version=2,
                )
                if kind == "attempt-reserved":
                    self.observation(
                        current,
                        {
                            **{
                                k: self.intent["clock"][k]
                                for k in (
                                    "policy",
                                    "source",
                                    "units",
                                    "suspendAware",
                                    "epoch",
                                )
                            },
                            "clockNs": event["clockNs"],
                            "observedAt": event["observedAt"],
                        },
                        last_clock=last_clock,
                        last_utc=last_utc,
                    )
                    task = self.plan["tasks"][task_index]
                    from execution_plan import charge

                    require(
                        all(
                            report["counts"]["reserved"][key] + value <= limits[key]
                            for key, value in charge(self.plan, task).items()
                        ),
                        "Native continuation effective caps",
                    )
                projected.append(
                    make_event(
                        self.intent,
                        projected,
                        event_clock,
                        self.plan,
                        kind,
                        task_index=min(task_index, len(self.plan["tasks"]) - 1),
                        ordinal=ordinal,
                        outcome=event["outcome"],
                        reason=event["stopReason"],
                    )
                )
            require(
                canonical(event) == canonical(expected),
                "Regenerated raw native continuation event",
            )
            report = self.projection(projected)
            if report["state"] == "created":
                report["state"] = "running"
            report["journalHead"] = event["id"]
            report["lastObservedAt"] = event["observedAt"]
            last_clock, last_utc = event["clockNs"], event["observedAt"]
        return report, projected, limits, invocations


def prepare_resume(
    root, *, authorization_record, expires_at, key_environments, limits=None
):
    with reader_lock(root):
        capture = ResumeCapture(root)
        request = {
            "schema": REQUEST,
            **capture.binding(),
            "action": "resume",
            "invocationId": str(uuid4()),
            "caps": copy.deepcopy(capture.limits if limits is None else limits),
            "expiresAt": expires_at,
            "authorization": copy.deepcopy(authorization_record),
            "externalCeilingMicros": capture.permit["externalSpending"][
                "ceilingMicros"
            ],
            "keyEnvironments": copy.deepcopy(key_environments),
        }
        capture.request_check(request, capture.events, capture.report, capture.limits)
        return request


def inspect_unlocked(root):
    capture = ResumeCapture(root)
    report = copy.deepcopy(capture.report)
    report.update(
        schema="normlab.native-resume-report/v1",
        **capture.binding(),
        checkpointSchema=capture.saved["schema"],
        invocationIds=capture.invocations,
        effectiveCaps=capture.limits,
        originalDeadlineNs=capture.intent["clock"]["deadlineNs"],
        localCaptureOnly=True,
        authorizationAttested=False,
        recordedClockVerified=False,
        resumeSupported=True,
        adoptionSupported=False,
        executionReady=False,
        dispatchAttemptsInvoked=0,
        inferenceCallsExecuted=0,
        semanticQualityEvidence=False,
    )
    return report


def inspect_resume(root):
    with reader_lock(root):
        return inspect_unlocked(root)
