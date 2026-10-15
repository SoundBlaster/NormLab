"""Stage1 scheduler faults use synthetic Linux time and fake HTTP; no paid calls."""

import copy
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import test_offline_stage1_native_plan as plan_fixtures
from execution_live_gate import current_gate
from execution_live_kernel import checkpoint as make_checkpoint
from execution_live_kernel import inspect_live
from execution_live_scheduler import MODE, run_schedule
from execution_live_wire import projection
from execution_plan import Store
from execution_stage1_bind import bind_stage1
from execution_stage1_plan import compile_stage1
from execution_test_support import ROOT, ExecutionCase, canonical
from offline_bundle import sha
from test_offline_runtime_mlflow_cli import GUARD


class FakeClock:
    def __init__(self):
        self.now = 1_000_000_000
        self.change = None

    def sample(self):
        self.now += 1_000_000
        value = {
            "policy": "same-host-boot-suspend-aware/v1",
            "source": "linux:CLOCK_BOOTTIME",
            "units": "nanoseconds",
            "suspendAware": True,
            "epoch": "e" * 64,
            "clockNs": self.now,
            "observedAt": (
                datetime(2026, 1, 1, tzinfo=timezone.utc)
                + timedelta(microseconds=self.now // 1000)
            ).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }
        if self.change:
            self.change(value)
        return value

    def sleep(self, seconds):
        self.now += int(seconds * 1_000_000_000)


class LiveScheduleTests(ExecutionCase):
    def prepared(self, *, dispatches=None, models=None, expires=None):
        compiled = self.root / "compiled"
        settings = plan_fixtures.options()
        if models:
            settings["acceptedModels"].update(models)
        compile_stage1(plan_fixtures.MANIFEST, compiled, settings)
        plan = Store(compiled).json("plan.json")
        authorization = {
            "schema": "normlab.stage1-native-authorization/v1",
            "planDigest": sha(canonical(plan)),
            "caps": dict(plan["caps"]),
            "expiresAt": "2026-01-02T00:00:00.000000Z",
            "authorization": {
                "operatorId": "synthetic-operator",
                "authorizationRef": "a" * 64,
                "authorizedAt": "2026-01-01T00:00:00.000000Z",
            },
            "externalSpending": {
                "currency": "USD",
                "ceilingMicros": 1000,
                "confirmationRef": "b" * 64,
                "provenance": "operator-asserted",
            },
        }
        if dispatches is not None:
            authorization["caps"]["dispatches"] = dispatches
        if expires is not None:
            authorization["expiresAt"] = expires
        clock = FakeClock()
        folder = self.root / "input"
        with patch("execution_live_kernel.LinuxClock", return_value=clock):
            bound = bind_stage1(compiled, folder, authorization)
        return folder, bound["confirmation"], clock

    def execute(self, folder, confirmation, clock, *, customize=None, hook=None):
        output = self.root / "output"
        calls, timeouts = [], []
        test = self

        class Transport:
            def dispatch(self, raw, secret, check):
                timeouts.append(check())
                checkpoint = json.loads((output / "checkpoint.json").read_bytes())
                test.assertEqual(checkpoint["journal"][-1]["type"], "attempt-reserved")
                test.assertEqual(
                    checkpoint["run"]["counts"]["reserved"]["dispatches"],
                    len(calls) + 1,
                )
                request = Store.decode_json(raw)
                calls.append(request)
                common = {
                    "model": request["body"]["model"],
                    "id": "synthetic-response",
                    "usage": {"input_tokens": 100, "output_tokens": 20},
                }
                distribution = {
                    "compatible": 1.0,
                    "incompatible": 0.0,
                    "indeterminate": 0.0,
                }
                answer = {
                    "type": "choice",
                    "choice": "compatible",
                    "confidence": 1.0,
                    "probabilities": distribution,
                }
                if request["url"].endswith("systemone"):
                    body = {**common, "answers": {"classification": answer}}
                elif request["url"].endswith("decisions"):
                    body = {
                        **common,
                        "answers": [
                            {
                                **answer,
                                "name": "classification",
                                "probabilities": [
                                    {"value": k, "probability": v}
                                    for k, v in distribution.items()
                                ],
                            }
                        ],
                    }
                else:
                    body = {
                        **common,
                        "status": "completed",
                        "output": [
                            {
                                "type": "message",
                                "status": "completed",
                                "content": [
                                    {
                                        "type": "output_text",
                                        "text": '{"overall":"compatible"}',
                                    }
                                ],
                            }
                        ],
                    }
                status = 200
                if customize:
                    changed = customize(body, request, len(calls))
                    if isinstance(changed, dict):
                        return changed
                    if changed is not None:
                        status = changed
                return {
                    "response": projection(
                        status, canonical(body), "fixture-id", secret
                    ),
                    "errorClass": None,
                }

        self.calls, self.timeouts = calls, timeouts
        with (
            patch("execution_live_kernel.LinuxClock", return_value=clock),
            patch("execution_live_kernel.NativeHTTP", Transport),
            patch(
                "execution_live_authority.AUTHORITY_ROOT",
                self.root.resolve() / "authority",
            ),
            patch("execution_live_scheduler.time.sleep", side_effect=clock.sleep),
            patch(
                "socket.create_connection", side_effect=AssertionError("network denied")
            ),
            patch.dict(
                os.environ,
                {"COREINFRA_API_KEY": "offline-only-placeholder"},
                clear=True,
            ),
        ):
            return run_schedule(folder, output, confirmation, hook=hook)

    def test_full_schedule_preserves_36_tasks_and_read_only_inspection(self):
        folder, confirmation, clock = self.prepared()
        report = self.execute(folder, confirmation, clock)
        self.assertEqual(report["stopReason"], "complete")
        self.assertEqual(len(self.calls), 36)
        self.assertEqual(report["dispatchAttemptsInvoked"], 36)
        self.assertEqual(report["inferenceCallsExecuted"], 36)
        self.assertEqual(report["counts"]["knownInputTokens"], 3600)
        self.assertTrue(all(len(t["attemptIds"]) == 1 for t in report["taskOutcomes"]))
        saved = inspect_live(self.root / "output")
        self.assertEqual(saved["dispatchAttemptsInvoked"], 0)
        self.assertEqual(saved["inferenceCallsExecuted"], 0)
        self.assertFalse(saved["nativeBoundary"]["resumeSupported"])
        self.assertFalse(saved["semanticQualityEvidence"])
        for task, request in zip(Store(folder).json("plan.json")["tasks"], self.calls):
            self.assertEqual(Store(folder).value(task["request"]), request)

    def test_retry_same_turn_consumes_original_caps_and_retains_unknown_usage(self):
        folder, confirmation, clock = self.prepared(dispatches=3)

        def transient(body, request, count):
            if count == 1:
                return {"response": None, "errorClass": "ReadTimeout"}

        report = self.execute(folder, confirmation, clock, customize=transient)
        self.assertEqual(report["stopReason"], "budget-exhaustion")
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 3)
        self.assertEqual(len(report["taskOutcomes"][0]["attemptIds"]), 2)
        self.assertEqual(
            report["taskOutcomes"][0]["first"]["status"], "transport-failed"
        )
        self.assertEqual(report["taskOutcomes"][0]["final"]["status"], "completed")
        self.assertIsNone(report["inferenceCallsExecuted"])
        self.assertEqual(report["unknownDispatchAttempts"], 1)
        self.assertEqual(report["taskOutcomes"][2]["attemptIds"], [])
        journal = json.loads((self.root / "output/checkpoint.json").read_bytes())[
            "journal"
        ]
        reservations = [e for e in journal if e["type"] == "attempt-reserved"]
        self.assertEqual(reservations[0]["turnId"], reservations[1]["turnId"])
        self.assertGreaterEqual(
            reservations[1]["clockNs"] - journal[1]["clockNs"], 1_000_000_000
        )

    def test_retry_exhaustion_and_terminal_failures_stop_suffix(self):
        for kind, expected_calls in (
            ("ReadTimeout", 3),
            ("SSLCertVerificationError", 1),
            ("http", 1),
            ("output", 1),
        ):
            with self.subTest(kind=kind):
                # Fresh independent fixture/output/authority for each failure.
                with self.subfolder(kind):
                    folder, confirmation, clock = self.prepared()

                    def failure(body, request, count):
                        if kind == "http":
                            return 503
                        if kind == "output":
                            body.pop("answers")
                            return None
                        return {"response": None, "errorClass": kind}

                    report = self.execute(
                        folder, confirmation, clock, customize=failure
                    )
                    self.assertEqual(len(self.calls), expected_calls)
                    self.assertEqual(report["stopReason"], "terminal-failure")
                    self.assertEqual(report["taskOutcomes"][1]["attemptIds"], [])

    def subfolder(self, name):
        from contextlib import contextmanager

        @contextmanager
        def folder():
            original = self.root
            self.root = original / name
            self.root.mkdir()
            try:
                yield
            finally:
                self.root = original

        return folder()

    def test_crash_unknown_reservation_cannot_continue_or_reuse_uuid(self):
        for phase in ("after-reservation", "after-dispatch", "after-response"):
            with self.subfolder(phase):
                folder, confirmation, clock = self.prepared()

                def crash(point):
                    if point == phase:
                        raise KeyboardInterrupt("synthetic crash")

                with self.assertRaises(KeyboardInterrupt):
                    self.execute(folder, confirmation, clock, hook=crash)
                report = inspect_live(self.root / "output")
                self.assertEqual(len(report["unknownAttemptIds"]), 1)
                self.assertEqual(report["taskOutcomes"][1]["attemptIds"], [])
                with self.assertRaises(FileExistsError):
                    self.execute(folder, confirmation, clock)

    def test_usage_excess_and_accepted_model_drift_stop_schedule(self):
        for kind in ("usage", "model"):
            with self.subfolder(kind):
                folder, confirmation, clock = self.prepared(
                    models={"jev-coreinfra": ["jev-1.13.0", "jev-next"]}
                )
                seen = []

                def change(body, request, count):
                    if kind == "usage":
                        body["usage"]["input_tokens"] = 20001
                    elif request["url"].endswith("systemone"):
                        seen.append(1)
                        if len(seen) > 1:
                            body["model"] = "jev-next"

                report = self.execute(folder, confirmation, clock, customize=change)
                self.assertEqual(
                    report["stopReason"],
                    "usage-ceiling-exceeded" if kind == "usage" else "terminal-failure",
                )
                self.assertLess(len(self.calls), 36)
                if kind == "model":
                    outcomes = [
                        t["final"] for t in report["taskOutcomes"] if t["final"]
                    ]
                    self.assertEqual(outcomes[-1]["status"], "model-rejected")

    def test_expiry_after_known_terminal_and_during_inflight(self):
        for inflight in (False, True):
            with self.subfolder(str(inflight)):
                folder, confirmation, clock = self.prepared()
                intent = Store(folder).json("run.json")

                def expire(point):
                    if point == ("before-dispatch" if inflight else "after-terminal"):
                        clock.now = intent["clock"]["deadlineNs"]

                if inflight:
                    with self.assertRaises(ValueError):
                        self.execute(folder, confirmation, clock, hook=expire)
                    self.assertEqual(
                        len(inspect_live(self.root / "output")["unknownAttemptIds"]), 1
                    )
                else:
                    report = self.execute(folder, confirmation, clock, hook=expire)
                    self.assertEqual(report["stopReason"], "deadline")
                    self.assertEqual(len(self.calls), 1)

    def test_cli_verify_and_inspect_are_sdk_free(self):
        folder, confirmation, clock = self.prepared(dispatches=1)
        self.execute(folder, confirmation, clock)
        for command, path in (
            ("verify-stage1", folder),
            ("inspect", self.root / "output"),
        ):
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-S",
                    "-c",
                    GUARD,
                    str(ROOT / "evaluation/execution_live_cli.py"),
                    command,
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env={"PATH": os.defpath},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["inferenceCallsExecuted"], 0)

    def test_task_gate_uses_selected_arm_caps_and_timeout(self):
        fixture = self.fixture(mock=False)
        second = copy.deepcopy(fixture.plan["arms"][0])
        second.update(id="arm-b", timeoutNs=7_000_000_000)
        second["requestCaps"]["inputTokens"] = 200
        fixture.plan["arms"].append(second)
        fixture.plan["tasks"][1]["armId"] = second["id"]
        fixture.plan["caps"]["inputTokens"] = 150
        fixture.bind_plan()
        fixture.save()
        confirmation = {
            "runId": fixture.run["id"],
            "planDigest": fixture.run["planDigest"],
            "permitDigest": fixture.run["permit"]["sha256"],
            "invocationId": fixture.run["initialInvocationId"],
            "externalCeilingMicros": fixture.permit["externalSpending"][
                "ceilingMicros"
            ],
        }
        sample = {
            k: fixture.run["clock"][k]
            for k in ("policy", "source", "units", "suspendAware", "epoch")
        }
        sample.update(
            clockNs=fixture.run["clock"]["startNs"],
            observedAt="2026-01-01T00:00:00.000000Z",
        )
        with self.assertRaises(ValueError):
            current_gate(
                fixture.plan,
                fixture.run,
                Store(fixture.folder),
                confirmation,
                sample,
                task_index=1,
            )
        post = current_gate(
            fixture.plan,
            fixture.run,
            Store(fixture.folder),
            confirmation,
            sample,
            task_index=1,
            reserve=False,
            last_sample=sample,
        )
        self.assertEqual(post["timeoutNs"], second["timeoutNs"])

    def test_attempt_timeout_and_utc_rollback_leave_unknown(self):
        for kind in ("attempt-timeout", "utc-rollback"):
            with self.subfolder(kind):
                folder, confirmation, clock = self.prepared()

                def stop(point):
                    if point == "before-dispatch":
                        if kind == "attempt-timeout":
                            clock.now += 31_000_000_000
                        else:
                            clock.change = lambda value: value.update(
                                observedAt="2026-01-01T00:00:00.000000Z"
                            )

                with self.assertRaises(ValueError):
                    self.execute(folder, confirmation, clock, hook=stop)
                self.assertEqual(
                    len(inspect_live(self.root / "output")["unknownAttemptIds"]), 1
                )

    def test_permit_expiry_after_known_result_stops_before_next_reservation(self):
        folder, confirmation, clock = self.prepared(
            expires="2026-01-01T00:00:05.000000Z"
        )

        def expire(point):
            if point == "after-terminal":
                clock.now = 5_000_000_000

        report = self.execute(folder, confirmation, clock, hook=expire)
        self.assertEqual(report["stopReason"], "operator-stop")
        self.assertEqual(len(self.calls), 1)

    def test_rehashed_normalized_result_and_mode_downgrade_reject(self):
        folder, confirmation, clock = self.prepared(dispatches=2)
        self.execute(folder, confirmation, clock)
        root = self.root / "output"
        path = root / "checkpoint.json"
        original = path.read_bytes()
        saved = Store.decode_json(original)
        changed = copy.deepcopy(saved)
        changed.pop("mode")
        changed["schema"] = "normlab.live-checkpoint/v1"
        path.write_bytes(canonical(changed))
        with self.assertRaises(ValueError):
            inspect_live(root)
        path.write_bytes(original)
        store = Store(root)
        terminal = saved["journal"][1]
        outcome = store.value(terminal["outcome"])
        result = store.value(outcome["result"])
        result["answers"][0]["value"] = "incompatible"

        def put(value):
            raw = canonical(value)
            ref = {
                "path": f"artifacts/{sha(raw)}.blob",
                "sha256": sha(raw),
                "bytes": len(raw),
            }
            (root / ref["path"]).write_bytes(raw)
            return ref

        outcome["result"] = put(result)
        terminal["outcome"] = put(outcome)
        previous = None
        for event in saved["journal"]:
            event["previousDigest"] = previous
            event["id"] = sha(canonical({k: v for k, v in event.items() if k != "id"}))
            previous = event["id"]
        intent = Store.decode_json((root / "intent.json").read_bytes())
        # The structural replay accepts this fully rehashed view; native regeneration must not.
        altered = make_checkpoint(intent, saved["journal"], Store(root), mode=MODE)
        path.write_bytes(canonical(altered))
        with self.assertRaisesRegex(ValueError, "normalization"):
            inspect_live(root)

    def test_compile_cli_is_sdk_free_without_intent_or_authority(self):
        options = self.root / "options.json"
        options.write_bytes(canonical(plan_fixtures.options()))
        compiled = self.root / "cli-compiled"
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-S",
                "-c",
                GUARD,
                str(ROOT / "evaluation/execution_live_cli.py"),
                "compile-stage1",
                str(plan_fixtures.MANIFEST),
                str(compiled),
                "--options",
                str(options),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env={"PATH": os.defpath},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["authorizedDispatches"], 0)
        self.assertFalse((compiled / "run.json").exists())


if __name__ == "__main__":
    unittest.main()
