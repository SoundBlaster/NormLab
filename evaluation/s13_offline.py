"""Compile and replay S1.3 logical tasks offline; no SDK, auth or dispatch path."""

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/parking-pilot/s13-offline-v1"
AXES = {
    "content": ("predicate", "stance"),
    "attribution": ("claimant", "actor", "grammaticalSubject"),
    "scope": ("mode", "subject", "aboutEntity", "episode", "scope"),
    "projection": ("stance", "mode", "claimant"),
}
STANCES = (
    "asserted",
    "denied",
    "explicit_unknown",
    "not_mentioned",
    "ambiguous",
    "multiple_positions",
    "verifier_uncertain",
)
STATUSES = ("completed", "transport-failed", "deadline", "not-dispatched")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(
        path.read_bytes(),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"Nonfinite JSON: {value}")
        ),
    )


def bound(entry):
    require(set(entry) == {"path", "sha256"}, "Artifact pin fields")
    path = (ROOT / entry["path"]).resolve()
    require(
        not Path(entry["path"]).is_absolute() and path.is_relative_to(ROOT),
        "Artifact path",
    )
    require(
        digest(path.read_bytes()) == entry["sha256"], f"Artifact drift: {entry['path']}"
    )
    return load(path)


def anchor(source, start, end):
    require(
        type(start) is int and type(end) is int and 0 <= start < end <= len(source),
        "Source anchor range",
    )
    return {
        "quote": source[start:end],
        "charStart": start,
        "charEnd": end,
        "byteStart": len(source[:start].encode()),
        "byteEnd": len(source[:end].encode()),
    }


def task(state, instructions, primitive, options=None):
    result = {"type": primitive, "instructions": instructions}
    if options is not None:
        result["criteria"] = options
    return result


