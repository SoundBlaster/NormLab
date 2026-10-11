"""Bounded three-provider Stage 1 execution; dry-run and SDK-free replay by default."""

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from harness import MAX_BYTES, artifact, digest, load_json, require
from plan_stage1_comparison import LABELS, canonical
from provider_config import ProviderConfig, build_provider, credential
from stage1_provider_plan import export, prepare, sha, summary, write_json
from stage1_provider_wire import decode, mock_response, normalize, public_response

SCHEMA = "normlab.stage1-provider-capture/v1"
ERRORS = {
    "transport-error",
    "provider-error",
    "invalid-output",
    "returned-model-change",
    "deadline",
    "request-mismatch",
    "configuration-error",
}


def code_pins():
    names = (
        "stage1_provider_executor.py",
        "stage1_provider_plan.py",
        "stage1_provider_wire.py",
        "stage1_wire_v2.py",
        "plan_stage1_comparison.py",
        "harness.py",
        "provider_config.py",
    )
    return {name: digest(Path(__file__).with_name(name).read_bytes()) for name in names}


def validate_permit(plan, permit, current=False):
    require(
        isinstance(permit, dict)
        and set(permit)
        == {"schema", "planDigest", "maxCalls", "expiresAt", "spending"},
        "Execution permit fields",
    )
    require(
        permit["schema"] == "normlab.stage1-execution-permit/v1"
        and permit["planDigest"] == sha(plan),
        "Plan-bound execution permit",
    )
    require(
        type(permit["maxCalls"]) is int
        and 0 < permit["maxCalls"] <= plan["budget"]["maxCalls"],
        "Authorized call cap",
    )
    expires = datetime.fromisoformat(permit["expiresAt"].replace("Z", "+00:00"))
    require(expires.tzinfo is not None, "Permit timezone")
    if current:
        require(datetime.now(timezone.utc) < expires, "Expired execution permit")
    spend = permit["spending"]
    require(
        isinstance(spend, dict)
        and set(spend)
        == {
            "enforcement",
            "amount",
            "currency",
            "pricingReference",
            "operatorConfirmed",
        },
        "Spending declaration",
    )
    require(
        spend["enforcement"] == "external-provider-limit"
        and spend["operatorConfirmed"] is True,
        "External spending limit must be confirmed by operator",
    )
    import math
    import re

    require(
        type(spend["amount"]) in (int, float)
        and math.isfinite(spend["amount"])
        and spend["amount"] > 0,
        "Positive external spending limit",
    )
    require(
        isinstance(spend["currency"], str)
        and re.fullmatch(r"[A-Z]{3}", spend["currency"]),
        "Currency",
    )
    require(
        isinstance(spend["pricingReference"], str)
        and 0 < len(spend["pricingReference"].strip()) <= 1024,
        "Operator pricing reference",
    )
    return permit["maxCalls"]


def empty_turn(job):
    return {
        "jobId": job["jobId"],
        "jobDigest": sha(job),
        "status": "not-executed",
        "dispatches": 0,
        "request": None,
        "httpStatus": None,
        "response": None,
        "result": None,
        "error": None,
        "latencySeconds": None,
    }


