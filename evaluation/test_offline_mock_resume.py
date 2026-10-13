"""5c continuation fault checks; deterministic local transport only."""

import copy
import json
import os
import selectors
import subprocess
import sys
import unittest

import test_offline_mock_execution as previous
from execution_checkpoint import inspect_checkpoint
from execution_continuation import Capture, continuation_request, inspect_continuation
from execution_mock import MockTransport, SimulatedClock, run_mock
from execution_mock_codec import reference
from execution_resume import continue_mock
from execution_test_support import NANO, ROOT, ExecutionCase, canonical, cli, sha


class ResumeTests(ExecutionCase):
    input = previous.MockExecutionTests.input
    output = previous.MockExecutionTests.output
    script = previous.MockExecutionTests.script
    failure = staticmethod(previous.MockExecutionTests.failure)

    def paused(self, point, *, tasks=2, retry=False, nth=1):
        fixture = self.input(tasks=tasks)
        script = self.script(fixture)
        if retry:
            script["tasks"][0]["attempts"].insert(0, self.failure())
        output = self.output("paused-" + str(len(list(self.root.glob("output-*")))))
        count = 0

        def hook(current):
            nonlocal count
            if current == point:
                count += 1
                if count == nth:
                    raise previous.Interrupted(current)

        transport = MockTransport()
        with self.assertRaises(previous.Interrupted):
            run_mock(fixture.folder, output, script, hook=hook, transport=transport)
        return fixture, output, script, transport

    def request(
        self,
        output,
        *,
        action="resume",
        now=None,
        duration=20 * NANO,
        outcome=None,
        limits=None,
    ):
        capture = Capture(output)
        now = (
            capture.checkpoint["run"]["lastClockNs"] + NANO // 10
            if now is None
            else now
        )
        clock = SimulatedClock(capture.script["clock"])
        clock.value = now
        authorized = clock.timestamp()
        clock.value = now + duration
        return continuation_request(
            output,
            action=action,
            now_ns=now,
            expires_at=clock.timestamp(),
            operator_authorization={
                "operatorId": "synthetic",
                "authorizationRef": "f" * 64,
                "authorizedAt": authorized,
            },
            attempt=capture.report["unknownAttemptIds"][0]
            if action != "resume"
            else None,
            outcome=outcome,
            limits=limits,
        )

    def orphan(self, output):
        for path in (output / "artifacts").glob("*.blob"):
            raw = path.read_bytes()
            saved = json.loads(raw)
            if (
                isinstance(saved, dict)
                and saved.get("schema") == "normlab.execution-outcome/v1"
            ):
                return reference(raw)
        self.fail("No orphan outcome")

    def boundary(self, report):
        for key in ("inferenceCallsExecuted", "authorizedDispatches"):
            self.assertEqual(report[key], 0)
        for key in (
            "semanticQualityEvidence",
            "runtimeClockVerified",
            "codePinsVerified",
            "providerWireValidated",
            "executionReady",
        ):
            self.assertFalse(report[key])
        self.assertIsNone(report["actualCost"])
        self.assertFalse(report["mockExecution"]["authorizationAttested"])
        self.assertTrue(report["mockExecution"]["clockContinuityChecked"])

    def rejected(self, output, request):
        before = {
            p.relative_to(output): p.read_bytes()
            for p in output.rglob("*")
            if p.is_file()
        }
        transport = MockTransport()
        with self.assertRaises((ValueError, KeyError, TypeError)):
            continue_mock(output, request, transport=transport)
        after = {
            p.relative_to(output): p.read_bytes()
            for p in output.rglob("*")
            if p.is_file()
        }
        self.assertEqual(before, after)
        self.assertEqual(transport.calls, [])

    def test_resume_created_preserves_base_and_read_only_cli(self):
        _, output, _, _ = self.paused("before-reservation")
        original = (output / "checkpoint.json").read_bytes()
        request = self.request(output)
        transport = MockTransport()
        report = continue_mock(output, request, transport=transport)
        self.assertEqual(report["state"], "finished")
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual((output / "checkpoint-v1.json").read_bytes(), original)
        self.assertEqual(Capture(output).intent["id"], request["runId"])
        self.boundary(report)
        with self.assertRaises(ValueError):
            inspect_checkpoint(output)
        inspected = cli(
            "inspect", output, script=ROOT / "evaluation/execution_resume_cli.py"
        )
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        self.assertEqual(json.loads(inspected.stdout), report)

    def test_resume_only_unstarted_suffix(self):
        _, output, _, old = self.paused("after-terminal")
        capture = Capture(output)
        prefix = copy.deepcopy(capture.events)
        transport = MockTransport()
        report = continue_mock(output, self.request(output), transport=transport)
        self.assertEqual(len(old.calls), 1)
        self.assertEqual(len(transport.calls), 1)
        self.assertNotEqual(old.calls[0]["attemptId"], transport.calls[0]["attemptId"])
        self.assertEqual(Capture(output).events[: len(prefix)], prefix)
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 2)
        self.assertEqual(
            report["taskOutcomes"][0]["final"],
            capture.report["taskOutcomes"][0]["final"],
        )

    def test_unknown_requires_explicit_resolution(self):
        _, output, _, _ = self.paused("before-dispatch")
        self.rejected(output, self.request(output))
        original = Capture(output).report
        transport = MockTransport()
        report = continue_mock(
            output, self.request(output, action="stop"), transport=transport
        )
        self.assertEqual(transport.calls, [])
        self.assertEqual(report["unknownAttemptIds"], original["unknownAttemptIds"])
        self.assertEqual(report["counts"], original["counts"])
        self.assertEqual(report["state"], "finished")
        self.assertEqual(
            report["mockExecution"]["resolvedUnknownAttemptIds"],
            original["unknownAttemptIds"],
        )
        self.rejected(output, self.request(output))

    def test_adopt_saved_response_then_explicit_suffix_resume(self):
        _, output, _, _ = self.paused("after-response")
        transport = MockTransport()
        report = continue_mock(
            output,
            self.request(
                output, action="adopt-saved-outcome", outcome=self.orphan(output)
            ),
            transport=transport,
        )
        self.assertEqual(transport.calls, [])
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 1)
        self.assertEqual(report["unknownAttemptIds"], [])
        self.assertIsNone(report["taskOutcomes"][1]["final"])
        final = continue_mock(output, self.request(output), transport=transport)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(final["state"], "finished")

    def test_request_mutations_rejected_without_writes(self):
        _, output, _, _ = self.paused("before-reservation")
        request = self.request(output)
        mutations = [
            ("runId", "00000000-0000-4000-8000-000000000000"),
            ("planDigest", "0" * 64),
            ("checkpointDigest", "0" * 64),
            ("journalHead", "0" * 64),
            ("action", "continue"),
            ("nowNs", 0),
            ("observedAt", "2025-01-01T00:00:00.000000Z"),
            ("expiresAt", request["observedAt"]),
        ]
        for field, value in mutations:
            with self.subTest(field=field):
                changed = copy.deepcopy(request)
                changed[field] = value
                self.rejected(output, changed)
        for field in request["clock"]:
            with self.subTest(clock=field):
                changed = copy.deepcopy(request)
                changed["clock"][field] = None
                self.rejected(output, changed)
        changed = copy.deepcopy(request)
        changed["caps"]["dispatches"] += 1
        self.rejected(output, changed)

    def test_retry_waits_only_remaining_backoff(self):
        for elapsed in (NANO // 4, 2 * NANO):
            with self.subTest(elapsed=elapsed):
                _, output, _, old = self.paused("during-backoff", tasks=1, retry=True)
                capture = Capture(output)
                terminal = capture.events[-1]
                request = self.request(output, now=terminal["clockNs"] + elapsed)
                transport = MockTransport()
                report = continue_mock(output, request, transport=transport)
                reserved = [
                    e for e in Capture(output).events if e["type"] == "attempt-reserved"
                ]
                self.assertEqual([e["ordinal"] for e in reserved], [1, 2])
                self.assertEqual(
                    reserved[-1]["clockNs"],
                    max(terminal["clockNs"] + NANO, request["nowNs"] + 1000),
                )
                self.assertEqual(len(transport.calls), 1)
                self.assertEqual(
                    transport.calls[0]["requestBytes"], old.calls[0]["requestBytes"]
                )
                self.assertNotEqual(
                    transport.calls[0]["attemptId"], old.calls[0]["attemptId"]
                )
                self.assertEqual(report["state"], "finished")

    def test_expiry_during_backoff_then_fresh_authorization(self):
        _, output, _, _ = self.paused("during-backoff", tasks=1, retry=True)
        terminal = Capture(output).events[-1]
        transport = MockTransport()
        request = self.request(
            output, now=terminal["clockNs"] + NANO // 4, duration=NANO // 4
        )
        report = continue_mock(output, request, transport=transport)
        self.assertEqual(transport.calls, [])
        self.assertEqual(
            report["mockExecution"]["continuationStopReason"], "authorization-expired"
        )
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 1)
        final = continue_mock(output, self.request(output), transport=transport)
        self.assertEqual(final["state"], "finished")
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(len(final["mockExecution"]["invocations"]), 2)

    def test_deadline_crossed_by_marker_never_dispatches(self):
        _, output, _, _ = self.paused("before-reservation", tasks=1)
        deadline = Capture(output).intent["clock"]["deadlineNs"]
        transport = MockTransport()
        report = continue_mock(
            output, self.request(output, now=deadline - 1), transport=transport
        )
        self.assertEqual(report["stopReason"], "deadline")
        self.assertEqual(transport.calls, [])
        self.assertEqual(Capture(output).intent["clock"]["deadlineNs"], deadline)

    def test_caps_cannot_increase_between_invocations(self):
        _, output, _, _ = self.paused("before-reservation")
        limits = dict(Capture(output).limits, dispatches=1)
        request = self.request(output, limits=limits)

        def hook(point):
            if point == "after-terminal":
                raise previous.Interrupted(point)

        with self.assertRaises(previous.Interrupted):
            continue_mock(output, request, hook=hook)
        self.rejected(output, self.request(output, limits=dict(limits, dispatches=2)))
        self.rejected(output, request)
        transport = MockTransport()
        report = continue_mock(output, self.request(output), transport=transport)
        self.assertEqual(report["stopReason"], "budget-exhaustion")
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 1)
        self.assertEqual(report["mockExecution"]["effectiveCaps"]["dispatches"], 1)
        self.assertEqual(transport.calls, [])
        self.rejected(output, self.request(output))

    def test_adoption_rehashing_cannot_change_semantics(self):
        _, output, _, _ = self.paused("after-response", tasks=1)
        saved = json.loads((output / self.orphan(output)["path"]).read_bytes())
        mutations = [
            ("model", "other-model"),
            ("providerRequestId", "other-request"),
            ("requestDigest", "0" * 64),
            ("contextDigest", "0" * 64),
            ("usage", {"inputTokens": 1, "outputTokens": 0}),
            ("response", None),
            ("result", None),
        ]
        for field, value in mutations:
            with self.subTest(field=field):
                changed = copy.deepcopy(saved)
                changed[field] = value
                raw = canonical(changed)
                ref = reference(raw)
                (output / ref["path"]).write_bytes(raw)
                self.rejected(
                    output,
                    self.request(output, action="adopt-saved-outcome", outcome=ref),
                )
        for artifact, field, value in (
            ("response", "attemptId", "0" * 64),
            ("result", "normalizer", "unreviewed-normalizer"),
        ):
            with self.subTest(artifact=artifact):
                changed = copy.deepcopy(saved)
                contents = json.loads((output / saved[artifact]["path"]).read_bytes())
                contents[field] = value
                raw = canonical(contents)
                changed[artifact] = reference(raw)
                (output / changed[artifact]["path"]).write_bytes(raw)
                raw = canonical(changed)
                ref = reference(raw)
                (output / ref["path"]).write_bytes(raw)
                self.rejected(
                    output,
                    self.request(output, action="adopt-saved-outcome", outcome=ref),
                )
        original_ref = reference(canonical(saved))
        original = (output / saved["result"]["path"]).read_bytes()
        (output / saved["result"]["path"]).write_bytes(original + b" ")
        self.rejected(
            output,
            self.request(output, action="adopt-saved-outcome", outcome=original_ref),
        )
        (output / saved["result"]["path"]).write_bytes(original)
        report = continue_mock(
            output,
            self.request(output, action="adopt-saved-outcome", outcome=original_ref),
        )
        self.assertEqual(report["state"], "finished")
        self.boundary(report)

    def test_caller_mutation_cannot_extend_authorization_after_reservation(self):
        _, output, _, _ = self.paused("before-reservation", tasks=1)
        request = self.request(output, duration=2000)

        def hook(point):
            if point == "after-reservation":
                request["expiresAt"] = "2030-01-01T00:00:00.000000Z"

        transport = MockTransport()
        report = continue_mock(output, request, hook=hook, transport=transport)
        self.assertEqual(report["state"], "paused-unknown")
        self.assertEqual(transport.calls, [])

    def test_resolution_expiry_after_marker_preserves_unknown(self):
        for action in ("stop", "adopt-saved-outcome"):
            with self.subTest(action=action):
                _, output, _, _ = self.paused("after-response", tasks=1)
                outcome = (
                    self.orphan(output) if action == "adopt-saved-outcome" else None
                )
                request = self.request(
                    output, action=action, outcome=outcome, duration=1000
                )
                transport = MockTransport()
                with self.assertRaisesRegex(
                    ValueError, "authorization expired before application"
                ):
                    continue_mock(output, request, transport=transport)
                report = inspect_continuation(output)
                self.assertEqual(report["state"], "paused-unknown")
                self.assertFalse(report["mockExecution"]["invocations"][-1]["applied"])
                self.assertEqual(report["counts"]["reserved"]["dispatches"], 1)
                self.assertEqual(transport.calls, [])
                final = continue_mock(
                    output, self.request(output, action=action, outcome=outcome)
                )
                self.assertEqual(final["state"], "finished")

    def test_continuation_commit_fault_matrix(self):
        points = (
            "base:before-file-flush",
            "base:after-directory-flush",
            "authorization:after-directory-flush",
            "invocation:after-file-flush",
            "invocation:after-replace",
            "after-invocation",
            "before-reservation",
            "reserved:after-file-flush",
            "reserved:after-replace",
            "after-reservation",
            "after-response",
            "terminal:after-replace",
            "stop:after-replace",
        )
        for point in points:
            with self.subTest(point=point):
                _, output, _, _ = self.paused("before-reservation", tasks=1)
                request = self.request(output)
                before = (output / "checkpoint.json").read_bytes()

                def hook(current):
                    if current == point:
                        raise previous.Interrupted(current)

                transport = MockTransport()
                with self.assertRaises(previous.Interrupted):
                    continue_mock(output, request, hook=hook, transport=transport)
                report = inspect_continuation(output)
                unknown = point in {
                    "reserved:after-replace",
                    "after-reservation",
                    "after-response",
                }
                self.assertEqual(report["state"] == "paused-unknown", unknown)
                self.assertEqual(
                    len(transport.calls),
                    int(
                        point
                        in {
                            "after-response",
                            "terminal:after-replace",
                            "stop:after-replace",
                        }
                    ),
                )
                if unknown:
                    self.rejected(output, self.request(output))
                elif report["state"] != "finished":
                    final = continue_mock(output, self.request(output))
                    self.assertEqual(final["state"], "finished")
                self.assertEqual(
                    (output / "checkpoint-v1.json").read_bytes(), before
                ) if (output / "checkpoint-v1.json").exists() else None

    def test_adoption_commit_fault_matrix(self):
        for point in (
            "before-adoption",
            "terminal:after-file-flush",
            "terminal:after-replace",
            "after-adoption",
        ):
            with self.subTest(point=point):
                _, output, _, _ = self.paused("after-response", tasks=1)
                request = self.request(
                    output, action="adopt-saved-outcome", outcome=self.orphan(output)
                )

                def hook(current):
                    if current == point:
                        raise previous.Interrupted(current)

                transport = MockTransport()
                with self.assertRaises(previous.Interrupted):
                    continue_mock(output, request, hook=hook, transport=transport)
                self.assertEqual(transport.calls, [])
                report = inspect_continuation(output)
                applied = point in {"terminal:after-replace", "after-adoption"}
                self.assertEqual(report["unknownAttemptIds"] == [], applied)
                if applied:
                    final = continue_mock(output, self.request(output))
                else:
                    final = continue_mock(
                        output,
                        self.request(
                            output,
                            action="adopt-saved-outcome",
                            outcome=request["outcome"],
                        ),
                    )
                self.assertEqual(final["state"], "finished")

    def child_args(self, output, request, point):
        path = self.root / "child-request.json"
        path.write_bytes(canonical(request))
        program = (
            previous.MOCK_GUARD
            + r"""
from execution_resume import continue_mock
from execution_mock import MockTransport
original = MockTransport.dispatch
def traced(self, request, attempt, spec):
    result = original(self, request, attempt, spec)
    with open(Path(sys.argv[2]) / 'resume-dispatch-trace', 'ab') as handle:
        handle.write((attempt + '\n').encode())
        handle.flush()
        os.fsync(handle.fileno())
    return result
MockTransport.dispatch = traced
def hook(point):
    if sys.argv[4] == 'hold' and point == 'after-invocation':
        print('LOCKED', flush=True)
        sys.stdin.readline()
    elif point == sys.argv[4]:
        os._exit(86)
print(json.dumps(continue_mock(sys.argv[2], json.loads(Path(sys.argv[3]).read_text()), hook=hook)), flush=True)
"""
        )
        return [
            sys.executable,
            "-B",
            "-S",
            "-c",
            program,
            str(ROOT / "evaluation"),
            str(output),
            str(path),
            point,
        ]

    def test_process_exit_and_active_network_sdk_guards(self):
        for point in (
            "reserved:after-file-flush",
            "after-reservation",
            "after-response",
            "after-terminal",
        ):
            with self.subTest(point=point):
                _, output, _, _ = self.paused("before-reservation", tasks=1)
                result = subprocess.run(
                    self.child_args(output, self.request(output), point),
                    capture_output=True,
                    text=True,
                    timeout=20,
                    env={"PATH": os.defpath},
                )
                self.assertEqual(result.returncode, 86, result.stderr)
                trace = output / "resume-dispatch-trace"
                self.assertEqual(
                    len(trace.read_text().splitlines()) if trace.exists() else 0,
                    int(point in {"after-response", "after-terminal"}),
                )
                report = inspect_continuation(output)
                if report["unknownAttemptIds"]:
                    self.rejected(output, self.request(output))
                else:
                    self.assertEqual(
                        continue_mock(output, self.request(output))["state"], "finished"
                    )

    def test_writer_and_reader_lock_contention(self):
        _, output, _, _ = self.paused("before-reservation", tasks=1)
        process = subprocess.Popen(
            self.child_args(output, self.request(output), "hold"),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={"PATH": os.defpath},
        )
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(10), "Child lock handshake")
                self.assertEqual(process.stdout.readline().strip(), "LOCKED")
            with self.assertRaises(BlockingIOError):
                inspect_continuation(output)
            with self.assertRaises(BlockingIOError):
                continue_mock(output, {})
            stdout, stderr = process.communicate("continue\n", timeout=20)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertEqual(json.loads(stdout)["state"], "finished")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=10)

    def test_rehashed_event_mutations_rejected(self):
        _, output, _, _ = self.paused("before-reservation", tasks=1)
        continue_mock(output, self.request(output))
        original = (output / "checkpoint.json").read_bytes()
        checkpoint = json.loads(original)
        mutations = [
            (0, "invocationId", checkpoint["run"]["initialInvocationId"]),
            (1, "invocationId", "00000000-0000-4000-8000-000000000000"),
            (1, "clockNs", 0),
            (1, "ordinal", 2),
            (
                1,
                "budgetDelta",
                dict(checkpoint["journal"][1]["budgetDelta"], dispatches=0),
            ),
            (1, "control", checkpoint["journal"][0]["control"]),
            (-1, "stopReason", "budget-exhaustion"),
            (-1, "control", checkpoint["journal"][0]["control"]),
        ]
        for index, field, value in mutations:
            with self.subTest(index=index, field=field):
                changed = copy.deepcopy(checkpoint)
                changed["journal"][index][field] = value
                head = None
                for event in changed["journal"]:
                    event["previousDigest"] = head
                    event["id"] = sha(
                        canonical({k: v for k, v in event.items() if k != "id"})
                    )
                    head = event["id"]
                changed["run"]["journalHead"] = head
                (output / "checkpoint.json").write_bytes(canonical(changed))
                with self.assertRaises((ValueError, KeyError, StopIteration)):
                    inspect_continuation(output)
        (output / "checkpoint.json").write_bytes(original)
        self.assertEqual(inspect_continuation(output)["state"], "finished")

    def test_saved_control_cannot_reset_caps_after_rehash(self):
        _, output, _, _ = self.paused("before-reservation", tasks=1)
        continue_mock(output, self.request(output))
        checkpoint = json.loads((output / "checkpoint.json").read_bytes())
        control = checkpoint["journal"][0]["control"]
        request = json.loads((output / control["path"]).read_bytes())
        request["caps"]["dispatches"] += 1
        raw = canonical(request)
        ref = reference(raw)
        (output / ref["path"]).write_bytes(raw)
        checkpoint["journal"][0]["control"] = ref
        head = None
        for event in checkpoint["journal"]:
            event["previousDigest"] = head
            event["id"] = sha(canonical({k: v for k, v in event.items() if k != "id"}))
            head = event["id"]
        checkpoint["run"]["journalHead"] = head
        (output / "checkpoint.json").write_bytes(canonical(checkpoint))
        with self.assertRaisesRegex(ValueError, "cannot increase"):
            inspect_continuation(output)

    def test_inventory_rejects_symlink_fifo_and_oversize(self):
        for kind in ("symlink", "fifo", "oversize"):
            with self.subTest(kind=kind):
                _, output, _, _ = self.paused("before-reservation", tasks=1)
                request = self.request(output)
                before = (output / "checkpoint.json").read_bytes()
                path = output / "untrusted-extra"
                if kind == "symlink":
                    path.symlink_to(output / "intent.json")
                elif kind == "fifo":
                    os.mkfifo(path)
                else:
                    with path.open("wb") as handle:
                        handle.truncate(2 * 1024 * 1024 + 1)
                with self.assertRaises(ValueError):
                    continue_mock(output, request)
                self.assertEqual((output / "checkpoint.json").read_bytes(), before)

    def test_resume_cli_apply_under_network_and_sdk_guard(self):
        _, output, _, _ = self.paused("before-reservation", tasks=1)
        path = self.root / "cli-request.json"
        path.write_bytes(canonical(self.request(output)))
        program = (
            previous.MOCK_GUARD
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
                str(ROOT / "evaluation/execution_resume_cli.py"),
                "apply",
                str(output),
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            env={"PATH": os.defpath},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.boundary(json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
