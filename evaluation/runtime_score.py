"""Deterministic selected-question agreement for immutable mock capture revisions."""

from pathlib import Path

from execution_outcomes import answer_schema
from offline_bundle import MAX_BYTES, canonical, decode, identity, require, sha
from runtime_archive_reader import VerifiedArchive
from runtime_reference import RuntimeReference, reference

POLICY = {
    "id": "runtime-selected-question-agreement/v1",
    "noul": {"yesAtLeast": 0.8, "noAtMost": 0.2},
    "choice": "exact-label",
    "score": "exact-scale-index",
    "denominator": "selected-completed-questions",
    "caseQuality": None,
}


def values(archive, outcome_ref, questions):
    if outcome_ref is None:
        return {}
    outcome = decode(archive.snapshot.files[outcome_ref["path"]])
    if outcome["status"] != "completed":
        return {}
    answers = decode(archive.snapshot.files[outcome["result"]["path"]])["answers"]
    result = {}
    for answer in answers:
        qid, value = answer["questionId"], answer["value"]
        if questions[qid]["type"] == "noul":
            value = "yes" if value >= 0.8 else "no" if value <= 0.2 else "uncertain"
        result[qid] = value
    return result


def summary(rows):
    questions = [q for row in rows for q in row["questions"]]
    selected = [q for q in questions if q["selected"]]
    scored = sum(q["agreement"] is not None for q in selected)
    passed = sum(q["agreement"] is True for q in selected)
    first_scored = sum(q["firstAgreement"] is not None for q in selected)
    return {
        "plannedTasks": len(rows),
        "plannedQuestions": len(questions),
        "selectedTasks": sum(
            any(q["selected"] for q in row["questions"]) for row in rows
        ),
        "selectedQuestions": len(selected),
        "unselectedQuestions": len(questions) - len(selected),
        "scoredQuestions": scored,
        "passedQuestions": passed,
        "disagreedQuestions": scored - passed,
        "selectedUnevaluatedQuestions": len(selected) - scored,
        "agreementAmongScored": passed / scored if scored else None,
        "firstScoredQuestions": first_scored,
        "firstPassedQuestions": sum(q["firstAgreement"] is True for q in selected),
        "statusCounts": {
            status: sum(row["status"] == status for row in rows)
            for status in sorted({r["status"] for r in rows})
        },
        "criticalErrorFreeRate": None,
    }


def score(archive, selected):
    require(
        type(archive) is VerifiedArchive and type(selected) is RuntimeReference,
        "Verified archive/reference required",
    )
    require(archive.index["evidenceKind"] == "mock", "Mock-only score consumer")
    inputs = selected.inputs
    checked = reference(
        archive,
        inputs["sourceUtf8"].encode(),
        [s.encode() for s in inputs["reviewsUtf8"]],
    )
    require(
        canonical(checked.document) == canonical(selected.document),
        "Reference projection binding",
    )
    expected = {
        (r["taskKey"], r["questionId"]): r["label"]
        for r in selected.document["expected"]
    }
    plan = archive.snapshot.plan
    questions = answer_schema(
        decode(archive.snapshot.files[plan["pins"]["outputSchema"]["path"]])
    )
    rows = []
    for task_ref in archive.projection.manifest["records"]:
        task = decode(archive.projection.files[task_ref["path"]])
        first = values(archive, task["firstOutcome"], questions)
        final = values(archive, task["finalOutcome"], questions)
        entries = []
        for qid in task["questionIds"]:
            pair = (task["key"], qid)
            label = expected.get(pair)
            chosen = pair in expected
            entries.append(
                {
                    "questionId": qid,
                    "type": questions[qid]["type"],
                    "selected": chosen,
                    "expected": label,
                    "prediction": final.get(qid),
                    "firstPrediction": first.get(qid),
                    "agreement": final[qid] == label
                    if chosen and qid in final
                    else None,
                    "firstAgreement": first[qid] == label
                    if chosen and qid in first
                    else None,
                    "notEvaluatedReason": None
                    if chosen and qid in final
                    else task["status"]
                    if chosen
                    else "unselected",
                }
            )
        rows.append(
            {
                "taskId": task["taskId"],
                "taskKey": task["key"],
                "caseId": task["caseId"],
                "armId": task["armId"],
                "repeat": task["repeat"],
                "status": task["status"],
                "attempts": len(task["attempts"]),
                "record": task_ref,
                "firstOutcome": task["firstOutcome"],
                "finalOutcome": task["finalOutcome"],
                "questions": entries,
            }
        )
    result = {
        "schema": "normlab.runtime-score-view/v1",
        "scoreId": None,
        "archiveId": archive.index["archiveId"],
        "executionId": archive.index["executionId"],
        "captureRevisionId": archive.index["captureRevisionId"],
        "planDigest": archive.projection.manifest["planDigest"],
        "reference": selected.document,
        "referenceInputs": inputs,
        "policy": decode(canonical(POLICY)),
        "scorerCodePins": {
            name: sha((Path(__file__).parent / name).read_bytes())
            for name in ("runtime_score.py", "runtime_reference.py")
        },
        "predictionSeal": archive.projection.manifest["predictionSeal"],
        "rows": rows,
        "summary": summary(rows),
        "arms": {
            arm: summary([r for r in rows if r["armId"] == arm])
            for arm in sorted({r["armId"] for r in rows})
        },
        "runtimeCounts": archive.projection.manifest["counts"],
        "evidenceKind": "mock",
        "actualCost": None,
        "criticalErrorFreeRate": None,
        "semanticQualityEvidence": False,
        "executionReady": False,
        "releaseApproved": False,
        "inferenceCallsExecuted": 0,
    }
    result["scoreId"] = identity(
        "runtime-score", {k: v for k, v in result.items() if k != "scoreId"}
    )
    require(len(canonical(result)) <= MAX_BYTES, "Score view byte cap")
    return result


def verify_score(archive, saved):
    inputs = saved["referenceInputs"]
    from offline_bundle import object_keys

    object_keys(inputs, "sourceUtf8 reviewsUtf8")
    require(
        isinstance(inputs["sourceUtf8"], str)
        and isinstance(inputs["reviewsUtf8"], list)
        and all(isinstance(s, str) for s in inputs["reviewsUtf8"]),
        "Embedded reference inputs",
    )
    selected = reference(
        archive,
        inputs["sourceUtf8"].encode(),
        [s.encode() for s in inputs["reviewsUtf8"]],
    )
    expected = score(archive, selected)
    require(canonical(saved) == canonical(expected), "Regenerated score view binding")
    return expected
