"""Deterministic runtime paired comparison; no inference, registry or quality promotion."""

from collections import Counter
from pathlib import Path

from offline_bundle import MAX_BYTES, canonical, identity, object_keys, require, sha
from runtime_pairing import RuntimeView, global_reasons, pair_reasons, policy, same


def side(item):
    if item is None:
        return None
    row, question = item["row"], item["question"]
    return {
        **{
            k: row[k]
            for k in (
                "taskId",
                "taskKey",
                "status",
                "attempts",
                "record",
                "firstOutcome",
                "finalOutcome",
            )
        },
        **{
            k: question[k]
            for k in (
                "selected",
                "expected",
                "type",
                "prediction",
                "agreement",
                "firstPrediction",
                "firstAgreement",
                "notEvaluatedReason",
            )
        },
    }


def verdict(a, b):
    return "regression" if a and not b else "rescue" if b and not a else "unchanged"


def paired_summary(rows):
    final = [r for r in rows if r["state"] == "evaluated"]
    first = [r for r in rows if r["firstVerdict"] is not None]

    def agreement(entries, field):
        count = len(entries)
        a = sum(r["baseline"][field] is True for r in entries)
        b = sum(r["candidate"][field] is True for r in entries)
        return {
            "denominator": count,
            "baselinePassed": a,
            "candidatePassed": b,
            "baselineRate": a / count if count else None,
            "candidateRate": b / count if count else None,
            "delta": (b - a) / count if count else None,
        }

    return {
        "unionQuestions": len(rows),
        "matchedQuestions": sum(
            r["baseline"] is not None and r["candidate"] is not None for r in rows
        ),
        "states": dict(sorted(Counter(r["state"] for r in rows).items())),
        "final": agreement(final, "agreement"),
        "first": agreement(first, "firstAgreement"),
        "firstScope": "compatible-selected-pairs-with-two-known-first-answers",
        "finalTransitions": dict(sorted(Counter(r["verdict"] for r in final).items())),
        "firstTransitions": dict(
            sorted(Counter(r["firstVerdict"] for r in first).items())
        ),
        "uniqueCases": len({r["key"][0] for r in rows}),
        "criticalErrorFreeRate": None,
        "confidenceInterval": None,
    }


def execution_conditions(view):
    return {
        **view.binding()["executionConditions"],
        "armLimits": {
            arm["id"]: {k: arm[k] for k in ("timeoutNs", "requestCaps")}
            for arm in view.plan["arms"]
        },
    }


def task_targets(view):
    # Full batch membership must match before row compatibility can establish
    # request/context equality for every task. IDs may differ between executions.
    return sorted(
        canonical(
            {
                **{k: task[k] for k in ("caseId", "armId", "repeat", "stage")},
                "source": task["source"]["sha256"],
                "candidate": task["candidate"]["sha256"],
                "questionIds": sorted(task["questionIds"]),
            }
        )
        for task in view.plan["tasks"]
    )


def operational(left, right, compatible):
    def counts(view):
        saved = view.score["summary"]
        planned = saved["plannedTasks"]
        completed = saved["statusCounts"].get("completed", 0)
        return {
            "plannedTasks": planned,
            "completedTasks": completed,
            "completionRate": completed / planned if planned else None,
            "statusCounts": saved["statusCounts"],
            **{
                key: view.score["runtimeCounts"][key]
                for key in (
                    "attempts",
                    "knownInputTokens",
                    "knownOutputTokens",
                    "unknownUsageAttempts",
                )
            },
        }

    a, b = counts(left), counts(right)
    same_tasks = task_targets(left) == task_targets(right)
    same_conditions = same(execution_conditions(left), execution_conditions(right))
    return {
        "scope": "all-planned-tasks-per-side",
        "baseline": a,
        "candidate": b,
        "samePlannedTaskTargets": same_tasks,
        "completionDelta": b["completionRate"] - a["completionRate"]
        if same_tasks and same_conditions and compatible
        else None,
        "deltaUnavailableReasons": (
            [] if same_tasks else ["planned-task-targets-differ"]
        )
        + ([] if same_conditions else ["execution-conditions-differ"])
        + ([] if compatible else ["comparison-incompatible"]),
    }


