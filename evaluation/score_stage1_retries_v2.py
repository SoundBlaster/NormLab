"""SDK-free sealed retry scoring: first-attempt availability and final agreement."""

import argparse
import itertools
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from harness import artifact, digest, load_json, require
from plan_stage1_comparison import LABELS
from score_stage1_providers import candidate_labels, ratio, save_new
from stage1_provider_plan import sha
from stage1_retry_executor_v2 import prepare, replay, retryable


def binding(plan, folder):
    replay(plan, folder)
    index, raw = load_json(folder / "capture.json")
    _, plan_raw = load_json(folder / "plan.json")
    exported_plan_digest = digest(plan_raw)
    children = []
    for entry in index["attempts"]:
        child = folder / entry["path"]
        capture = child / "capture.json"
        child_plan = child / "plan.json"
        if capture.exists():
            value, child_raw = load_json(capture)
            child_digest, turns = digest(child_raw), value["turnArtifacts"]
        else:
            child_digest, turns = None, None
        plan_digest = None
        if child_plan.exists():
            _, plan_raw = load_json(child_plan)
            plan_digest = digest(plan_raw)
        children.append(
            {
                "path": entry["path"],
                "captureDigest": child_digest,
                "planDigest": plan_digest,
                "turnArtifacts": turns,
            }
        )
    return {
        "planDigest": sha(plan),
        "exportedPlanDigest": exported_plan_digest,
        "captureDigest": digest(raw),
        "attemptArtifacts": children,
        "scorerCodePins": {
            name: digest(Path(__file__).with_name(name).read_bytes())
            for name in ("score_stage1_retries_v2.py", "score_stage1_providers.py")
        },
    }


def seal(plan, folder):
    return {
        "schema": "normlab.stage1-retry-prediction-seal/v2",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        **binding(plan, folder),
    }


def attempts(plan, folder, index):
    groups = defaultdict(list)
    for entry in index["attempts"]:
        child = folder / entry["path"]
        if (child / "capture.json").exists():
            capture, _ = load_json(child / "capture.json")
            turn = artifact(child.resolve(), capture["turnArtifacts"][0])
            dispatches = turn["dispatches"]
        else:
            turn, dispatches = None, 1  # Conservative unknown reservation, as replay.
        finished = entry["finished"] and turn is not None
        completed = turn["result"] if turn and turn["status"] == "completed" else None
        result = completed if finished else None
        groups[entry["jobId"]].append(
            {
                "ordinal": entry["ordinal"],
                "finished": finished,
                "status": turn["status"] if finished else "unknown-sent-outcome",
                "error": turn["error"] if turn else None,
                "exceptionClasses": entry["exceptionClasses"],
                "dispatches": dispatches,
                "observed": result["label"] if result else None,
                "usage": completed["usage"] if completed else None,
                "scheduledBackoffSeconds": entry["backoffSeconds"],
                "retryEligible": bool(
                    finished and retryable(turn, entry["exceptionClasses"])
                ),
            }
        )
    # Child executors accept each standalone model; outer replay rejects cross-job drift.
    if index["stopReason"] == "returned-model-change" and index["attempts"]:
        last = groups[index["attempts"][-1]["jobId"]][-1]
        last.update(status="model-rejected", observed=None)
    return groups


def metrics(rows, phase):
    completed = [r for r in rows if r[phase]["observed"] is not None]
    matched = sum(r[phase]["matches"] for r in completed)
    by_case = defaultdict(list)
    for row in rows:
        by_case[row["caseId"]].append(row)
    return {
        "plannedJobs": len(rows),
        "completedJobs": len(completed),
        "statuses": dict(Counter(r[phase]["status"] for r in rows)),
        "completionPerPlanned": ratio(len(completed), len(rows)),
        "candidateMatches": matched,
        "candidateAgreementAmongCompleted": ratio(matched, len(completed)),
        "candidateMatchesPerPlanned": ratio(matched, len(rows)),
        "confusionExpectedToObserved": {
            label: dict(
                Counter(
                    r[phase]["observed"] for r in completed if r["expected"] == label
                )
            )
            for label in LABELS
        },
        "casesPlanned": len(by_case),
        "casesFullyCompleted": sum(
            all(r[phase]["observed"] is not None for r in group)
            for group in by_case.values()
        ),
        "casesAllPlannedVerdictsMatch": sum(
            all(r[phase]["matches"] for r in group) for group in by_case.values()
        ),
    }


def paired(rows, arms, phase):
    reports = []
    for arm_a, arm_b in itertools.combinations(arms, 2):
        maps = [
            {
                (r["caseId"], r["recordId"], r["repeat"]): r
                for r in rows
                if r["armId"] == arm
            }
            for arm in (arm_a, arm_b)
        ]
        require(maps[0].keys() == maps[1].keys(), "Matched semantic denominator")
        complete = [
            (a, maps[1][key])
            for key, a in maps[0].items()
            if a[phase]["observed"] is not None
            and maps[1][key][phase]["observed"] is not None
        ]
        reports.append(
            {
                "armA": arm_a,
                "armB": arm_b,
                "plannedPairs": len(maps[0]),
                "bothCompleted": len(complete),
                "bothMatch": sum(
                    a[phase]["matches"] and b[phase]["matches"] for a, b in complete
                ),
                "onlyAMatches": sum(
                    a[phase]["matches"] and not b[phase]["matches"] for a, b in complete
                ),
                "onlyBMatches": sum(
                    b[phase]["matches"] and not a[phase]["matches"] for a, b in complete
                ),
                "neitherMatches": sum(
                    not a[phase]["matches"] and not b[phase]["matches"]
                    for a, b in complete
                ),
            }
        )
    return reports


