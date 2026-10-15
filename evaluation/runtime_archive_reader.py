"""Portable read-only mock archive replay, using trusted installed Python modules."""

import stat
from pathlib import Path

from execution_checkpoint import bounded_read, reader_lock
from execution_continuation import Capture
from execution_plan import Store
from offline_bundle import MAX_BYTES, MAX_FILES, require, sha
from runtime_archive_format import (
    check_index,
    directories,
    file_limit,
    prepare_archive,
    producer_pins,
)
from runtime_capture import RuntimeSnapshot
from runtime_export import prepare_export


def read_inventory(root, index, index_raw):
    inventory = check_index(index)
    require(
        index["producerPins"] == producer_pins(index["evidenceKind"]),
        "Supported trusted archive producer revision",
    )
    folder_names = directories(inventory)
    expected = set(inventory) | folder_names | {"archive.json", ".writer.lock"}
    seen = set()
    files = {}
    for number, path in enumerate(root.rglob("*"), 1):
        require(
            number <= MAX_FILES and not path.is_symlink(),
            "Bounded archive tree without symlinks",
        )
        name = str(path.relative_to(root))
        require(name in expected, "No undeclared archive entries")
        seen.add(name)
        mode = path.stat().st_mode
        if name in folder_names:
            require(stat.S_ISDIR(mode), "Declared archive directory")
            continue
        require(stat.S_ISREG(mode), "Regular archive file")
        limit = (
            file_limit(name)
            if name in inventory
            else MAX_BYTES
            if name == "archive.json"
            else 0
        )
        raw = bounded_read(path, limit)
        if name in inventory:
            ref = inventory[name]
            require(
                len(raw) == ref["bytes"] and sha(raw) == ref["sha256"],
                "Exact archive file digest/length",
            )
            files[name] = raw
        else:
            require(
                raw == (index_raw if name == "archive.json" else b""),
                "Archive marker/lock bytes",
            )
    require(seen == expected, "Complete archive tree inventory")
    return files


class VerifiedArchive:
    def __init__(self, plan, projection):
        self._plan, self._projection = plan, projection

    @property
    def index(self):
        return self._plan.index

    @property
    def files(self):
        return self._plan.files

    @property
    def projection(self):
        return self._projection

    @property
    def snapshot(self):
        return self._projection.snapshot

    def summary(self):
        report = self.snapshot.report
        result = {
            "schema": "normlab.runtime-archive-verification/v1",
            "archiveId": self.index["archiveId"],
            "executionId": self.index["executionId"],
            "captureRevisionId": self.index["captureRevisionId"],
            "state": report["state"],
            "stopReason": report["stopReason"],
            "counts": self.projection.manifest["counts"],
            "unknownAttemptIds": report["unknownAttemptIds"],
            "predictionSeal": self.projection.manifest["predictionSeal"],
            "archiveVerified": True,
            "producerPinsMatched": True,
            "sourceAuthenticated": False,
            "runtimeClockVerified": False,
            "executionReady": False,
            "semanticQualityEvidence": False,
            "inferenceCallsExecuted": 0,
            "registryWritesExecuted": 0,
            "actualCost": None,
        }
        if self.index["evidenceKind"] == "live-capture":
            result["schema"] = "normlab.runtime-archive-verification/v2"
            result["evidenceKind"] = "live-capture"
            result["nativeBoundary"] = report["nativeBoundary"]
        return result


def read_archive(directory):
    root = Path(directory).resolve(strict=True)
    require(root.is_dir(), "Archive directory")
    with reader_lock(root):
        raw = bounded_read(root / "archive.json", MAX_BYTES)
        index = Store.decode_json(raw)
        files = read_inventory(root, index, raw)
        if index["evidenceKind"] == "live-capture":
            from runtime_live_capture import NativeCapture

            snapshot = RuntimeSnapshot(NativeCapture(root / "source"))
        else:
            snapshot = RuntimeSnapshot(Capture(root / "source"))
        projection = prepare_export(snapshot)
        expected = prepare_archive(projection)
        require(raw == expected.index_bytes, "Regenerated archive index binding")
        require(
            set(files) == set(expected.files)
            and all(files[name] == content for name, content in expected.files.items()),
            "Regenerated source/projection archive binding",
        )
    return VerifiedArchive(expected, projection)
