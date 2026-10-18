"""Explicit stop of one resumed unknown; frozen native/v3 producers stay closed."""

import copy
import os
import stat
from pathlib import Path
from uuid import uuid4

from execution_checkpoint import DurableWriter, bounded_read, reader_lock
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
from runtime_archive_export import ArchiveWriter
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


def orphan_files(root, snapshot, request):
    """Retain uncommitted bytes without interpreting them as an attempt outcome."""
    files = {}
    own_request = "artifacts/" + sha(canonical(request)) + ".blob"
    folder = Path(root) / "artifacts"
    require(
        folder.is_dir() and not folder.is_symlink(), "Regular source artifact directory"
    )
    for number, path in enumerate(folder.iterdir(), 1):
        require(
            number <= MAX_FILES and not path.is_symlink(), "Bounded source artifacts"
        )
        # Unpublished writer temporaries are bounded by the outer inventory.
        # A failed stop-request write must not change the immutable blob set.
        if path.name.startswith(".pending-"):
            continue
        name = "artifacts/" + path.name
        if name in snapshot.files or name == own_request:
            continue
        raw = bounded_read(path, MAX_BYTES)
        require(name == "artifacts/" + sha(raw) + ".blob", "Orphan content address")
        files[name] = raw
        require(sum(map(len, files.values())) <= MAX_TOTAL_BYTES, "Orphan byte bound")
    return files


def evidence_manifest(snapshot, archive_id, files):
    record = {
        "schema": "normlab.resumed-stop-evidence/v1",
        **binding(snapshot),
        "baseArchiveId": archive_id,
        "orphanFiles": [
            {"path": name, "sha256": sha(raw), "bytes": len(raw)}
            for name, raw in sorted(files.items())
        ],
        "association": "unattributed-uncommitted-artifacts",
        "adopted": False,
        "inferenceCallsExecuted": 0,
        "codePins": code_pins(),
    }
    result = {**record, "evidenceId": identity("resumed-stop-evidence", record)}
    require(len(canonical(result)) <= MAX_BYTES, "Orphan evidence manifest bound")
    return result


def publish_base(root, planned, files, manifest, hook):
    # The outer marker commits both the strict unchanged v3 capture and the
    # separate uncommitted-byte inventory. Neither can be partially reused.
    with ArchiveWriter(root, hook) as writer:
        (writer.root / "artifacts").mkdir(mode=0o700)
        DurableWriter.flush_directory(writer.root)
        with ResumeArchiveWriter(writer.root / "capture", hook) as capture_writer:
            capture_writer.publish(planned)
        for name, raw in sorted(files.items()):
            writer._write_file(name, raw, "orphan-content")
        writer.hook("orphan-evidence:before-marker")
        temporary = ".pending-" + str(uuid4())
        writer._write_file(temporary, canonical(manifest), "orphan-marker")
        os.replace(writer.root / temporary, writer.root / "evidence.json")
        writer.hook("orphan-evidence:after-replace")
        DurableWriter.flush_directory(writer.root)
        writer.hook("orphan-evidence:after-directory-flush")
        writer.committed = True


def read_base(root):
    """Portable pre-stop evidence; recorded orphan bytes remain unadopted."""
    root = Path(root)
    with reader_lock(root):
        raw = bounded_read(root / "evidence.json", MAX_BYTES)
        manifest = Store.decode_json(raw)
        object_keys(
            manifest,
            "schema runId planDigest checkpointDigest captureRevisionId journalHead baseArchiveId orphanFiles association adopted inferenceCallsExecuted codePins evidenceId",
        )
        require(
            type(manifest["orphanFiles"]) is list
            and len(manifest["orphanFiles"]) <= MAX_FILES,
            "Orphan inventory bound",
        )
        archive = read_archive(root / "capture")
        files = {}
        for ref in manifest["orphanFiles"]:
            object_keys(ref, "path sha256 bytes")
            name = ref["path"]
            require(
                type(name) is str
                and type(ref["sha256"]) is str
                and name == "artifacts/" + ref["sha256"] + ".blob"
                and len(ref["sha256"]) == 64
                and all(c in "0123456789abcdef" for c in ref["sha256"])
                and name not in files,
                "Closed orphan path",
            )
            files[name] = bounded_read(root / name, MAX_BYTES)
            require(
                sum(map(len, files.values())) <= MAX_TOTAL_BYTES,
                "Bounded orphan read bytes",
            )
        require(
            raw
            == canonical(
                evidence_manifest(archive.snapshot, archive.index["archiveId"], files)
            ),
            "Regenerated uncommitted-byte evidence",
        )
        expected = {".writer.lock", "evidence.json", "artifacts", "capture"}
        for name in {*archive.files, "archive.json", ".writer.lock"}:
            parts = ("capture/" + name).split("/")
            expected.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
        expected.update(files)
        leaves = {
            ".writer.lock",
            "evidence.json",
            *files,
            "capture/archive.json",
            "capture/.writer.lock",
        }
        leaves.update("capture/" + name for name in archive.files)
        seen, total = set(), 0
        for number, path in enumerate(root.rglob("*"), 1):
            name = str(path.relative_to(root))
            require(
                number <= MAX_FILES and not path.is_symlink() and name in expected,
                "Exact bounded stop evidence tree",
            )
            metadata = path.stat()
            require(
                stat.S_ISREG(metadata.st_mode)
                if name in leaves
                else stat.S_ISDIR(metadata.st_mode),
                "Declared stop evidence entry type",
            )
            total += metadata.st_size if stat.S_ISREG(metadata.st_mode) else 0
            require(total <= MAX_TOTAL_BYTES, "Stop evidence aggregate byte bound")
            seen.add(name)
        require(
            seen == expected and bounded_read(root / ".writer.lock", 0) == b"",
            "Complete stop evidence inventory",
        )
    return archive, manifest, files


