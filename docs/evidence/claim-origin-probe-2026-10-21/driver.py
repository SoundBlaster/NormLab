"""One-off source-origin diagnostic; never accepts whole markup or changes runtime."""

import getpass
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from clairic_smoke import NoRedirect, total_deadline  # noqa: E402


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def reject_constant(value):
    raise ValueError("Non-finite JSON")


def main():
    if not __debug__:
        raise RuntimeError("Optimized Python is not permitted")
    plan_path = ROOT / "fixtures/providers/claim-origin-probe-v1/plan.json"
    plan_raw = plan_path.read_bytes()
    plan = json.loads(plan_raw)
    assert plan["status"] == "authorized-frozen"
    assert digest(Path(__file__).read_bytes()) == plan["driverSha256"]
    assert plan["caps"]["maxAttempts"] == 8
    assert plan["caps"]["maxNetworkRetries"] == 2
    assert plan["arms"]["jev"]["endpoint"] == "https://api.typesafe.ai/v1/systemone"
    assert plan["arms"]["jev"]["model"] == "jev-1.13.0"
    assert (
        plan["arms"]["ultra"]["endpoint"]
        == "https://api.liquid.ai/decisions/v1/systemone"
    )
    assert plan["arms"]["ultra"]["model"] == "d1-ultra"
    for binding in plan["bindings"]:
        assert digest((ROOT / binding["path"]).read_bytes()) == binding["sha256"]
    refs_raw = (ROOT / plan["references"]["path"]).read_bytes()
    assert digest(refs_raw) == plan["references"]["sha256"]
    refs = {r["id"]: r["expectedAnswer"] for r in json.loads(refs_raw)["records"]}
    tasks = {}
    for task in plan["tasks"]:
        raw = (ROOT / task["taskPath"]).read_bytes()
        assert digest(raw) == task["taskSha256"]
        data = json.loads(raw)
        assert set(data) == {"state", "questions"} and len(data["questions"]) == 1
        tasks[task["id"]] = data
    jobs = {job["job"]: job for job in plan["order"]}
    assert len(jobs) == len(plan["order"]) == 6 and set(tasks) == set(refs)
    assert subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT) == b""
    output = Path(__file__).parent / "report.json"
    assert not output.exists(), "Never overwrite an execution"
    keys = {"jev": os.environ.get("TYPESAFE_API_KEY", "")}
    assert keys["jev"] and keys["jev"] == keys["jev"].strip()
    keys["ultra"] = getpass.getpass("Liquid key (hidden): ")
    assert all(key and all(33 <= ord(c) <= 126 for c in key) for key in keys.values())
    report = {
        "schema": "normlab.claim-origin-capture/v1",
        "protocolCommit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "planSha256": digest(plan_raw),
        "plannedJobs": 6,
        "attempts": 0,
        "retries": 0,
        "attemptLog": [],
        "jobs": {id: {"status": "not-executed"} for id in jobs},
        "stoppingReason": None,
        "costUSD": None,
        "billingVerified": False,
    }

    def save():
        raw = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
        for key in keys.values():
            raw = raw.replace(key, "[redacted]")
        temporary = output.with_suffix(".tmp")
        temporary.write_text(raw + "\n")
        temporary.replace(output)

    save()
    started = time.monotonic()
    schedule = list(jobs)
    cursor = 0
    attempts_by_job = {}
    while cursor < len(schedule):
        remaining = 360 - (time.monotonic() - started)
        if remaining <= 0 or report["attempts"] >= 8:
            report["stoppingReason"] = "global-cap-or-deadline"
            break
        id = schedule[cursor]
        cursor += 1
        job = jobs[id]
        arm = plan["arms"][job["arm"]]
        task = tasks[job["task"]]
        qid = next(iter(task["questions"]))
        job_attempt = attempts_by_job.get(id, 0) + 1
        assert job_attempt <= 2
        if job_attempt > 1:
            report["retries"] += 1
            assert report["retries"] <= 2
        attempts_by_job[id] = job_attempt
        payload = {"model": arm["model"], **task}
        record = {
            **job,
            "jobAttempt": job_attempt,
            "sequence": report["attempts"] + 1,
            "status": "in-flight",
            "request": payload,
            "requestSha256": digest(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ),
            "expectedAnswer": refs[job["task"]],
            "httpStatus": None,
            "response": None,
            "usage": None,
        }
        report["attemptLog"].append(record)
        report["jobs"][id] = record
        report["attempts"] += 1
        save()
        call_started = time.monotonic()
        try:
            with total_deadline(min(30, remaining)):
                request = urllib.request.Request(
                    arm["endpoint"],
                    data=json.dumps(payload, ensure_ascii=False).encode(),
                    headers={
                        "Authorization": "Bearer " + keys[job["arm"]],
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                opener = urllib.request.build_opener(
                    NoRedirect(), urllib.request.ProxyHandler({})
                )
                with opener.open(request, timeout=min(30, remaining)) as response:
                    record["httpStatus"] = response.status
                    assert response.status == 200
                    record["requestId"] = response.headers.get(
                        "x-typesafe-request-id"
                    ) or response.headers.get("x-request-id")
                    raw = response.read(1048577)
                assert len(raw) <= 1048576
                document = json.loads(raw, parse_constant=reject_constant)
                record["response"] = document
                assert document["model"] == arm["model"] and set(
                    document["answers"]
                ) == {qid}
                answer = document["answers"][qid]
                probabilities = answer["probabilities"]
                assert answer["type"] == "choice" and set(probabilities) == set(
                    task["questions"][qid]["criteria"]
                )
                assert all(
                    type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1
                    for p in probabilities.values()
                )
                assert abs(sum(probabilities.values()) - 1) <= 0.001
                assert (
                    answer["choice"] in probabilities
                    and probabilities[answer["choice"]]
                    >= max(probabilities.values()) - 1e-6
                )
                confidence = answer["confidence"]
                assert (
                    type(confidence) in (int, float)
                    and math.isfinite(confidence)
                    and 0 <= confidence <= 1
                )
                usage = document["usage"]
                assert all(
                    type(usage[k]) is int and usage[k] >= 0
                    for k in ("input_tokens", "output_tokens")
                )
                record.update(
                    status="completed",
                    label=answer["choice"],
                    confidence=confidence,
                    selectedProbability=probabilities[answer["choice"]],
                    usage=usage,
                    candidateMatches=answer["choice"] == refs[job["task"]],
                )
        except urllib.error.HTTPError as error:
            record.update(status="http-failed", httpStatus=error.code)
            error.close()
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            record.update(
                status="unknown",
                errorType=type(error).__name__,
                reasonType=type(getattr(error, "reason", error)).__name__,
            )
        except (ValueError, TypeError, KeyError, AssertionError):
            record.update(status="protocol-failed")
        record["elapsedSeconds"] = round(time.monotonic() - call_started, 3)
        retry = (
            record["status"] == "unknown"
            and job_attempt == 1
            and report["retries"] < 2
            and report["attempts"] < 8
            and time.monotonic() - started < 359
        )
        record["retryScheduled"] = retry
        if retry:
            schedule.insert(cursor, id)
        elif record["status"] not in ("completed", "unknown"):
            report["stoppingReason"] = id + ":" + record["status"]
        report["elapsedSeconds"] = round(time.monotonic() - started, 3)
        save()
        print(
            json.dumps(
                {
                    k: record.get(k)
                    for k in (
                        "job",
                        "status",
                        "jobAttempt",
                        "label",
                        "candidateMatches",
                        "retryScheduled",
                        "errorType",
                        "reasonType",
                        "elapsedSeconds",
                    )
                }
            ),
            flush=True,
        )
        if report["stoppingReason"]:
            break
        if retry:
            time.sleep(1)
    report["elapsedSeconds"] = round(time.monotonic() - started, 3)
    save()
    print("Finished; actual attempts:", report["attempts"], flush=True)


if __name__ == "__main__":
    main()
