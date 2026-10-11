"""Versioned Stage 1 network retries with an aggregate dispatch cap and replay."""

import argparse
import json
import math
import random
import sys
import time
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

from harness import artifact, digest, load_json, require
from stage1_provider_executor import code_pins as parent_pins
from stage1_provider_executor import replay as replay_attempt
from stage1_provider_executor import run as run_attempt
from stage1_provider_executor import validate_permit
from stage1_provider_plan import prepare as prepare_parent
from stage1_provider_plan import sha, write_json

TRANSIENT = {
    "ConnectError",
    "ConnectTimeout",
    "ReadError",
    "ReadTimeout",
    "WriteError",
    "WriteTimeout",
    "RemoteProtocolError",
    "SSLEOFError",
}
SAFE_CLASSES = TRANSIENT | {
    "SSLCertVerificationError",
    "CertificateError",
    "OtherError",
}
POLICY = {
    "maxAttemptsPerJob": 3,
    "baseDelaySeconds": 1,
    "jitterMaxSeconds": 0.5,
    "transientClasses": sorted(TRANSIENT),
    "unknownSentOutcome": "stop-no-resume",
}


def prepare(path, profile):
    parent = prepare_parent(path, profile)
    return {
        "schema": "normlab.stage1-retry-plan/v1",
        "parent": parent,
        "parentDigest": sha(parent),
        "codePins": {
            **parent_pins(),
            "stage1_retry_executor.py": digest(Path(__file__).read_bytes()),
        },
        "retryPolicy": POLICY,
        "budget": {
            **parent["budget"],
            "maxCalls": len(parent["jobs"]) * POLICY["maxAttemptsPerJob"],
            "maxQuestions": len(parent["jobs"]) * POLICY["maxAttemptsPerJob"],
        },
    }


def child_plan(plan, job, ordinal):
    parent = plan["parent"]
    return {
        **parent,
        "schema": "normlab.stage1-provider-attempt-plan/v1",
        "retryPlanDigest": sha(plan),
        "retryOrdinal": ordinal,
        "jobs": [job],
        "budget": {**parent["budget"], "maxCalls": 1, "maxQuestions": 1},
    }


def chain(error):
    result, seen = [], set()
    while error is not None and id(error) not in seen and len(result) < 8:
        seen.add(id(error))
        name = type(error).__name__
        result.append(name if name in SAFE_CLASSES else "OtherError")
        error = error.__cause__ or error.__context__
    return result


@contextmanager
def observe_network(classes):
    # Sequential local runner only. Do not change SDK retry behavior or exception flow.
    import httpx2

    original = httpx2.HTTPTransport.handle_request
    original_iter = httpx2.Response.iter_bytes

    def observed(self, request):
        try:
            return original(self, request)
        except Exception as error:
            if not classes:
                classes.extend(chain(error))
            raise

    def observed_iter(self, *args, **kwargs):
        try:
            yield from original_iter(self, *args, **kwargs)
        except Exception as error:
            if not classes:
                classes.extend(chain(error))
            raise

    httpx2.HTTPTransport.handle_request = observed
    httpx2.Response.iter_bytes = observed_iter
    try:
        yield
    finally:
        httpx2.HTTPTransport.handle_request = original
        httpx2.Response.iter_bytes = original_iter


def retryable(turn, classes):
    return (
        turn["status"] == "failed"
        and turn["error"] == "transport-error"
        and not set(classes) & {"SSLCertVerificationError", "CertificateError"}
        and bool(set(classes) & TRANSIENT)
    )


def delay_bounds(ordinal):
    low = POLICY["baseDelaySeconds"] * 2 ** (ordinal - 1)
    return low, low + POLICY["jitterMaxSeconds"]


