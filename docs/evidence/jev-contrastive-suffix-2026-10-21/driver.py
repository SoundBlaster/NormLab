"""One-off authorized Jev comparison with bounded network retries; not a production provider adapter."""

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
    raise ValueError("Non-finite JSON number")


def main():
    if not __debug__:
        raise RuntimeError(
            "Optimized Python is not permitted for this frozen diagnostic"
        )
    plan_path = ROOT / "fixtures/providers/jev-contrastive-suffix-v1/plan.json"
    plan_raw = plan_path.read_bytes()
    plan = json.loads(plan_raw)
    assert (
        plan["status"] == "authorized-frozen"
        and plan["authorization"]["authorizedAttempts"] == 8
    )
    assert digest(Path(__file__).read_bytes()) == plan["driverSha256"]
    assert plan["endpoint"] == "https://hub.coreinfra.ai/typesafe/api/v1/systemone"
    assert plan["model"] == "jev-1.13.0" and plan["proposedCaps"]["retries"] == 2
    assert len(plan["tasks"]) == len(plan["order"]) == len(set(plan["order"])) == 6
    assert plan["authorization"]["status"] == "authorized"
    assert plan["proposedCaps"]["maxHttpAttempts"] == 8
    assert plan["proposedCaps"]["perRequestDeadlineSeconds"] == 30
    assert plan["proposedCaps"]["seriesDeadlineSeconds"] == 360
    for binding in plan["bindings"]:
        assert digest((ROOT / binding["path"]).read_bytes()) == binding["sha256"]
    refs_raw = (ROOT / plan["references"]["path"]).read_bytes()
    assert digest(refs_raw) == plan["references"]["sha256"]
    references = {
        item["id"]: item["expectedAnswer"]
        for item in json.loads(refs_raw)["records"]
        if item["id"] in plan["order"]
    }
    tasks = {}
    for task in plan["tasks"]:
        raw = (ROOT / task["taskPath"]).read_bytes()
        assert digest(raw) == task["taskSha256"]
        data = json.loads(raw)
        assert set(data) == {"state", "questions"}
        assert set(data["questions"]) == {"overall"}
        tasks[task["id"]] = (task, data)
    assert (
        digest((ROOT / plan["references"]["path"]).read_bytes())
        == plan["references"]["sha256"]
    )
    prior = json.loads((ROOT / plan["continuation"]["priorCapturePath"]).read_bytes())
    assert prior["attempts"] == 8 and prior["retries"] == 2
    assert all(
        prior["records"][name]["status"] == "not-executed" for name in plan["order"]
    )
    assert len(tasks) == 6 and set(tasks) == set(plan["order"]) == set(references)
    assert subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT) == b"", (
        "Freeze a clean Git tree before dispatch"
    )
    output = Path(__file__).parent / "report.json"
    assert not output.exists(), "Never overwrite a previous execution"
    key = os.environ.get("COREINFRA_API_KEY", "")
    assert key and key == key.strip() and all(33 <= ord(c) <= 126 for c in key)
    report = {
        "schema": "normlab.jev-contrastive-suffix-capture/v1",
        "protocolCommit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "planSha256": digest(plan_raw),
        "pythonVersion": sys.version,
        "planned": 6,
        "attempts": 0,
        "retries": 0,
        "mode": "live-direct-http",
        "attemptLog": [],
        "records": {name: {"status": "not-executed"} for name in plan["order"]},
        "stoppingReason": None,
        "costUSD": None,
        "billingVerified": False,
    }

    def save():
        raw = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
        raw = raw.replace(key, "[redacted]")
        temporary = output.with_suffix(".tmp")
        temporary.write_text(raw + "\n")
        temporary.replace(output)

    save()
    started = time.monotonic()
    schedule = list(plan["order"])
    cursor = 0
    attempts_by_job = {}
    while cursor < len(schedule):
        name = schedule[cursor]
        cursor += 1
        assert report["attempts"] < 8
        remaining = 360 - (time.monotonic() - started)
        if remaining <= 0:
            report["stoppingReason"] = "series-deadline"
            break
        task, data = tasks[name]
        payload = {"model": plan["model"], **data}
        job_attempt = attempts_by_job.get(name, 0) + 1
        assert job_attempt <= 2
        if job_attempt > 1:
            report["retries"] += 1
            assert report["retries"] <= 2
        attempts_by_job[name] = job_attempt
        record = {
            "job": name,
            "jobAttempt": job_attempt,
            "sequence": report["attempts"] + 1,
            "status": "in-flight",
            "expectedAnswer": references[name],
            "request": payload,
            "requestSha256": digest(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ),
            "httpStatus": None,
            "response": None,
            "usage": None,
        }
        report["attemptLog"].append(record)
        report["records"][name] = record
        report["attempts"] += 1
        save()
        request = urllib.request.Request(
            plan["endpoint"],
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        call_started = time.monotonic()
        try:
            with total_deadline(min(30, remaining)):
                opener = urllib.request.build_opener(
                    NoRedirect(), urllib.request.ProxyHandler({})
                )
                with opener.open(request, timeout=min(30, remaining)) as response:
                    record["httpStatus"] = response.status
                    assert response.status == 200, "expected HTTP200"
                    record["providerRequestId"] = response.headers.get(
                        "x-typesafe-request-id"
                    ) or response.headers.get("x-request-id")
                    raw = response.read(1048577)
                assert len(raw) <= 1048576, "response cap"
                document = json.loads(raw, parse_constant=reject_constant)
                record["response"] = document
                assert document["model"] == "jev-1.13.0", "returned model drift"
                assert set(document["answers"]) == {"overall"}
                answer = document["answers"]["overall"]
                probabilities = answer["probabilities"]
                assert answer["type"] == "choice"
                assert set(probabilities) == set(
                    data["questions"]["overall"]["criteria"]
                )
                assert all(
                    type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1
                    for p in probabilities.values()
                )
                assert abs(sum(probabilities.values()) - 1) <= 0.001
                assert answer["choice"] in probabilities
                assert (
                    probabilities[answer["choice"]]
                    >= max(probabilities.values()) - 1e-6
                )
                confidence = answer["confidence"]
                assert type(confidence) in (int, float) and 0 <= confidence <= 1
                usage = document["usage"]
                assert all(
                    type(usage.get(k)) is int and usage[k] >= 0
                    for k in ("input_tokens", "output_tokens")
                )
                record.update(
                    status="completed",
                    usage=usage,
                    label=answer["choice"],
                    confidence=confidence,
                    selectedProbability=probabilities[answer["choice"]],
                    candidateMatches=answer["choice"] == references[name],
                )
        except urllib.error.HTTPError as error:
            record.update(status="http-failed", httpStatus=error.code)
            error.close()
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            record.update(
                status="unknown",
                error="Network/TLS/timeout failure",
                errorType=type(error).__name__,
                reasonType=type(getattr(error, "reason", error)).__name__,
            )
        except (ValueError, TypeError, KeyError, AssertionError):
            record.update(
                status="protocol-failed", error="Fixed protocol/model check failed"
            )
        record["elapsedSeconds"] = round(time.monotonic() - call_started, 3)
        report["elapsedSeconds"] = round(time.monotonic() - started, 3)
        retry_scheduled = (
            record["status"] == "unknown"
            and job_attempt == 1
            and report["retries"] < 2
            and report["attempts"] < 8
            and time.monotonic() - started < 359
        )
        record["retryScheduled"] = retry_scheduled
        if retry_scheduled:
            schedule.insert(cursor, name)
        elif record["status"] not in ("completed", "unknown"):
            report["stoppingReason"] = name + ":" + record["status"]
        save()
        print(
            json.dumps(
                {
                    "job": name,
                    **{
                        k: record.get(k)
                        for k in (
                            "status",
                            "jobAttempt",
                            "retryScheduled",
                            "errorType",
                            "reasonType",
                            "label",
                            "candidateMatches",
                            "confidence",
                            "elapsedSeconds",
                        )
                    },
                }
            ),
            flush=True,
        )
        if report["stoppingReason"]:
            break
        if retry_scheduled:
            time.sleep(1)
    report["elapsedSeconds"] = round(time.monotonic() - started, 3)
    save()
    print("Finished; actual attempts:", report["attempts"], flush=True)


if __name__ == "__main__":
    main()
