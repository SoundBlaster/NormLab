"""Bounded, dependency-free offline replay. Never constructs a live provider."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from mellea_candidate import bound_fragments, parse_candidate

SCHEMA = "normlab.evaluation-experiment/v1"
SCORER = "classification-selected-probes/v1"
MAX_BYTES = 2 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value)


def load_json(path):
    require(
        path.is_file() and path.stat().st_size <= MAX_BYTES,
        "Bounded JSON file required",
    )
    raw = path.read_bytes()
    return json.loads(raw), raw


def artifact(root, entry):
    require(
        isinstance(entry, dict) and set(entry) == {"path", "sha256"},
        "Artifact reference contract",
    )
    name = entry["path"]
    require(
        isinstance(name, str)
        and not Path(name).is_absolute()
        and ".." not in Path(name).parts,
        "Relative artifact path required",
    )
    path = (root / name).resolve()
    require(path.is_relative_to(root), "Artifact escapes experiment directory")
    value, raw = load_json(path)
    require(digest(raw) == entry["sha256"], "Artifact digest mismatch")
    return value


def prepare(path, labels_path=None):
    manifest, raw = load_json(path)
    require(
        isinstance(manifest, dict)
        and set(manifest)
        == {
            "schema",
            "experimentId",
            "dataset",
            "mode",
            "strategy",
            "tactic",
            "provider",
            "budget",
            "definitions",
            "cases",
            "records",
        },
        "Experiment manifest contract",
    )
    require(
        manifest["schema"] == SCHEMA and identifier(manifest["experimentId"]),
        "Experiment identity contract",
    )
    require(manifest["mode"] == "offline-replay", "Only offline replay is implemented")
    dataset = manifest["dataset"]
    require(
        isinstance(dataset, dict) and set(dataset) == {"id", "version"},
        "Dataset contract",
    )
    require(
        identifier(dataset["id"]) and identifier(dataset["version"]),
        "Dataset identity contract",
    )
    require(
        all(identifier(manifest[k]) for k in ("strategy", "tactic")),
        "Strategy/tactic identity contract",
    )
    provider = manifest["provider"]
    require(
        isinstance(provider, dict)
        and set(provider) == {"id", "route", "requestedModel", "settings"},
        "Provider metadata contract",
    )
    require(
        identifier(provider["id"]) and identifier(provider["route"]),
        "Provider identity contract",
    )
    require(
        provider["requestedModel"] is None or identifier(provider["requestedModel"]),
        "Model identity contract",
    )
    require(
        isinstance(provider["settings"], dict) and not provider["settings"],
        "Offline v1 supports empty settings only",
    )
    budget = manifest["budget"]
    require(
        isinstance(budget, dict) and set(budget) == {"maxRecords", "liveCalls"},
        "Budget contract",
    )
    require(
        type(budget["maxRecords"]) is int
        and 0 < budget["maxRecords"] <= 256
        and budget["liveCalls"] == 0,
        "Offline budget contract",
    )
    cases, records = manifest["cases"], manifest["records"]
    require(isinstance(cases, list) and 0 < len(cases) <= 128, "Case count contract")
    require(
        isinstance(records, list) and 0 < len(records) <= budget["maxRecords"],
        "Record count contract",
    )
    root, by_case, bound = path.resolve().parent, {}, []
    definitions = artifact(root, manifest["definitions"])
    current = Path(__file__).resolve().parents[1] / "server/inference-prompts.json"
    require(
        definitions == json.loads(current.read_text()),
        "Definition version differs from current classification contract",
    )
    for case in cases:
        require(
            isinstance(case, dict)
            and set(case) == {"id", "family", "language", "input", "parent"},
            "Case contract",
        )
        require(
            identifier(case["id"])
            and case["id"] not in by_case
            and identifier(case["family"]),
            "Unique case identity required",
        )
        require(case["language"] in {"ru", "en"}, "Language contract")
        request, parent = artifact(root, case["input"]), artifact(root, case["parent"])
        bound_fragments(request, parent)
        by_case[case["id"]] = (case, request, parent)
    seen = set()
    for record in records:
        require(
            isinstance(record, dict) and set(record) == {"id", "caseId", "capture"},
            "Record contract",
        )
        require(
            identifier(record["id"])
            and record["id"] not in seen
            and record["caseId"] in by_case,
            "Unique bound record identity required",
        )
        seen.add(record["id"])
        capture = artifact(root, record["capture"])
        require(
            isinstance(capture, dict)
            and set(capture)
            == {
                "schema",
                "recordId",
                "sourceDigest",
                "parentDigest",
                "returnedModel",
                "turns",
            },
            "Capture contract",
        )
        require(
            capture["schema"] == "normlab.evaluation-capture/v1"
            and capture["recordId"] == record["id"],
            "Capture identity contract",
        )
        case, request, parent = by_case[record["caseId"]]
        require(
            capture["sourceDigest"] == request["sourceDigest"]
            and capture["parentDigest"] == case["parent"]["sha256"],
            "Capture context binding mismatch",
        )
        require(
            capture["returnedModel"] is None or identifier(capture["returnedModel"]),
            "Returned model contract",
        )
        turns = capture["turns"]
        require(
            isinstance(turns, list) and len(turns) == 1,
            "Offline v1 replays one classification turn only",
        )
        turn = turns[0]
        require(
            isinstance(turn, dict)
            and set(turn)
            == {
                "id",
                "stage",
                "status",
                "output",
                "error",
                "usage",
                "latencyMs",
                "cost",
            },
            "Turn contract",
        )
        require(
            turn["id"] == "turn_1" and turn["stage"] == "classification",
            "Turn identity contract",
        )
        require(
            turn["status"] in {"completed", "failed", "partial"}, "Turn status contract"
        )
        require(
            turn["usage"] is None
            and turn["latencyMs"] is None
            and turn["cost"] is None,
            "Fixture measurements must remain null",
        )
        if turn["status"] == "completed":
            require(
                isinstance(turn["output"], str) and turn["error"] is None,
                "Completed turn output contract",
            )
        else:
            require(
                turn["output"] is None
                and turn["error"]
                in {"transport", "refusal", "timeout", "cancelled", "unknown"},
                "Failure contract",
            )
        bound.append((record, case, parent, turn, capture["returnedModel"]))
    labels, label_hash = None, None
    if labels_path:
        labels, label_raw = load_json(labels_path)
        require(
            isinstance(labels, dict)
            and set(labels) == {"schema", "experimentDigest", "status", "expectations"},
            "Label contract",
        )
        require(
            labels["schema"] == "normlab.evaluation-labels/v1"
            and labels["experimentDigest"] == digest(raw),
            "Labels bound to another experiment",
        )
        require(
            labels["status"] == "candidate"
            and isinstance(labels["expectations"], dict)
            and set(labels["expectations"]) == seen,
            "Candidate label coverage contract",
        )
        for record, _, parent, _, _ in bound:
            expected = labels["expectations"][record["id"]]
            ids = {f["fragmentId"] for f in parent["fragments"]}
            require(isinstance(expected, list) and expected, "Expected probes required")
            pairs = set()
            for item in expected:
                require(
                    isinstance(item, dict)
                    and set(item) == {"fragmentId", "predicate", "stance"},
                    "Probe contract",
                )
                require(
                    item["fragmentId"] in ids
                    and item["predicate"] == "payment"
                    and item["stance"] in {"asserted", "denied", "unknown"},
                    "Offline v1 payment probe contract",
                )
                pair = (item["fragmentId"], item["predicate"])
                require(pair not in pairs, "Duplicate expected probe")
                pairs.add(pair)
        label_hash = digest(label_raw)
    return manifest, digest(raw), bound, labels, label_hash


def replay(prepared):
    manifest, manifest_hash, bound, labels, label_hash = prepared
    rows = []
    for record, case, parent, turn, returned_model in bound:
        row = {
            "recordId": record["id"],
            "caseId": case["id"],
            "family": case["family"],
            "language": case["language"],
            "status": turn["status"],
            "error": turn["error"],
            "structuralPass": False,
            "probePass": None,
            "mismatches": [],
            "returnedModel": returned_model,
            "usage": None,
            "latencyMs": None,
            "cost": None,
        }
        if turn["status"] == "completed":
            try:
                flat, _ = parse_candidate(turn["output"], parent["fragments"])
                row["structuralPass"] = True
                if labels:
                    actual = {
                        (i["fragmentId"], i["predicate"], i["stance"]) for i in flat
                    }
                    for probe in labels["expectations"][record["id"]]:
                        if {
                            stance
                            for fragment, predicate, stance in actual
                            if fragment == probe["fragmentId"]
                            and predicate == probe["predicate"]
                        } != {probe["stance"]}:
                            row["mismatches"].append(probe)
                    row["probePass"] = not row["mismatches"]
            except (ValueError, TypeError, KeyError):
                row["status"] = "invalid-output"
                if labels:
                    row["probePass"] = False
        elif labels:
            row["probePass"] = False
        rows.append(row)
    return {
        "schema": "normlab.evaluation-replay/v1",
        "experimentId": manifest["experimentId"],
        "dataset": manifest["dataset"],
        "manifestDigest": manifest_hash,
        "labelsDigest": label_hash,
        "scorer": SCORER,
        "scorerDigest": digest(Path(__file__).read_bytes()),
        "dependencyDigests": {
            name: digest(Path(__file__).with_name(name).read_bytes())
            for name in ("mellea_candidate.py", "classification_v3.py", "anchor.py")
        },
        "definitionsDigest": manifest["definitions"]["sha256"],
        "evidence": "offline-fixed-candidates-selected-probes",
        "provider": manifest["provider"],
        "strategy": manifest["strategy"],
        "tactic": manifest["tactic"],
        "expectationsStatus": "candidate" if labels else "not_evaluated",
        "criticalErrorFreeRate": None,
        "semanticVerifierQuality": "not_evaluated",
        "records": rows,
        "counts": {
            "total": len(rows),
            "completed": sum(r["status"] == "completed" for r in rows),
            "failed": sum(r["status"] == "failed" for r in rows),
            "partial": sum(r["status"] == "partial" for r in rows),
            "invalidOutput": sum(r["status"] == "invalid-output" for r in rows),
            "structuralPass": sum(r["structuralPass"] for r in rows),
            "probePass": sum(r["probePass"] is True for r in rows) if labels else None,
            "liveCalls": 0,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--labels", type=Path, help="Reviewer-only labels; never model input"
    )
    parser.add_argument(
        "--output", type=Path, help="New directory for immutable replay artifacts"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    prepared = prepare(args.manifest, args.labels)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "experimentId": prepared[0]["experimentId"],
                    "records": len(prepared[2]),
                    "liveCalls": 0,
                    "mode": "offline-replay",
                }
            )
        )
        return
    require(args.output is not None, "Replay requires --output")
    report = replay(prepared)
    args.output.mkdir(parents=True, mode=0o700, exist_ok=False)
    (args.output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    entries = {
        "experiment.json": args.manifest,
        "harness.py": Path(__file__),
        "classification_v3.py": Path(__file__).with_name("classification_v3.py"),
        "mellea_candidate.py": Path(__file__).with_name("mellea_candidate.py"),
        "anchor.py": Path(__file__).with_name("anchor.py"),
        "definitions.json": Path(__file__).resolve().parents[1]
        / "server/inference-prompts.json",
    }
    if args.labels:
        entries["reviewer-labels.json"] = args.labels
    for name, path in entries.items():
        (args.output / name).write_bytes(path.read_bytes())
    # Preserve the original directory-relative artifacts so the saved manifest can be replayed.
    definition_entry = prepared[0]["definitions"]
    target = args.output / "dataset" / definition_entry["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(
        (args.manifest.resolve().parent / definition_entry["path"]).read_bytes()
    )
    for case in prepared[0]["cases"]:
        for key in ("input", "parent"):
            entry = case[key]
            target = args.output / "dataset" / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(
                (args.manifest.resolve().parent / entry["path"]).read_bytes()
            )
    for record in prepared[0]["records"]:
        entry = record["capture"]
        target = args.output / "dataset" / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(
            (args.manifest.resolve().parent / entry["path"]).read_bytes()
        )
    (args.output / "dataset" / "experiment.json").write_bytes(
        args.manifest.read_bytes()
    )
    files = [
        {"path": str(p.relative_to(args.output)), "sha256": digest(p.read_bytes())}
        for p in sorted(args.output.rglob("*"))
        if p.is_file()
    ]
    (args.output / "artifact-manifest.json").write_text(
        json.dumps(
            {
                "schema": "normlab.evaluation-artifacts/v1",
                "entries": files,
                "signed": False,
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(report["counts"]))


if __name__ == "__main__":
    main()
