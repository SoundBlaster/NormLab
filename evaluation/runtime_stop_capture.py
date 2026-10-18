"""Versioned read-only final stop capture; recorded controls grant no authority."""

import copy
from pathlib import Path
from types import MappingProxyType

import native_resumed_stop as resumed
import native_stop_resolution as native
from execution_checkpoint import bounded_read, reader_lock
from execution_plan import MAX_JOURNAL_BYTES, Store
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
from runtime_export import RuntimeExportProjection

FORMAT = "native-stop-control/v1"


def consumer_pins():
    return {
        name: sha(Path(__file__).with_name(name).read_bytes())
        for name in (
            "runtime_stop_capture.py",
            "runtime_stop_archive.py",
            "runtime_consumer_v4.py",
        )
    }


class StopSnapshot(RuntimeSnapshot):
    """Caller holds the source shared lock or the immutable outer archive lock."""

    def __init__(self, root):
        root = Path(root)
        raw = bounded_read(root / "checkpoint.json", MAX_JOURNAL_BYTES)
        saved = Store.decode_json(raw)
        if saved.get("schema") == native.CHECKPOINT:
            report = native.inspect_unlocked(root)
            base = read_archive(root / native.BASE)
            prefix = native.BASE + "/"
            nested = {prefix + name: data for name, data in base.files.items()}
            nested[prefix + "archive.json"] = canonical(base.index)
            nested[prefix + ".writer.lock"] = b""
        else:
            require(
                saved.get("schema") == resumed.CHECKPOINT,
                "Explicit native stop-control source",
            )
            report = resumed.inspect_unlocked(root)
            base, evidence, archived_orphans = resumed.read_base(root / resumed.BASE)
            prefix = resumed.BASE + "/"
            nested = {
                prefix + "capture/" + name: data for name, data in base.files.items()
            }
            nested.update(
                {prefix + name: data for name, data in archived_orphans.items()}
            )
            nested[prefix + "capture/archive.json"] = canonical(base.index)
            nested[prefix + "capture/.writer.lock"] = b""
            nested[prefix + "evidence.json"] = canonical(evidence)
            nested[prefix + ".writer.lock"] = b""
        snapshot = base.snapshot
        files = dict(snapshot.files)
        for name, data in files.items():
            if name != "checkpoint.json":
                require(
                    bounded_read(root / name, len(data)) == data,
                    "Stop source matches verified pre-stop bytes",
                )
        store = Store(root)
        request = store.value(saved["request"])
        orphans = resumed.orphan_files(root, snapshot, request)
        files.update(store.files)
        files.update(orphans)
        files.update(nested)
        files["checkpoint.json"] = raw
        control = {
            "checkpointSchema": saved["schema"],
            "resolutionId": report["resolutionId"],
            "controlState": report["controlState"],
            "sourceState": report["sourceState"],
            "originalCheckpointDigest": report["checkpointDigest"],
            "baseArchiveId": base.index["archiveId"],
            "baseCaptureRevisionId": base.index["captureRevisionId"],
            "originalDeadlineNs": report["originalDeadlineNs"],
            "operatorStoppedAttemptIds": report["operatorStoppedAttemptIds"],
            "unknownAttemptIds": report["unknownAttemptIds"],
            "preStopEvidenceId": saved.get("preStopEvidenceId"),
            "orphanFiles": [
                {"path": name, "sha256": sha(data), "bytes": len(data)}
                for name, data in sorted(orphans.items())
            ],
            "orphanAssociation": "unattributed-uncommitted-artifacts",
            "adopted": False,
            "resumeSupported": False,
        }
        sources = [
            {"path": name, "sha256": sha(data), "bytes": len(data)}
            for name, data in sorted(files.items())
        ]
        pins = consumer_pins()
        manifest = {
            "schema": "normlab.runtime-capture/v4",
            "sourceFormat": FORMAT,
            "executionId": snapshot.intent["id"],
            "captureRevisionId": identity(
                "capture",
                {
                    "executionId": snapshot.intent["id"],
                    "sources": sources,
                    "consumerPins": pins,
                },
            ),
            "planDigest": snapshot.intent["planDigest"],
            "checkpointSchema": saved["schema"],
            "checkpointDigest": sha(raw),
            "journalHead": report["journalHead"],
            "state": snapshot.report["state"],
            "stopReason": snapshot.report["stopReason"],
            "controlState": report["controlState"],
            "stopControl": control,
            "evidenceKind": "live-capture",
            "sourceFiles": sources,
            "recordedDependencies": snapshot.plan["pins"]["dependencies"],
            "recordedDispatches": {
                "observed": report["counts"]["observedDispatches"],
                "unknown": report["unknownDispatchAttempts"],
            },
            "consumerPins": pins,
            "inferenceCallsExecuted": 0,
            "executionReady": False,
            "semanticQualityEvidence": False,
        }
        encoded = canonical(manifest)
        require(
            len(files) <= MAX_FILES
            and len(encoded) <= MAX_BYTES
            and sum(map(len, files.values())) + len(encoded) <= MAX_TOTAL_BYTES,
            "Stop snapshot aggregate bounds",
        )
        self._manifest, self._files = encoded, MappingProxyType(files)
        self._plan, self._intent, self._events = (
            snapshot.plan,
            snapshot.intent,
            snapshot.events,
        )
        self._base = base
        self._report = snapshot.report
        self._report.update(
            controlState=report["controlState"], stopControl=copy.deepcopy(control)
        )
        self._report["nativeBoundary"] = {
            "mode": FORMAT,
            "historicalReplayOnly": True,
            "resumeSupported": False,
            "recordedRuntimeVerified": False,
        }