def frame(request_ref, snapshot, archive, sample, evidence_id):
    record = {
        "schema": CHECKPOINT,
        **binding(snapshot),
        "request": request_ref,
        "baseArchiveId": archive.index["archiveId"],
        "preStopEvidenceId": evidence_id,
        "sample": copy.deepcopy(sample),
        "codePins": code_pins(),
    }
    return {**record, "resolutionId": identity("resumed-stop", record)}


def inspect_unlocked(root):
    root = Path(root)
    saved = Store.decode_json(bounded_read(root / "checkpoint.json", MAX_JOURNAL_BYTES))
    object_keys(
        saved,
        "schema runId planDigest checkpointDigest captureRevisionId journalHead request baseArchiveId preStopEvidenceId sample codePins resolutionId",
    )
    require(saved["schema"] == CHECKPOINT, "Explicit resumed-stop checkpoint")
    archive, evidence, orphans = read_base(root / BASE)
    snapshot = archive.snapshot
    for name, raw in snapshot.files.items():
        if name != "checkpoint.json":
            require(
                bounded_read(root / name, len(raw)) == raw,
                "Original resumed-stop source byte binding",
            )
    request = Store(root).value(saved["request"])
    require(
        orphan_files(root, snapshot, request) == orphans,
        "Original uncommitted artifact bytes/inventory",
    )
    check_request(snapshot, request)
    check_sample(snapshot, request, saved["sample"])
    require(
        canonical(saved)
        == canonical(
            frame(
                saved["request"],
                snapshot,
                archive,
                saved["sample"],
                evidence["evidenceId"],
            )
        ),
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
        "orphanEvidence": {
            k: evidence[k]
            for k in ("evidenceId", "orphanFiles", "association", "adopted")
        },
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
        orphans = orphan_files(writer.root, snapshot, request)
        evidence = evidence_manifest(snapshot, planned.index["archiveId"], orphans)
        base_exists = (writer.root / BASE).exists()
        require(
            len(writer.inventory)
            + (
                0
                if base_exists
                else planned.index["totals"]["publishedEntries"] + len(orphans) + 6
            )
            + 3
            <= MAX_FILES
            and sum(writer.inventory.values())
            + (
                0
                if base_exists
                else planned.index["totals"]["contentBytes"]
                + len(planned.index_bytes)
                + len(canonical(evidence))
                + sum(map(len, orphans.values()))
            )
            + 3 * MAX_BYTES
            <= MAX_TOTAL_BYTES,
            "Combined resumed-stop publication bounds",
        )
        if base_exists:
            archive, saved_evidence, saved_orphans = read_base(writer.root / BASE)
            require(
                archive.index == planned.index
                and saved_evidence == evidence
                and saved_orphans == orphans,
                "Immutable resumed-stop base binding",
            )
        else:
            publish_base(writer.root / BASE, planned, orphans, evidence, writer.hook)
            archive, _, _ = read_base(writer.root / BASE)
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
        require(
            orphan_files(writer.root, snapshot, request) == orphans,
            "Uncommitted bytes unchanged before control commit",
        )
        record = frame(ref, snapshot, archive, fresh, evidence["evidenceId"])
        writer.publish(
            "checkpoint.json", canonical(record), phase="resumed-stop", replace=True
        )
    report = inspect_stop(root)
    report["operation"] = "apply-stop"
    return report
