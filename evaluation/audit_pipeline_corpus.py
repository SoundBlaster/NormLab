"""Inventory existing development texts without inference or label promotion."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "fixtures/parking-pilot"
DEFAULT = BASE / "pipeline-quality-v1/corpus-inventory.json"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def inventory():
    datasets = []
    all_hashes = []
    for name, filename, group_field, labels_status in [
        ("stage1-audit-v2", "sources.json", "familyId", "candidate-llm-reviewed"),
        ("synthetic-v1", "manifest.json", "family", "partial-candidate-probes"),
        ("corpus", "manifest.json", "sourceGroup", "unlabelled-editorial"),
    ]:
        path = BASE / name / filename
        raw = path.read_bytes()
        manifest = json.loads(raw)
        records = []
        for case in manifest["cases"]:
            if "sourceText" in case:
                source = case["sourceText"].encode("utf-8")
                locator = f"{path.relative_to(ROOT)}#cases/{case['id']}/sourceText"
            else:
                source_path = (path.parent / case["sourceFile"]).resolve()
                if not source_path.is_relative_to(path.parent.resolve()):
                    raise ValueError("Source path escapes its dataset")
                source = source_path.read_bytes()
                source.decode("utf-8", errors="strict")
                locator = str(source_path.relative_to(ROOT))
            digest = sha(source)
            if digest != case["sourceDigest"]:
                raise ValueError(f"Source digest mismatch: {name}/{case['id']}")
            if "development" not in case["split"] or case.get("holdoutEligible"):
                raise ValueError("Existing texts must remain development-only")
            all_hashes.append(digest)
            records.append(
                {
                    "id": case["id"],
                    "source": locator,
                    "sourceDigest": digest,
                    "declaredGroup": case[group_field],
                    "split": case["split"],
                    "holdoutEligible": False,
                }
            )
        datasets.append(
            {
                "id": name,
                "manifest": str(path.relative_to(ROOT)),
                "manifestDigest": sha(raw),
                "inputCount": len(records),
                "groupMeaning": group_field,
                "declaredGroupCount": len({r["declaredGroup"] for r in records}),
                "labelsStatus": labels_status,
                "records": records,
            }
        )
    duplicates = [
        {"sourceDigest": digest, "occurrences": count}
        for digest, count in sorted(Counter(all_hashes).items())
        if count > 1
    ]
    return {
        "schema": "normlab.pipeline-quality-corpus-inventory/v1",
        "purpose": "pipeline-development-not-provider-ranking",
        "inputCount": len(all_hashes),
        "uniqueTextDigestCount": len(set(all_hashes)),
        "independentCaseCount": None,
        "independenceStatus": "manual-cross-dataset-family-dedup-pending",
        "holdoutEligibleCount": 0,
        "goldCasePassRate": None,
        "exactDuplicates": duplicates,
        "datasets": datasets,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        result = inventory()
        if args.check:
            if json.loads(args.output.read_bytes()) != result:
                raise ValueError(
                    "Inventory is stale; review changes before regeneration"
                )
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as output:
                output.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({k: v for k, v in result.items() if k != "datasets"}))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "rejected", "errorType": type(error).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
