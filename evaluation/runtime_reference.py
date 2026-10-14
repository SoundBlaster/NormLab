"""Closed, source-bound selected-question references; review declarations are unsigned."""

import json
from types import MappingProxyType

from execution_outcomes import answer_schema
from execution_records import items, revision, text
from offline_bundle import (
    MAX_BYTES,
    canonical,
    decode,
    identity,
    object_keys,
    require,
    sha,
)
from runtime_archive_reader import VerifiedArchive

SOURCE_SCHEMA = "normlab.runtime-reference-source/v1"
REVIEW_SCHEMA = "normlab.runtime-reference-review/v1"
STATUSES = {"candidate-not-independent", "human-adjudicated"}


class RuntimeReference:
    def __init__(self, document, source, reviews):
        self._document = canonical(document)
        self._files = MappingProxyType({sha(raw): raw for raw in [source, *reviews]})
        self._source, self._reviews = source, tuple(reviews)

    @property
    def document(self):
        return json.loads(self._document)

    @property
    def files(self):
        return self._files

    @property
    def inputs(self):
        return {
            "sourceUtf8": self._source.decode(),
            "reviewsUtf8": [raw.decode() for raw in self._reviews],
        }


def reference(archive, source_raw, review_raw=()):
    require(type(archive) is VerifiedArchive, "Verified archive before reference")
    require(
        type(source_raw) is bytes and 0 < len(source_raw) <= MAX_BYTES,
        "Reference source cap",
    )
    require(
        isinstance(review_raw, (list, tuple)) and len(review_raw) <= 16,
        "Review inventory cap",
    )
    require(
        all(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES for raw in review_raw),
        "Review artifact cap",
    )
    require(
        len(source_raw) + sum(map(len, review_raw)) <= MAX_BYTES,
        "Reference aggregate cap",
    )
    require(
        len({sha(raw) for raw in review_raw}) == len(review_raw),
        "Unique review artifacts",
    )
    source = decode(source_raw)
    object_keys(source, "schema revision status planDigest dataset expected")
    require(
        source["schema"] == SOURCE_SCHEMA and source["status"] in STATUSES,
        "Reference schema/status",
    )
    text(source["revision"])
    plan = archive.snapshot.plan
    revision(source["dataset"])
    require(
        source["planDigest"] == archive.projection.manifest["planDigest"]
        and canonical(source["dataset"]) == canonical(plan["dataset"]),
        "Reference plan/dataset binding",
    )
    questions = answer_schema(
        decode(archive.snapshot.files[plan["pins"]["outputSchema"]["path"]])
    )
    tasks = {task["key"]: task for task in plan["tasks"]}
    items(source["expected"], 1, maximum=4096)
    seen = set()
    for entry in source["expected"]:
        object_keys(entry, "taskKey questionId label")
        key, qid, label = entry["taskKey"], entry["questionId"], entry["label"]
        require(
            isinstance(key, str)
            and key in tasks
            and isinstance(qid, str)
            and qid in tasks[key]["questionIds"],
            "Reference selected task/question",
        )
        require((key, qid) not in seen, "Unique reference selection")
        seen.add((key, qid))
        definition = questions[qid]
        if definition["type"] == "noul":
            require(
                isinstance(label, str) and label in {"yes", "no", "uncertain"},
                "Noul reference label",
            )
        elif definition["type"] == "choice":
            require(
                isinstance(label, str) and label in definition["labels"],
                "Choice reference label",
            )
        else:
            require(
                type(label) is int and 0 <= label < len(definition["labels"]),
                "Score reference scale index",
            )
    require(
        source["status"] != "candidate-not-independent" or not review_raw,
        "Candidate reference has no adjudication claims",
    )
    require(
        source["status"] != "human-adjudicated" or bool(review_raw),
        "Human review evidence required",
    )
    for raw in review_raw:
        review = decode(raw)
        object_keys(
            review,
            "schema reviewer method sourceDigest planDigest dataset scope approved",
        )
        text(review["reviewer"])
        text(review["method"])
        require(
            review["schema"] == REVIEW_SCHEMA
            and review["sourceDigest"] == sha(source_raw)
            and review["planDigest"] == source["planDigest"]
            and canonical(review["dataset"]) == canonical(source["dataset"])
            and review["scope"] == "selected-questions-only"
            and review["approved"] is True,
            "Review source/plan/scope binding",
        )

    def ref(raw):
        return {"sha256": sha(raw), "bytes": len(raw)}

    document = {
        "schema": "normlab.runtime-reference/v1",
        "referenceId": None,
        "revision": source["revision"],
        "status": source["status"],
        "planDigest": source["planDigest"],
        "dataset": source["dataset"],
        "expected": source["expected"],
        "provenance": {
            "source": ref(source_raw),
            "reviews": [ref(raw) for raw in review_raw],
        },
        "scope": "selected-questions-only",
        "reviewAuthenticated": False,
        "criticalErrorFreeRate": None,
        "semanticQualityEvidence": False,
    }
    document["referenceId"] = identity(
        "runtime-reference", {k: v for k, v in document.items() if k != "referenceId"}
    )
    require(len(canonical(document)) <= MAX_BYTES, "Reference projection cap")
    return RuntimeReference(document, source_raw, review_raw)
