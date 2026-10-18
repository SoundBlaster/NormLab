"""Bounded portable final stop-control archive v4; never acquires run authority."""

import os
import re
import stat
from pathlib import Path
from types import MappingProxyType
from uuid import uuid4

from execution_checkpoint import DurableWriter, bounded_read, reader_lock
from execution_plan import Store
from execution_records import digest, integer, items, run_id
from native_resumed_stop import code_pins
from offline_bundle import (
    MAX_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    canonical,
    identity,
    object_keys,
    require,
)
from runtime_archive_export import ArchiveWriter
from runtime_archive_format import ArchivePlan, directories, file_ref
from runtime_archive_format import file_limit as original_limit
from runtime_archive_reader import VerifiedArchive
from runtime_resume_archive import file_limit as continuation_limit
from runtime_stop_capture import (
    FORMAT,
    StopExportProjection,
    StopSnapshot,
    capture_stop,
    consumer_pins,
)

SCHEMA = "normlab.runtime-archive/v4"


def producer_pins():
    return {**code_pins(), **consumer_pins()}


def embedded_limit(name, reader):
    if name == "archive.json":
        return MAX_BYTES
    if name == ".writer.lock":
        return 0
    return reader(name)


def file_limit(name):
    require(type(name) is str, "Stop archive path string")
    prefix = "source/native-stop-base/"
    if name.startswith(prefix):
        return embedded_limit(name[len(prefix) :], original_limit)
    prefix = "source/native-resumed-stop-base/"
    if name.startswith(prefix):
        nested = name[len(prefix) :]
        if nested.startswith("capture/"):
            return embedded_limit(nested[len("capture/") :], continuation_limit)
        if nested == "evidence.json":
            return MAX_BYTES
        if nested == ".writer.lock":
            return 0
        require(
            re.fullmatch(r"artifacts/[0-9a-f]{64}\.blob", nested) is not None,
            "Closed stop evidence path",
        )
        return MAX_BYTES
    return continuation_limit(name)


def check_index(index):
    object_keys(
        index,
        "schema sourceFormat archiveId executionId captureRevisionId projectionId producerPins capture projection inventory totals evidenceKind inferenceCallsExecuted executionReady semanticQualityEvidence",
    )
    require(
        index["schema"] == SCHEMA
        and index["sourceFormat"] == FORMAT
        and index["evidenceKind"] == "live-capture",
        "Explicit stop archive schema/source/kind",
    )
    run_id(index["executionId"])
    for key, prefix in (
        ("captureRevisionId", "capture-"),
        ("projectionId", "runtime-view-"),
    ):
        require(
            type(index[key]) is str and index[key].startswith(prefix),
            "Stop derived ID kind",
        )
        digest(index[key][len(prefix) :])
    require(
        type(index["inferenceCallsExecuted"]) is int
        and index["inferenceCallsExecuted"] == 0
        and index["executionReady"] is False
        and index["semanticQualityEvidence"] is False,
        "Stop archive read-only flags",
    )
    require(
        index["producerPins"] == producer_pins(),
        "Current trusted stop archive producer pins",
    )
    items(index["inventory"], 1, maximum=MAX_FILES)
    refs = {}
    for ref in index["inventory"]:
        object_keys(ref, "path sha256 bytes")
        limit = file_limit(ref["path"])
        digest(ref["sha256"])
        integer(ref["bytes"])
        require(
            ref["bytes"] <= limit and ref["path"] not in refs,
            "Stop inventory bound/uniqueness",
        )
        if "/artifacts/" in ref["path"]:
            require(
                ref["path"].split("/")[-1] == ref["sha256"] + ".blob",
                "Stop artifact name binding",
            )
        refs[ref["path"]] = ref
    require(list(refs) == sorted(refs), "Sorted stop inventory")
    for key in ("capture", "projection"):
        require(index[key] == refs.get(key + ".json"), "Stop metadata reference")
    require(
        {"source/plan.json", "source/intent.json", "source/checkpoint.json"}
        <= set(refs),
        "Stop source roots",
    )
    totals = {
        "contentFiles": len(refs),
        "contentBytes": sum(r["bytes"] for r in refs.values()),
        "publishedEntries": len(refs) + len(directories(refs)) + 2,
    }
    raw = canonical(index)
    require(
        canonical(totals) == canonical(index["totals"])
        and len(raw) <= MAX_BYTES
        and totals["publishedEntries"] <= MAX_FILES
        and totals["contentBytes"] + len(raw) <= MAX_TOTAL_BYTES,
        "Stop archive total bounds",
    )
    require(
        index["archiveId"]
        == identity("archive", {k: v for k, v in index.items() if k != "archiveId"}),
        "Stop archive identity",
    )
    return refs