def capture_stop(root):
    with reader_lock(root):
        return StopSnapshot(root)


class StopExportProjection(RuntimeExportProjection):
    def __init__(self, snapshot):
        require(type(snapshot) is StopSnapshot, "Validated stop snapshot required")
        # Task records and all counts are already verified in the immutable base.
        # A stop never changes an attempt's semantic outcome or seals predictions.
        base = snapshot._base.projection
        manifest, files = base.manifest, dict(base.files)
        require(
            manifest["predictionSeal"]["status"] == "unsealed",
            "Unknown stop stays unsealed",
        )
        files.pop(manifest["captureManifest"]["path"])
        raw = canonical(snapshot.manifest)
        ref = {
            "path": "artifacts/" + sha(raw) + ".blob",
            "sha256": sha(raw),
            "bytes": len(raw),
        }
        files[ref["path"]] = raw
        manifest.update(
            schema="normlab.runtime-export-plan/v4",
            sourceFormat=FORMAT,
            captureRevisionId=snapshot.manifest["captureRevisionId"],
            captureManifest=ref,
            stopControl=snapshot.manifest["stopControl"],
            controlState="stopped-with-unknown",
        )
        control = snapshot.manifest["stopControl"]
        manifest["controlMetrics"] = {
            "operatorStoppedUnknownAttempts": len(control["operatorStoppedAttemptIds"]),
            "retainedOrphanBlobs": len(control["orphanFiles"]),
            "retainedOrphanBytes": sum(ref["bytes"] for ref in control["orphanFiles"]),
            "adoptedOutcomes": 0,
        }
        manifest["projectionId"] = identity(
            "runtime-view", {k: v for k, v in manifest.items() if k != "projectionId"}
        )
        encoded = canonical(manifest)
        require(
            len(encoded) <= MAX_BYTES
            and len(files) + len(snapshot.files) <= MAX_FILES
            and sum(map(len, files.values()))
            + sum(map(len, snapshot.files.values()))
            + len(encoded)
            <= MAX_TOTAL_BYTES,
            "Stop projection aggregate bounds",
        )
        self._snapshot, self._manifest, self._files = (
            snapshot,
            encoded,
            MappingProxyType(files),
        )
