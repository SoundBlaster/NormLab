"""Schema-specific reference provenance and native report consistency; stdlib only."""

from collections import Counter

from offline_bundle import canonical, decode, object_keys, require


def equal(actual, expected, message):
    # JSON equality must distinguish booleans from integer counts.
    require(canonical(actual) == canonical(expected), message)


def validate_reference(envelope, tasks, artifact, manifest, report, is_s13):
    ref = envelope["reference"]
    reference = decode(artifact(ref["artifact"])) if ref else None
    if not is_s13:
        if reference is None:
            return None
        object_keys(reference, "schema experimentDigest status expectations")
        require(
            reference["schema"] == "normlab.evaluation-labels/v1"
            and reference["experimentDigest"]
            == envelope["source"]["manifest"]["sha256"]
            and reference["status"] == "candidate",
            "Classification candidate reference provenance",
        )
        expectations = reference["expectations"]
        require(
            isinstance(expectations, dict)
            and set(expectations)
            == {row["id"] for row in manifest["records"]}
            == {task["originalId"] for task in tasks},
            "Classification reference coverage",
        )
        inputs = envelope["source"]["inputs"]
        parents = {
            case["id"]: decode(artifact(inputs[2 + 2 * number]["artifact"]))
            for number, case in enumerate(manifest["cases"])
        }
        for task in tasks:
            probes = expectations[task["originalId"]]
            ids = {row["fragmentId"] for row in parents[task["caseId"]]["fragments"]}
            require(isinstance(probes, list) and probes, "Reference probes required")
            seen = set()
            for probe in probes:
                object_keys(probe, "fragmentId predicate stance")
                require(
                    probe["fragmentId"] in ids
                    and probe["predicate"] == "payment"
                    and probe["stance"] in {"asserted", "denied", "unknown"},
                    "Classification reference probe contract",
                )
                pair = (probe["fragmentId"], probe["predicate"])
                require(pair not in seen, "Duplicate reference probe")
                seen.add(pair)
        return reference

    require(
        isinstance(reference, dict)
        and reference["schema"] == "normlab.s13-reference/v1"
        and reference["planDigest"] == report["planDigest"]
        and reference["status"] in {"candidate-not-independent", "human-adjudicated"},
        "S1.3 reference provenance",
    )
    if reference["status"] == "human-adjudicated":
        evidence = reference.get("adjudicationEvidence")
        require(
            reference["revision"] != "s13-candidate-v1"
            and isinstance(evidence, list)
            and bool(evidence)
            and all(isinstance(entry, str) and entry.strip() for entry in evidence),
            "Human review evidence required",
        )
    expected = reference["expected"]
    require(
        isinstance(expected, dict)
        and set(expected) == {task["originalId"] for task in tasks},
        "S1.3 reference planned coverage",
    )
    for task in tasks:
        questions = decode(artifact(task["context"]["artifact"]))["questions"]
        labels = expected[task["originalId"]]
        require(
            isinstance(labels, dict) and set(labels) == set(questions),
            "S1.3 reference question coverage",
        )
        for qid, label in labels.items():
            allowed = (
                {"yes", "no", "uncertain"}
                if questions[qid]["type"] == "noul"
                else set(questions[qid]["criteria"])
            )
            require(isinstance(label, str) and label in allowed, "Reference label")
    return reference


def question_counts(rows):
    questions = [question for row in rows for question in row["questions"]]
    return {
        "plannedCalls": len(rows),
        "plannedQuestions": len(questions),
        "statusCounts": dict(Counter(row["status"] for row in rows)),
        "questionAgreementCount": sum(q["agreement"] is True for q in questions),
        "questionDisagreementCount": sum(q["agreement"] is False for q in questions),
        "unevaluatedQuestionCount": sum(q["agreement"] is None for q in questions),
    }


def selected_verdict(values):
    values = set(values)
    if "no" in values:
        return "incompatible"
    return "indeterminate" if "uncertain" in values else "compatible"


def response_value(question, answer):
    """Frozen S1.3 v1 response rules, without executing its saved scorer code."""
    if question["type"] == "noul":
        object_keys(answer, "p_yes")
        value = answer["p_yes"]
        require(type(value) in (int, float) and 0 <= value <= 1, "Noul probability")
        return "yes" if value >= 0.8 else "no" if value <= 0.2 else "uncertain"
    object_keys(answer, "choice")
    require(answer["choice"] in question["criteria"], "Choice alternative")
    return answer["choice"]


def validate_s13_rows(rows, reference, tasks, artifact):
    by_id = {task["originalId"]: task for task in tasks}
    for row in rows:
        require(row["arm"] in {"A", "B", "C", "D"}, "S1.3 report arm")
        task = by_id[row["jobId"]]
        payload = decode(artifact(task["context"]["artifact"]))
        prediction_ref = task["turn"]["predictionArtifact"]
        prediction = decode(artifact(prediction_ref)) if prediction_ref else None
        values = {}
        outcome = prediction["status"] if prediction else "not-dispatched"
        if outcome == "completed":
            try:
                require(
                    set(prediction["answers"]) == set(payload["questions"]),
                    "Answer coverage",
                )
                values = {
                    qid: response_value(question, prediction["answers"][qid])
                    for qid, question in payload["questions"].items()
                }
            except (ValueError, TypeError, KeyError):
                outcome = "invalid-schema"
        equal(row["status"], outcome, "S1.3 scored outcome")
        labels = reference["expected"][row["jobId"]]
        questions = row["questions"]
        require(
            isinstance(questions, list)
            and len(questions) == len(labels)
            and {q["questionId"] for q in questions} == set(labels),
            "S1.3 scored question coverage",
        )
        for question in questions:
            expected = labels[question["questionId"]]
            equal(
                question["prediction"],
                values.get(question["questionId"]),
                "Scored prediction answer binding",
            )
            equal(question["expected"], expected, "Scored reference answer binding")
            equal(
                question["agreement"],
                question["prediction"] == expected
                if row["status"] == "completed"
                else None,
                "Scored question agreement",
            )
        equal(
            row["referenceSelectedClaimVerdict"],
            selected_verdict(labels.values()) if row["arm"] != "D" else None,
            "Scored reference verdict",
        )
        equal(
            row["overallSelectedClaimVerdict"],
            selected_verdict(q["prediction"] for q in questions)
            if row["arm"] != "D" and row["status"] == "completed"
            else None,
            "Scored selected verdict",
        )


