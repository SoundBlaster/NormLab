"""5b real local file/lock barriers and process interruption, no provider calls."""

import copy
import json
import os
import selectors
import subprocess
import sys
import unittest
from unittest.mock import patch

from execution_checkpoint import (
    DurableWriter,
    bounded_read,
    inspect_checkpoint,
    load_checkpoint,
    reader_lock,
)
from execution_mock import MockTransport, run_mock
from execution_test_support import NANO, ROOT, ExecutionCase, canonical, cli, sha

MOCK_CLI = ROOT / "evaluation/execution_mock_cli.py"
MOCK_GUARD = r"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
def guard(event, args):
    if event.startswith('socket.') or event == 'subprocess.Popen':
        raise AssertionError('No network or child process in mock executor')
    if event == 'import' and args[0].split('.')[0] in {
        'openai', 'mellea', 'jev', 'mellea_jev_adapter', 'typesafe', 'requests',
        'httpx', 'httpx2', 'urllib3', 'aiohttp', 'anthropic', 'langextract', 'ollama'
    }:
        raise AssertionError('No provider SDK in mock executor')
sys.addaudithook(guard)
"""
CHILD = (
    MOCK_GUARD
    + r"""
from execution_mock import run_mock, MockTransport
original = MockTransport.dispatch
def traced(self, request, attempt, spec):
    returned = original(self, request, attempt, spec)
    with open(Path(sys.argv[3]) / 'test-dispatch-trace', 'ab') as handle:
        handle.write((attempt + '\n').encode())
        handle.flush()
        os.fsync(handle.fileno())
    return returned
MockTransport.dispatch = traced
held = False
def hook(point):
    global held
    if sys.argv[5] == 'hold' and point == 'before-dispatch' and not held:
        held = True
        print('LOCKED', flush=True)
        sys.stdin.readline()
    if point == sys.argv[5]:
        os._exit(86)
