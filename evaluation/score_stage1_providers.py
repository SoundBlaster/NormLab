"""Seal and score replay-validated Stage 1 captures without SDKs or network."""

import argparse
import itertools
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from harness import artifact, digest, load_json, require
from plan_stage1_comparison import LABELS, ROOT, bound
from stage1_provider_executor import replay
from stage1_provider_plan import prepare, sha


def capture_binding(plan, folder):
    replay(plan, folder)
    index, raw = load_json(folder / "capture.json")
    return {
        "planDigest": sha(plan),
        "captureDigest": digest(raw),
        "turnArtifacts": index["turnArtifacts"],
    }


def seal(plan, folder):
    return {
        "schema": "normlab.stage1-prediction-seal/v1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        **capture_binding(plan, folder),
    }


def candidate_labels(manifest_path, plan):
    manifest, _ = load_json(manifest_path)
    parent = bound(manifest["parent"])
    dataset = bound(parent["artifacts"]["datasetManifest"])
    dataset_path = ROOT / parent["artifacts"]["datasetManifest"]["path"]
    entry = dataset["artifacts"]["reviewer-only"]
    labels = artifact(dataset_path.parent.resolve(), entry)
    require(
        labels["schema"] == "normlab.stage1-review/v2"
        and labels["datasetId"] == plan["datasetId"]
        and labels["sourcesDigest"] == parent["artifacts"]["sources"]["sha256"]
        and labels["labelStatus"] == "candidate-not-independent"
        and labels["evaluationPolicy"] == "selected-claim-support",
        "Candidate label provenance",
    )
    cases = {row["caseId"]: row for row in labels["cases"]}
    require(len(cases) == len(labels["cases"]), "Unique annotation cases")
    rows = {(r["caseId"], r["recordId"]): r for r in labels["records"]}
    require(len(rows) == len(labels["records"]), "Unique annotation records")
    for job in plan["jobs"]:
        row = rows[(job["caseId"], job["recordId"])]
        require(row["expectation"] in LABELS, "Known candidate expectation")
        require(
            cases[job["caseId"]]["sourceDigest"] == job["sourceDigest"],
            "Annotation source binding",
        )
    return rows, entry["sha256"]


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def score(manifest_path, plan, folder, seal_path):
    saved, seal_raw = load_json(seal_path)
    require(
        set(saved)
        == {"schema", "createdAt", "planDigest", "captureDigest", "turnArtifacts"}
        and saved["schema"] == "normlab.stage1-prediction-seal/v1",
        "Prediction seal shape",
    )
    require(
        {k: saved[k] for k in ("planDigest", "captureDigest", "turnArtifacts")}
        == capture_binding(plan, folder),
        "Capture changed after sealing",
    )
    # Label artifacts are opened only after the capture has passed replay and seal.
    expected, labels_digest = candidate_labels(manifest_path, plan)
    index, _ = load_json(folder / "capture.json")
    rows = []
    for job, entry in zip(plan["jobs"], index["turnArtifacts"]):
        turn = artifact(folder.resolve(), entry)
        label = turn["result"]["label"] if turn["status"] == "completed" else None
        expectation = expected[(job["caseId"], job["recordId"])]["expectation"]
        rows.append(
            {
                **{
                    k: job[k]
                    for k in (
                        "jobId",
                        "armId",
                        "caseId",
                        "familyId",
                        "recordId",
                        "repeat",
                    )
                },
                "status": turn["status"],
                "error": turn["error"],
                "expected": expectation,
                "observed": label,
                "agrees": label == expectation,
            }
        )
    arms = {}
    for arm in plan["providers"]:
        subset = [r for r in rows if r["armId"] == arm]
        completed = [r for r in subset if r["status"] == "completed"]
        correct = sum(r["agrees"] for r in completed)
        by_case, by_record = defaultdict(list), defaultdict(list)
        for row in subset:
            by_case[row["caseId"]].append(row)
            by_record[(row["caseId"], row["recordId"])].append(row)
        complete_cases = sum(
            all(r["status"] == "completed" for r in group) for group in by_case.values()
        )
        all_correct = sum(all(r["agrees"] for r in group) for group in by_case.values())
        confusion = {
            label: dict(
                Counter(r["observed"] for r in completed if r["expected"] == label)
            )
            for label in LABELS
        }
        arms[arm] = {
            "planned": len(subset),
            "completed": len(completed),
            "statuses": dict(Counter(r["status"] for r in subset)),
            "candidateMatches": correct,
            "candidateAgreementAmongCompleted": ratio(correct, len(completed)),
            "candidateMatchesPerPlanned": ratio(correct, len(subset)),
            "confusionExpectedToObserved": confusion,
            "casesPlanned": len(by_case),
            "casesFullyCompleted": complete_cases,
            "casesAllPlannedVerdictsMatch": all_correct,
            "casesAllPlannedVerdictsMatchRate": ratio(all_correct, len(by_case)),
            "recordsWithAllRepeatsCompleted": sum(
                all(r["status"] == "completed" for r in group)
                for group in by_record.values()
            ),
            "recordsWithObservedLabelVariation": sum(
                len({r["observed"] for r in group if r["observed"] is not None}) > 1
                for group in by_record.values()
            ),
        }
    paired = []
    for arm_a, arm_b in itertools.combinations(plan["providers"], 2):
        maps = [
            {
                (r["caseId"], r["recordId"], r["repeat"]): r
                for r in rows
                if r["armId"] == arm
            }
            for arm in (arm_a, arm_b)
        ]
        require(maps[0].keys() == maps[1].keys(), "Matched comparison denominator")
        both = [
            (a, maps[1][key])
            for key, a in maps[0].items()
            if a["observed"] is not None and maps[1][key]["observed"] is not None
        ]
        paired.append(
            {
                "armA": arm_a,
                "armB": arm_b,
                "plannedPairs": len(maps[0]),
                "bothCompleted": len(both),
                "bothMatch": sum(a["agrees"] and b["agrees"] for a, b in both),
                "onlyAMatches": sum(a["agrees"] and not b["agrees"] for a, b in both),
                "onlyBMatches": sum(b["agrees"] and not a["agrees"] for a, b in both),
                "neitherMatches": sum(
                    not a["agrees"] and not b["agrees"] for a, b in both
                ),
                "observedLabelsAgree": sum(
                    a["observed"] == b["observed"] for a, b in both
                ),
            }
        )
    require(
        {k: saved[k] for k in ("planDigest", "captureDigest", "turnArtifacts")}
        == capture_binding(plan, folder),
        "Capture changed during scoring",
    )
    return {
        "schema": "normlab.stage1-provider-score/v1",
        "planDigest": sha(plan),
        "captureDigest": saved["captureDigest"],
        "sealDigest": digest(seal_raw),
        "labelsDigest": labels_digest,
        "scorerDigest": digest(Path(__file__).read_bytes()),
        "mode": index["mode"],
        "annotationStatus": "candidate-not-independent",
        "semanticQualityEvidence": False,
        "criticalErrorFreeRate": None,
        "populationAccuracy": None,
        "statisticalSignificance": None,
        "scope": "selected-claim-support-on-diagnostic-development-cases",
        "stopReason": replay(plan, folder)["stopReason"],
        "arms": arms,
        "paired": paired,
        "rows": rows,
    }


def save_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(
            json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--profile", choices=("pilot", "corpus"), default="pilot")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--seal-output", type=Path)
    mode.add_argument("--seal", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        require(not (args.seal_output and args.output), "Seal uses its own output path")
        plan = prepare(args.manifest, args.profile)
        if args.seal_output:
            result = seal(plan, args.capture)
            save_new(args.seal_output, result)
        else:
            result = score(args.manifest, plan, args.capture, args.seal)
            if args.output:
                save_new(args.output, result)
        print(
            json.dumps(
                {k: v for k, v in result.items() if k not in ("rows", "turnArtifacts")},
                ensure_ascii=False,
            )
        )
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps({"status": "rejected", "errorType": type(error).__name__}))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
