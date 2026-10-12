"""Task/turn bindings and denominator checks for offline envelope v1."""

from collections import Counter

from offline_bundle import (
    MAX_TASKS,
    TASK_SCHEMA,
    canonical,
    decode,
    digest_value,
    identity,
    object_keys,
    require,
    sha,
)


def validate_tasks(envelope, artifact, refs, run, is_s13, original_report):
    records = envelope["records"]
    require(isinstance(records, list) and 0 < len(records) <= MAX_TASKS, "Task cap")
    tasks, seen = [], set()
    report_rows = original_report["results" if is_s13 else "records"]
    report_key = "jobId" if is_s13 else "recordId"
    require(
        isinstance(report_rows, list) and len(report_rows) == len(records),
        "Scored row denominator",
    )
    scores = {row[report_key]: row for row in report_rows}
    manifest = decode(artifact(envelope["source"]["manifest"]))
    if is_s13:
        sources_ref = next(
            entry["artifact"]
            for entry in envelope["source"]["inputs"]
            if entry["role"] == "sources"
        )
        cases = {row["id"]: row for row in decode(artifact(sources_ref))["cases"]}
    else:
        cases = {row["id"]: row for row in manifest["cases"]}
    require(len(scores) == len(records), "Unique scored rows")
    captures = [decode(artifact(ref)) for ref in envelope["source"]["captures"]]
    predictions = (
        {row["jobId"]: row for row in captures[0]["records"]}
        if is_s13
        else {row["recordId"]: row for row in captures}
    )
    require(
        len(predictions) == (len(captures[0]["records"]) if is_s13 else len(captures)),
        "Unique original predictions",
    )
    for ref in records:
        task = decode(artifact(ref))
        object_keys(
            task,
            "schema id originalId caseId candidateId familyId language armId repeat sourceDigest taskDigest context turn scoreArtifact",
        )
        require(task["schema"] == TASK_SCHEMA, "Task schema")
        require(task["caseId"] in cases, "Original case identity")
        case = cases[task["caseId"]]
        require(
            task["familyId"] == case["familyId" if is_s13 else "family"]
            and task["language"] == case["language"],
            "Original case metadata",
        )
        if is_s13:
            require(
                task["sourceDigest"] == case["sourceDigest"]
                and task["repeat"] == int(task["originalId"].split("-")[1]),
                "S1.3 case/repeat binding",
            )
        else:
            require(
                task["taskDigest"]
                == sha(
                    canonical(
                        {
                            "input": case["input"]["sha256"],
                            "parent": case["parent"]["sha256"],
                            "definitions": manifest["definitions"]["sha256"],
                        }
                    )
                ),
                "Classification logical binding",
            )
        require(
            isinstance(task["originalId"], str)
            and isinstance(task["caseId"], str)
            and isinstance(task["armId"], str),
            "Task identity metadata",
        )
        require(
            task["repeat"] is None
            or (type(task["repeat"]) is int and task["repeat"] > 0),
            "Repeat metadata",
        )
        require(
            task["candidateId"] is None or isinstance(task["candidateId"], str),
            "Candidate identity metadata",
        )
        require(
            task["id"] == identity("task", [run["id"], task["originalId"]])
            and task["id"] not in seen,
            "Unique task binding",
        )
        seen.add(task["id"])
        require(
            digest_value(task["sourceDigest"]) and digest_value(task["taskDigest"]),
            "Task digests",
        )
        refs(task)
        require(
            task["originalId"] in scores
            and decode(artifact(task["scoreArtifact"])) == scores[task["originalId"]],
            "Per-task score binding",
        )
        context, turn = task["context"], task["turn"]
        object_keys(context, "kind artifact policy")
        require(context["kind"] in {"unavailable", "logical-payload"}, "Context kind")
        require(
            context["kind"] == ("logical-payload" if is_s13 else "unavailable"),
            "Legacy context provenance",
        )
        require(
            (context["artifact"] is None) == (context["kind"] == "unavailable"),
            "Context availability",
        )
        require(
            context["policy"] is None or isinstance(context["policy"], str),
            "Context policy",
        )
        if context["kind"] == "logical-payload":
            require(
                context["artifact"]["sha256"] == task["taskDigest"],
                "Logical payload digest",
            )
        object_keys(
            turn,
            "id stage originalStatus status predictionArtifact error returnedModel usage latencyMs cost attempts questionIds",
        )
        require(turn["id"] == identity("turn", task["id"]), "Turn binding")
        validate_legacy_turn(
            task,
            scores[task["originalId"]],
            predictions.get(task["originalId"]),
            artifact,
            is_s13,
        )
        require(
            turn["status"] == scores[task["originalId"]]["status"],
            "Scored outcome binding",
        )
        require(
            turn["status"]
            in {
                "completed",
                "failed",
                "partial",
                "invalid-output",
                "transport-failed",
                "deadline",
                "not-dispatched",
                "invalid-schema",
            },
            "Outcome status",
        )
        # These legacy formats cannot establish a physical dispatch/attempt history.
        require(
            turn["attempts"] is None
            and turn["latencyMs"] is None
            and turn["cost"] is None,
            "Unavailable legacy metadata",
        )
        require(
            turn["questionIds"] is None
            or (
                isinstance(turn["questionIds"], list)
                and all(isinstance(q, str) for q in turn["questionIds"])
                and len(set(turn["questionIds"])) == len(turn["questionIds"])
            ),
            "Question identity",
        )
        tasks.append(task)
    return tasks