def run(plan, folder, *, permit=None, mock=False, max_mock_calls=None, scenario=None):
    require(type(mock) is bool, "Execution mode")
    if mock:
        require(permit is None, "Mocks cannot use a permit")
        cap = plan["budget"]["maxCalls"] if max_mock_calls is None else max_mock_calls
        require(type(cap) is int and 0 <= cap <= plan["budget"]["maxCalls"], "Mock cap")
    else:
        require(
            scenario is None and max_mock_calls is None,
            "Mock flags forbidden in live mode",
        )
        cap = validate_permit(plan, permit, current=True)
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    index = {
        "schema": "normlab.stage1-retry-capture/v1",
        "planDigest": sha(plan),
        "mode": "mock-http" if mock else "live",
        "permit": permit,
        "maxCalls": cap,
        "scenario": scenario,
        "attempts": [],
        "stopReason": None,
        "elapsedSeconds": 0,
    }
    write_json(folder / "plan.json", plan)
    started = time.monotonic()
    deadline = started + plan["budget"]["wallDeadlineSeconds"]

    def checkpoint():
        index["elapsedSeconds"] = time.monotonic() - started
        write_json(folder / "capture.json", index)

    checkpoint()
    used, models = 0, {}
    for job in plan["parent"]["jobs"]:
        for ordinal in range(1, POLICY["maxAttemptsPerJob"] + 1):
            if used >= cap:
                index["stopReason"] = "budget-exhaustion"
                break
            if time.monotonic() >= deadline:
                index["stopReason"] = "deadline"
                break
            if not mock:
                try:
                    validate_permit(plan, permit, current=True)
                except ValueError:
                    index["stopReason"] = "permit-expired"
                    break
            child = child_plan(plan, job, ordinal)
            name = f"attempt-{len(index['attempts']) + 1:04d}"
            entry = {
                "jobId": job["jobId"],
                "ordinal": ordinal,
                "path": name,
                "exceptionClasses": [],
                "backoffSeconds": None,
                "finished": False,
            }
            index["attempts"].append(entry)
            checkpoint()  # Reserve the attempt before calling the child runner.
            fault = None
            if mock and job is plan["parent"]["jobs"][0]:
                kind = {
                    "recover": "transport",
                    "backoff-interrupt": "transport",
                    "exhaust": "transport",
                    "http": "http",
                    "invalid": "malformed",
                    "interrupt": "interrupt",
                }.get(scenario)
                if kind and (scenario == "exhaust" or ordinal == 1):
                    fault = {"slot": 0, "kind": kind}
                    if kind == "transport":
                        entry["exceptionClasses"] = ["ReadTimeout"]
            child_permit = (
                None if mock else {**permit, "planDigest": sha(child), "maxCalls": 1}
            )
            try:
                with observe_network(entry["exceptionClasses"]):
                    run_attempt(
                        child,
                        folder / name,
                        permit=child_permit,
                        mock=mock,
                        max_mock_calls=1 if mock else None,
                        fault=fault,
                    )
            except KeyboardInterrupt:
                checkpoint()
                raise
            except Exception:
                # No automatic retry after a missing/invalid child artifact.
                index["stopReason"] = "attempt-operation-error"
                checkpoint()
                raise
            entry["finished"] = True
            child_index, _ = load_json(folder / name / "capture.json")
            turn = artifact((folder / name).resolve(), child_index["turnArtifacts"][0])
            used += turn["dispatches"]
            checkpoint()
            if time.monotonic() >= deadline:
                index["stopReason"] = "deadline"
                break
            if turn["status"] == "completed":
                model = turn["result"]["returnedModel"]
                if models.setdefault(job["armId"], model) != model:
                    index["stopReason"] = "returned-model-change"
                break
            if not retryable(turn, entry["exceptionClasses"]):
                index["stopReason"] = (
                    child_index["stopReason"] or "unknown-sent-outcome"
                )
                break
            if ordinal == POLICY["maxAttemptsPerJob"]:
                index["stopReason"] = "retries-exhausted"
                break
            if used >= cap:
                index["stopReason"] = "budget-exhaustion"
                break
            low, high = delay_bounds(ordinal)
            delay = low if mock else random.SystemRandom().uniform(low, high)
            if time.monotonic() + delay >= deadline:
                index["stopReason"] = "deadline"
                break
            entry["backoffSeconds"] = delay
            checkpoint()
            try:
                if scenario == "backoff-interrupt":
                    raise KeyboardInterrupt
                if not mock:
                    time.sleep(delay)
            except KeyboardInterrupt:
                index["stopReason"] = "interrupted-during-backoff"
                checkpoint()
                raise
        if index["stopReason"]:
            break
    checkpoint()
    return replay(plan, folder)


