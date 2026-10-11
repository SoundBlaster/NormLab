"""Offline executor v2; v1 executor and captures remain frozen for replay."""

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from harness import MAX_BYTES, artifact, digest, load_json, require
from plan_stage1_comparison import LABELS, canonical, export_plan, prepare, summary
from stage1_wire_v2 import finite, normalize, wire_response

SCHEMA = "normlab.stage1-offline-capture/v2"
TURN_SCHEMA = "normlab.stage1-offline-turn/v2"


def sha(value):
    return digest(canonical(value).encode())


def write_json(path, value):
    raw = (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    require(len(raw) <= MAX_BYTES, "Capture artifact exceeds bound")
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(raw)
    temporary.replace(path)
    return {"path": path.name, "sha256": digest(raw)}


def empty_turn(job):
    return {
        "schema": TURN_SCHEMA,
        "jobId": job["jobId"],
        "jobDigest": sha(job),
        "status": "not-executed",
        "fixtureCalls": 0,
        "request": None,
        "httpStatus": None,
        "result": None,
        "response": None,
        "error": None,
        "latencySeconds": None,
    }


def run(plan, fixture, folder, max_calls=None, clock=time.monotonic):
    """Consume fixture slots once, checkpoint before consumption, stop on first failure.

    The fixtures are already in memory: there is no pluggable network callback.
    authorizedCalls=0 remains intact and means zero live calls.
    """
    limit = plan["budget"]["maxCalls"] if max_calls is None else max_calls
    require(
        type(limit) is int and 0 <= limit <= plan["budget"]["maxCalls"],
        "Fixture call cap",
    )
    require(
        set(fixture) == {"schema", "planDigest", "responses"}
        and fixture["schema"] == "normlab.stage1-wire-fixtures/v1"
        and fixture["planDigest"] == sha(plan)
        and isinstance(fixture["responses"], dict)
        and set(fixture["responses"]) == {j["jobId"] for j in plan["jobs"]},
        "Fixture must bind every planned job",
    )
    export_plan(plan, folder)
    turns = [empty_turn(job) for job in plan["jobs"]]
    code = Path(__file__)
    index = {
        "schema": SCHEMA,
        "mode": "offline-fixture",
        "planDigest": sha(plan),
        "fixtureDigest": sha(fixture),
        "codePins": {
            p.name: digest(p.read_bytes())
            for p in (code, code.with_name("stage1_wire_v2.py"))
        },
        "maxFixtureCalls": limit,
        "networkCalls": 0,
        "stopReason": None,
        "turnArtifacts": [],
    }

    def checkpoint(updated=None):
        if not index["turnArtifacts"]:
            index["turnArtifacts"] = [
                write_json(folder / f"{turn['jobId']}.json", turn) for turn in turns
            ]
        elif updated is not None:
            number = next(i for i, turn in enumerate(turns) if turn is updated)
            index["turnArtifacts"][number] = write_json(
                folder / f"{updated['jobId']}.json", updated
            )
        write_json(folder / "capture.json", index)

    checkpoint()
    started = clock()
    models = {}
    for number, (job, turn) in enumerate(zip(plan["jobs"], turns)):
        if number >= limit:
            index["stopReason"] = "budget-exhaustion"
            break
        if clock() - started >= plan["budget"]["wallDeadlineSeconds"]:
            index["stopReason"] = "deadline"
            break
        turn.update(status="sent", fixtureCalls=1, request=job["request"])
        checkpoint(turn)  # Interrupted consumption is unknown; never auto-resume.
        call_start = clock()
        raw = fixture["responses"][job["jobId"]]
        try:
            require(
                isinstance(raw, dict) and set(raw) == {"httpStatus", "body"},
                "Wire fixture shape",
            )
            status = raw["httpStatus"]
            require(type(status) is int and 100 <= status <= 599, "HTTP status")
            turn["httpStatus"] = status
            if status != 200:
                turn["error"] = "provider-error"
            else:
                require(
                    len(canonical(raw["body"]).encode()) <= MAX_BYTES // 2,
                    "Response bound",
                )
                result = normalize(job["armId"], raw["body"])
                previous = models.setdefault(job["armId"], result["returnedModel"])
                if previous != result["returnedModel"]:
                    turn["error"] = "returned-model-change"
                else:
                    turn["result"] = result
                    turn["response"] = raw["body"]
        except (ValueError, KeyError, TypeError, OverflowError):
            turn["error"] = (
                "invalid-output"  # Never serialize exception text or error body.
            )
        turn["latencySeconds"] = max(0, clock() - call_start)
        if clock() - started >= plan["budget"]["wallDeadlineSeconds"]:
            turn["error"] = "deadline"
        if turn["error"]:
            turn.update(status="failed", result=None, response=None)
            index["stopReason"] = turn["error"]
            checkpoint(turn)
            break
        turn["status"] = "completed"
        checkpoint(turn)
    checkpoint()
    return replay(plan, folder)


def replay(plan, folder):
    """Validate checkpoint state and bind public requests to the freshly compiled plan."""
    index, _ = load_json(folder / "capture.json")
    require(
        set(index)
        == {
            "schema",
            "mode",
            "planDigest",
            "fixtureDigest",
            "codePins",
            "maxFixtureCalls",
            "networkCalls",
            "stopReason",
            "turnArtifacts",
        },
        "Capture shape",
    )
    require(
        index["schema"] == SCHEMA
        and index["mode"] == "offline-fixture"
        and type(index["networkCalls"]) is int
        and index["networkCalls"] == 0,
        "Offline capture required",
    )
    require(index["planDigest"] == sha(plan), "Plan mismatch")
    exported, _ = load_json(folder / "plan.json")
    require(
        exported["schema"] == "normlab.stage1-comparison-export/v1",
        "Plan export schema",
    )
    reconstructed = {
        **exported["plan"],
        "jobs": [artifact(folder.resolve(), x) for x in exported["jobArtifacts"]],
    }
    require(reconstructed == plan, "Exported plan mismatch")
    require(
        artifact(folder.resolve(), exported["summaryArtifact"]) == summary(plan),
        "Plan summary mismatch",
    )
    require(
        index["codePins"]
        == {
            p.name: digest(p.read_bytes())
            for p in (
                Path(__file__),
                Path(__file__).with_name("stage1_wire_v2.py"),
            )
        },
        "Executor version drift",
    )
    limit = index["maxFixtureCalls"]
    require(
        type(limit) is int and 0 <= limit <= plan["budget"]["maxCalls"], "Replay cap"
    )
    require(
        len(index["turnArtifacts"]) == len(plan["jobs"]), "Complete planned denominator"
    )
    counts = {}
    consumed = 0
    stopped = False
    failure = None
    models = {}
    for job, entry in zip(plan["jobs"], index["turnArtifacts"]):
        require(entry["path"] == f"{job['jobId']}.json", "Turn ordering")
        turn = artifact(folder.resolve(), entry)
        expected = empty_turn(job)
        require(set(turn) == set(expected), "Turn shape")
        require(
            all(turn[k] == expected[k] for k in ("schema", "jobId", "jobDigest")),
            "Job binding",
        )
        status = turn["status"]
        require(status in ("not-executed", "sent", "failed", "completed"), "Turn state")
        arm = counts.setdefault(job["armId"], Counter())
        arm["planned"] += 1
        arm[status] += 1
        if status == "not-executed":
            require(
                turn == expected and type(turn["fixtureCalls"]) is int,
                "Unused turn must be empty",
            )
            stopped = True
            continue
        require(not stopped, "Executed turn after stop")
        require(
            type(turn["fixtureCalls"]) is int
            and turn["fixtureCalls"] == 1
            and turn["request"] == job["request"],
            "Consumed request binding",
        )
        consumed += 1
        if status == "sent":
            require(
                all(
                    turn[k] is None
                    for k in (
                        "httpStatus",
                        "result",
                        "response",
                        "error",
                        "latencySeconds",
                    )
                ),
                "Unknown sent outcome",
            )
            failure = "unknown-sent-outcome"
            stopped = True
            continue
        require(
            finite(turn["latencySeconds"]) and turn["latencySeconds"] >= 0,
            "Latency contract",
        )
        if status == "failed":
            error = turn["error"]
            http = turn["httpStatus"]
            require(
                turn["result"] is None and turn["response"] is None,
                "Failed turn cannot have a verdict",
            )
            require(
                error
                in (
                    "provider-error",
                    "invalid-output",
                    "returned-model-change",
                    "deadline",
                ),
                "Failure category",
            )
            require(
                http is None or (type(http) is int and 100 <= http <= 599),
                "Failure HTTP status",
            )
            require(
                error != "provider-error" or (http is not None and http != 200),
                "HTTP failure invariant",
            )
            require(
                error != "returned-model-change" or http == 200,
                "Model change requires response",
            )
            require(
                error != "invalid-output" or http in (None, 200),
                "Invalid output requires malformed status or successful response",
            )
            failure = error
            stopped = True
            continue
        require(
            turn["httpStatus"] == 200 and turn["error"] is None,
            "Completed state invariant",
        )
        result = turn["result"]
        require(
            isinstance(result, dict)
            and set(result)
            == {
                "label",
                "returnedModel",
                "requestId",
                "confidence",
                "probabilities",
                "usage",
                "cost",
            },
            "Result shape",
        )
        require(
            normalize(job["armId"], turn["response"]) == result, "Result validation"
        )
        previous = models.setdefault(job["armId"], result["returnedModel"])
        require(previous == result["returnedModel"], "Returned model drift")
        arm[result["label"]] += 1
    require(consumed <= limit, "Consumed slot cap exceeded")
    reason = index["stopReason"]
    if failure == "unknown-sent-outcome":
        require(reason is None, "Interrupted checkpoint cannot assert final stop")
    elif failure:
        require(reason == failure, "Failure stop mismatch")
    elif consumed < len(plan["jobs"]):
        require(
            reason == "deadline"
            or (reason == "budget-exhaustion" and consumed == limit),
            "Unused suffix reason",
        )
    else:
        require(reason is None, "Finished run cannot assert stop")
    return {
        "schema": "normlab.stage1-offline-summary/v1",
        "planDigest": sha(plan),
        "fixtureCalls": consumed,
        "networkCalls": 0,
        "stopReason": failure or reason,
        "arms": {key: dict(value) for key, value in counts.items()},
        "criticalErrorFreeRate": None,
        "semanticQualityEvidence": False,
        "actualCost": None,
    }


def demo_fixture(plan):
    """Cycle labels by schedule position, without opening reviewer labels."""
    responses = {}
    for number, job in enumerate(plan["jobs"]):
        label = LABELS[number % len(LABELS)]
        responses[job["jobId"]] = {
            "httpStatus": 200,
            "body": wire_response(
                job["armId"],
                label,
                job["request"]["body"]["model"] + "-fixture",
                "fixture-" + job["jobId"],
                {"input_tokens": 100, "output_tokens": 10},
                1.0,
                {k: float(k == label) for k in LABELS},
            ),
        }
    return {
        "schema": "normlab.stage1-wire-fixtures/v1",
        "planDigest": sha(plan),
        "responses": responses,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--profile", default="pilot")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--mock-output",
        type=Path,
        help="New capture directory; synthetic responses only",
    )
    group.add_argument("--replay", type=Path)
    parser.add_argument("--max-fixture-calls", type=int)
    args = parser.parse_args()
    plan = prepare(args.manifest, args.profile)
    if args.mock_output:
        result = run(plan, demo_fixture(plan), args.mock_output, args.max_fixture_calls)
    elif args.replay:
        require(args.max_fixture_calls is None, "Replay uses captured cap")
        result = replay(plan, args.replay)
    else:
        require(args.max_fixture_calls is None, "Fixture cap requires mock execution")
        result = summary(plan)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