def validate_legacy_turn(task, score, prediction, artifact, is_s13):
    turn = task["turn"]
    if is_s13:
        require(
            task["armId"] == score["arm"] and task["candidateId"] == score["recordId"],
            "S1.3 arm/candidate binding",
        )
        require(
            turn["stage"] == "selected-claim-verification"
            and turn["returnedModel"] is None
            and turn["error"] is None,
            "S1.3 turn metadata",
        )
        payload = decode(artifact(task["context"]["artifact"]))
        require(
            task["sourceDigest"] == sha(payload["state"]["sourceText"].encode()),
            "S1.3 source binding",
        )
        require(
            isinstance(turn["questionIds"], list)
            and set(turn["questionIds"]) == set(payload["questions"]),
            "Logical question coverage",
        )
        require(
            turn["originalStatus"]
            == (prediction["status"] if prediction else "not-recorded"),
            "Original outcome binding",
        )
        require(
            turn["usage"]
            == (
                {key: prediction[key] for key in ("inputTokens", "outputTokens")}
                if prediction
                else None
            ),
            "Original usage binding",
        )
        require(
            (turn["predictionArtifact"] is None) == (prediction is None),
            "Missing prediction binding",
        )
        if prediction:
            require(
                decode(artifact(turn["predictionArtifact"])) == prediction
                and task["taskDigest"] == prediction["requestDigest"],
                "Original prediction binding",
            )
    else:
        require(
            prediction is not None
            and decode(artifact(turn["predictionArtifact"])) == prediction,
            "Original capture binding",
        )
        require(
            task["sourceDigest"] == prediction["sourceDigest"]
            and task["caseId"] == score["caseId"]
            and task["familyId"] == score["family"]
            and task["language"] == score["language"],
            "Classification case binding",
        )
        require(
            task["candidateId"] is None
            and task["repeat"] is None
            and task["armId"] == "classification",
            "Unavailable classification metadata",
        )
        original = prediction["turns"][0]
        require(
            turn["originalStatus"] == original["status"]
            and turn["stage"] == original["stage"]
            and turn["error"] == original["error"]
            and turn["returnedModel"] == prediction["returnedModel"],
            "Original turn binding",
        )
        require(
            turn["usage"] is None and turn["questionIds"] is None,
            "Unavailable measurements/questions",
        )


def validate_counts(counts, tasks):
    object_keys(
        counts,
        "plannedTasks plannedQuestions recordedOutcomes statusCounts knownInputTokens knownOutputTokens unknownUsageOutcomes",
    )
    for key, value in counts.items():
        if key != "statusCounts":
            require(
                (key == "plannedQuestions" and value is None)
                or (type(value) is int and value >= 0),
                "Count type",
            )
    require(counts["plannedTasks"] == len(tasks), "Planned denominator")
    require(
        counts["statusCounts"] == dict(Counter(t["turn"]["status"] for t in tasks)),
        "Status denominator",
    )
    require(
        counts["recordedOutcomes"]
        == sum(t["turn"]["predictionArtifact"] is not None for t in tasks),
        "Recorded denominator",
    )
    questions = [t["turn"]["questionIds"] for t in tasks]
    require(
        counts["plannedQuestions"]
        == (
            None
            if any(q is None for q in questions)
            else sum(len(q) for q in questions)
        ),
        "Question denominator",
    )
    for name, field in (
        ("knownInputTokens", "inputTokens"),
        ("knownOutputTokens", "outputTokens"),
    ):
        values = []
        for task in tasks:
            usage = task["turn"]["usage"]
            if usage is not None:
                object_keys(usage, "inputTokens outputTokens")
                for value in usage.values():
                    require(
                        value is None or (type(value) is int and value >= 0),
                        "Token usage",
                    )
            values.append(usage[field] if usage else None)
        require(
            counts[name] == sum(v for v in values if v is not None), "Known usage sum"
        )
    require(
        counts["unknownUsageOutcomes"]
        == sum(
            t["turn"]["predictionArtifact"] is not None
            and (
                t["turn"]["usage"] is None
                or any(v is None for v in t["turn"]["usage"].values())
            )
            for t in tasks
        ),
        "Unknown usage denominator",
    )
