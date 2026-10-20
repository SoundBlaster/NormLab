"""One authorized fresh rerun via the existing CLI; no reusable executor."""

import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUTPUT = Path(
    "/Volumes/TB5/Developer/Builds/GitHub/NormLab-s1-3-a092c0e9e6e405bd/"
    "python/probes/ru-en-source-language-2026-10-19"
)


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    os.umask(0o077)
    plan = read(HERE / "plan.json")
    auth = read(HERE / "authorization.json")
    require(digest(HERE / "plan.json") == auth["planSha256"], "Plan drift")
    require(len(plan["jobs"]) == 6 and auth["authorizedRequests"] == 8, "Grant")
    require(plan["budget"]["maximumProtocolRetries"] == 2, "Retry cap")
    require(bool(os.environ.get("COREINFRA_API_KEY")), "Credential missing")
    require(
        not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT),
        "Dirty source",
    )
    subprocess.run(
        ["git", "diff", "--exit-code", plan["executableCommit"], "--", "evaluation"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    runtime = {
        k: importlib.metadata.version(k) for k in plan["runtime"] if k != "python"
    }
    runtime["python"] = sys.version.split()[0]
    require(runtime == plan["runtime"], "Runtime drift")
    refs = (
        plan["inputProvenance"]
        + [
            plan["parentPlan"],
            plan["policy"],
            plan["reviewerOnly"],
            plan["translationReview"],
        ]
        + list(plan["configs"].values())
        + [r["task"] for r in plan["inputs"]]
    )

    def check_inputs():
        require(digest(HERE / "plan.json") == auth["planSha256"], "Plan drift")
        for ref in refs:
            require(digest(ROOT / ref["path"]) == ref["sha256"], "Artifact drift")

    check_inputs()
    OUTPUT.mkdir(mode=0o700, parents=True, exist_ok=False)
    policy = read(ROOT / plan["policy"]["path"])
    inputs = {r["id"]: r for r in plan["inputs"]}
    index = {
        "schema": "normlab.oneoff-protocol-retry-execution/v1",
        "executionCommit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "planSha256": auth["planSha256"],
        "driverSha256": digest(Path(__file__)),
        "authorizationSha256": digest(HERE / "authorization.json"),
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "runtime": runtime,
        "reservedRequests": 0,
        "knownHttpRequests": 0,
        "protocolRetries": 0,
        "stopReason": None,
        "jobs": [
            {k: j[k] for k in ("jobId", "taskId", "controlId", "language", "arm")}
            | {"status": "not-executed", "attemptIds": []}
            for j in plan["jobs"]
        ],
        "attempts": [],
    }
    started = time.monotonic()
    returned_model = None

    def checkpoint():
        temp = OUTPUT / "execution.tmp"
        temp.write_text(
            json.dumps(index, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
        temp.replace(OUTPUT / "execution.json")

    checkpoint()
    for job, final in zip(plan["jobs"], index["jobs"]):
        for ordinal in (1, 2):
            attempt_id = f"{job['jobId']}-A{ordinal}"
            attempt = {
                "attemptId": attempt_id,
                "jobId": job["jobId"],
                "ordinal": ordinal,
                "status": "not-dispatched",
            }
            retryable = False
            try:
                check_inputs()
                remaining = 300 - (time.monotonic() - started)
                require(remaining > 0 and index["reservedRequests"] < 8, "Series cap")
                if ordinal == 2:
                    require(index["protocolRetries"] < 2, "Retry cap")
                    index["protocolRetries"] += 1
                index["attempts"].append(attempt)
                final["attemptIds"].append(attempt_id)
                final["status"] = "in-progress"
                attempt["status"] = "reserved"
                index["reservedRequests"] += 1
                checkpoint()
                child = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        *job["argv"],
                        "--live",
                        "--output",
                        str(OUTPUT / attempt_id),
                    ],
                    cwd=ROOT,
                    env={
                        "COREINFRA_API_KEY": os.environ["COREINFRA_API_KEY"],
                        "PYTHONDONTWRITEBYTECODE": "1",
                    },
                    capture_output=True,
                    timeout=remaining,
                )
                path = OUTPUT / attempt_id / "report.json"
                require(path.is_file(), "Missing report")
                report = read(path)
                attempt.update(
                    reportPath=f"{attempt_id}/report.json", reportSha256=digest(path)
                )
                require(
                    type(report["calls"]) is int and 0 <= report["calls"] <= 1,
                    "Per-child cap",
                )
                attempt["knownHttpRequests"] = report["calls"]
                index["knownHttpRequests"] += report["calls"]
                require(
                    report["calls"] == len(report["requests"]) == 1,
                    "Expected one request",
                )
                row = inputs[job["taskId"]]
                task = read(ROOT / row["task"]["path"])
                config = read(ROOT / plan["configs"][job["arm"]]["path"])
                wire = report["requests"][0]
                require(
                    wire["endpoint"] == config["endpoint_url"]
                    and wire["body"]
                    == {
                        "model": config["model"],
                        "state": task["state"],
                        "questions": task["questions"],
                    },
                    "Wire drift",
                )
                require(
                    report["semanticTaskDigest"] == row["semanticTaskDigest"]
                    and report["policy"] == policy,
                    "Task/policy drift",
                )
                item = report["records"]["overall"]
                attempt.update(
                    status=item["status"],
                    httpStatus=wire.get("httpStatus"),
                    error=item["error"],
                    semanticWireMatched=True,
                )
                if item["status"] == "completed":
                    require(
                        child.returncode == 0 and wire.get("httpStatus") == 200,
                        "Completion mismatch",
                    )
                    result = item["result"]
                    require(
                        result["decision"]["outcome"]
                        == policy["questions"]["overall"][result["answers"]["overall"]],
                        "Policy projection drift",
                    )
                    model = result["returned_model"]
                    require(
                        model is not None
                        and (returned_model is None or model == returned_model),
                        "Model drift",
                    )
                    returned_model = model
                    attempt["result"] = result
                    final.update(status="completed", finalAttemptId=attempt_id)
                else:
                    retryable = (
                        child.returncode == 3
                        and item["status"] == "failed"
                        and wire.get("httpStatus") == 200
                        and item["error"]
                        == {"category": "JevProtocolError", "httpStatus": None}
                    )
                    attempt["retryEligibleProtocolFailure"] = retryable
                    final["status"] = "failed"
                    if not (
                        retryable and ordinal == 1 and index["protocolRetries"] < 2
                    ):
                        index["stopReason"] = (
                            "nonretryable-error-or-retry-budget-exhausted"
                        )
            except subprocess.TimeoutExpired:
                attempt["status"] = final["status"] = "unknown"
                index["stopReason"] = "outer-deadline-unknown-outcome"
            except Exception as exc:
                attempt["status"] = final["status"] = "failed"
                attempt["errorCategory"] = type(exc).__name__
                index["stopReason"] = "operational-error-or-drift"
            checkpoint()
            print(
                attempt_id,
                job["taskId"],
                attempt["status"],
                attempt.get("result", {}).get("answers", {}).get("overall"),
                flush=True,
            )
            if final["status"] == "completed" or index["stopReason"] is not None:
                break
            require(retryable and ordinal == 1, "Unexpected continuation")
        if index["stopReason"] is not None:
            break
    index["finishedAt"] = datetime.now(timezone.utc).isoformat()
    index["elapsedSeconds"] = round(time.monotonic() - started, 6)
    index["completedJobs"] = sum(j["status"] == "completed" for j in index["jobs"])
    checkpoint()
    print(
        "Finished",
        index["completedJobs"],
        "/6; attempts",
        index["reservedRequests"],
        "; protocol retries",
        index["protocolRetries"],
        flush=True,
    )
    return 0 if index["completedJobs"] == 6 else 3


if __name__ == "__main__":
    raise SystemExit(main())