script = json.loads(Path(sys.argv[4]).read_text())
print(json.dumps(run_mock(sys.argv[2], sys.argv[3], script, hook=hook)), flush=True)
"""
)


class Interrupted(BaseException):
    pass


class MockExecutionTests(ExecutionCase):
    def test_run_cli_and_active_network_sdk_process_guards(self):
        fixture = self.input(tasks=1)
        output = self.output("cli")
        script = fixture.folder / "cli-script.json"
        script.write_bytes(canonical(self.script(fixture)))
        program = (
            MOCK_GUARD
            + "\nimport runpy\nsys.argv = sys.argv[2:]\nrunpy.run_path(sys.argv[0], run_name='__main__')\n"
        )
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-S",
                "-c",
                program,
                str(ROOT / "evaluation"),
                str(MOCK_CLI),
                "run",
                str(fixture.folder),
                str(output),
                str(script),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            env={"PATH": os.defpath},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_boundary(json.loads(result.stdout))
        for probe, message in (
            ("import socket; socket.socket()", "No network or child process"),
            (
                "import subprocess; subprocess.run(['no-such-program'])",
                "No network or child process",
            ),
            ("import openai", "No provider SDK"),
        ):
            checked = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-S",
                    "-c",
                    MOCK_GUARD + "\n" + probe,
                    str(ROOT / "evaluation"),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                env={"PATH": os.defpath},
            )
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("AssertionError: " + message, checked.stderr)

    def test_dispatch_requires_file_and_directory_barriers(self):
        fixture = self.input(tasks=1)
        transport = MockTransport()
        points = []
        original = transport.dispatch
        output = self.output("barriers")

        def checked(request, attempt, spec):
            self.assertLess(
                points.index("initial:after-directory-flush"),
                points.index("before-transport-construction"),
            )
            self.assertLess(
                points.index("reserved:after-file-flush"),
                points.index("reserved:after-replace"),
            )
            self.assertLess(
                points.index("reserved:after-replace"),
                points.index("reserved:after-directory-flush"),
            )
            self.assertLess(
                points.index("reserved:after-directory-flush"),
                points.index("before-dispatch"),
            )
            checkpoint, report = load_checkpoint(output)
            self.assertEqual(checkpoint["journal"][-1]["attemptId"], attempt)
            self.assertEqual(report["state"], "paused-unknown")
            self.assertEqual(report["counts"]["reserved"]["dispatches"], 1)
            return original(request, attempt, spec)

        with patch.object(transport, "dispatch", side_effect=checked):
            run_mock(
                fixture.folder,
                output,
                self.script(fixture),
                hook=points.append,
                transport=transport,
            )
        for phase, count in (
            ("reserved:before-file-flush", 0),
            ("reserved:after-replace", 1),
        ):
            with self.subTest(phase=phase):
                armed = False
                real_sync = os.fsync

                def hook(point):
                    nonlocal armed
                    if point == phase:
                        armed = True

                def fail_sync(descriptor):
                    if armed:
                        raise OSError("Injected storage barrier failure")
                    return real_sync(descriptor)

                output = self.output(phase.replace(":", "-"))
                transport = MockTransport()
                with patch("execution_checkpoint.os.fsync", side_effect=fail_sync):
                    with self.assertRaises(OSError):
                        run_mock(
                            fixture.folder,
                            output,
                            self.script(fixture),
                            hook=hook,
                            transport=transport,
                        )
                self.assertEqual(transport.calls, [])
                self.assertEqual(
                    inspect_checkpoint(output)["counts"]["reserved"]["dispatches"],
                    count,
                )

    def test_writer_file_and_total_byte_bounds(self):
        for constant, limit in (("MAX_FILES", 1), ("MAX_TOTAL_BYTES", 2)):
            with self.subTest(constant=constant):
                with DurableWriter(self.output(constant)) as writer:
                    with patch("execution_checkpoint." + constant, limit):
                        writer.put(b"a", phase="first")
                        with self.assertRaisesRegex(ValueError, "publication .* cap"):
                            writer.put(b"bb", phase="second")
                    self.assertEqual(
                        len(list((writer.root / "artifacts").iterdir())), 1
                    )

    def script(self, fixture, *, attempts=None):
        answer = [
            {"questionId": "supported", "type": "noul", "value": 0.92},
            {"questionId": "team", "type": "choice", "value": "billing"},
            {"questionId": "urgency", "type": "score", "value": 1.5},
        ]
        complete = {
            "status": "completed",
            "model": "mock-model",
            "answers": answer,
            "errorClass": None,
            "statusCode": None,
            "latencyNs": 1000,
        }
        return {
            "schema": "normlab.mock-script/v1",
            "clock": {
                "startNs": NANO,
                "utcStart": "2026-01-01T00:00:00.000000Z",
                "stepNs": 1000,
            },
            "tasks": [
                {"key": task["key"], "attempts": copy.deepcopy(attempts or [complete])}
                for task in fixture.plan["tasks"]
            ],
        }

    @staticmethod
    def failure(status="transport-failed", error="ReadTimeout"):
        return {
            "status": status,
            "model": "mock-model",
            "answers": None,
            "errorClass": error if status == "transport-failed" else None,
            "statusCode": 503 if status == "http-failed" else None,
            "latencyNs": 1000,
        }

    def input(self, **kwargs):
        fixture = self.fixture(mock=True, **kwargs)
        fixture.save()
        return fixture

    def output(self, name):
        return self.root / ("output-" + name)

    def assert_boundary(self, report):
        self.assertEqual(report["inferenceCallsExecuted"], 0)
        self.assertEqual(report["authorizedDispatches"], 0)
        self.assertFalse(report["semanticQualityEvidence"])
        self.assertFalse(report["runtimeClockVerified"])
        self.assertFalse(report["codePinsVerified"])
        self.assertFalse(report["providerWireValidated"])
        self.assertFalse(report["executionReady"])
        self.assertIsNone(report["actualCost"])
        self.assertTrue(report["mockExecution"]["clockSimulated"])
        self.assertFalse(report["mockExecution"]["resumeSupported"])

    def test_completed_mock_exact_context_and_read_only_inspection(self):
        for protocol in (
            "typesafe-systemone/v1",
            "openai-decisions/v1",
            "openai-chat-completions/v1",
            "openai-responses/v1",
        ):
            with self.subTest(protocol=protocol):
                fixture = self.input(protocol=protocol)
                output = self.output(protocol.replace("/", "-"))
                transport = MockTransport()
                report = run_mock(
                    fixture.folder, output, self.script(fixture), transport=transport
                )
                self.assert_boundary(report)
                self.assertNotEqual(report["runId"], fixture.run["id"])
                self.assertEqual(report["state"], "finished")
                self.assertEqual(report["stopReason"], "complete")
                self.assertEqual(
                    report["counts"]["reserved"],
                    {
                        "dispatches": 2,
                        "questions": 6,
                        "inputTokens": 200,
                        "outputTokens": 100,
                    },
                )
                self.assertEqual(report["counts"]["knownInputTokens"], 0)
                self.assertEqual(report["counts"]["observedDispatches"], 0)
                self.assertEqual(report["mockExecution"]["committedMockOutcomes"], 2)
                for call, task in zip(transport.calls, fixture.plan["tasks"]):
                    raw = (fixture.folder / task["request"]["path"]).read_bytes()
                    self.assertEqual(call["requestBytes"], raw)
                    self.assertEqual(
                        (output / task["request"]["path"]).read_bytes(), raw
                    )
                before = {
                    p.relative_to(output): sha(p.read_bytes())
                    for p in output.rglob("*")
                    if p.is_file()
                }
                result = cli("inspect", output, script=MOCK_CLI)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), report)
                self.assertEqual(
                    before,
                    {
                        p.relative_to(output): sha(p.read_bytes())
                        for p in output.rglob("*")
                        if p.is_file()
                    },
                )

    def test_retry_recovery_exhaustion_and_no_hidden_calls(self):
        fixture = self.input(tasks=1)
        for exhausted in (False, True):
            script = self.script(fixture)
            final = script["tasks"][0]["attempts"][0]
            script["tasks"][0]["attempts"] = (
                [self.failure()] * 3 if exhausted else [self.failure(), final]
            )
            transport = MockTransport()
            output = self.output(str(exhausted))
            report = run_mock(fixture.folder, output, script, transport=transport)
            self.assert_boundary(report)
            self.assertEqual(len(transport.calls), 3 if exhausted else 2)
            self.assertEqual(len({call["requestBytes"] for call in transport.calls}), 1)
            self.assertEqual(
                len({call["attemptId"] for call in transport.calls}),
                len(transport.calls),
            )
            first, last = (
                report["taskOutcomes"][0]["first"],
                report["taskOutcomes"][0]["final"],
            )
            self.assertEqual(first["status"], "transport-failed")
            self.assertEqual(
                last["status"], "transport-failed" if exhausted else "completed"
            )
            self.assertEqual(
                report["stopReason"], "terminal-failure" if exhausted else "complete"
            )
            self.assertEqual(
                report["counts"]["reserved"]["dispatches"], len(transport.calls)
            )
            self.assertEqual(report["counts"]["knownInputTokens"], 0)

    def test_terminal_failures_and_unknown_stop_suffix(self):
        for status in (
            "http-failed",
            "invalid-output",
            "refused",
            "transport-failed",
            "unknown-outcome",
            "model-rejected",
        ):
            with self.subTest(status=status):
                fixture = self.input()
                spec = self.failure(status, "CertificateError")
                if status == "model-rejected":
                    spec["model"] = "unexpected"
                script = self.script(fixture)
                script["tasks"][0]["attempts"] = [spec]
                transport = MockTransport()
                report = run_mock(
                    fixture.folder, self.output(status), script, transport=transport
                )
                self.assertEqual(len(transport.calls), 1)
                self.assertEqual(report["counts"]["reserved"]["dispatches"], 1)
                self.assertIsNone(report["taskOutcomes"][1]["final"])
                self.assertEqual(
                    report["state"],
                    "paused-unknown" if status == "unknown-outcome" else "finished",
                )
                self.assertEqual(
                    report["stopReason"],
                    "unknown-outcome"
                    if status == "unknown-outcome"
                    else "terminal-failure",
                )

    def test_completed_model_drift_becomes_model_rejected(self):
        fixture = self.input()
        script = self.script(fixture)
        script["tasks"][1]["attempts"][0]["model"] = "other-model"
        report = run_mock(fixture.folder, self.output("drift"), script)
        self.assertEqual(report["taskOutcomes"][1]["final"]["status"], "model-rejected")
        self.assertEqual(report["stopReason"], "terminal-failure")

    def test_zero_and_exact_caps_preserve_unstarted_denominator(self):
        for key, charge in (
            ("dispatches", 1),
            ("questions", 3),
            ("inputTokens", 100),
            ("outputTokens", 50),
        ):
            for calls in (0, 1):
                with self.subTest(key=key, calls=calls):
                    fixture = self.input()
                    fixture.plan["caps"][key] = calls * charge
                    fixture.bind_plan()
                    fixture.save()
                    transport = MockTransport()
                    report = run_mock(
                        fixture.folder,
                        self.output("cap-" + key + str(calls)),
                        self.script(fixture),
                        transport=transport,
                    )
                    self.assertEqual(len(transport.calls), calls)
                    self.assertEqual(report["counts"]["reserved"][key], calls * charge)
                    self.assertEqual(report["counts"]["reserved"]["dispatches"], calls)
                    self.assertEqual(len(report["taskOutcomes"]), 2)
                    self.assertEqual(report["stopReason"], "budget-exhaustion")

    def test_simulated_deadline_during_backoff_and_after_reservation(self):
        fixture = self.input(tasks=1)
        fixture.plan["wallTimeNs"] = NANO
        fixture.bind_plan()
        fixture.save()
        script = self.script(fixture)
        final = script["tasks"][0]["attempts"][0]
        script["tasks"][0]["attempts"] = [self.failure(), final]
        transport = MockTransport()
        report = run_mock(
            fixture.folder, self.output("backoff-expiry"), script, transport=transport
        )
        self.assertEqual(report["stopReason"], "deadline")
        self.assertEqual(len(transport.calls), 1)
        fixture = self.input(tasks=1)
        fixture.plan["wallTimeNs"] = 1000
        fixture.bind_plan()
        fixture.save()
        transport = MockTransport()
        report = run_mock(
            fixture.folder,
            self.output("reserve-expiry"),
            self.script(fixture),
            transport=transport,
        )
        self.assertEqual(len(transport.calls), 0)
        self.assertEqual(report["state"], "paused-unknown")
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 1)

    def test_invalid_script_and_live_transport_reject_before_output(self):
        changes = (
            lambda s: s.update(schema="live"),
            lambda s: s["tasks"].pop(),
            lambda s: s["clock"].update(stepNs=True),
            lambda s: s["tasks"][0]["attempts"][0].update(latencyNs=2 * NANO),
            lambda s: s["tasks"][0]["attempts"][0]["answers"][0].update(value=9),
            lambda s: s["tasks"][0].update(attempts=[self.failure()]),
            lambda s: s["tasks"][0]["attempts"][0].update(api_key="DO_NOT_PRINT"),
        )
        fixture = self.input()
        for number, change in enumerate(changes):
            script = self.script(fixture)
            change(script)
            output = self.output("invalid-" + str(number))
            with self.assertRaises((ValueError, TypeError)):
                run_mock(fixture.folder, output, script)
            self.assertFalse(output.exists())
        output = self.output("live")
        with self.assertRaisesRegex(ValueError, "built-in mock transport"):
            run_mock(fixture.folder, output, self.script(fixture), transport=object())
        self.assertFalse(output.exists())

    def test_cannot_overwrite_or_implicitly_resume_existing_directory(self):
        fixture = self.input()
        output = self.output("existing")
        script = self.script(fixture)
        run_mock(fixture.folder, output, script)
        before = (output / "checkpoint.json").read_bytes()
        transport = MockTransport()
        with self.assertRaises(FileExistsError):
            run_mock(fixture.folder, output, script, transport=transport)
        self.assertEqual(transport.calls, [])
        self.assertEqual(before, (output / "checkpoint.json").read_bytes())

    def test_reservation_commit_boundary_fault_matrix(self):
        expected_reserved = {
            "before-reservation": 0,
            "reserved:before-write": 0,
            "reserved:before-file-flush": 0,
            "reserved:after-file-flush": 0,
            "reserved:after-replace": 1,
            "reserved:after-directory-flush": 1,
            "after-reservation": 1,
            "before-dispatch": 1,
        }
        fixture = self.input()
        for number, (point, count) in enumerate(expected_reserved.items()):
            with self.subTest(point=point):

                def hook(current):
                    if current == point:
                        raise Interrupted(current)

                transport = MockTransport()
                output = self.output("reserve-fault-" + str(number))
                with self.assertRaises(Interrupted):
                    run_mock(
                        fixture.folder,
                        output,
                        self.script(fixture),
                        hook=hook,
                        transport=transport,
                    )
                self.assertEqual(len(transport.calls), 0)
                report = inspect_checkpoint(output)
                self.assertEqual(report["counts"]["reserved"]["dispatches"], count)
                self.assertEqual(
                    report["state"], "paused-unknown" if count else "created"
                )

    def test_response_terminal_and_finalization_fault_matrix(self):
        points = (
            "after-dispatch",
            "response:before-file-flush",
            "response:after-directory-flush",
            "result:after-directory-flush",
            "outcome:after-directory-flush",
            "after-response",
            "before-terminal",
            "terminal:after-file-flush",
            "terminal:after-replace",
            "terminal:after-directory-flush",
            "after-terminal",
            "before-finalization",
            "stop:after-file-flush",
            "stop:after-replace",
            "after-finalization",
        )
        fixture = self.input(tasks=1)
        for number, point in enumerate(points):
            with self.subTest(point=point):

                def hook(current):
                    if current == point:
                        raise Interrupted(current)

                output = self.output("terminal-fault-" + str(number))
                transport = MockTransport()
                with self.assertRaises(Interrupted):
                    run_mock(
                        fixture.folder,
                        output,
                        self.script(fixture),
                        hook=hook,
                        transport=transport,
                    )
                report = inspect_checkpoint(output)
                self.assertEqual(len(transport.calls), 1)
                self.assertEqual(report["counts"]["reserved"]["dispatches"], 1)
                completed = point in points[8:]
                self.assertEqual(
                    report["mockExecution"]["committedMockOutcomes"], int(completed)
                )
                self.assertEqual(
                    report["state"],
                    "finished"
                    if point in points[13:]
                    else "running"
                    if completed
                    else "paused-unknown",
                )
                if not completed:
                    self.assertEqual(len(report["unknownAttemptIds"]), 1)
                    self.assertIsNone(report["taskOutcomes"][0]["final"])

    def child_args(self, fixture, output, script, point):
        path = fixture.folder / "script-for-child.json"
        path.write_bytes(canonical(script))
        return [
            sys.executable,
            "-B",
            "-S",
            "-c",
            CHILD,
            str(ROOT / "evaluation"),
            str(fixture.folder),
            str(output),
            str(path),
            point,
        ]

    def test_hard_process_exit_keeps_reservation_and_never_redispatches(self):
        fixture = self.input(tasks=1)
        for number, point in enumerate(
            (
                "reserved:after-file-flush",
                "after-reservation",
                "after-dispatch",
                "after-response",
                "after-terminal",
                "during-backoff",
            )
        ):
            with self.subTest(point=point):
                script = self.script(fixture)
                if point == "during-backoff":
                    script["tasks"][0]["attempts"].insert(0, self.failure())
                output = self.output("exit-" + str(number))
                result = subprocess.run(
                    self.child_args(fixture, output, script, point),
                    capture_output=True,
                    text=True,
                    timeout=20,
                    env={"PATH": os.defpath},
                )
                self.assertEqual(result.returncode, 86, result.stderr)
                report = inspect_checkpoint(output)
                expected = 0 if point == "reserved:after-file-flush" else 1
                self.assertEqual(report["counts"]["reserved"]["dispatches"], expected)
                trace = output / "test-dispatch-trace"
                observed = len(trace.read_text().splitlines()) if trace.exists() else 0
                self.assertEqual(
                    observed,
                    int(
                        point
                        in {
                            "after-dispatch",
                            "after-response",
                            "after-terminal",
                            "during-backoff",
                        }
                    ),
                )
                with self.assertRaises(FileExistsError):
                    run_mock(fixture.folder, output, script)
                self.assertEqual(report, inspect_checkpoint(output))

    def test_actual_fsync_failure_before_dispatch_poisoned_writer(self):
        output = self.output("poison")
        with DurableWriter(output) as writer:
            with patch(
                "execution_checkpoint.os.fsync", side_effect=OSError("DO_NOT_PRINT")
            ):
                with self.assertRaises(OSError):
                    writer.put(b"synthetic", phase="reserved")
            with self.assertRaisesRegex(ValueError, "Healthy exclusive mock writer"):
                writer.put(b"synthetic", phase="later")
        self.assertFalse((output / "checkpoint.json").exists())

    def test_second_process_cannot_inspect_or_write_while_lock_held(self):
        fixture = self.input(tasks=1)
        output = self.output("locked")
        process = subprocess.Popen(
            self.child_args(fixture, output, self.script(fixture), "hold"),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={"PATH": os.defpath},
        )
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                self.assertTrue(
                    selector.select(timeout=10), "Writer did not signal lock"
                )
            self.assertEqual(process.stdout.readline().strip(), "LOCKED")
            with self.assertRaises(BlockingIOError):
                with reader_lock(output):
                    self.fail("Shared reader bypassed writer lock")
            result = cli("inspect", output, script=MOCK_CLI)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stderr)["errorType"], "BlockingIOError")
            with self.assertRaises(FileExistsError):
                run_mock(fixture.folder, output, self.script(fixture))
            stdout, stderr = process.communicate(input="continue\n", timeout=10)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertEqual(json.loads(stdout)["stopReason"], "complete")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
        self.assertEqual(
            inspect_checkpoint(output)["counts"]["reserved"]["dispatches"], 1
        )

    def test_checkpoint_binding_corruption_and_orphan_outcome(self):
        fixture = self.input(tasks=1)
        for name in ("view", "intent", "script", "journal", "tail", "symlink"):
            output = self.output("corrupt-" + name)
            run_mock(fixture.folder, output, self.script(fixture))
            path = output / "checkpoint.json"
            checkpoint = json.loads(path.read_bytes())
            if name == "view":
                checkpoint["run"]["counts"]["reserved"]["dispatches"] = 0
                path.write_bytes(canonical(checkpoint))
            elif name in {"intent", "script"}:
                (
                    output / ("intent.json" if name == "intent" else "mock-script.json")
                ).write_bytes(b"{}")
            elif name == "journal":
                checkpoint["journal"].pop()
                path.write_bytes(canonical(checkpoint))
            elif name == "tail":
                path.write_bytes(b'{"schema":')
            else:
                path.rename(output / "real-checkpoint")
                path.symlink_to("real-checkpoint")
            result = cli("inspect", output, script=MOCK_CLI)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotEqual(
                json.loads(result.stderr)["errorType"], "AssertionError"
            )
            self.assertNotIn(str(output), result.stderr)

    def test_frozen_source_bytes_are_copied_before_transport(self):
        fixture = self.input(tasks=1)
        task = fixture.plan["tasks"][0]
        before = (fixture.folder / task["request"]["path"]).read_bytes()

        def hook(point):
            if point == "before-dispatch":
                (fixture.folder / task["request"]["path"]).write_bytes(
                    b"changed source after snapshot"
                )

        transport = MockTransport()
        run_mock(
            fixture.folder,
            self.output("frozen"),
            self.script(fixture),
            hook=hook,
            transport=transport,
        )
        self.assertEqual(transport.calls[0]["requestBytes"], before)

    def test_bounded_script_reader_rejects_fifo_and_symlink(self):
        path = self.root / "fifo"
        os.mkfifo(path)
        with self.assertRaises(ValueError):
            bounded_read(path, 100)
        path.unlink()
        target = self.root / "target"
        target.write_bytes(b"{}")
        path.symlink_to(target)
        with self.assertRaises(OSError):
            bounded_read(path, 100)


if __name__ == "__main__":
    unittest.main()