def score(manifest, plan, folder, seal_path):
    saved, raw = load_json(seal_path)
    keys = {
        "planDigest",
        "exportedPlanDigest",
        "captureDigest",
        "attemptArtifacts",
        "scorerCodePins",
    }
    require(
        set(saved) == keys | {"schema", "createdAt"}
        and saved["schema"] == "normlab.stage1-retry-prediction-seal/v2",
        "Retry seal shape",
    )
    frozen = {k: saved[k] for k in keys}
    require(frozen == binding(plan, folder), "Retry capture changed after sealing")
    # No label reads happen until both outer and every child capture are bound.
    labels, labels_digest = candidate_labels(manifest, plan["parent"])
    index, _ = load_json(folder / "capture.json")
    groups = attempts(plan, folder, index)
    rows = []
    for job in plan["parent"]["jobs"]:
        history = groups[job["jobId"]]
        expected = labels[(job["caseId"], job["recordId"])]["expectation"]
        row = {
            k: job[k]
            for k in ("jobId", "armId", "caseId", "familyId", "recordId", "repeat")
        }
        row.update(
            expected=expected,
            attempts=history,
            attemptsStarted=len(history),
            dispatches=sum(a["dispatches"] for a in history),
            firstFailureRetryEligible=bool(history and history[0]["retryEligible"]),
        )
        for phase, turn in (
            ("first", history[0] if history else None),
            ("final", history[-1] if history else None),
        ):
            observed = turn["observed"] if turn else None
            row[phase] = {
                "status": turn["status"] if turn else "not-executed",
                "observed": observed,
                "matches": observed == expected,
            }
        rows.append(row)
    arms = {}
    for arm in plan["parent"]["providers"]:
        subset = [r for r in rows if r["armId"] == arm]
        history = [a for r in subset for a in r["attempts"]]
        started = sum(bool(r["attempts"]) for r in subset)
        eligible = sum(r["firstFailureRetryEligible"] for r in subset)
        recovered = sum(
            r["firstFailureRetryEligible"] and r["final"]["observed"] is not None
            for r in subset
        )
        arms[arm] = {
            "first": metrics(subset, "first"),
            "final": metrics(subset, "final"),
            "startedJobs": started,
            "firstAttemptCompletionAmongStarted": ratio(
                sum(r["first"]["observed"] is not None for r in subset), started
            ),
            "finalCompletionAmongStarted": ratio(
                sum(r["final"]["observed"] is not None for r in subset), started
            ),
            "retryEligibleFirstFailures": eligible,
            "recoveredJobs": recovered,
            "recoveryAmongRetryEligibleFirstFailures": ratio(recovered, eligible),
            "recoveredMatchingCandidate": sum(
                r["firstFailureRetryEligible"] and r["final"]["matches"] for r in subset
            ),
            "attemptsStarted": len(history),
            "retryAttemptsStarted": sum(
                max(0, r["attemptsStarted"] - 1) for r in subset
            ),
            "dispatches": sum(a["dispatches"] for a in history),
            "firstDispatches": sum(
                r["attempts"][0]["dispatches"] for r in subset if r["attempts"]
            ),
            "retryDispatches": sum(
                a["dispatches"] for r in subset for a in r["attempts"][1:]
            ),
            "dispatchedAttemptsWithoutUsage": sum(
                a["dispatches"] and a["usage"] is None for a in history
            ),
            "knownInputTokens": sum(
                a["usage"]["input_tokens"] for a in history if a["usage"]
            ),
            "knownOutputTokens": sum(
                a["usage"]["output_tokens"] for a in history if a["usage"]
            ),
            "scheduledBackoffSeconds": sum(
                a["scheduledBackoffSeconds"] or 0 for a in history
            ),
        }
    run_summary = replay(plan, folder)
    require(
        sum(a["dispatches"] for a in arms.values())
        == run_summary["networkCalls"] + run_summary["mockHttpCalls"],
        "Scored dispatch accounting",
    )
    require(frozen == binding(plan, folder), "Retry capture changed during scoring")
    return {
        "schema": "normlab.stage1-retry-score/v2",
        **frozen,
        "sealDigest": digest(raw),
        "labelsDigest": labels_digest,
        "mode": index["mode"],
        "stopReason": run_summary["stopReason"],
        "annotationStatus": "candidate-not-independent",
        "semanticQualityEvidence": False,
        "populationAccuracy": None,
        "criticalErrorFreeRate": None,
        "statisticalSignificance": None,
        "actualCost": None,
        "arms": arms,
        "paired": {phase: paired(rows, arms, phase) for phase in ("first", "final")},
        "rows": rows,
    }


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
        require(not (args.seal_output and args.output), "Seal uses its own output")
        plan = prepare(args.manifest, args.profile)
        if args.seal_output:
            report = seal(plan, args.capture)
            save_new(args.seal_output, report)
        else:
            report = score(args.manifest, plan, args.capture, args.seal)
            if args.output:
                save_new(args.output, report)
        print(
            json.dumps(
                {
                    k: v
                    for k, v in report.items()
                    if k not in ("rows", "attemptArtifacts")
                },
                ensure_ascii=False,
            )
        )
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "rejected", "errorType": type(error).__name__}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
