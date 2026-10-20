"""One authorized series through the existing CLI; not a reusable executor."""

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
PACKET = ROOT / "fixtures/providers/bridge-semantic-probe-v1"
OUTPUT = Path(
    "/Volumes/TB5/Developer/Builds/GitHub/NormLab-s1-3-a092c0e9e6e405bd/"
    "python/probes/bridge-semantic-controls-2026-10-18"
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def wire_matches(body, task, arm):
    if arm == "coreinfra-jev":
        return body["state"] == task["state"] and body["questions"] == task["questions"]
    if arm == "coreinfra-decisions":
        question = body["questions"][0]
        expected = task["questions"]["overall"]
        return (
            json.loads(body["input"]) == task["state"]
            and len(body["questions"]) == 1
            and question["name"] == "overall"
            and question["type"] == "choice"
            and question["instructions"] == expected["instructions"]
            and [q["value"] for q in question["choices"]] == list(expected["criteria"])
            and {q["value"]: q.get("description") for q in question["choices"]}
            == expected["criteria"]
        )
    return (
        json.loads(body["input"]) == {"state": task["state"]}
        and json.loads(body["instructions"].split("\n", 1)[1])
        == {
            k: {f: v for f, v in q.items() if f != "type"}
            for k, q in task["questions"].items()
        }
        and body["text"]["format"]["schema"]["properties"]["answers"]["properties"][
            "overall"
        ]["enum"]
        == list(task["questions"]["overall"]["criteria"])
        and body["reasoning"] == {"effort": "low"}
        and body["max_output_tokens"] == 1024
        and body["store"] is False
        and body["stream"] is False
        and body["truncation"] == "disabled"
    )


def main():
    os.umask(0o077)
    authorization = read(HERE / "authorization.json")
    plan = read(PACKET / "plan.json")
    require(digest(PACKET / "plan.json") == authorization["planSha256"], "Plan drift")
    require(
        authorization["authorizedRequests"] == len(plan["jobs"]) == 12, "Call grant"
    )
    require(bool(os.environ.get("COREINFRA_API_KEY")), "Missing selected credential")
    subprocess.run(
        ["git", "diff", "--exit-code", plan["executableCommit"], "--", "evaluation"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    require(
        not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT),
        "Dirty source",
    )
    runtime = {
        k: importlib.metadata.version(k) for k in plan["runtime"] if k != "python"
    }
    runtime["python"] = sys.version.split()[0]
    require(runtime == plan["runtime"], "Runtime drift")
    refs = (
        plan["inputProvenance"]
        + [plan["policy"], plan["reviewerOnly"]]
        + list(plan["configs"].values())
        + [row["task"] for row in plan["inputs"]]
    )

    def check_inputs():
        require(
            digest(PACKET / "plan.json") == authorization["planSha256"], "Plan drift"
        )
        for ref in refs:
            require(digest(ROOT / ref["path"]) == ref["sha256"], "Artifact drift")

    check_inputs()
    OUTPUT.mkdir(mode=0o700, parents=True, exist_ok=False)
    inputs = {x["id"]: read(ROOT / x["task"]["path"]) for x in plan["inputs"]}
    policy = read(ROOT / plan["policy"]["path"])
    index = {
        "schema": "normlab.bridge-probe-execution/v1",
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "packetCommit": authorization["packetCommit"],
        "executionCommit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "planSha256": digest(PACKET / "plan.json"),
        "driverSha256": digest(Path(__file__)),
        "authorizationSha256": digest(HERE / "authorization.json"),
        "runtime": runtime,
        "reservedRequests": 0,
        "knownHttpRequests": 0,
        "stopReason": None,
        "records": [
            {
                "jobId": j["jobId"],
                "taskId": j["taskId"],
                "arm": j["arm"],
                "status": "not-executed",
            }
            for j in plan["jobs"]
        ],
    }
    started = time.monotonic()

    def checkpoint():
        temp = OUTPUT / "execution.tmp"
        temp.write_text(
            json.dumps(index, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
        temp.replace(OUTPUT / "execution.json")

    checkpoint()
    models = {}
    for job, record in zip(plan["jobs"], index["records"]):
        try:
            check_inputs()
            remaining = 420 - (time.monotonic() - started)
            require(
                remaining > 0 and index["reservedRequests"] < 12,
                "Series budget exhausted",
            )
            record["status"] = "reserved"
            index["reservedRequests"] += 1
            checkpoint()
            child_output = OUTPUT / job["jobId"]
            env = {
                "COREINFRA_API_KEY": os.environ["COREINFRA_API_KEY"],
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            child = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    *job["argv"],
                    "--live",
                    "--output",
                    str(child_output),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                timeout=remaining,
            )
            report_path = child_output / "report.json"
            require(report_path.is_file(), "Missing child report")
            report = read(report_path)
            record.update(
                reportPath=f"{job['jobId']}/report.json",
                reportSha256=digest(report_path),
            )
            require(
                type(report["calls"]) is int and 0 <= report["calls"] <= 1,
                "Per-child cap",
            )
            record["knownHttpRequests"] = report["calls"]
            index["knownHttpRequests"] += report["calls"]
            child_record = report["records"]["overall"]
            record["childStatus"] = child_record["status"]
            require(
                child.returncode == 0 and child_record["status"] == "completed",
                "Child operational failure",
            )
            require(
                report["calls"] == len(report["requests"]) == 1, "Expected one request"
            )
            require(
                report["schema"] == "normlab.categorical-evaluation-smoke/v1",
                "Report schema",
            )
            task = inputs[job["taskId"]]
            config = read(ROOT / plan["configs"][job["arm"]]["path"])
            request = report["requests"][0]
            require(
                request["httpStatus"] == 200
                and request["endpoint"] == config["endpoint_url"],
                "HTTP binding",
            )
            require(
                request["body"]["model"] == config["model"], "Requested model drift"
            )
            require(
                wire_matches(request["body"], task, job["arm"]), "Semantic wire drift"
            )
            row = next(r for r in plan["inputs"] if r["id"] == job["taskId"])
            require(
                report["semanticTaskDigest"] == row["semanticTaskDigest"]
                and report["policy"] == policy,
                "Task/policy drift",
            )
            result = child_record["result"]
            require(
                result["decision"]["outcome"]
                == policy["questions"]["overall"][result["answers"]["overall"]],
                "Policy projection drift",
            )
            record.update(status="completed", result=result, semanticWireMatched=True)
            model = result["returned_model"]
            if model is not None:
                require(
                    job["arm"] not in models or models[job["arm"]] == model,
                    "Returned model changed within arm",
                )
                models[job["arm"]] = model
            print(
                job["jobId"],
                job["taskId"],
                job["arm"],
                result["answers"]["overall"],
                result["decision"]["outcome"],
                flush=True,
            )
        except subprocess.TimeoutExpired:
            record["status"] = "unknown"
            index["stopReason"] = "outer-deadline-unknown-outcome"
        except Exception as exc:
            record["status"] = "failed"
            record["errorCategory"] = type(exc).__name__
            index["stopReason"] = "first-operational-error-or-drift"
        record["elapsedSeriesSeconds"] = round(time.monotonic() - started, 6)
        checkpoint()
        if index["stopReason"] is not None:
            print(job["jobId"], "STOP", record["status"], flush=True)
            break
    index["elapsedSeconds"] = round(time.monotonic() - started, 6)
    index["finishedAt"] = datetime.now(timezone.utc).isoformat()
    index["completed"] = sum(r["status"] == "completed" for r in index["records"])
    checkpoint()
    print(
        "Finished",
        index["completed"],
        "/12; reserved",
        index["reservedRequests"],
        "; known HTTP",
        index["knownHttpRequests"],
        flush=True,
    )
    return 0 if index["completed"] == 12 else 3


if __name__ == "__main__":
    raise SystemExit(main())