class StopArchivePlan(ArchivePlan):
    def __init__(self, projection):
        require(type(projection) is StopExportProjection, "Validated stop projection")
        files = {
            "source/" + name: raw for name, raw in projection.snapshot.files.items()
        }
        files.update(
            {"projection/" + name: raw for name, raw in projection.files.items()}
        )
        files.update(
            {
                "capture.json": canonical(projection.snapshot.manifest),
                "projection.json": canonical(projection.manifest),
            }
        )
        index = {
            "schema": SCHEMA,
            "sourceFormat": FORMAT,
            "archiveId": None,
            **{
                k: projection.manifest[k]
                for k in ("executionId", "captureRevisionId", "projectionId")
            },
            "producerPins": producer_pins(),
            "capture": file_ref("capture.json", files["capture.json"]),
            "projection": file_ref("projection.json", files["projection.json"]),
            "inventory": [file_ref(name, raw) for name, raw in sorted(files.items())],
            "totals": {
                "contentFiles": len(files),
                "contentBytes": sum(map(len, files.values())),
                "publishedEntries": len(files) + len(directories(files)) + 2,
            },
            "evidenceKind": "live-capture",
            "inferenceCallsExecuted": 0,
            "executionReady": False,
            "semanticQualityEvidence": False,
        }
        index["archiveId"] = identity(
            "archive", {k: v for k, v in index.items() if k != "archiveId"}
        )
        check_index(index)
        self._index, self._files = canonical(index), MappingProxyType(files)


class VerifiedStopArchive(VerifiedArchive):
    def summary(self):
        result = super().summary()
        result.update(
            schema="normlab.runtime-archive-verification/v4",
            sourceFormat=FORMAT,
            controlState="stopped-with-unknown",
            stopControl=self.snapshot.manifest["stopControl"],
        )
        return result


def read_archive(directory):
    root = Path(directory).resolve(strict=True)
    require(root.is_dir(), "Stop archive directory")
    with reader_lock(root):
        raw = bounded_read(root / "archive.json", MAX_BYTES)
        index = Store.decode_json(raw)
        refs = check_index(index)
        folders = directories(refs)
        expected = set(refs) | folders | {"archive.json", ".writer.lock"}
        seen, files = set(), {}
        for number, path in enumerate(root.rglob("*"), 1):
            name = str(path.relative_to(root))
            require(
                number <= MAX_FILES and not path.is_symlink() and name in expected,
                "Exact bounded stop archive tree",
            )
            seen.add(name)
            mode = path.stat().st_mode
            if name in folders:
                require(stat.S_ISDIR(mode), "Declared stop archive folder")
                continue
            require(stat.S_ISREG(mode), "Regular stop archive file")
            data = bounded_read(
                path,
                file_limit(name)
                if name in refs
                else MAX_BYTES
                if name == "archive.json"
                else 0,
            )
            if name in refs:
                require(
                    file_ref(name, data) == refs[name], "Stop archive digest/length"
                )
                files[name] = data
            else:
                require(
                    data == (raw if name == "archive.json" else b""),
                    "Stop archive marker/lock bytes",
                )
        require(seen == expected, "Complete stop archive inventory")
        projection = StopExportProjection(StopSnapshot(root / "source"))
        planned = StopArchivePlan(projection)
        require(
            raw == planned.index_bytes and files == dict(planned.files),
            "Regenerated stop archive binding",
        )
    return VerifiedStopArchive(planned, projection)


class StopArchiveWriter(ArchiveWriter):
    def publish(self, plan):
        require(
            self.lock is not None
            and not self.poisoned
            and not self.committed
            and type(plan) is StopArchivePlan,
            "Healthy validated stop archive writer",
        )
        refs = check_index(plan.index)
        require(
            set(refs) == set(plan.files)
            and all(
                file_ref(name, raw) == refs[name] for name, raw in plan.files.items()
            ),
            "Exact stop publication inventory",
        )
        try:
            for name in sorted(
                directories(plan.files), key=lambda v: (v.count("/"), v)
            ):
                (self.root / name).mkdir(mode=0o700)
                DurableWriter.flush_directory((self.root / name).parent)
            self.hook("directories:after-flush")
            for name, raw in sorted(plan.files.items()):
                self._write_file(name, raw, "content")
            self.hook("before-marker")
            temporary = ".pending-" + str(uuid4())
            self._write_file(temporary, plan.index_bytes, "marker")
            os.replace(self.root / temporary, self.root / "archive.json")
            self.hook("marker:after-replace")
            DurableWriter.flush_directory(self.root)
            self.hook("marker:after-directory-commit")
            self.committed = True
        except BaseException:
            self.poisoned = True
            raise


def export_archive(source, output, *, hook=None):
    snapshot = capture_stop(source)
    require(
        not Path(output).resolve().is_relative_to(Path(source).resolve()),
        "Stop archive outside source",
    )
    planned = StopArchivePlan(StopExportProjection(snapshot))
    with StopArchiveWriter(output, hook) as writer:
        writer.publish(planned)
    return {
        "archiveId": planned.index["archiveId"],
        "captureRevisionId": planned.index["captureRevisionId"],
        "durabilityAcknowledged": True,
        "inferenceCallsExecuted": 0,
    }