def replay(plan, folder):
    saved, _ = load_json(folder / "plan.json")
    require(saved == plan, "Retry plan binding")
    index, _ = load_json(folder / "capture.json")
    require(
        set(index)
        == {
            "schema",
            "planDigest",
            "mode",
            "permit",
            "maxCalls",
            "scenario",
            "attempts",
            "stopReason",
            "elapsedSeconds",
        },
        "Retry capture fields",
    )
    require(
        index["schema"] == "normlab.stage1-retry-capture/v1"
        and index["planDigest"] == sha(plan),
        "Retry capture binding",
    )
    require(index["mode"] in ("mock-http", "live"), "Capture mode")
    mock = index["mode"] == "mock-http"
    cap = index["maxCalls"]
    require(type(cap) is int and 0 <= cap <= plan["budget"]["maxCalls"], "Dispatch cap")
    if mock:
        require(index["permit"] is None, "No mock permit")
    else:
        require(
            index["scenario"] is None and validate_permit(plan, index["permit"]) == cap,
            "Aggregate permit binding",
        )
    require(
        type(index["elapsedSeconds"]) in (int, float)
        and math.isfinite(index["elapsedSeconds"])
        and index["elapsedSeconds"] >= 0,
        "Elapsed time",
    )
    jobs = plan["parent"]["jobs"]
    position, ordinal, used, previous, pending = 0, 1, 0, None, False
    models, results, attempts_per_arm = {}, {}, Counter()
    last = None
    for number, entry in enumerate(index["attempts"]):
        require(
            not pending and position < len(jobs), "No attempt after unknown outcome/end"
        )
        require(
            set(entry)
            == {
                "jobId",
                "ordinal",
                "path",
                "exceptionClasses",
                "backoffSeconds",
                "finished",
            },
            "Attempt entry fields",
        )
        job = jobs[position]
        require(
            entry["jobId"] == job["jobId"]
            and type(entry["ordinal"]) is int
            and entry["ordinal"] == ordinal
            and entry["path"] == f"attempt-{number + 1:04d}",
            "Ordered attempt identity",
        )
        require(
            type(entry["finished"]) is bool
            and isinstance(entry["exceptionClasses"], list)
            and len(entry["exceptionClasses"]) <= 8
            and all(c in SAFE_CLASSES for c in entry["exceptionClasses"]),
            "Sanitized exception classes",
        )
        if previous:
            require(
                retryable(previous[0], previous[1]["exceptionClasses"]),
                "Only transient network failures retry",
            )
            delay = previous[1]["backoffSeconds"]
            low, high = delay_bounds(ordinal - 1)
            require(
                type(delay) in (int, float)
                and math.isfinite(delay)
                and low <= delay <= high,
                "Bounded exponential backoff",
            )
        child = child_plan(plan, job, ordinal)
        child_folder = folder / entry["path"]
        if not (child_folder / "capture.json").exists():
            require(
                not entry["finished"] and number == len(index["attempts"]) - 1,
                "Missing attempt outcome",
            )
            # Reserved unknown attempt may have been billed; conservatively consume one.
            used += 1
            attempts_per_arm[job["armId"]] += 1
            results[job["jobId"]] = {"status": "unknown-sent-outcome"}
            pending = True
            break
        summary = replay_attempt(child, child_folder)
        child_index, _ = load_json(child_folder / "capture.json")
        require(
            child_index["mode"] == index["mode"] and child_index["maxCalls"] == 1,
            "Child mode/cap",
        )
        if not mock:
            require(
                child_index["permit"]
                == {**index["permit"], "planDigest": sha(child), "maxCalls": 1},
                "Derived permit binding",
            )
        turn = artifact(child_folder.resolve(), child_index["turnArtifacts"][0])
        used += turn["dispatches"]
        attempts_per_arm[job["armId"]] += turn["dispatches"]
        if not entry["finished"]:
            require(number == len(index["attempts"]) - 1, "Pending suffix")
            pending = True
            results[job["jobId"]] = {"status": "unknown-sent-outcome"}
            break
        last = (turn, entry, summary)
        results[job["jobId"]] = turn
        if turn["status"] == "completed":
            require(
                entry["backoffSeconds"] is None and not entry["exceptionClasses"],
                "Successful attempt is final",
            )
            model = turn["result"]["returnedModel"]
            if models.setdefault(job["armId"], model) != model:
                require(
                    number == len(index["attempts"]) - 1
                    and index["stopReason"] == "returned-model-change",
                    "Model drift stops run",
                )
                results[job["jobId"]] = {"status": "model-rejected"}
            position += 1
            ordinal, previous = 1, None
        else:
            require(ordinal <= POLICY["maxAttemptsPerJob"], "Attempt bound")
            previous = (turn, entry)
            ordinal += 1
            if ordinal > POLICY["maxAttemptsPerJob"] or not retryable(
                turn, entry["exceptionClasses"]
            ):
                require(
                    number == len(index["attempts"]) - 1
                    and entry["backoffSeconds"] is None,
                    "Terminal failure cannot retry",
                )
    require(used <= cap, "Aggregate dispatch cap")
    reason = index["stopReason"]
    if pending:
        require(
            reason is None or reason == "attempt-operation-error",
            "Pending outcome cannot claim success",
        )
        reason = "unknown-sent-outcome"
    elif reason == "budget-exhaustion":
        require(used == cap and position < len(jobs), "Exhausted budget")
    elif reason == "retries-exhausted":
        require(
            last is not None
            and last[1]["ordinal"] == POLICY["maxAttemptsPerJob"]
            and retryable(last[0], last[1]["exceptionClasses"]),
            "Exhausted retries",
        )
    elif reason == "interrupted-during-backoff":
        require(
            last is not None
            and retryable(last[0], last[1]["exceptionClasses"])
            and last[1]["backoffSeconds"] is not None,
            "Interrupted retry delay",
        )
    elif reason in ("deadline", "permit-expired", "returned-model-change"):
        pass
    elif reason:
        require(
            last is not None
            and reason == last[2]["stopReason"]
            and not retryable(last[0], last[1]["exceptionClasses"]),
            "Terminal error binding",
        )
    else:
        require(position == len(jobs), "Complete planned denominator")
    arms = {}
    for job in jobs:
        counts = arms.setdefault(job["armId"], Counter())
        counts["planned"] += 1
        turn = results.get(job["jobId"])
        counts[turn["status"] if turn else "not-executed"] += 1
    return {
        "schema": "normlab.stage1-retry-summary/v1",
        "planDigest": sha(plan),
        "mode": index["mode"],
        "networkCalls": 0 if mock else used,
        "mockHttpCalls": used if mock else 0,
        "stopReason": reason,
        "attemptsPerArm": dict(attempts_per_arm),
        "arms": {k: dict(v) for k, v in arms.items()},
        "semanticQualityEvidence": False,
        "actualCost": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--profile", choices=("pilot", "corpus"), default="pilot")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--mock-output", type=Path)
    mode.add_argument("--live-output", type=Path)
    mode.add_argument("--replay", type=Path)
    parser.add_argument("--permit", type=Path)
    parser.add_argument("--max-mock-calls", type=int)
    parser.add_argument(
        "--mock-scenario",
        choices=(
            "recover",
            "exhaust",
            "http",
            "invalid",
            "interrupt",
            "backoff-interrupt",
        ),
    )
    args = parser.parse_args()
    try:
        require(
            (args.permit is not None) == (args.live_output is not None),
            "Live requires a permit",
        )
        require(
            args.mock_output is not None
            or (args.max_mock_calls is None and args.mock_scenario is None),
            "Mock-only options",
        )
        plan = prepare(args.manifest, args.profile)
        if args.replay:
            result = replay(plan, args.replay)
        elif args.live_output:
            permit, _ = load_json(args.permit)
            result = run(plan, args.live_output, permit=permit)
        elif args.mock_output:
            result = run(
                plan,
                args.mock_output,
                mock=True,
                max_mock_calls=args.max_mock_calls,
                scenario=args.mock_scenario,
            )
        else:
            result = {
                "schema": plan["schema"],
                "planDigest": sha(plan),
                "plannedJobs": len(plan["parent"]["jobs"]),
                "maxDispatches": plan["budget"]["maxCalls"],
                "authorizedCalls": 0,
                "retryPolicy": POLICY,
            }
        print(json.dumps(result, ensure_ascii=False))
        return 3 if result.get("stopReason") else 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "rejected", "errorType": type(error).__name__}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
