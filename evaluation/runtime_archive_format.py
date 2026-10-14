"""Closed bounded mock runtime archive layout and deterministic publication plan."""

import re
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from execution_plan import MAX_JOURNAL_BYTES
from execution_records import digest, integer, items, run_id
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
from runtime_export import RuntimeExportProjection

SCHEMA = "normlab.runtime-archive/v1"
ROOT_FILES = {
    "plan.json",
    "intent.json",
    "mock-script.json",
    "checkpoint.json",
    "checkpoint-v1.json",
}
PIN_MODULES = (
    "runtime_archive_format",
    "execution_checkpoint",
    "execution_continuation",
    "execution_mock",
    "execution_mock_codec",
    "execution_outcomes",
    "execution_plan",
    "execution_records",
    "execution_replay",
    "offline_bundle",
    "runtime_capture",
    "runtime_export",
)


def producer_pins():
    root = Path(__file__).parent
    return {name: sha((root / (name + ".py")).read_bytes()) for name in PIN_MODULES}


def file_limit(name):
    if name in {"capture.json", "projection.json"}:
        return MAX_BYTES
    parts = name.split("/")
    require(parts[0] in {"source", "projection"}, "Archive file namespace")
    if parts[0] == "source" and len(parts) == 2 and parts[1] in ROOT_FILES:
        return MAX_JOURNAL_BYTES if parts[1].startswith("checkpoint") else MAX_BYTES
    require(
        len(parts) == 3
        and parts[1] == "artifacts"
        and re.fullmatch(r"[0-9a-f]{64}\.blob", parts[2]) is not None,
        "Archive content-addressed path",
    )
    return MAX_BYTES


def directories(names):
    return {
        str(parent)
        for name in names
        for parent in PurePosixPath(name).parents
        if str(parent) != "."
    }


def file_ref(name, raw):
    return {"path": name, "sha256": sha(raw), "bytes": len(raw)}


def check_index(index):
    object_keys(
        index,
        "schema archiveId executionId captureRevisionId projectionId producerPins capture projection inventory totals evidenceKind inferenceCallsExecuted executionReady semanticQualityEvidence",
    )
    require(
        index["schema"] == SCHEMA and index["evidenceKind"] == "mock",
        "Mock archive schema",
    )
    run_id(index["executionId"])
    for field, prefix in (
        ("captureRevisionId", "capture-"),
        ("projectionId", "runtime-view-"),
    ):
        require(
            isinstance(index[field], str) and index[field].startswith(prefix),
            "Archive derived identity kind",
        )
        digest(index[field][len(prefix) :])
    require(
        index["inferenceCallsExecuted"] == 0
        and type(index["inferenceCallsExecuted"]) is int
        and index["executionReady"] is False
        and index["semanticQualityEvidence"] is False,
        "Archive offline evidence flags",
    )
    require(
        type(index["producerPins"]) is dict
        and set(index["producerPins"]) == set(PIN_MODULES),
        "Archive producer pin set",
    )
    for value in index["producerPins"].values():
        digest(value)
    items(index["inventory"], minimum=1, maximum=MAX_FILES)
    inventory = {}
    for ref in index["inventory"]:
        object_keys(ref, "path sha256 bytes")
        require(type(ref["path"]) is str, "Archive path string")
        limit = file_limit(ref["path"])
        digest(ref["sha256"])
        integer(ref["bytes"])
        require(
            ref["bytes"] <= limit and ref["path"] not in inventory,
            "Archive file bound/uniqueness",
        )
        inventory[ref["path"]] = ref
        if "/artifacts/" in ref["path"]:
            require(
                ref["path"].split("/")[-1] == ref["sha256"] + ".blob",
                "Archive artifact name binding",
            )
    require(list(inventory) == sorted(inventory), "Sorted archive inventory")
    for key, name in (("capture", "capture.json"), ("projection", "projection.json")):
        require(index[key] == inventory.get(name), "Archive metadata reference")
    require(
        {
            "source/plan.json",
            "source/intent.json",
            "source/mock-script.json",
            "source/checkpoint.json",
        }
        <= set(inventory),
        "Archive source roots",
    )
    expected_totals = {
        "contentFiles": len(inventory),
        "contentBytes": sum(ref["bytes"] for ref in inventory.values()),
        "publishedEntries": len(inventory) + len(directories(inventory)) + 2,
    }
    require(
        canonical(index["totals"]) == canonical(expected_totals),
        "Archive derived totals",
    )
    raw = canonical(index)
    require(
        len(raw) <= MAX_BYTES
        and expected_totals["publishedEntries"] <= MAX_FILES
        and expected_totals["contentBytes"] + len(raw) <= MAX_TOTAL_BYTES,
        "Archive aggregate limits",
    )
    require(
        index["archiveId"]
        == identity(
            "archive",
            {key: value for key, value in index.items() if key != "archiveId"},
        ),
        "Archive identity",
    )
    return inventory


class ArchivePlan:
    def __init__(self, projection):
        require(
            type(projection) is RuntimeExportProjection,
            "Validated runtime projection required",
        )
        files = {
            "source/" + name: raw for name, raw in projection.snapshot.files.items()
        }
        files.update(
            {"projection/" + name: raw for name, raw in projection.files.items()}
        )
        files["capture.json"] = canonical(projection.snapshot.manifest)
        files["projection.json"] = canonical(projection.manifest)
        index = {
            "schema": SCHEMA,
            "archiveId": None,
            "executionId": projection.manifest["executionId"],
            "captureRevisionId": projection.manifest["captureRevisionId"],
            "projectionId": projection.manifest["projectionId"],
            "producerPins": producer_pins(),
            "capture": file_ref("capture.json", files["capture.json"]),
            "projection": file_ref("projection.json", files["projection.json"]),
            "inventory": [file_ref(name, raw) for name, raw in sorted(files.items())],
            "totals": {
                "contentFiles": len(files),
                "contentBytes": sum(map(len, files.values())),
                "publishedEntries": len(files) + len(directories(files)) + 2,
            },
            "evidenceKind": "mock",
            "inferenceCallsExecuted": 0,
            "executionReady": False,
            "semanticQualityEvidence": False,
        }
        index["archiveId"] = identity(
            "archive",
            {key: value for key, value in index.items() if key != "archiveId"},
        )
        check_index(index)
        self._index = canonical(index)
        self._files = MappingProxyType(files)

    @property
    def index_bytes(self):
        return self._index

    @property
    def index(self):
        from execution_plan import Store

        return Store.decode_json(self._index)

    @property
    def files(self):
        return self._files


def prepare_archive(projection):
    return ArchivePlan(projection)
