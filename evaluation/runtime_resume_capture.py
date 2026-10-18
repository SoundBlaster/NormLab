"""Additive read-only continuation snapshots/projections; frozen producers unchanged."""

import copy
from pathlib import Path
from types import MappingProxyType

from execution_checkpoint import bounded_read, reader_lock
from native_resume_capture import BASE, CHECKPOINT, ResumeCapture
from offline_bundle import (
    MAX_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    canonical,
    identity,
    require,
    sha,
)
from runtime_archive_reader import read_archive
from runtime_capture import RuntimeSnapshot
from runtime_export import RuntimeExportProjection, journal_index, task_record

FORMAT = "native-continuation/v1"


def consumer_pins():
    return {
        name: sha(Path(__file__).with_name(name).read_bytes())
        for name in (
            "runtime_resume_capture.py",
            "runtime_resume_archive.py",
            "runtime_consumer.py",
        )
    }


class ResumeSnapshot(RuntimeSnapshot):
    """Caller holds source shared lock or immutable outer archive lock."""

    def __init__(self, root):
        capture = ResumeCapture(root)
        require(
            capture.saved["schema"] == CHECKPOINT, "Explicit native continuation source"
        )
        base = read_archive(capture.root / BASE)
        files = dict(capture.store.files)
        files.update(
            {
                "checkpoint.json": capture.raw,
                "intent.json": bounded_read(capture.root / "intent.json", MAX_BYTES),
            }
        )
        for event in capture.events:
            for key in ("request", "control", "outcome"):
                if event.get(key) is not None:
                    capture.store.artifact(event[key])
            if event["outcome"] is not None:
                saved = capture.store.value(event["outcome"])
                for key in ("response", "result"):
                    if saved[key] is not None:
                        capture.store.artifact(saved[key])
        files.update(capture.store.files)
        files.update({BASE + "/" + name: raw for name, raw in base.files.items()})
        files[BASE + "/archive.json"] = canonical(base.index)
        files[BASE + "/.writer.lock"] = b""
        sources = [
            {"path": name, "sha256": sha(raw), "bytes": len(raw)}
            for name, raw in sorted(files.items())
        ]
        continuation = {
            "baseArchiveId": base.index["archiveId"],
            "baseCaptureRevisionId": base.index["captureRevisionId"],
            "baseCheckpointDigest": sha(capture.base.raw),
            "invocationIds": capture.invocations,
            "effectiveCaps": capture.limits,
            "originalDeadlineNs": capture.intent["clock"]["deadlineNs"],
            "codePins": capture.saved["codePins"],
        }
        pins = consumer_pins()
        manifest = {
            "schema": "normlab.runtime-capture/v3",
            "sourceFormat": FORMAT,
            "executionId": capture.intent["id"],
            "captureRevisionId": identity(
                "capture",
                {
                    "executionId": capture.intent["id"],
                    "sources": sources,
                    "consumerPins": pins,
                },
            ),
            "planDigest": capture.intent["planDigest"],
            "checkpointSchema": CHECKPOINT,
            "checkpointDigest": sha(capture.raw),
            "journalHead": capture.report["journalHead"],
            "state": capture.report["state"],
            "stopReason": capture.report["stopReason"],
            "evidenceKind": "live-capture",
            "sourceFiles": sources,
            "recordedDependencies": capture.plan["pins"]["dependencies"],
            "recordedDispatches": {
                "observed": capture.report["counts"]["observedDispatches"],
                "unknown": capture.report["unknownDispatchAttempts"],
            },
            "continuation": continuation,
            "consumerPins": pins,
            "inferenceCallsExecuted": 0,
            "executionReady": False,
            "semanticQualityEvidence": False,
        }
        raw = canonical(manifest)
        require(
            len(files) <= MAX_FILES
            and len(raw) <= MAX_BYTES
            and sum(map(len, files.values())) + len(raw) <= MAX_TOTAL_BYTES,
            "Continuation snapshot aggregate bounds",
        )
        self._manifest, self._files = raw, MappingProxyType(files)
        self._plan, self._intent, self._events = (
            copy.deepcopy(capture.plan),
            copy.deepcopy(capture.intent),
            copy.deepcopy(capture.events),
        )
        self._report = copy.deepcopy(capture.report)
        self._report["nativeBoundary"] = {
            "mode": FORMAT,
            "historicalReplayOnly": True,
            "resumeSupported": False,
            "recordedRuntimeVerified": False,
        }


def capture_resume(root):
    with reader_lock(root):
        return ResumeSnapshot(root)


class ResumeExportProjection(RuntimeExportProjection):
    def __init__(self, snapshot):
        require(
            type(snapshot) is ResumeSnapshot, "Validated continuation snapshot required"
        )
        self._snapshot = snapshot
        blobs = {}

        def put(value):
            raw = canonical(value)
            require(len(raw) <= MAX_BYTES, "Continuation projection artifact bound")
            ref = {
                "path": "artifacts/" + sha(raw) + ".blob",
                "sha256": sha(raw),
                "bytes": len(raw),
            }
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
            task_record(snapshot, task, ids_, outcome, reservations, observations)
            for task, ids_, outcome in zip(
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
            **{
                key: report["counts"][key]
                for key in (
                    "reserved",
                    "knownInputTokens",
                    "knownOutputTokens",
                    "unknownUsageAttempts",
                    "observedDispatches",
                )
            },
            "unknownDispatchAttempts": report["unknownDispatchAttempts"],
        }
        seal = {"status": "unsealed", "id": None, "artifact": None}
        if (
            report["state"] == "finished"
            and report["stopReason"] == "complete"
            and statuses == {"completed": len(records)}
            and not report["unknownAttemptIds"]
        ):
            binding = {
                "schema": "normlab.runtime-prediction-seal/v1",
                "executionId": intent["id"],
                "captureRevisionId": snapshot.manifest["captureRevisionId"],
                "predictions": [
                    {"taskId": ids_["taskId"], "result": outcome["final"]["result"]}
                    for ids_, outcome in zip(intent["tasks"], report["taskOutcomes"])
                ],
            }
            seal = {
                "status": "sealed",
                "id": identity("seal", binding),
                "artifact": put(binding),
            }
        manifest = {
            "schema": "normlab.runtime-export-plan/v3",
            "sourceFormat": FORMAT,
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
            "continuation": snapshot.manifest["continuation"],
            "reference": None,
            "score": None,
            "evidenceKind": "live-capture",
            "actualCost": None,
            "criticalErrorFreeRate": None,
            "inferenceCallsExecuted": 0,
            "executionReady": False,
            "semanticQualityEvidence": False,
            "exportWritten": False,
        }
        manifest["projectionId"] = identity(
            "runtime-view", {k: v for k, v in manifest.items() if k != "projectionId"}
        )
        raw = canonical(manifest)
        merged = {**snapshot.files, **blobs}
        require(
            len(raw) <= MAX_BYTES
            and len(merged) <= MAX_FILES
            and sum(map(len, merged.values())) + len(raw) <= MAX_TOTAL_BYTES,
            "Continuation projection aggregate bounds",
        )
        self._manifest, self._files = raw, MappingProxyType(blobs)
