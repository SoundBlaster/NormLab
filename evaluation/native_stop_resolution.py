"""Explicit native unknown-attempt stop; no adoption, dispatch or execution grant."""

import copy
import fcntl
import os
import stat
from pathlib import Path

from execution_checkpoint import DurableWriter, bounded_read, reader_lock
from execution_live_gate import LinuxClock
from execution_plan import MAX_JOURNAL_BYTES, Store
from execution_records import authorization, integer, utc
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
from runtime_archive_export import export_archive
from runtime_archive_format import prepare_archive
from runtime_archive_reader import read_archive
from runtime_capture import RuntimeSnapshot
from runtime_export import prepare_export
from runtime_live_capture import NativeCapture

REQUEST = "normlab.native-stop-request/v1"
CHECKPOINT = "normlab.native-stop-checkpoint/v1"
BASE = "native-stop-base"


def code_pins():
    return {"native_stop_resolution.py": sha(Path(__file__).read_bytes())}


def binding(snapshot):
    return {
        "runId": snapshot.intent["id"],
        "planDigest": snapshot.intent["planDigest"],
        "checkpointDigest": snapshot.manifest["checkpointDigest"],
        "captureRevisionId": snapshot.manifest["captureRevisionId"],
        "journalHead": snapshot.report["journalHead"],
    }


def check_request(snapshot, request):
    object_keys(
        request,
        "schema runId planDigest checkpointDigest captureRevisionId journalHead action attemptId authorization expiresAt",
    )
    require(request["schema"] == REQUEST, "Native stop request schema")
    require(
        request["action"] == "stop",
        "Only stop supported; adoption/redispatch unsupported",
    )
    require(
        all(request[key] == value for key, value in binding(snapshot).items()),
        "Exact native execution/plan/checkpoint/capture/head binding",
    )
    report = snapshot.report
    require(
        report["state"] == "paused-unknown"
        and report["unknownAttemptIds"] == [request["attemptId"]],
        "Stop targets the original single paused unknown attempt",
    )
    authorization(request["authorization"])
    authorized = utc(request["authorization"]["authorizedAt"])
    require(
        utc(snapshot.events[-1]["observedAt"])
        <= authorized
        < utc(request["expiresAt"]),
        "Fresh head-bound stop authorization and expiry",
    )


def check_sample(snapshot, request, sample):
    object_keys(sample, "policy source units suspendAware epoch clockNs observedAt")
    clock = snapshot.intent["clock"]
    require(
        canonical(
            {
                k: sample[k]
                for k in ("policy", "source", "units", "suspendAware", "epoch")
            }
        )
        == canonical(
            {
                k: clock[k]
                for k in ("policy", "source", "units", "suspendAware", "epoch")
            }
        ),
        "Current same-host boot/source capability",
    )
    integer(sample["clockNs"])
    require(
        sample["clockNs"] >= snapshot.intent["clock"]["startNs"]
        and sample["clockNs"] >= snapshot.events[-1]["clockNs"],
        "Current stop clock continuity",
    )
    observed = utc(sample["observedAt"])
    require(
        utc(snapshot.events[-1]["observedAt"]) <= observed
        and utc(request["authorization"]["authorizedAt"])
        <= observed
        < utc(request["expiresAt"]),
        "Current stop authorization/UTC continuity",
    )
    # Closing an unknown does not require unused inference permission or renew it.


def prepare_stop(root, *, attempt_id, authorization_record, expires_at):
    """Read-only proposal. A document is neither applied control nor live authority."""
    with reader_lock(root):
        snapshot = RuntimeSnapshot(NativeCapture(root))
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


class StopWriter(DurableWriter):
    def inventory_check(self):
        self.inventory = {}
        total = 0
        for number, path in enumerate(self.root.rglob("*"), 1):
            require(
                number <= MAX_FILES and not path.is_symlink(),
                "Bounded native stop inventory without symlinks",
            )
            name = str(path.relative_to(self.root))
            mode = path.stat().st_mode
            if stat.S_ISDIR(mode):
                size = 0
            else:
                require(stat.S_ISREG(mode), "Regular native stop inventory")
                size = path.stat().st_size
                limit = (
                    MAX_JOURNAL_BYTES
                    if path.name == "checkpoint.json"
                    or path.name.startswith(".pending-")
                    else MAX_BYTES
                )
                require(size <= limit, "Native stop file bound")
            total += size
            require(total <= MAX_TOTAL_BYTES, "Native stop aggregate byte bound")
            self.inventory[name] = size

    def __enter__(self):
        require(self.lock is None and not self.poisoned, "Fresh native stop writer")
        self.root = self.root.resolve(strict=True)
        require(self.root.is_dir(), "Existing native execution directory")
        try:
            self.lock = os.open(
                self.root / ".writer.lock", os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
            )
            require(
                stat.S_ISREG(os.fstat(self.lock).st_mode), "Regular native writer lock"
            )
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.inventory_check()
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self