def compile_plan():
    """Read only public inputs/config. Reviewer labels never participate in planning."""
    manifest = load(FIXTURE / "experiment.json")
    require(manifest["schema"] == "normlab.s13-offline/v1", "Manifest revision")
    require(
        manifest["noulDecision"]
        == {"yesAtOrAbove": 0.8, "noAtOrBelow": 0.2, "otherwise": "uncertain"},
        "Pinned Noul triage",
    )
    require(
        manifest["mode"] == "offline-only" and manifest["authorizedLiveCalls"] == 0,
        "Offline boundary",
    )
    require(
        manifest["providerBinding"]
        == {"supplier": None, "model": None, "modelVersion": None},
        "Live binding needs a new manifest",
    )
    require(
        set(manifest["artifacts"])
        == {"sources", "candidates", "definitions", "conventions", "prompts"},
        "Public artifact allowlist",
    )
    require(
        set(manifest["codePins"]) == {"evaluation/s13_offline.py"}, "Code pin coverage"
    )
    for name, expected in manifest["codePins"].items():
        require(digest((ROOT / name).read_bytes()) == expected, "Compiler/scorer drift")
    data = {key: bound(value) for key, value in manifest["artifacts"].items()}
    sources = {row["id"]: row for row in data["sources"]["cases"]}
    candidates = data["candidates"]["records"]
    require(len(sources) == 16 and len(candidates) == 32, "Matched corpus size")
    require(
        len({row["id"] for row in candidates}) == len(candidates),
        "Duplicate candidates",
    )
    conventions = {
        key: data["conventions"][key]
        for key in (
            "identityPolicy",
            "operatorPolicy",
            "scopeMeanings",
            "diagnosticPredicates",
        )
    }
    prompts = data["prompts"]
    base_jobs = []
    targets = {}

    def add(arm, case_id, record_id, state, questions, mapping):
        payload = {"state": state, "questions": questions}
        require(
            set(state)
            <= {"sourceText", "definitions", "conventions", "candidate", "target"},
            "Public state fields",
        )
        require(set(payload) == {"state", "questions"}, "Task fields")
        require(
            len(canonical(payload).encode()) <= manifest["caps"]["maxRequestUtf8Bytes"],
            "Request byte cap",
        )
        require(
            len(questions) <= manifest["caps"]["maxQuestionsPerRequest"], "Question cap"
        )
        base_jobs.append(
            {
                "arm": arm,
                "caseId": case_id,
                "recordId": record_id,
                "payload": payload,
                "questionTargets": mapping,
            }
        )

    for record in candidates:
        case_id = record["caseId"]
        source = sources[case_id]["sourceText"]
        require(
            digest(source.encode()) == sources[case_id]["sourceDigest"], "Source digest"
        )
        claims = record["claims"]
        state = {
            "sourceText": source,
            "definitions": data["definitions"],
            "conventions": conventions,
            "candidate": {"claims": claims},
        }
        for claim in claims:
            focus = anchor(source, claim["start"], claim["end"])
            require(focus["quote"] == claim["quote"], "Candidate source quote")
            key = f"{case_id}:{claim['start']}:{claim['end']}:{claim['predicate']}"
            targets[key] = {
                "id": key,
                "caseId": case_id,
                "predicate": claim["predicate"],
                "focus": focus,
                "queryFrame": "selected-relation-under-source-operator",
            }
        add(
            "A",
            case_id,
            record["id"],
            state,
            {"overall": task(state, prompts["whole"], "noul")},
            {},
        )
        questions, mapping = {}, {}
        for index, claim in enumerate(claims, 1):
            for axis, fields in AXES.items():
                key = f"c{index}_{axis}"
                target = {
                    "predicate": claim["predicate"],
                    "fragment": claim["quote"],
                    "charStart": claim["start"],
                    "charEnd": claim["end"],
                    "values": {field: claim[field] for field in fields},
                }
                instruction = prompts["local"][axis] + "\nTarget: " + canonical(target)
                questions[key] = task(state, instruction, "noul")
                mapping[key] = {"claimId": claim["id"], "axis": axis}
        add("B", case_id, record["id"], state, questions, mapping)
        add(
            "C",
            case_id,
            record["id"],
            state,
            {
                "overall": task(
                    state, prompts["whole"], "choice", prompts["binaryCriteria"]
                )
            },
            {},
        )
    # A fixed grid adds explicit absence controls; it is not an exhaustive search.
    for case_id, source in sources.items():
        for predicate in ("payment", "paidRegime"):
            key = f"{case_id}:global:{predicate}"
            targets[key] = {
                "id": key,
                "caseId": case_id,
                "predicate": predicate,
                "focus": anchor(source["sourceText"], 0, len(source["sourceText"])),
                "queryFrame": "actual-event-commitment",
            }
    for target_id, target in sorted(targets.items()):
        state = {
            "sourceText": sources[target["caseId"]]["sourceText"],
            "definitions": data["definitions"],
            "conventions": conventions,
            "target": {
                key: target[key] for key in ("predicate", "focus", "queryFrame")
            },
        }
        instruction = prompts["sourceOnly"] + "\nTarget: " + canonical(state["target"])
        add(
            "D",
            target["caseId"],
            None,
            state,
            {"stance": task(state, instruction, "choice", prompts["stanceCriteria"])},
            {"stance": {"targetId": target_id}},
        )
    jobs = []
    for repetition in range(manifest["repetitions"]):
        # Hash order uses payload and repetition, never labels or arm answer expectations.
        ordered = sorted(
            base_jobs,
            key=lambda row: digest(
                (manifest["orderSeed"] + str(repetition) + canonical(row)).encode()
            ),
        )
        for index, row in enumerate(ordered, 1):
            payload_hash = digest(canonical(row["payload"]).encode())
            jobs.append(
                {
                    **row,
                    "jobId": f"S13-{repetition + 1}-{index:03}",
                    "repetition": repetition + 1,
                    "requestDigest": payload_hash,
                }
            )
    caps = manifest["caps"]
    for field in (
        "maxLogicalCalls",
        "maxSemanticQuestions",
        "maxAttempts",
        "maxRequestUtf8Bytes",
        "maxQuestionsPerRequest",
        "maxInputTokens",
        "maxOutputTokens",
        "maxTotalTokens",
        "maxRequestSeconds",
        "maxRunSeconds",
    ):
        require(
            type(caps[field]) is int and caps[field] > 0,
            f"Positive integer cap: {field}",
        )
    require(
        type(manifest["repetitions"]) is int and manifest["repetitions"] == 3,
        "Matched repetitions",
    )
    require(len(jobs) <= caps["maxLogicalCalls"], "Logical call cap")
    question_count = sum(len(row["payload"]["questions"]) for row in jobs)
    require(question_count <= caps["maxSemanticQuestions"], "Total question cap")
    require(
        caps["maxAttempts"] == caps["maxLogicalCalls"] and caps["retries"] == 0,
        "No implicit retries",
    )
    require(
        caps["maxRunSeconds"] == caps["maxAttempts"] * caps["maxRequestSeconds"],
        "Serial deadline cap",
    )
    require(
        caps["maxTotalTokens"]
        == caps["maxAttempts"] * (caps["maxInputTokens"] + caps["maxOutputTokens"]),
        "Token accounting cap",
    )
    require(
        set(prompts["stanceCriteria"]) == set(STANCES), "Fixed source-only alternatives"
    )
    summary = {
        "schema": "normlab.s13-plan-summary/v1",
        "manifestDigest": digest((FIXTURE / "experiment.json").read_bytes()),
        "planDigest": digest(canonical(jobs).encode()),
        "calls": len(jobs),
        "questions": question_count,
        "arms": dict(sorted(Counter(row["arm"] for row in jobs).items())),
        "sourceOnlyTargets": len(targets),
        "authorizedLiveCalls": 0,
        "sourceCount": len(sources),
        "candidateCount": len(candidates),
    }
    return manifest, jobs, summary