def validate_s13_report(envelope, tasks, artifact, report, reference):
    rows = report["results"]
    validate_s13_rows(rows, reference, tasks, artifact)
    arms = {}
    for arm in ("A", "B", "C", "D"):
        arm_rows = [row for row in rows if row["arm"] == arm]
        arms[arm] = {
            **question_counts(arm_rows),
            "selectedClaimVerdicts": dict(
                Counter(
                    row["overallSelectedClaimVerdict"]
                    for row in arm_rows
                    if row["overallSelectedClaimVerdict"] is not None
                )
            ),
            **{
                name: sum(
                    row["overallSelectedClaimVerdict"] == prediction
                    and row["referenceSelectedClaimVerdict"] == expected
                    for row in arm_rows
                )
                if arm != "D"
                else None
                for name, prediction, expected in (
                    ("falseAcceptanceCount", "compatible", "incompatible"),
                    ("falseRejectionCount", "incompatible", "compatible"),
                )
            },
        }
    capture = decode(artifact(envelope["source"]["captures"][0]))
    require(
        {row["jobId"] for row in capture["records"]}
        <= {task["originalId"] for task in tasks},
        "Captured jobs inside planned denominator",
    )
    counts = envelope["counts"]
    expected = {
        "schema": "normlab.s13-replay-report/v1",
        "evidenceKind": "offline-fixture",
        "planDigest": capture["planDigest"],
        "captureDigest": report["captureDigest"],
        "referenceDigest": envelope["reference"]["artifact"]["sha256"],
        "referenceStatus": reference["status"],
        "referenceRevision": reference["revision"],
        **question_counts(rows),
        **{
            name: counts[name]
            for name in (
                "knownInputTokens",
                "knownOutputTokens",
                "unknownUsageOutcomes",
            )
        },
        "providerQualityScore": None,
        "wholeSourceCompleteness": "not-evaluated",
        "arms": arms,
        "inferenceCalls": 0,
        "results": rows,
    }
    equal(report, expected, "S1.3 native report metadata/aggregates")


def validate_classification_report(envelope, manifest, report, reference):
    rows = report["records"]
    for row in rows:
        require(type(row["structuralPass"]) is bool, "Structural pass type")
        equal(
            row["structuralPass"],
            row["status"] == "completed",
            "Structural pass outcome",
        )
        mismatches = row["mismatches"]
        require(isinstance(mismatches, list), "Probe mismatches")
        require(
            row["status"] == "completed" or not mismatches, "Unparsed probe mismatches"
        )
        if reference is None:
            require(row["probePass"] is None and not mismatches, "Unscored probes")
        else:
            probes = reference["expectations"][row["recordId"]]
            require(
                all(item in probes for item in mismatches)
                and len({canonical(item) for item in mismatches}) == len(mismatches),
                "Mismatch reference probes",
            )
            equal(
                row["probePass"],
                row["status"] == "completed"
                and row["structuralPass"]
                and not mismatches,
                "Selected probe outcome",
            )
        require(
            row["usage"] is None and row["latencyMs"] is None and row["cost"] is None,
            "Classification unavailable report measurements",
        )
    scorer = envelope["score"]["scorer"]
    expected = {
        "schema": "normlab.evaluation-replay/v2",
        "experimentId": manifest["experimentId"],
        "dataset": manifest["dataset"],
        "manifestDigest": envelope["source"]["manifest"]["sha256"],
        "labelsDigest": envelope["reference"]["artifact"]["sha256"]
        if reference
        else None,
        "scorer": "classification-selected-probes/v1",
        "replayContract": "model-metadata/v2",
        "inputSchema": manifest["schema"],
        "scorerDigest": scorer["code"]["sha256"],
        "dependencyDigests": {
            key: ref["sha256"] for key, ref in scorer["dependencies"].items()
        },
        "definitionsDigest": manifest["definitions"]["sha256"],
        "evidence": "offline-fixed-candidates-selected-probes",
        **{key: manifest[key] for key in ("provider", "strategy", "tactic")},
        "expectationsStatus": "candidate" if reference else "not_evaluated",
        "criticalErrorFreeRate": None,
        "semanticVerifierQuality": "not_evaluated",
        "records": rows,
        "counts": {
            "total": len(rows),
            **{
                key: sum(row["status"] == key for row in rows)
                for key in ("completed", "failed", "partial")
            },
            "invalidOutput": sum(row["status"] == "invalid-output" for row in rows),
            "structuralPass": sum(row["structuralPass"] for row in rows),
            "probePass": sum(row["probePass"] is True for row in rows)
            if reference
            else None,
            "liveCalls": 0,
        },
    }
    equal(report, expected, "Classification native report metadata/aggregates")


def validate_score(envelope, tasks, artifact, is_s13, report):
    manifest = decode(artifact(envelope["source"]["manifest"]))
    reference = validate_reference(envelope, tasks, artifact, manifest, report, is_s13)
    if is_s13:
        validate_s13_report(envelope, tasks, artifact, report, reference)
    else:
        validate_classification_report(envelope, manifest, report, reference)
