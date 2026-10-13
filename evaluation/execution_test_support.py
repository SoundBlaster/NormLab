"""Independent synthetic record construction and guarded CLI checks, tests only."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evaluation/execution_contract_cli.py"
NANO = 1_000_000_000
GUARD = r"""
import os, runpy, sys
from pathlib import Path
planning = sys.argv[2] in {'plan', 'dry-run'}
def guard(event, args):
    if event.startswith('socket.') or event == 'subprocess.Popen':
        raise AssertionError('Offline network/process guard active')
    if event == 'import' and args[0].split('.')[0] in {
        'openai', 'mellea', 'jev', 'mellea_jev_adapter', 'typesafe', 'anthropic',
        'requests', 'httpx', 'httpx2', 'urllib3', 'aiohttp', 'ollama', 'langextract'
    }:
        raise AssertionError('Offline SDK guard active')
    if event == 'open':
        path, mode, flags = args
        if isinstance(path, (str, bytes)):
            name = Path(os.fsdecode(path)).name
            if name == 'reviewer-only.json':
                raise AssertionError('Offline label-read guard active')
            if planning and name in {'run.json', 'journal.json', 'resolution.json'}:
                raise AssertionError('Planning cannot read execution/authorization records')
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        ):
            raise AssertionError('Offline write guard active')
    if event in {'os.mkdir', 'os.remove', 'os.rename', 'os.rmdir', 'os.symlink', 'os.truncate'}:
        raise AssertionError('Offline write guard active')
