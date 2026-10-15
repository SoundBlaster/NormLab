"""Bounded mock runtime export projection; no bundle/archive is written."""

import json
from types import MappingProxyType

from execution_mock_codec import reference
from execution_plan import Store
from offline_bundle import (
    MAX_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    canonical,
    identity,
    require,
)
from runtime_capture import RuntimeSnapshot, capture_runtime


def journal_index(events):
    reservations, observations = {}, {}
    for event in events:
        if event["type"] == "attempt-reserved":
            reservations.setdefault(event["taskId"], []).append(event)
        elif event["type"] in {"attempt-observed", "attempt-terminal"}:
            observations.setdefault(event["attemptId"], []).append(
                {
                    "eventId": event["id"],
                    "invocationId": event["invocationId"],
                    "kind": event["type"],
                    "outcome": event["outcome"],
                }
            )
    return reservations, observations


def task_record(snapshot, task, ids, report, reservations, observations):
    attempts = []
    for event in reservations.get(ids["taskId"], []):
        history = observations.get(event["attemptId"], [])
        outcome = history[-1]["outcome"] if history else None
        saved = Store.decode_json(snapshot.files[outcome["path"]]) if outcome else None
        attempts.append(
            {
                "id": event["attemptId"],
                "ordinal": event["ordinal"],
                "invocationId": event["invocationId"],
                "reservationEventId": event["id"],
                "request": event["request"],
                "context": task["context"],
                "reserved": event["budgetDelta"],
                "outcomeHistory": history,
                "finalOutcome": outcome,
                "status": saved["status"] if saved else "unknown-outcome",
            }
        )
    final = report["final"]
    return {
        "schema": "normlab.runtime-export-task/v1",
        "taskId": ids["taskId"],
        "turnId": ids["turnId"],
        "key": task["key"],
        "caseId": task["caseId"],
        "armId": task["armId"],
        "repeat": task["repeat"],
        "stage": task["stage"],
        "source": task["source"],
        "candidate": task["candidate"],
        "request": task["request"],
        "context": task["context"],
        "questionIds": task["questionIds"],
        "status": final["status"]
        if final
        else "unknown-outcome"
        if attempts
        else "not-dispatched",
        "firstOutcome": attempts[0]["finalOutcome"] if attempts else None,
        "finalOutcome": attempts[-1]["finalOutcome"] if attempts else None,
        "attempts": attempts,
    }


class RuntimeExportProjection:
    def __init__(self, snapshot):
        require(
            type(snapshot) is RuntimeSnapshot, "Validated runtime snapshot required"
        )
        evidence_kind = snapshot.manifest["evidenceKind"]
        require(
            evidence_kind in {"mock", "live-capture"},
            "Runtime projection evidence kind",
        )
        self._snapshot = snapshot
        blobs = {}

        def put(value):
            raw = canonical(value)
            require(len(raw) <= MAX_BYTES, "Runtime projection artifact cap")
            ref = reference(raw)
            blobs[ref["path"]] = raw
            return ref

        report, plan, intent, events = (
            snapshot.report,
            snapshot.plan,
            snapshot.intent,
            snapshot.events,
        )
        reservations, observations = journal_index(events)
        records = [
            task_record(snapshot, task, ids, outcome, reservations, observations)
            for task, ids, outcome in zip(
                plan["tasks"], intent["tasks"], report["taskOutcomes"]
            )
        ]
        statuses = {}
        for record in records:
            statuses[record["status"]] = statuses.get(record["status"], 0) + 1
        counts = {
            "plannedTasks": len(records),
            "plannedQuestions": sum(len(r["questionIds"]) for r in records),
            "attempts": sum(len(r["attempts"]) for r in records),
            "statusCounts": statuses,
            "reserved": report["counts"]["reserved"],
            "knownInputTokens": report["counts"]["knownInputTokens"],
            "knownOutputTokens": report["counts"]["knownOutputTokens"],
            "unknownUsageAttempts": report["counts"]["unknownUsageAttempts"],
        }
        if evidence_kind == "live-capture":
            counts.update(
                observedDispatches=report["counts"]["observedDispatches"],
                unknownDispatchAttempts=report["unknownDispatchAttempts"],
            )
        complete = (
            # A prediction seal binds completed predictions, not billing completeness.
            report["state"] == "finished"
            and report["stopReason"] == "complete"
            and statuses == {"completed": len(records)}
            and not report["unknownAttemptIds"]
        )
        seal = {"status": "unsealed", "id": None, "artifact": None}
        if complete:
            binding = {
                "schema": "normlab.runtime-prediction-seal/v1",
                "executionId": intent["id"],
                "captureRevisionId": snapshot.manifest["captureRevisionId"],
                "predictions": [
                    {"taskId": ids["taskId"], "result": outcome["final"]["result"]}
                    for ids, outcome in zip(intent["tasks"], report["taskOutcomes"])
                ],
            }
            seal = {
                "status": "sealed",
                "id": identity("seal", binding),
                "artifact": put(binding),
            }
        manifest = {
            "schema": "normlab.runtime-export-plan/v1"
            if evidence_kind == "mock"
            else "normlab.runtime-export-plan/v2",
            "projectionId": None,
            "executionId": intent["id"],
            "captureRevisionId": snapshot.manifest["captureRevisionId"],
            "captureManifest": put(snapshot.manifest),
            "planDigest": intent["planDigest"],
            "arms": plan["arms"],
            "contextPolicy": plan["contextPolicy"],
            "records": [put(record) for record in records],
            "counts": counts,
            "predictionSeal": seal,
            "reference": None,
            "score": None,
            "evidenceKind": evidence_kind,
            "actualCost": None,
            "criticalErrorFreeRate": None,
            "inferenceCallsExecuted": 0,
            "executionReady": False,
            "semanticQualityEvidence": False,
            "exportWritten": False,
        }
        manifest["projectionId"] = identity(
            "runtime-view",
            {key: value for key, value in manifest.items() if key != "projectionId"},
        )
        raw = canonical(manifest)
        require(len(raw) <= MAX_BYTES, "Runtime projection index cap")
        merged = {**snapshot.files, **blobs}
        require(
            len(merged) <= MAX_FILES
            and sum(map(len, merged.values())) + len(raw) <= MAX_TOTAL_BYTES,
            "Runtime projection aggregate caps",
        )
        self._manifest = raw
        self._files = MappingProxyType(blobs)

    @property
    def snapshot(self):
        return self._snapshot

    @property
    def manifest(self):
        return json.loads(self._manifest)

    @property
    def files(self):
        return self._files


def prepare_export(snapshot):
    return RuntimeExportProjection(snapshot)


def verify_export_projection(root, manifest, artifacts):
    kind = manifest.get("evidenceKind")
    require(
        (manifest.get("schema"), kind)
        in {
            ("normlab.runtime-export-plan/v1", "mock"),
            ("normlab.runtime-export-plan/v2", "live-capture"),
        },
        "Export plan schema/evidence kind",
    )
    expected = prepare_export(capture_runtime(root, evidence_kind=kind))
    require(
        canonical(manifest) == canonical(expected.manifest),
        "Runtime projection manifest binding",
    )
    require(
        set(artifacts) == set(expected.files)
        and all(artifacts[name] == raw for name, raw in expected.files.items()),
        "Runtime projection artifact binding",
    )
    return expected