def run(plan, folder, *, permit=None, mock=False, max_mock_calls=None, fault=None):
    """Use actual SDK control flow through either HTTPTransport or MockTransport."""
    require(type(mock) is bool, "Execution mode")
    if mock:
        require(permit is None, "Mock mode cannot consume live authorization")
        limit = len(plan["jobs"]) if max_mock_calls is None else max_mock_calls
        require(type(limit) is int and 0 <= limit <= len(plan["jobs"]), "Mock cap")
    else:
        require(
            max_mock_calls is None and fault is None,
            "Mock options forbidden in live mode",
        )
        limit = validate_permit(plan, permit, current=True)
    import importlib.metadata

    import httpx2

    versions = {
        name: importlib.metadata.version(name)
        for name in ("mellea-jev-adapter", "typesafe-sdk", "openai", "httpx2")
    }
    require(
        versions["mellea-jev-adapter"] == plan["adapterVersion"],
        "Adapter version mismatch",
    )
    # Resolve all keys before output/dispatch; mock never reads environment credentials.
    keys = {
        arm: "offline-placeholder-not-a-real-key"
        if mock
        else credential(SimpleNamespace(key_env=p["keyEnvironment"]))
        for arm, p in plan["providers"].items()
    }
    os.umask(0o077)
    export(plan, folder)
    turns = [empty_turn(j) for j in plan["jobs"]]
    index = {
        "schema": SCHEMA,
        "mode": "mock-http" if mock else "live",
        "planDigest": sha(plan),
        "codePins": code_pins(),
        "dependencies": {**versions, "python": sys.version.split()[0]},
        "permit": permit,
        "permitDigest": sha(permit),
        "maxCalls": limit,
        "fault": fault,
        "stopReason": None,
        "turnArtifacts": [],
    }

    def checkpoint(turn=None):
        if not index["turnArtifacts"]:
            index["turnArtifacts"] = [
                write_json(folder / f"{t['jobId']}.json", t) for t in turns
            ]
        elif turn is not None:
            position = next(n for n, t in enumerate(turns) if t is turn)
            index["turnArtifacts"][position] = write_json(
                folder / f"{turn['jobId']}.json", turn
            )
        write_json(folder / "capture.json", index)

    checkpoint()
    started = time.monotonic()
    deadline = started + plan["budget"]["wallDeadlineSeconds"]
    models = {}
    used = 0
    for number, (job, turn) in enumerate(zip(plan["jobs"], turns)):
        if used >= limit:
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
        p = plan["providers"][job["armId"]]
        timeout = min(
            plan["budget"]["transportTimeoutSeconds"], deadline - time.monotonic()
        )
        request_id = "fixture-" + job["jobId"]
        label = LABELS[number % len(LABELS)]

        def mock_handler(request):
            if fault and number == fault["slot"]:
                if fault["kind"] == "interrupt":
                    raise KeyboardInterrupt
                if fault["kind"] == "transport":
                    raise httpx2.ReadTimeout(
                        "offline transport fixture", request=request
                    )
                if fault["kind"] == "http":
                    return httpx2.Response(503, json={"error": "synthetic"})
                if fault["kind"] == "malformed":
                    return httpx2.Response(200, content=b"{broken")
            model = p["model"] + "-fixture"
            if fault and number == fault["slot"] and fault["kind"] == "model-drift":
                model += "-changed"
            body = mock_response(p["apiFormat"], label, model, request_id)
            return httpx2.Response(
                200,
                json=body,
                headers={
                    "x-typesafe-request-id": request_id,
                    "x-request-id": request_id,
                },
            )

        class Recorder(httpx2.BaseTransport):
            def __init__(self):
                self.inner = (
                    httpx2.MockTransport(mock_handler)
                    if mock
                    else httpx2.HTTPTransport(retries=0, trust_env=False)
                )

            def handle_request(self, request):
                nonlocal used
                try:
                    actual = {
                        "method": request.method,
                        "endpoint": str(request.url),
                        "body": decode(request.read()),
                    }
                    if (
                        fault
                        and number == fault["slot"]
                        and fault["kind"] == "request-mismatch"
                    ):
                        actual["body"]["model"] = "unexpected-fixture-model"
                    require(actual == job["request"], "SDK request does not match plan")
                    require(
                        turn["dispatches"] == 0 and used < limit,
                        "No retry / request cap",
                    )
                except (ValueError, TypeError):
                    turn["error"] = "request-mismatch"
                    raise
                if time.monotonic() >= deadline:
                    turn["error"] = "deadline"
                    raise ValueError("Deadline")
                if not mock:
                    validate_permit(plan, permit, current=True)
                turn.update(status="sent", dispatches=1, request=actual)
                used += 1
                checkpoint(
                    turn
                )  # Possibly billable/unknown outcome from this point onward.
                remaining = min(timeout, max(0.001, deadline - time.monotonic()))
                request.extensions["timeout"] = {
                    k: remaining for k in ("connect", "read", "write", "pool")
                }
                try:
                    response = self.inner.handle_request(request)
                    turn["httpStatus"] = response.status_code
                    chunks, size = [], 0
                    try:
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            require(size <= MAX_BYTES // 2, "Response bound")
                            require(time.monotonic() < deadline, "Deadline")
                            chunks.append(chunk)
                    finally:
                        response.close()
                except Exception:
                    turn["error"] = (
                        "deadline"
                        if time.monotonic() >= deadline
                        else "transport-error"
                    )
                    raise
                raw = b"".join(chunks)
                if response.status_code != 200:
                    turn["error"] = "provider-error"
                else:
                    try:
                        body = decode(raw)
                        require(isinstance(body, dict), "Response object")
                        rid = (
                            body.get("id")
                            if p["apiFormat"] == "openai-responses"
                            else response.headers.get(
                                "x-typesafe-request-id"
                                if p["apiFormat"] == "typesafe-systemone"
                                else "x-request-id"
                            )
                        )
                        public = public_response(p["apiFormat"], body, rid)
                        result = normalize(p["apiFormat"], public)
                        require(
                            len(canonical(public).encode()) <= MAX_BYTES // 2,
                            "Public response bound",
                        )
                        turn.update(response=public, result=result)
                    except (ValueError, TypeError, KeyError, OverflowError):
                        turn["error"] = "invalid-output"
                        raise
                # Preserve only the request-ID headers required by SDK normalization.
                headers = {
                    k: response.headers[k]
                    for k in ("x-typesafe-request-id", "x-request-id")
                    if k in response.headers
                }
                return httpx2.Response(
                    response.status_code, headers=headers, content=raw
                )

            def close(self):
                self.inner.close()

        recorder = Recorder()
        call_start = time.monotonic()
        try:
            if p["apiFormat"] == "openai-responses":
                with httpx2.Client(
                    transport=recorder,
                    timeout=timeout,
                    follow_redirects=False,
                    trust_env=False,
                ) as client:
                    client.post(
                        p["endpoint"],
                        json=job["request"]["body"],
                        headers={"Authorization": "Bearer " + keys[job["armId"]]},
                    )
            else:
                config = ProviderConfig(
                    job["armId"],
                    p["apiFormat"],
                    p["endpoint"],
                    p["model"],
                    p["keyEnvironment"],
                    timeout,
                )
                q = job["task"]["questions"]["overall"]
                with build_provider(
                    config, api_key=keys[job["armId"]], transport=recorder
                ) as provider:
                    result = provider.choice(
                        state=job["task"]["state"],
                        question=q["instructions"],
                        criteria=q["criteria"],
                    )
                    require(
                        result.choice == turn["result"]["label"]
                        and result.model == turn["result"]["returnedModel"]
                        and result.request_id == turn["result"]["requestId"],
                        "SDK/replay disagreement",
                    )
            if not turn["error"]:
                require(turn["result"] is not None, "No provider result")
                model = turn["result"]["returnedModel"]
                if models.setdefault(job["armId"], model) != model:
                    turn["error"] = "returned-model-change"
        except Exception:
            turn["error"] = turn["error"] or (
                "invalid-output" if turn["httpStatus"] == 200 else "configuration-error"
            )
        finally:
            recorder.close()
        turn["latencySeconds"] = max(0, time.monotonic() - call_start)
        if time.monotonic() >= deadline:
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
    index, _ = load_json(folder / "capture.json")
    require(
        set(index)
        == {
            "schema",
            "mode",
            "planDigest",
            "codePins",
            "dependencies",
            "permit",
            "permitDigest",
            "maxCalls",
            "fault",
            "stopReason",
            "turnArtifacts",
        },
        "Capture shape",
    )
    require(
        index["schema"] == SCHEMA
        and index["mode"] in ("live", "mock-http")
        and index["planDigest"] == sha(plan),
        "Capture plan binding",
    )
    require(index["codePins"] == code_pins(), "Capture code drift")
    require(index["permitDigest"] == sha(index["permit"]), "Permit digest")
    limit = index["maxCalls"]
    require(type(limit) is int and 0 <= limit <= len(plan["jobs"]), "Capture cap")
    if index["mode"] == "live":
        require(
            validate_permit(plan, index["permit"]) == limit and index["fault"] is None,
            "Live permit binding",
        )
    else:
        require(index["permit"] is None, "Mock authorization must be absent")
    require(
        isinstance(index["dependencies"], dict)
        and index["dependencies"].get("mellea-jev-adapter") == plan["adapterVersion"],
        "Runtime metadata",
    )
    saved, _ = load_json(folder / "plan.json")
    restored = {
        **saved["plan"],
        "jobs": [artifact(folder.resolve(), entry) for entry in saved["jobs"]],
    }
    require(restored == plan, "Exported plan binding")
    require(len(index["turnArtifacts"]) == len(plan["jobs"]), "Complete denominator")
    arms, used, stopped, failure, models = {}, 0, False, None, {}
    for job, entry in zip(plan["jobs"], index["turnArtifacts"]):
        require(entry["path"] == f"{job['jobId']}.json", "Turn order")
        turn = artifact(folder.resolve(), entry)
        blank = empty_turn(job)
        require(
            set(turn) == set(blank)
            and all(turn[k] == blank[k] for k in ("jobId", "jobDigest")),
            "Job binding",
        )
        counts = arms.setdefault(job["armId"], Counter())
        counts["planned"] += 1
        status = turn["status"]
        require(status in ("not-executed", "sent", "completed", "failed"), "Turn state")
        counts[status] += 1
        require(
            type(turn["dispatches"]) is int and turn["dispatches"] in (0, 1),
            "Dispatch count",
        )
        counts["dispatched"] += turn["dispatches"]
        if status == "not-executed":
            require(turn == blank, "Empty unused turn")
            stopped = True
            continue
        require(not stopped, "Executed turn after stop")
        require(
            type(turn["dispatches"]) is int and turn["dispatches"] in (0, 1),
            "Dispatch count",
        )
        used += turn["dispatches"]
        require(
            turn["request"] == (job["request"] if turn["dispatches"] else None),
            "Actual request binding",
        )
        if status == "sent":
            require(
                turn["dispatches"] == 1
                and all(
                    turn[k] is None
                    for k in (
                        "httpStatus",
                        "response",
                        "result",
                        "error",
                        "latencySeconds",
                    )
                ),
                "Unknown sent outcome",
            )
            failure, stopped = "unknown-sent-outcome", True
            continue
        require(
            type(turn["latencySeconds"]) in (int, float)
            and 0 <= turn["latencySeconds"] < float("inf"),
            "Finite latency",
        )
        http = turn["httpStatus"]
        require(
            http is None or (type(http) is int and 100 <= http <= 599), "HTTP status"
        )
        if status == "failed":
            require(
                turn["error"] in ERRORS
                and turn["response"] is None
                and turn["result"] is None,
                "Failed turn has no verdict",
            )
            require(
                turn["dispatches"] == 1 or http is None,
                "Unsent turn cannot have HTTP status",
            )
            require(
                turn["error"]
                not in (
                    "transport-error",
                    "provider-error",
                    "invalid-output",
                    "returned-model-change",
                )
                or turn["dispatches"] == 1,
                "Failure requires dispatch",
            )
            require(
                turn["error"] != "invalid-output" or http == 200,
                "Invalid output requires HTTP 200",
            )
            require(
                turn["error"] != "provider-error" or (http is not None and http != 200),
                "HTTP error invariant",
            )
            require(
                turn["error"] != "returned-model-change" or http == 200,
                "Model drift invariant",
            )
            failure, stopped = turn["error"], True
            continue
        require(
            turn["dispatches"] == 1 and http == 200 and turn["error"] is None,
            "Completed invariant",
        )
        result = normalize(
            plan["providers"][job["armId"]]["apiFormat"], turn["response"]
        )
        require(result == turn["result"], "Replay normalized result")
        require(
            models.setdefault(job["armId"], result["returnedModel"])
            == result["returnedModel"],
            "Returned model drift",
        )
        counts[result["label"]] += 1
    require(used <= limit, "Dispatch budget exceeded")
    reason = index["stopReason"]
    if failure == "unknown-sent-outcome":
        require(reason is None, "Interrupted run cannot claim final outcome")
    elif failure:
        require(reason == failure, "Failure stop binding")
    elif stopped:
        require(
            reason in ("deadline", "permit-expired")
            or (reason == "budget-exhaustion" and used == limit),
            "Unused suffix reason",
        )
    else:
        require(reason is None, "Complete run stop invariant")
    return {
        "schema": "normlab.stage1-provider-run-summary/v1",
        "mode": index["mode"],
        "planDigest": sha(plan),
        "networkCalls": used if index["mode"] == "live" else 0,
        "mockHttpCalls": used if index["mode"] == "mock-http" else 0,
        "stopReason": failure or reason,
        "arms": {k: dict(v) for k, v in arms.items()},
        "semanticQualityEvidence": False,
        "criticalErrorFreeRate": None,
        "actualCost": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--profile", choices=("pilot", "corpus"), default="pilot")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--mock-output", type=Path)
    group.add_argument("--replay", type=Path)
    group.add_argument("--live-output", type=Path)
    parser.add_argument("--permit", type=Path)
    parser.add_argument("--max-mock-calls", type=int)
    parser.add_argument(
        "--mock-fault",
        choices=(
            "transport",
            "http",
            "malformed",
            "model-drift",
            "interrupt",
            "request-mismatch",
        ),
    )
    parser.add_argument("--mock-fault-slot", type=int, default=0)
    args = parser.parse_args()
    try:
        plan = prepare(args.manifest, args.profile)
        require(
            args.mock_output is not None
            or (args.max_mock_calls is None and args.mock_fault is None),
            "Mock flags require mock output",
        )
        require(
            (args.permit is not None) == (args.live_output is not None),
            "Live requires explicit permit and output",
        )
        fault = None
        if args.mock_fault:
            require(0 <= args.mock_fault_slot < len(plan["jobs"]), "Fault slot")
            fault = {"kind": args.mock_fault, "slot": args.mock_fault_slot}
        if args.mock_output:
            result = run(
                plan,
                args.mock_output,
                mock=True,
                max_mock_calls=args.max_mock_calls,
                fault=fault,
            )
        elif args.live_output:
            permit, _ = load_json(args.permit)
            result = run(plan, args.live_output, permit=permit)
        elif args.replay:
            result = replay(plan, args.replay)
        else:
            result = summary(plan)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 3 if result.get("stopReason") else 0
    except Exception as exc:
        # No exception text, body, URL or credential in diagnostics.
        print(
            json.dumps(
                {"error": "stage1-operation-failed", "category": type(exc).__name__}
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
