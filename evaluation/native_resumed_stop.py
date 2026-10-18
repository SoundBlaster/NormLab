"""Explicit stop of one resumed unknown; frozen native/v3 producers stay closed."""

import copy
import os
from pathlib import Path

from execution_checkpoint import bounded_read, reader_lock
from execution_live_gate import LinuxClock
from execution_plan import MAX_JOURNAL_BYTES, Store
from native_stop_resolution import StopWriter, binding, check_sample
from offline_bundle import (
    MAX_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    canonical,
    identity,
    object_keys,
    require,
    sha,
)
from runtime_resume_archive import (
    ResumeArchivePlan,
    ResumeArchiveWriter,
    producer_pins,
    read_archive,
)
from runtime_resume_capture import ResumeExportProjection, ResumeSnapshot

REQUEST = "normlab.resumed-stop-request/v1"
CHECKPOINT = "normlab.resumed-stop-checkpoint/v1"
BASE = "native-resumed-stop-base"


def code_pins():
    return {
        **producer_pins(),
        **{
            name: sha(Path(__file__).with_name(name).read_bytes())
            for name in ("native_resumed_stop.py", "native_resumed_stop_cli.py")
        },
    }


def check_request(snapshot, request):
    object_keys(
        request,
        "schema runId planDigest checkpointDigest captureRevisionId journalHead action attemptId authorization expiresAt",
    )
    require(request["schema"] == REQUEST, "Explicit resumed-stop request schema")
    # Reuse the original stop policy, with only its wire-version discriminator
    # translated. Its exact head/single-unknown/authorization rules stay intact.
    from native_stop_resolution import REQUEST as ORIGINAL_REQUEST
    from native_stop_resolution import check_request as check_original

    check_original(snapshot, {**request, "schema": ORIGINAL_REQUEST})


def prepare_stop(root, *, attempt_id, authorization_record, expires_at):
    with reader_lock(root):
        snapshot = ResumeSnapshot(root)
        request = {
            "schema": REQUEST,
            **binding(snapshot),
            "action": "stop",
            "attemptId": attempt_id,
            "authorization": copy.deepcopy(authorization_record),
            "expiresAt": expires_at,
        }
        check_request(snapshot, request)
        return request


def frame(request_ref, snapshot, archive, sample):
    record = {
        "schema": CHECKPOINT,
        **binding(snapshot),
        "request": request_ref,
        "baseArchiveId": archive.index["archiveId"],
        "sample": copy.deepcopy(sample),
        "codePins": code_pins(),
    }
    return {**record, "resolutionId": identity("resumed-stop", record)}


def inspect_unlocked(root):
    root = Path(root)
    saved = Store.decode_json(bounded_read(root / "checkpoint.json", MAX_JOURNAL_BYTES))
    object_keys(
        saved,
        "schema runId planDigest checkpointDigest captureRevisionId journalHead request baseArchiveId sample codePins resolutionId",
    )
    require(saved["schema"] == CHECKPOINT, "Explicit resumed-stop checkpoint")
    archive = read_archive(root / BASE)
    snapshot = archive.snapshot
    for name, raw in snapshot.files.items():
        if name != "checkpoint.json":
            require(
                bounded_read(root / name, len(raw)) == raw,
                "Original resumed-stop source byte binding",
            )
    request = Store(root).value(saved["request"])
    check_request(snapshot, request)
    check_sample(snapshot, request, saved["sample"])
    require(
        canonical(saved)
        == canonical(frame(saved["request"], snapshot, archive, saved["sample"])),
        "Regenerated resumed-stop decision",
    )
    report = snapshot.report
    return {
        "schema": "normlab.resumed-stop-report/v1",
        "resolutionId": saved["resolutionId"],
        **binding(snapshot),
        "action": "stop",
        "operatorStoppedAttemptIds": [request["attemptId"]],
        "unknownAttemptIds": report["unknownAttemptIds"],
        "unknownDispatchAttempts": report["unknownDispatchAttempts"],
        "counts": report["counts"],
        "taskOutcomes": report["taskOutcomes"],
        "continuation": snapshot.manifest["continuation"],
        "sourceState": report["state"],
        "controlState": "stopped-with-unknown",
        "originalDeadlineNs": snapshot.intent["clock"]["deadlineNs"],
        "localCaptureOnly": True,
        "authorizationAttested": False,
        "recordedClockVerified": False,
        "resumeSupported": False,
        "adoptionSupported": False,
        "executionReady": False,
        "dispatchAttemptsInvoked": 0,
        "inferenceCallsExecuted": 0,
        "semanticQualityEvidence": False,
    }


def inspect_stop(root):
    """Read historical control only, without clocks, claims, keys or transport."""
    with reader_lock(root):
        return inspect_unlocked(root)


def private_root(root):
    metadata = root.stat()
    require(
        root.is_dir()
        and metadata.st_uid == os.geteuid()
        and metadata.st_mode & 0o077 == 0,
        "Existing owner-private resumed-stop directory",
    )


def apply_stop(root, request, *, confirm_request_digest, hook=None):
    request = copy.deepcopy(request)
    require(
        confirm_request_digest == sha(canonical(request)),
        "Current exact resumed-stop confirmation",
    )
    root = Path(root).resolve(strict=True)
    private_root(root)
    with StopWriter(root, hook) as writer:
        private_root(writer.root)
        current = Store.decode_json(
            bounded_read(writer.root / "checkpoint.json", MAX_JOURNAL_BYTES)
        )
        if current.get("schema") == CHECKPOINT:
            report = inspect_unlocked(writer.root)
            require(
                Store(writer.root).value(current["request"]) == request,
                "Committed resumed-stop cannot be replaced",
            )
            report["operation"] = "already-applied"
            return report
        snapshot = ResumeSnapshot(writer.root)
        check_request(snapshot, request)
        sample = LinuxClock().sample()
        check_sample(snapshot, request, sample)
        planned = ResumeArchivePlan(ResumeExportProjection(snapshot))
        base_exists = (writer.root / BASE).exists()
        require(
            len(writer.inventory)
            + (0 if base_exists else planned.index["totals"]["publishedEntries"])
            + 3
            <= MAX_FILES
            and sum(writer.inventory.values())
            + (
                0
                if base_exists
                else planned.index["totals"]["contentBytes"] + len(planned.index_bytes)
            )
            + 3 * MAX_BYTES
            <= MAX_TOTAL_BYTES,
            "Combined resumed-stop publication bounds",
        )
        if base_exists:
            archive = read_archive(writer.root / BASE)
            require(
                archive.index == planned.index, "Immutable resumed-stop base binding"
            )
        else:
            with ResumeArchiveWriter(writer.root / BASE, writer.hook) as archive_writer:
                archive_writer.publish(planned)
            archive = read_archive(writer.root / BASE)
        writer.inventory_check()
        writer.hook("after-resumed-stop-base")
        ref = writer.put(canonical(request), phase="resumed-stop-request")
        fresh = LinuxClock().sample()
        check_sample(snapshot, request, fresh)
        from execution_records import utc

        require(
            fresh["clockNs"] >= sample["clockNs"]
            and utc(fresh["observedAt"]) >= utc(sample["observedAt"]),
            "Resumed-stop publication clock regression",
        )
        private_root(writer.root)
        record = frame(ref, snapshot, archive, fresh)
        writer.publish(
            "checkpoint.json", canonical(record), phase="resumed-stop", replace=True
        )
    report = inspect_stop(root)
    report["operation"] = "apply-stop"
    return report