def frame(request_ref, snapshot, archive, sample):
    record = {
        "schema": CHECKPOINT,
        **binding(snapshot),
        "request": request_ref,
        "baseArchiveId": archive.index["archiveId"],
        "sample": copy.deepcopy(sample),
        "codePins": code_pins(),
    }
    return {**record, "resolutionId": identity("native-stop", record)}


def inspect_unlocked(root):
    root = Path(root)
    saved = Store.decode_json(bounded_read(root / "checkpoint.json", MAX_JOURNAL_BYTES))
    object_keys(
        saved,
        "schema runId planDigest checkpointDigest captureRevisionId journalHead request baseArchiveId sample codePins resolutionId",
    )
    require(saved["schema"] == CHECKPOINT, "Native stop checkpoint schema")
    archive = read_archive(root / BASE)
    snapshot = RuntimeSnapshot(NativeCapture(root / BASE / "source"))
    require(
        canonical(snapshot.manifest) == archive.files["capture.json"],
        "Verified native stop base capture",
    )
    for name in ("plan.json", "intent.json"):
        require(
            bounded_read(root / name, MAX_BYTES) == snapshot.files[name],
            "Original native stop input binding",
        )
    request = Store(root).value(saved["request"])
    check_request(snapshot, request)
    check_sample(snapshot, request, saved["sample"])
    require(
        canonical(saved)
        == canonical(frame(saved["request"], snapshot, archive, saved["sample"])),
        "Regenerated native stop decision",
    )
    report = snapshot.report
    return {
        "schema": "normlab.native-stop-report/v1",
        "resolutionId": saved["resolutionId"],
        **binding(snapshot),
        "action": "stop",
        "operatorStoppedAttemptIds": [request["attemptId"]],
        "unknownAttemptIds": report["unknownAttemptIds"],
        "unknownDispatchAttempts": report["unknownDispatchAttempts"],
        "counts": report["counts"],
        "taskOutcomes": report["taskOutcomes"],
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
    """Offline inspection: no clock sample, key lookup, I/O authority or repair."""
    with reader_lock(root):
        return inspect_unlocked(root)


def apply_stop(root, request, *, confirm_request_digest, hook=None):
    request = copy.deepcopy(request)
    require(
        confirm_request_digest == sha(canonical(request)),
        "Current exact stop request confirmation",
    )
    with StopWriter(root, hook) as writer:
        current = Store.decode_json(
            bounded_read(writer.root / "checkpoint.json", MAX_JOURNAL_BYTES)
        )
        if current.get("schema") == CHECKPOINT:
            report = inspect_unlocked(writer.root)
            require(
                Store(writer.root).value(current["request"]) == request,
                "Existing stop decision cannot be replaced",
            )
            report["operation"] = "already-applied"
            return report
        snapshot = RuntimeSnapshot(NativeCapture(writer.root))
        check_request(snapshot, request)
        sample = LinuxClock().sample()
        check_sample(snapshot, request, sample)
        planned = prepare_archive(prepare_export(snapshot))
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
            "Native stop combined publication bounds",
        )
        if base_exists:
            archive = read_archive(writer.root / BASE)
            require(
                archive.index == planned.index, "Existing immutable stop base binding"
            )
        else:
            export_archive(planned, writer.root / BASE, hook=writer.hook)
            archive = read_archive(writer.root / BASE)
        writer.inventory_check()
        writer.hook("after-stop-base")
        ref = writer.put(canonical(request), phase="stop-request")
        # Recheck expiry/continuity after archival work, immediately before commit.
        fresh = LinuxClock().sample()
        check_sample(snapshot, request, fresh)
        require(
            fresh["clockNs"] >= sample["clockNs"]
            and utc(fresh["observedAt"]) >= utc(sample["observedAt"]),
            "Stop publication clock regression",
        )
        record = frame(ref, snapshot, archive, fresh)
        writer.publish(
            "checkpoint.json", canonical(record), phase="native-stop", replace=True
        )
    report = inspect_stop(root)
    report["operation"] = "apply-stop"
    return report
