"""Versioned portable continuation archive; old archive schemas stay closed."""

import os
import stat
from pathlib import Path
from types import MappingProxyType
from uuid import uuid4

from execution_checkpoint import DurableWriter, bounded_read, reader_lock
from execution_plan import Store
from execution_records import digest, integer, items, run_id
from native_resume_capture import BASE, code_pins
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
from runtime_resume_capture import (
    FORMAT,
    ResumeExportProjection,
    ResumeSnapshot,
    capture_resume,
    consumer_pins,
)

SCHEMA = "normlab.runtime-archive/v3"


def producer_pins():
    return {**code_pins(), **consumer_pins()}


def file_limit(name):
    prefix = "source/" + BASE + "/"
    if isinstance(name, str) and name.startswith(prefix):
        nested = name[len(prefix) :]
        if nested == "archive.json":
            return MAX_BYTES
        if nested == ".writer.lock":
            return 0
        return original_limit(nested)
    return original_limit(name)


def check_index(index):
    object_keys(
        index,
        "schema sourceFormat archiveId executionId captureRevisionId projectionId producerPins capture projection inventory totals evidenceKind inferenceCallsExecuted executionReady semanticQualityEvidence",
    )
    require(
        index["schema"] == SCHEMA
        and index["sourceFormat"] == FORMAT
        and index["evidenceKind"] == "live-capture",
        "Explicit continuation archive schema/format/evidence",
    )
    run_id(index["executionId"])
    for key, prefix in (
        ("captureRevisionId", "capture-"),
        ("projectionId", "runtime-view-"),
    ):
        require(
            isinstance(index[key], str) and index[key].startswith(prefix),
            "Continuation derived ID kind",
        )
        digest(index[key][len(prefix) :])
    require(
        type(index["inferenceCallsExecuted"]) is int
        and index["inferenceCallsExecuted"] == 0
        and index["executionReady"] is False
        and index["semanticQualityEvidence"] is False,
        "Continuation archive offline flags",
    )
    require(
        index["producerPins"] == producer_pins(),
        "Supported continuation consumer producer pins",
    )
    items(index["inventory"], 1, maximum=MAX_FILES)
    refs = {}
    for ref in index["inventory"]:
        object_keys(ref, "path sha256 bytes")
        require(type(ref["path"]) is str, "Continuation archive path")
        limit = file_limit(ref["path"])
        digest(ref["sha256"])
        integer(ref["bytes"])
        require(
            ref["bytes"] <= limit and ref["path"] not in refs,
            "Continuation inventory bound/uniqueness",
        )
        if "/artifacts/" in ref["path"]:
            require(
                ref["path"].split("/")[-1] == ref["sha256"] + ".blob",
                "Continuation content address",
            )
        refs[ref["path"]] = ref
    require(list(refs) == sorted(refs), "Sorted continuation inventory")
    for field in ("capture", "projection"):
        require(
            index[field] == refs.get(field + ".json"), "Continuation metadata reference"
        )
    roots = {
        "source/plan.json",
        "source/intent.json",
        "source/checkpoint.json",
        "source/" + BASE + "/archive.json",
        "source/" + BASE + "/.writer.lock",
    }
    require(roots <= set(refs), "Continuation source and original archive roots")
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
        "Continuation archive totals/bounds",
    )
    require(
        index["archiveId"]
        == identity("archive", {k: v for k, v in index.items() if k != "archiveId"}),
        "Continuation archive identity",
    )
    return refs


class ResumeArchivePlan(ArchivePlan):
    def __init__(self, projection):
        require(
            type(projection) is ResumeExportProjection,
            "Validated continuation projection required",
        )
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


class VerifiedResumeArchive(VerifiedArchive):
    def summary(self):
        result = super().summary()
        result.update(
            schema="normlab.runtime-archive-verification/v3",
            sourceFormat=FORMAT,
            continuation=self.snapshot.manifest["continuation"],
        )
        return result


def read_archive(directory):
    root = Path(directory).resolve(strict=True)
    require(root.is_dir(), "Continuation archive directory")
    with reader_lock(root):
        raw = bounded_read(root / "archive.json", MAX_BYTES)
        index = Store.decode_json(raw)
        refs = check_index(index)
        folders = directories(refs)
        expected = set(refs) | folders | {"archive.json", ".writer.lock"}
        seen, files = set(), {}
        for number, path in enumerate(root.rglob("*"), 1):
            require(
                number <= MAX_FILES and not path.is_symlink(),
                "Bounded continuation archive without symlinks",
            )
            name = str(path.relative_to(root))
            require(name in expected, "No undeclared continuation entries")
            seen.add(name)
            mode = path.stat().st_mode
            if name in folders:
                require(stat.S_ISDIR(mode), "Declared continuation directory")
                continue
            require(stat.S_ISREG(mode), "Regular continuation file")
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
                    file_ref(name, data) == refs[name],
                    "Continuation file digest/length",
                )
                files[name] = data
            else:
                require(
                    data == (raw if name == "archive.json" else b""),
                    "Continuation marker/lock bytes",
                )
        require(seen == expected, "Complete continuation inventory")
        projection = ResumeExportProjection(ResumeSnapshot(root / "source"))
        planned = ResumeArchivePlan(projection)
        require(
            raw == planned.index_bytes and files == dict(planned.files),
            "Regenerated continuation archive binding",
        )
    return VerifiedResumeArchive(planned, projection)


class ResumeArchiveWriter(ArchiveWriter):
    def publish(self, plan):
        require(
            self.lock is not None and not self.poisoned and not self.committed,
            "Healthy continuation writer",
        )
        require(type(plan) is ResumeArchivePlan, "Validated continuation publication")
        refs = check_index(plan.index)
        require(
            set(refs) == set(plan.files)
            and all(
                file_ref(name, raw) == refs[name] for name, raw in plan.files.items()
            ),
            "Exact continuation publication inventory",
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
    snapshot = capture_resume(source)
    require(
        not Path(output).resolve().is_relative_to(Path(source).resolve()),
        "Continuation archive outside source",
    )
    plan = ResumeArchivePlan(ResumeExportProjection(snapshot))
    check_index(plan.index)
    with ResumeArchiveWriter(output, hook) as writer:
        writer.publish(plan)
    return {
        "archiveId": plan.index["archiveId"],
        "captureRevisionId": plan.index["captureRevisionId"],
        "durabilityAcknowledged": True,
        "inferenceCallsExecuted": 0,
    }