def compare(
    baseline_archive,
    baseline_score,
    candidate_archive,
    candidate_score,
    *,
    context="strict-wire",
    vary=(),
):
    selected_policy = policy(context, vary)
    left, right = (
        RuntimeView(baseline_archive, baseline_score),
        RuntimeView(candidate_archive, candidate_score),
    )
    global_errors = global_reasons(left, right, selected_policy)
    rows = []
    for key in sorted(left.rows.keys() | right.rows.keys()):
        a, b = left.rows.get(key), right.rows.get(key)
        reasons = []
        final_verdict = first_verdict = None
        if a is None or b is None:
            state = "candidate-only" if a is None else "baseline-only"
            reasons = ["missing-baseline" if a is None else "missing-candidate"]
        else:
            reasons = pair_reasons(left, right, a, b, selected_policy, global_errors)
            qa, qb = a["question"], b["question"]
            if reasons:
                state = "incompatible"
            else:
                if (
                    qa["selected"]
                    and qb["selected"]
                    and qa["firstAgreement"] is not None
                    and qb["firstAgreement"] is not None
                ):
                    first_verdict = verdict(qa["firstAgreement"], qb["firstAgreement"])
                if (
                    qa["selected"]
                    and qb["selected"]
                    and qa["agreement"] is not None
                    and qb["agreement"] is not None
                ):
                    state = "evaluated"
                    final_verdict = verdict(qa["agreement"], qb["agreement"])
                else:
                    state = "not-evaluated"
                    reasons = [
                        "baseline-" + (qa["notEvaluatedReason"] or "unselected")
                        if qa["agreement"] is None
                        else None,
                        "candidate-" + (qb["notEvaluatedReason"] or "unselected")
                        if qb["agreement"] is None
                        else None,
                    ]
                    reasons = [r for r in reasons if r is not None]
        rows.append(
            {
                "key": list(key),
                "baseline": side(a),
                "candidate": side(b),
                "state": state,
                "reasons": reasons,
                "verdict": final_verdict,
                "firstVerdict": first_verdict,
            }
        )
    lb, rb = left.binding(), right.binding()
    result = {
        "schema": "normlab.runtime-comparison/v1",
        "comparisonId": None,
        "policy": selected_policy,
        "codePins": {
            name: sha((Path(__file__).parent / name).read_bytes())
            for name in ("runtime_pairing.py", "runtime_compare.py")
        },
        "baseline": lb,
        "candidate": rb,
        "globalIncompatibilities": global_errors,
        "sameExecution": lb["executionId"] == rb["executionId"],
        "sameCapture": lb["captureRevisionId"] == rb["captureRevisionId"],
        "sameScore": lb["scoreId"] == rb["scoreId"],
        "executionConditionsMatch": same(
            execution_conditions(left), execution_conditions(right)
        ),
        "executionIndependence": "not-established",
        "contextEvidence": selected_policy["context"],
        "rows": rows,
        "summary": paired_summary(rows),
        "operational": operational(
            left,
            right,
            not global_errors and not any(r["state"] == "incompatible" for r in rows),
        ),
        "arms": {
            arm: paired_summary([r for r in rows if r["key"][2] == arm])
            for arm in sorted({r["key"][2] for r in rows})
        },
        "semanticQualityEvidence": False,
        "executionReady": False,
        "releaseApproved": False,
        "criticalErrorFreeRate": None,
        "actualCost": None,
        "inferenceCallsExecuted": 0,
        "registryWritesExecuted": 0,
    }
    result["comparisonId"] = identity(
        "runtime-comparison", {k: v for k, v in result.items() if k != "comparisonId"}
    )
    require(len(canonical(result)) <= MAX_BYTES, "Runtime comparison byte cap")
    return result


def verify_comparison(
    baseline_archive, baseline_score, candidate_archive, candidate_score, saved
):
    selected = saved["policy"]
    object_keys(selected, "id context vary unit")
    require(
        same(selected, policy(selected["context"], selected["vary"])),
        "Comparison policy binding",
    )
    expected = compare(
        baseline_archive,
        baseline_score,
        candidate_archive,
        candidate_score,
        context=selected["context"],
        vary=selected["vary"],
    )
    require(same(saved, expected), "Regenerated runtime comparison binding")
    return expected
