"""Deterministically regenerate frozen native score views from verified inputs.

No reference loader or CLI is called here. Bindings and provenance are validated
by offline_stage1_reference before these frozen scoring formulas are applied.
"""

import itertools
from collections import Counter, defaultdict
from pathlib import Path

from harness import artifact, load_json
from offline_bundle import require, sha
from plan_stage1_comparison import LABELS
from score_stage1_providers import ratio
from score_stage1_retries_v2 import attempts, metrics, paired


def provider_report(plan, folder, seal_raw, expected, labels_digest, binding, summary):
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
    return {
        "schema": "normlab.stage1-provider-score/v1",
        "planDigest": binding["planDigest"],
        "captureDigest": binding["captureDigest"],
        "sealDigest": sha(seal_raw),
        "labelsDigest": labels_digest,
        "scorerDigest": sha(
            Path(__file__).with_name("score_stage1_providers.py").read_bytes()
        ),
        "mode": index["mode"],
        "annotationStatus": "candidate-not-independent",
        "semanticQualityEvidence": False,
        "criticalErrorFreeRate": None,
        "populationAccuracy": None,
        "statisticalSignificance": None,
        "scope": "selected-claim-support-on-diagnostic-development-cases",
        "stopReason": summary["stopReason"],
        "arms": arms,
        "paired": paired,
        "rows": rows,
    }


def retry_report(plan, folder, seal_raw, labels, labels_digest, binding, summary):
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
    require(
        sum(a["dispatches"] for a in arms.values())
        == summary["networkCalls"] + summary["mockHttpCalls"],
        "Scored dispatch accounting",
    )
    return {
        "schema": "normlab.stage1-retry-score/v2",
        **binding,
        "sealDigest": sha(seal_raw),
        "labelsDigest": labels_digest,
        "mode": index["mode"],
        "stopReason": summary["stopReason"],
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
