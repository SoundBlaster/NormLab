"""Collect pinned public development inputs; never run inference or infer gold labels."""

import argparse
import hashlib
import json
import shutil
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "fixtures/external-diagnostics-v1"
SEED = "normlab-external-diagnostics-v1"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def jsonl_bytes(rows):
    return ("\n".join(canonical(row) for row in rows) + "\n").encode()


def rank(value):
    return digest((SEED + "\n" + canonical(value)).encode())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def acquire(lock, cache, fetch):
    cache.mkdir(parents=True, exist_ok=True)
    for artifact in lock["artifacts"]:
        path = cache / artifact["cacheFile"]
        if not path.exists() and fetch:
            partial = path.with_suffix(path.suffix + ".partial")
            with urllib.request.urlopen(artifact["url"], timeout=60) as response:
                with partial.open("wb") as output:
                    shutil.copyfileobj(response, output)
            require(digest(partial.read_bytes()) == artifact["sha256"], "Download hash")
            partial.replace(path)
        require(digest(path.read_bytes()) == artifact["sha256"], "Upstream hash")


def collect(cache):
    inputs, annotations, records = [], [], []

    def add(dataset, ordinal, row, text, candidate=None, related=None):
        case_id = f"EXT-{dataset.upper()}-{ordinal:03d}"
        text_hash = digest(text.encode())
        item = {"id": case_id, "sourceText": text}
        if candidate is not None:
            item["candidateText"] = candidate
        inputs.append(item)
        annotations.append(
            {
                "id": case_id,
                "reviewStatus": "pending-human-rubric-review",
                "criticalErrorFree": None,
                "expectedClaims": None,
                "expectedGaps": None,
                "upstreamAnnotation": (
                    {
                        key: row.get(key)
                        for key in ("label", "verb", "negation", "genre")
                    }
                    if dataset == "rcb"
                    else None
                ),
            }
        )
        records.append(
            {
                "id": case_id,
                "dataset": dataset,
                "task": "textual-entailment"
                if dataset == "rcb"
                else "claim-extraction",
                "split": "development-external-diagnostic",
                "holdoutEligible": False,
                "upstreamSplit": "train",
                "upstreamId": row["idx"] if dataset == "rcb" else row["id"],
                "upstreamRecordSha256": digest(canonical(row).encode()),
                "relatedUpstreamRows": related,
                "sourceField": "premise" if dataset == "rcb" else "source",
                "sourceDigest": text_hash,
                "candidateDigest": digest(candidate.encode()) if candidate else None,
                "exactTextGroup": f"{dataset}:{text_hash}",
                "originDocumentUrl": None,
                "category": row.get("category"),
                "license": "MIT" if dataset == "rcb" else "GPL-3.0",
                "transformations": [],
            }
        )

    with zipfile.ZipFile(cache / "rcb.zip") as archive:
        rcb = [
            json.loads(line) for line in archive.read("RCB/train.jsonl").splitlines()
        ]
    used = set()
    selected_rcb = []
    for label in ("entailment", "contradiction", "neutral"):
        for negation in ("negation", "no_negation"):
            count = 0
            candidates = (
                r for r in rcb if r["label"] == label and r.get("negation") == negation
            )
            for row in sorted(candidates, key=rank):
                text_hash = digest(row["premise"].encode())
                if text_hash in used:
                    continue
                used.add(text_hash)
                selected_rcb.append(row)
                count += 1
                if count == 4:
                    break
            require(count == 4, f"Insufficient RCB records: {label}/{negation}")

    # Assign public IDs only after a label-independent global ordering. The
    # stratified selection above must not leak its label/negation loop order.
    for ordinal, row in enumerate(sorted(selected_rcb, key=rank), start=1):
        add("rcb", ordinal, row, row["premise"], row["hypothesis"])

    courts = json.loads((cache / "court.json").read_bytes())
    grouped = defaultdict(list)
    for index, row in enumerate(courts):
        grouped[digest(row["source"].encode())].append((index, row))
    court_count = 0
    for category, quota in (
        ("sud_resh_admin_pravo", 6),
        ("sud_resh_grazhd_pravo", 3),
        ("sud_resh_fin_pravo", 3),
    ):
        eligible = [
            (text_hash, members)
            for text_hash, members in grouped.items()
            if members[0][1]["category"] == category
            and 1500 <= len(members[0][1]["source"]) <= 20000
        ]
        chosen = sorted(eligible, key=lambda group: rank(group[0]))[:quota]
        require(len(chosen) == quota, f"Insufficient court records: {category}")
        for _, members in chosen:
            index, row = min(members, key=lambda pair: pair[1]["id"])
            court_count += 1
            related = [
                {"id": member["id"], "jsonPointer": f"/{i}/source"}
                for i, member in sorted(members)
            ]
            add("sud", court_count, row, row["source"], related=related)
            records[-1]["upstreamJsonPointer"] = f"/{index}/source"
    return inputs, annotations, records