sys.addaudithook(guard)
script = Path(sys.argv[1]).resolve()
sys.argv = sys.argv[1:]
sys.path.insert(0, str(script.parent))
runpy.run_path(str(script), run_name='__main__')
"""


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(kind, value):
    return kind + "-" + sha(canonical(value))


def cli(command, folder, *, script=SCRIPT):
    return subprocess.run(
        [sys.executable, "-B", "-S", "-c", GUARD, str(script), command, str(folder)],
        cwd=folder,
        env={"PATH": os.defpath, "PYTHONNOUSERSITE": "1"},
        capture_output=True,
        text=True,
        timeout=20,
    )


def zero():
    return {
        key: 0 for key in ("dispatches", "questions", "inputTokens", "outputTokens")
    }


class Records:
    """Build expected counters/identities without calling production validators."""

    def __init__(
        self, folder, *, mock=False, protocol="typesafe-systemone/v1", tasks=2
    ):
        self.folder = folder
        (folder / "artifacts").mkdir(parents=True)
        self.plan = {
            "schema": "normlab.execution-plan/v1",
            **{
                key: {"id": key, "revision": "synthetic-v1", "sha256": "a" * 64}
                for key in ("experiment", "dataset", "strategy", "tactic")
            },
            "pins": {
                "definitions": self.put({"synthetic": True}),
                "prompt": self.put("Synthetic verifier instructions"),
                "outputSchema": self.put(
                    {
                        "schema": "normlab.execution-answer-schema/v1",
                        "questions": [
                            {"id": "supported", "type": "noul", "labels": []},
                            {
                                "id": "team",
                                "type": "choice",
                                "labels": ["billing", "legal"],
                            },
                            {
                                "id": "urgency",
                                "type": "score",
                                "labels": ["later", "week", "now"],
                            },
                        ],
                    }
                ),
                "code": {"synthetic-reader": "b" * 64},
                "dependencies": {"synthetic-runtime": "c" * 64},
            },
            "arms": [
                {
                    "id": "arm-a",
                    "provider": "synthetic-provider",
                    "protocol": protocol,
                    "endpoint": "https://example.invalid/inference",
                    "model": "mock-model",
                    "acceptedModels": ["mock-model", "other-model"],
                    "settings": {
                        "temperature": None,
                        "reasoningEffort": None,
                        "maxOutputTokens": 50,
                    },
                    "adapter": {
                        "id": "synthetic-normalizer",
                        "revision": "1",
                        "sha256": "d" * 64,
                    },
                    "requestCaps": {
                        "dispatches": 1,
                        "questions": 3,
                        "inputTokens": 100,
                        "outputTokens": 50,
                    },
                    "timeoutNs": NANO,
                }
            ],
            "tasks": [],
            "caps": {
                "dispatches": 10,
                "questions": 30,
                "inputTokens": 1000,
                "outputTokens": 500,
            },
            "wallTimeNs": 30 * NANO,
            "contextPolicy": "independent-public-request/v1",
            "retryPolicy": "stage1-transient-transport/v1",
            "clockPolicy": "same-host-boot-suspend-aware/v1",
        }
        for number in range(tasks):
            source = self.put(f"Я оплатил парковку. Учебный эпизод {number}.")
            candidate = self.put({"selectedClaim": "parking paid", "episode": number})
            body = {"model": "mock-model"}
            if protocol in {"typesafe-systemone/v1", "openai-decisions/v1"}:
                body.update(
                    state={
                        "source": self.value(source),
                        "candidate": self.value(candidate),
                    },
                    questions={
                        "supported": {
                            "type": "noul",
                            "instructions": "Was parking paid?",
                        },
                        "team": {
                            "type": "choice",
                            "instructions": "Select team",
                            "criteria": {"billing": "Payment", "legal": "Law"},
                        },
                        "urgency": {
                            "type": "score",
                            "instructions": "Select urgency",
                            "criteria": ["later", "week", "now"],
                        },
                    },
                )
            elif protocol == "openai-chat-completions/v1":
                body.update(
                    messages=[{"role": "user", "content": self.value(source)}],
                    max_completion_tokens=50,
                )
            else:
                body.update(input=self.value(source), max_output_tokens=50)
            request = self.put(
                {
                    "method": "POST",
                    "url": self.plan["arms"][0]["endpoint"],
                    "headers": {"Content-Type": "application/json"},
                    "body": body,
                },
                ordered=True,
            )
            question_ids = ["supported", "team", "urgency"]
            context = self.put(
                {
                    "policy": self.plan["contextPolicy"],
                    "sourceDigest": source["sha256"],
                    "candidateDigest": candidate["sha256"],
                    "requestDigest": request["sha256"],
                    "questionIds": question_ids,
                    "parentTurnIds": [],
                    "history": [],
                }
            )
            self.plan["tasks"].append(
                {
                    "key": f"task-{number}",
                    "caseId": f"case-{number}",
                    "armId": "arm-a",
                    "repeat": 0,
                    "stage": "verify",
                    "source": source,
                    "candidate": candidate,
                    "request": request,
                    "context": context,
                    "questionIds": question_ids,
                }
            )
        self.run = {
            "schema": "normlab.execution-run/v1",
            "id": "10000000-0000-4000-8000-000000000001",
            "initialInvocationId": "10000000-0000-4000-8000-000000000002",
            "identityKind": "runtime-allocated",
            "evidenceKind": "mock" if mock else "live-capture",
            "planDigest": None,
            "clock": {
                "policy": self.plan["clockPolicy"],
                "source": "linux:CLOCK_BOOTTIME",
                "units": "nanoseconds",
                "suspendAware": True,
                "epoch": "e" * 64,
                "startNs": NANO,
                "deadlineNs": 31 * NANO,
            },
            "tasks": [],
            "permit": None,
            "predecessor": None,
            "journalHead": None,
            "lastClockNs": NANO,
            "state": "created",
            "stopReason": None,
            "counts": {},
        }
        self.events = []
        self.permit = (
            None
            if mock
            else {
                "schema": "normlab.execution-permit/v1",
                "runId": self.run["id"],
                "planDigest": None,
                "scopeDigest": None,
                "caps": dict(self.plan["caps"]),
                "expiresAt": "2026-01-01T00:01:00.000000Z",
                "authorization": self.authorization(),
                "externalSpending": {
                    "currency": "USD",
                    "ceilingMicros": 100000,
                    "confirmationRef": "f" * 64,
                    "provenance": "operator-asserted",
                },
            }
        )
        self.bind_plan()

    @staticmethod
    def authorization():
        return {
            "operatorId": "synthetic-operator",
            "authorizationRef": "f" * 64,
            "authorizedAt": "2026-01-01T00:00:00.000000Z",
        }

    def put(self, value, *, ordered=False):
        raw = (
            json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
            if ordered
            else canonical(value)
        )
        ref = {
            "path": f"artifacts/{sha(raw)}.blob",
            "sha256": sha(raw),
            "bytes": len(raw),
        }
        (self.folder / ref["path"]).write_bytes(raw)
        return ref

    def value(self, ref):
        return json.loads((self.folder / ref["path"]).read_bytes())

    def bind_plan(self):
        old = {entry["taskId"]: index for index, entry in enumerate(self.run["tasks"])}
        self.run["planDigest"] = sha(canonical(self.plan))
        self.run["tasks"] = []
        for task in self.plan["tasks"]:
            task_id = identity("task", [self.run["id"], task])
            self.run["tasks"].append(
                {
                    "key": task["key"],
                    "taskId": task_id,
                    "turnId": identity("turn", [task_id, task["stage"], []]),
                }
            )
        for event in self.events:
            if event["taskId"] in old:
                index = old[event["taskId"]]
                ids = self.run["tasks"][index]
                event.update(
                    taskId=ids["taskId"],
                    turnId=ids["turnId"],
                    attemptId=identity("attempt", [ids["turnId"], event["ordinal"]]),
                    request=self.plan["tasks"][index]["request"],
                )
        if self.permit is not None:
            self.permit.update(
                planDigest=self.run["planDigest"],
                scopeDigest=sha(canonical(self.plan["arms"])),
            )
            self.run["permit"] = self.put(self.permit)

    def event(self, kind, task=0, ordinal=1, *, outcome=None, reason=None, clock=None):
        ids = self.run["tasks"][task]
        last = self.events[-1]["clockNs"] if self.events else NANO
        stop = kind == "run-stopped"
        event = {
            "schema": "normlab.execution-event/v1",
            "id": None,
            "runId": self.run["id"],
            "invocationId": self.run["initialInvocationId"],
            "sequence": len(self.events) + 1,
            "previousDigest": None,
            "type": kind,
            "taskId": None if stop else ids["taskId"],
            "turnId": None if stop else ids["turnId"],
            "attemptId": None
            if stop
            else identity("attempt", [ids["turnId"], ordinal]),
            "ordinal": None if stop else ordinal,
            "clockNs": last + 1_000_000 if clock is None else clock,
            "observedAt": f"2026-01-01T00:00:00.{len(self.events) + 1:06d}Z",
            "request": None if stop else self.plan["tasks"][task]["request"],
            "budgetDelta": zero(),
            "outcome": outcome,
            "stopReason": reason,
        }
        if kind == "attempt-reserved":
            event["budgetDelta"] = {
                "dispatches": 1,
                "questions": 3,
                "inputTokens": 100,
                "outputTokens": 50,
            }
        self.events.append(event)
        return event

    def outcome(
        self,
        status="completed",
        task=0,
        *,
        usage=None,
        observed=True,
        model="mock-model",
        backoff=None,
        errors=None,
    ):
        if self.run["evidenceKind"] == "mock":
            observed, usage = False, {"inputTokens": 0, "outputTokens": 0}
        if usage is None:
            usage = {"inputTokens": 17, "outputTokens": 5}
        response = (
            self.put({"syntheticResponse": True})
            if status
            in {
                "completed",
                "http-failed",
                "invalid-output",
                "refused",
                "model-rejected",
            }
            else None
        )
        result = None
        if status == "completed":
            result = self.put(
                {
                    "schema": "normlab.execution-answers/v1",
                    "normalizer": self.plan["arms"][0]["adapter"],
                    "answers": [
                        {"questionId": "supported", "type": "noul", "value": 0.92},
                        {"questionId": "team", "type": "choice", "value": "billing"},
                        {"questionId": "urgency", "type": "score", "value": 1.5},
                    ],
                }
            )
        return self.put(
            {
                "schema": "normlab.execution-outcome/v1",
                "status": status,
                "requestDigest": self.plan["tasks"][task]["request"]["sha256"],
                "contextDigest": self.plan["tasks"][task]["context"]["sha256"],
                "model": model,
                "providerRequestId": "synthetic-request",
                "dispatchObserved": observed,
                "usage": usage,
                "response": response,
                "result": result,
                "errorClasses": (errors or ["ReadTimeout"])
                if status == "transport-failed"
                else [],
                "backoffNs": backoff,
                "statusCode": 503 if status == "http-failed" else None,
            }
        )

    def completed(self, task=0, *, model="mock-model", usage=None):
        self.event("attempt-reserved", task)
        self.event(
            "attempt-terminal",
            task,
            outcome=self.outcome(task=task, model=model, usage=usage),
        )

    def change_outcome(self, index, change):
        value = self.value(self.events[index]["outcome"])
        change(value)
        self.events[index]["outcome"] = self.put(value)

    def save(self, *, renumber=False):
        head, active, stopped = None, None, None
        counts = {
            "reserved": zero(),
            "observedDispatches": 0,
            "knownInputTokens": 0,
            "knownOutputTokens": 0,
            "unknownUsageAttempts": 0,
        }
        attempts = {}
        for number, event in enumerate(self.events, 1):
            if renumber:
                event["sequence"] = number
            event["previousDigest"] = head
            event["id"] = sha(
                canonical({key: value for key, value in event.items() if key != "id"})
            )
            head = event["id"]
            if event["type"] == "attempt-reserved":
                active = event["attemptId"]
                attempts[active] = None
                for key, count in event["budgetDelta"].items():
                    counts["reserved"][key] += count
            elif event["type"] in {"attempt-observed", "attempt-terminal"}:
                attempts[event["attemptId"]] = self.value(event["outcome"])
                if event["type"] == "attempt-terminal":
                    active = None
            elif event["type"] == "run-stopped":
                stopped = event["stopReason"]
        for value in attempts.values():
            if value is None:
                counts["unknownUsageAttempts"] += 1
                continue
            counts["observedDispatches"] += value["dispatchObserved"] is True
            counts["unknownUsageAttempts"] += any(
                count is None for count in value["usage"].values()
            )
            for key, total in (
                ("inputTokens", "knownInputTokens"),
                ("outputTokens", "knownOutputTokens"),
            ):
                if value["usage"][key] is not None:
                    counts[total] += value["usage"][key]
        self.run.update(
            journalHead=head,
            lastClockNs=self.events[-1]["clockNs"] if self.events else NANO,
            state="finished"
            if stopped
            else "paused-unknown"
            if active
            else "running"
            if self.events
            else "created",
            stopReason=stopped or ("unknown-outcome" if active else None),
            counts=counts,
        )
        for name, value in (
            ("plan", self.plan),
            ("run", self.run),
            ("journal", self.events),
        ):
            (self.folder / f"{name}.json").write_bytes(canonical(value))

    def resolution(self, action="stop"):
        value = {
            "schema": "normlab.execution-resolution/v1",
            "runId": self.run["id"],
            "planDigest": self.run["planDigest"],
            "journalHead": self.run["journalHead"],
            "attemptId": self.events[0]["attemptId"],
            "action": action,
            "evidence": [self.put({"savedResponse": "synthetic"})]
            if action == "adopt-saved-outcome"
            else [],
            "authorization": {
                **self.authorization(),
                "authorizedAt": "2026-01-01T00:00:01.000000Z",
            },
        }
        (self.folder / "resolution.json").write_bytes(canonical(value))
        return value


class ExecutionCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.serial = 0

    def fixture(self, **kwargs):
        self.serial += 1
        return Records(self.root / str(self.serial), **kwargs)

    def accepted(self, fixture, command="replay"):
        before = {
            p.relative_to(fixture.folder): sha(p.read_bytes())
            for p in fixture.folder.rglob("*")
            if p.is_file()
        }
        result = cli(command, fixture.folder)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        report = json.loads(result.stdout)
        self.assertEqual(report["authorizedDispatches"], 0)
        self.assertEqual(report["inferenceCallsExecuted"], 0)
        self.assertFalse(report["semanticQualityEvidence"])
        for key in (
            "runtimeClockVerified",
            "codePinsVerified",
            "providerWireValidated",
            "executionReady",
        ):
            self.assertIs(report[key], False)
        self.assertIsNone(report["actualCost"])
        self.assertTrue(report["missingCapabilities"])
        self.assertEqual(
            before,
            {
                p.relative_to(fixture.folder): sha(p.read_bytes())
                for p in fixture.folder.rglob("*")
                if p.is_file()
            },
        )
        return report

    def rejected(self, fixture, command="replay"):
        result = cli(command, fixture.folder)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        report = json.loads(result.stderr)
        self.assertEqual(report["status"], "rejected")
        self.assertNotEqual(report["errorType"], "AssertionError", result.stderr)
        self.assertEqual(report["authorizedDispatches"], 0)
        self.assertEqual(report["inferenceCallsExecuted"], 0)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn("DO_NOT_PRINT", result.stderr)
        self.assertNotIn(str(fixture.folder), result.stderr)

    def retry_fixture(self, *, exhausted=False):
        fixture = self.fixture(tasks=1)
        for ordinal in range(1, 4 if exhausted else 3):
            clock = (
                None
                if ordinal == 1
                else fixture.events[-1]["clockNs"] + (2 ** (ordinal - 2)) * NANO
            )
            fixture.event("attempt-reserved", ordinal=ordinal, clock=clock)
            final = ordinal == (3 if exhausted else 2)
            status = "transport-failed" if exhausted or not final else "completed"
            fixture.event(
                "attempt-terminal",
                ordinal=ordinal,
                outcome=fixture.outcome(
                    status, backoff=(2 ** (ordinal - 1)) * NANO if not final else None
                ),
            )
        fixture.event(
            "run-stopped", reason="terminal-failure" if exhausted else "complete"
        )
        fixture.save()
        return fixture