def response_value(question, answer):
    if question["type"] == "noul":
        require(set(answer) == {"p_yes"}, "Noul answer fields")
        value = answer["p_yes"]
        require(
            type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
            "Noul probability",
        )
        return "yes" if value >= 0.8 else "no" if value <= 0.2 else "uncertain"
    require(set(answer) == {"choice"}, "Choice answer fields")
    require(answer["choice"] in question["criteria"], "Choice alternative")
    return answer["choice"]


def selected_verdict(values):
    return (
        "incompatible"
        if "no" in values
        else "indeterminate"
        if "uncertain" in values
        else "compatible"
    )


def replay(capture, reference_path):
    manifest, jobs, summary = compile_plan()
    require(capture["schema"] == "normlab.s13-offline-capture/v1", "Capture schema")
    require(
        capture["evidenceKind"] == "offline-fixture",
        "Only offline fixture evidence is supported",
    )
    require(capture["planDigest"] == summary["planDigest"], "Capture plan binding")
    require(
        capture["manifestDigest"] == summary["manifestDigest"],
        "Capture manifest binding",
    )
    require(
        set(capture)
        == {"schema", "evidenceKind", "planDigest", "manifestDigest", "records"},
        "Capture fields",
    )
    planned = {job["jobId"]: job for job in jobs}
    predictions = {}
    # Validate and seal predictions before reading any reference labels.
    for row in capture["records"]:
        require(
            set(row)
            == {
                "jobId",
                "requestDigest",
                "status",
                "answers",
                "inputTokens",
                "outputTokens",
            },
            "Capture row fields",
        )
        key = row["jobId"]
        require(key in planned and key not in predictions, "Unknown or duplicate job")
        require(
            row["requestDigest"] == planned[key]["requestDigest"],
            "Request digest mismatch",
        )
        require(row["status"] in STATUSES, "Capture status")
        for field in ("inputTokens", "outputTokens"):
            value = row[field]
            require(
                value is None
                or (
                    type(value) is int
                    and 0
                    <= value
                    <= manifest["caps"][
                        "maxInputTokens"
                        if field == "inputTokens"
                        else "maxOutputTokens"
                    ]
                ),
                "Token usage",
            )
        require(
            row["status"] == "completed" or row["answers"] == {},
            "Failure cannot have answers",
        )
        predictions[key] = row
    sealed_digest = digest(canonical(capture).encode())
    reference_raw = reference_path.read_bytes()
    reference = load(reference_path)
    require(reference["schema"] == "normlab.s13-reference/v1", "Reference schema")
    require(reference["planDigest"] == summary["planDigest"], "Reference plan binding")
    require(
        reference["status"] in ("candidate-not-independent", "human-adjudicated"),
        "Reference status",
    )
    require(
        reference["status"] != "human-adjudicated"
        or (
            reference["revision"] != "s13-candidate-v1"
            and isinstance(reference["adjudicationEvidence"], list)
            and bool(reference["adjudicationEvidence"])
            and all(
                isinstance(entry, str) and entry.strip()
                for entry in reference["adjudicationEvidence"]
            )
        ),
        "Human review evidence required",
    )
    require(
        set(reference["expected"]) == set(planned),
        "Reference covers full planned denominator",
    )
    results = []
    for key, job in planned.items():
        row = predictions.get(key)
        expected = reference["expected"][key]
        questions = job["payload"]["questions"]
        values, outcome = {}, row["status"] if row else "not-dispatched"
        if row and row["status"] == "completed":
            try:
                require(
                    set(row["answers"]) == set(questions), "Answer question coverage"
                )
                values = {
                    qid: response_value(question, row["answers"][qid])
                    for qid, question in questions.items()
                }
            except (ValueError, TypeError, KeyError):
                outcome = "invalid-schema"
        require(set(expected) == set(questions), "Reference question coverage")
        for qid, label in expected.items():
            allowed = (
                {"yes", "no", "uncertain"}
                if questions[qid]["type"] == "noul"
                else set(questions[qid]["criteria"])
            )
            require(label in allowed, "Reference label outside contract")
        overall = None
        expected_overall = None
        if job["arm"] != "D":
            expected_overall = selected_verdict(expected.values())
        if outcome == "completed" and job["arm"] != "D":
            overall = selected_verdict(values.values())
        questions_report = [
            {
                "questionId": qid,
                "prediction": values.get(qid),
                "expected": label,
                "agreement": values[qid] == label if outcome == "completed" else None,
                "target": job["questionTargets"].get(qid),
            }
            for qid, label in expected.items()
        ]
        stance_comparisons = []
        if job["arm"] == "D":
            target = job["payload"]["state"]["target"]
            predicted_stance = values.get("stance")
            if target["queryFrame"] == "selected-relation-under-source-operator":
                for candidate_job in jobs:
                    if (
                        candidate_job["arm"] != "A"
                        or candidate_job["repetition"] != job["repetition"]
                        or candidate_job["caseId"] != job["caseId"]
                    ):
                        continue
                    for claim in candidate_job["payload"]["state"]["candidate"][
                        "claims"
                    ]:
                        if (claim["start"], claim["end"], claim["predicate"]) != (
                            target["focus"]["charStart"],
                            target["focus"]["charEnd"],
                            target["predicate"],
                        ):
                            continue
                        candidate_stance = (
                            "explicit_unknown"
                            if claim["stance"] == "unknown"
                            else claim["stance"]
                        )
                        stance_comparisons.append(
                            {
                                "recordId": candidate_job["recordId"],
                                "claimId": claim["id"],
                                "candidateStance": candidate_stance,
                                "sourceStanceMatchesCandidate": (
                                    predicted_stance == candidate_stance
                                    if outcome == "completed"
                                    and predicted_stance
                                    in (
                                        "asserted",
                                        "denied",
                                        "explicit_unknown",
                                    )
                                    else None
                                ),
                            }
                        )
        results.append(
            {
                "jobId": key,
                "arm": job["arm"],
                "recordId": job["recordId"],
                "status": outcome,
                "overallSelectedClaimVerdict": overall,
                "referenceSelectedClaimVerdict": expected_overall,
                "questions": questions_report,
                "candidateStanceComparisons": stance_comparisons,
                "defectLocations": [
                    job["questionTargets"][qid]
                    for qid, value in values.items()
                    if job["arm"] == "B" and value == "no"
                ],
            }
        )
    known_input = sum(row["inputTokens"] or 0 for row in predictions.values())
    known_output = sum(row["outputTokens"] or 0 for row in predictions.values())
    question_rows = [question for row in results for question in row["questions"]]
    arms = {}
    for arm in ("A", "B", "C", "D"):
        arm_rows = [row for row in results if row["arm"] == arm]
        arm_questions = [q for row in arm_rows for q in row["questions"]]
        arms[arm] = {
            "plannedCalls": len(arm_rows),
            "plannedQuestions": len(arm_questions),
            "statusCounts": dict(Counter(row["status"] for row in arm_rows)),
            "questionAgreementCount": sum(
                q["agreement"] is True for q in arm_questions
            ),
            "questionDisagreementCount": sum(
                q["agreement"] is False for q in arm_questions
            ),
            "unevaluatedQuestionCount": sum(
                q["agreement"] is None for q in arm_questions
            ),
            "selectedClaimVerdicts": dict(
                Counter(
                    row["overallSelectedClaimVerdict"]
                    for row in arm_rows
                    if row["overallSelectedClaimVerdict"] is not None
                )
            ),
            "falseAcceptanceCount": sum(
                row["overallSelectedClaimVerdict"] == "compatible"
                and row["referenceSelectedClaimVerdict"] == "incompatible"
                for row in arm_rows
            )
            if arm != "D"
            else None,
            "falseRejectionCount": sum(
                row["overallSelectedClaimVerdict"] == "incompatible"
                and row["referenceSelectedClaimVerdict"] == "compatible"
                for row in arm_rows
            )
            if arm != "D"
            else None,
        }
    return {
        "schema": "normlab.s13-replay-report/v1",
        "evidenceKind": "offline-fixture",
        "planDigest": summary["planDigest"],
        "captureDigest": sealed_digest,
        "referenceDigest": digest(reference_raw),
        "referenceStatus": reference["status"],
        "referenceRevision": reference["revision"],
        "plannedCalls": len(jobs),
        "plannedQuestions": len(question_rows),
        "statusCounts": dict(Counter(row["status"] for row in results)),
        "questionAgreementCount": sum(q["agreement"] is True for q in question_rows),
        "questionDisagreementCount": sum(
            q["agreement"] is False for q in question_rows
        ),
        "unevaluatedQuestionCount": sum(q["agreement"] is None for q in question_rows),
        "knownInputTokens": known_input,
        "knownOutputTokens": known_output,
        "unknownUsageOutcomes": sum(
            row["inputTokens"] is None or row["outputTokens"] is None
            for row in predictions.values()
        ),
        "providerQualityScore": None,
        "wholeSourceCompleteness": "not-evaluated",
        "arms": arms,
        "inferenceCalls": 0,
        "results": results,
    }