def build(lock_path, cache, output, fetch):
    lock = json.loads(lock_path.read_bytes())
    acquire(lock, cache, fetch)
    inputs, annotations, records = collect(cache)
    files = {
        "inputs.jsonl": jsonl_bytes(inputs),
        "reviewer-annotations.jsonl": jsonl_bytes(annotations),
        "upstream-sources.json": lock_path.read_bytes(),
    }
    for item, record in zip(inputs, records):
        name = f"texts/{item['id']}.source.txt"
        files[name] = item["sourceText"].encode()
        record["sourceFile"] = name
    for artifact in lock["artifacts"]:
        if artifact.get("snapshotFile"):
            files[artifact["snapshotFile"]] = (
                cache / artifact["cacheFile"]
            ).read_bytes()
    manifest = {
        "schema": "normlab.external-diagnostic-corpus/v1",
        "collectedOn": "2026-10-11",
        "purpose": "pipeline-development-not-provider-ranking",
        "inputCount": len(inputs),
        "datasetCounts": dict(Counter(record["dataset"] for record in records)),
        "independentCaseCount": None,
        "holdoutEligibleCount": 0,
        "goldCasePassRate": None,
        "selection": {
            "seed": SEED,
            "order": "ascending SHA256(seed + newline + canonical JSON)",
            "rcbIdAssignment": "selected rows globally sorted by the same label-independent rank before sequential IDs",
            "rcb": "train only; 4 negation + 4 no_negation per label; unique premise hashes",
            "sud": "6 admin, 3 civil, 3 financial; unique source hashes; 1500..20000 chars",
            "dependenceReview": "exact text grouped; incident and semantic dedup pending",
            "contamination": "public training exposure unknown; development only",
        },
        "files": {name: digest(raw) for name, raw in sorted(files.items())},
        "records": records,
    }
    files["manifest.json"] = json_bytes(manifest)
    require(
        all(not (output / name).exists() for name in files),
        "Output exists; build into a new directory and review changes",
    )
    for name, raw in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as target:
            target.write(raw)


def check(output):
    manifest = json.loads((output / "manifest.json").read_bytes())
    for name, expected in manifest["files"].items():
        path = (output / name).resolve()
        require(path.is_relative_to(output.resolve()), "Snapshot path escapes corpus")
        require(digest(path.read_bytes()) == expected, f"Snapshot hash: {name}")
    inputs = [
        json.loads(line) for line in (output / "inputs.jsonl").read_bytes().splitlines()
    ]
    annotations = [
        json.loads(line)
        for line in (output / "reviewer-annotations.jsonl").read_bytes().splitlines()
    ]
    records = manifest["records"]
    ids = [item["id"] for item in inputs]
    require(
        len(ids) == len(set(ids)) == manifest["inputCount"] == 36, "Input count/IDs"
    )
    require(
        ids == [r["id"] for r in records] == [a["id"] for a in annotations], "Join IDs"
    )
    require(manifest["holdoutEligibleCount"] == 0, "No holdout")
    require(manifest["independentCaseCount"] is None, "Independence not established")
    require(manifest["goldCasePassRate"] is None, "No full gold quality score")
    require(
        Counter(r["dataset"] for r in records) == {"rcb": 24, "sud": 12},
        "Dataset quotas",
    )
    require(
        Counter(
            (a["upstreamAnnotation"]["label"], a["upstreamAnnotation"]["negation"])
            for a in annotations
            if a["upstreamAnnotation"] is not None
        )
        == {
            (label, neg): 4
            for label in ("entailment", "contradiction", "neutral")
            for neg in ("negation", "no_negation")
        },
        "RCB strata",
    )
    for item, record, annotation in zip(inputs, records, annotations):
        allowed = {"id", "sourceText", "candidateText"}
        require(set(item) <= allowed, "Reviewer metadata in model input")
        require(
            digest(item["sourceText"].encode()) == record["sourceDigest"], "Text hash"
        )
        require(
            (output / record["sourceFile"]).read_bytes() == item["sourceText"].encode(),
            "Readable text differs from model input",
        )
        candidate = item.get("candidateText")
        require(
            (digest(candidate.encode()) if candidate else None)
            == record["candidateDigest"],
            "Candidate hash",
        )
        require(not record["holdoutEligible"], "Development only")
        require(record["transformations"] == [], "No text normalization")
        require(annotation["criticalErrorFree"] is None, "No inferred gold")
    require(len({r["sourceDigest"] for r in records}) == 36, "Exact duplicate inputs")
    print(json.dumps({"status": "ok", "inputs": 36, "holdout": 0, "inferenceCalls": 0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT)
    parser.add_argument("--lock", type=Path, default=DEFAULT / "upstream-sources.json")
    parser.add_argument("--cache", type=Path)
    parser.add_argument(
        "--fetch", action="store_true", help="Download hash-pinned public files"
    )
    parser.add_argument(
        "--check", action="store_true", help="Offline snapshot consistency only"
    )
    args = parser.parse_args()
    if args.check:
        require(not args.fetch and args.cache is None, "Check is offline")
        check(args.output)
    else:
        require(args.cache is not None, "Build requires --cache")
        build(args.lock, args.cache, args.output, args.fetch)
        check(args.output)


if __name__ == "__main__":
    main()