def write_new(path, value):
    with path.open("x", encoding="utf-8") as handle:
        handle.write(
            json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "export", "replay"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--capture", type=Path, default=FIXTURE / "mock-capture.json")
    parser.add_argument(
        "--reference", type=Path, default=FIXTURE / "reviewer-only.json"
    )
    args = parser.parse_args()
    if args.command == "replay":
        report = replay(load(args.capture), args.reference)
        if args.output:
            write_new(args.output, report)
        print(
            canonical({key: value for key, value in report.items() if key != "results"})
        )
        return
    manifest, jobs, summary = compile_plan()
    if args.command == "export":
        require(args.output is not None, "Export output directory required")
        require(not args.output.exists(), "Refuse to overwrite an export")
        args.output.mkdir(parents=True)
        # Each artifact stays under the prior harness's 2 MiB boundary.
        chunk, byte_count, index, chunks = [], 0, 0, []
        for job in jobs:
            line = canonical(job) + "\n"
            size = len(line.encode())
            require(size <= 1_048_576, "Individual job export cap")
            if chunk and byte_count + size > 1_048_576:
                filename = f"plan-{index:03}.jsonl"
                raw = "".join(chunk).encode()
                (args.output / filename).write_bytes(raw)
                chunks.append(
                    {"path": filename, "sha256": digest(raw), "jobs": len(chunk)}
                )
                chunk, byte_count, index = [], 0, index + 1
            chunk.append(line)
            byte_count += size
        if chunk:
            filename = f"plan-{index:03}.jsonl"
            raw = "".join(chunk).encode()
            (args.output / filename).write_bytes(raw)
            chunks.append({"path": filename, "sha256": digest(raw), "jobs": len(chunk)})
        write_new(args.output / "summary.json", {**summary, "chunks": chunks})
        print(canonical(summary))
        return
    require(load(FIXTURE / "plan-summary.json") == summary, "Frozen plan drift")
    examples = load(FIXTURE / "examples.json")
    for example in examples:
        require(example in jobs, "Example drift")
    require(
        {job["arm"] for job in examples} == {"A", "B", "C", "D"}, "Example arm coverage"
    )
    report = replay(load(args.capture), args.reference)
    require(
        load(FIXTURE / "mock-replay-summary.json")
        == {key: value for key, value in report.items() if key != "results"},
        "Frozen replay drift",
    )
    print(
        canonical(
            {
                **summary,
                "replayStatusCounts": report["statusCounts"],
                "inferenceCalls": 0,
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"S1.3 offline contract failed: {error}", file=sys.stderr)
        sys.exit(1)
