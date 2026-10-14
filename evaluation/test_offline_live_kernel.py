"""One-attempt native boundary exercised with synthetic clock and fake HTTP only."""

import json
import os
import subprocess
import sys
import unittest
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import test_offline_live_wire as wire_fixtures
from execution_live_kernel import inspect_live, requirements, run_once
from execution_live_wire import projection
from execution_records import utc
from execution_test_support import ROOT, ExecutionCase, canonical
from test_offline_runtime_mlflow_cli import GUARD


class LiveKernelTests(ExecutionCase):
    def prepared(self, *, tasks=2, protocol="typesafe-systemone/v1"):
        fixture = self.fixture(mock=False, tasks=tasks, protocol=protocol)
        fixture.run["id"] = str(uuid4())
        fixture.permit["runId"] = fixture.run["id"]
        pins = requirements()
        fixture.plan["pins"].update(
            code=pins["code"], dependencies=pins["dependencies"]
        )
        fixture.plan["arms"][0]["adapter"] = pins["adapter"]
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
        return fixture, confirmation

    def execute(
        self,
        fixture,
        confirmation,
        output,
        *,
        hook=None,
        reply=None,
        change_clock=None,
        with_key=True,
    ):
        calls = []

        class Clock:
            count = 0

            def sample(self):
                self.count += 1
                value = {
                    k: fixture.run["clock"][k]
                    for k in ("policy", "source", "units", "suspendAware", "epoch")
                }
                value.update(
                    clockNs=fixture.run["clock"]["startNs"] + self.count * 1000,
                    observedAt=(
                        utc(fixture.permit["authorization"]["authorizedAt"])
                        + timedelta(microseconds=self.count)
                    ).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                )
                if change_clock is not None:
                    change_clock(value)
                return value

        class Transport:
            def __init__(self):
                calls.append("constructed")

            def dispatch(self, raw, secret, check):
                check()
                saved = json.loads((output / "checkpoint.json").read_bytes())
                self_test.assertEqual(
                    saved["run"]["counts"]["reserved"]["dispatches"], 1
                )
                self_test.assertEqual(saved["journal"][-1]["type"], "attempt-reserved")
                calls.append("dispatch")
                return reply or {
                    "response": projection(
                        200,
                        canonical(
                            wire_fixtures.body(fixture.plan["arms"][0]["protocol"])
                        ),
                        "fixture-id",
                        secret,
                    ),
                    "errorClass": None,
                }

        self_test = self
        with (
            patch("execution_live_kernel.LinuxClock", Clock),
            patch("execution_live_kernel.NativeHTTP", Transport),
            patch(
                "execution_live_authority.AUTHORITY_ROOT",
                self.root.resolve() / "authority",
            ),
            patch(
                "socket.create_connection", side_effect=AssertionError("network denied")
            ),
            patch.dict(
                os.environ,
                {"NORMLAB_OFFLINE_KEY": "offline-placeholder-key"} if with_key else {},
                clear=True,
            ),
        ):
            try:
                result = run_once(
                    fixture.folder,
                    output,
                    confirmation,
                    "NORMLAB_OFFLINE_KEY",
                    hook=hook,
                )
            except BaseException as error:
                self.last_calls = calls
                raise error
        self.last_calls = calls
        return result

    def test_success_one_task_usage_once_and_input_preservation(self):
        for protocol in (
            "typesafe-systemone/v1",
            "openai-decisions/v1",
            "openai-chat-completions/v1",
            "openai-responses/v1",
        ):
            fixture, confirmation = self.prepared(protocol=protocol)
            before = {
                p: p.read_bytes() for p in fixture.folder.rglob("*") if p.is_file()
            }
            output = self.root / ("native-" + protocol.split("/")[0])
            report = self.execute(fixture, confirmation, output)
            with self.subTest(protocol=protocol):
                self.assertEqual(self.last_calls, ["constructed", "dispatch"])
                self.assertEqual(report["counts"]["reserved"]["dispatches"], 1)
                self.assertEqual(report["counts"]["knownInputTokens"], 17)
                self.assertEqual(report["counts"]["knownOutputTokens"], 5)
                self.assertEqual(report["stopReason"], "operator-stop")
                self.assertEqual(report["taskOutcomes"][1]["attemptIds"], [])
                self.assertFalse(report["executionReady"])
                self.assertFalse(report["semanticQualityEvidence"])
                self.assertEqual(
                    before,
                    {
                        p: p.read_bytes()
                        for p in fixture.folder.rglob("*")
                        if p.is_file()
                    },
                )
                self.assertTrue(
                    all(
                        b"offline-placeholder-key" not in p.read_bytes()
                        for p in output.rglob("*")
                        if p.is_file()
                    )
                )

    def test_crash_before_reserve_or_after_reserve_response_and_terminal(self):
        phases = {
            "attempt-reserved:before-file-flush": (0, 0, 0),
            "after-reservation": (1, 0, 1),
            "before-dispatch": (1, 0, 1),
            "after-dispatch": (1, 1, 1),
            "after-response": (1, 1, 1),
            "attempt-terminal:before-file-flush": (1, 1, 1),
            "after-terminal": (1, 1, 0),
        }
        for phase, (reserved, dispatched, unknown) in phases.items():
            fixture, confirmation = self.prepared()
            output = self.root / ("fault-" + phase)

            def fault(point):
                if point == phase:
                    raise KeyboardInterrupt("synthetic interruption")

            with self.subTest(phase=phase), self.assertRaises(KeyboardInterrupt):
                self.execute(fixture, confirmation, output, hook=fault)
            report = inspect_live(output)
            self.assertEqual(report["counts"]["reserved"]["dispatches"], reserved)
            self.assertEqual(self.last_calls.count("dispatch"), dispatched)
            self.assertEqual(len(report["unknownAttemptIds"]), unknown)
            self.assertFalse(report["nativeBoundary"]["resumeSupported"])

    def test_post_reservation_expiry_or_missing_key_never_constructs_transport(self):
        fixture, confirmation = self.prepared()
        expired = [False]

        def hook(point):
            if point == "after-reservation":
                expired[0] = True

        def clock(value):
            if expired[0]:
                value["clockNs"] = fixture.run["clock"]["deadlineNs"]

        output = self.root / "expired"
        with self.assertRaises(ValueError):
            self.execute(fixture, confirmation, output, hook=hook, change_clock=clock)
        self.assertEqual(self.last_calls, [])
        self.assertEqual(len(inspect_live(output)["unknownAttemptIds"]), 1)
        output = self.root / "missing-key"
        fixture, confirmation = self.prepared()
        with self.assertRaises(ValueError):
            self.execute(fixture, confirmation, output, with_key=False)
        self.assertEqual(self.last_calls, [])
        self.assertEqual(len(inspect_live(output)["unknownAttemptIds"]), 1)

    def test_preflight_pin_confirmation_and_output_alias_fail_without_publication(self):
        fixture, confirmation = self.prepared()
        bad = {**confirmation, "runId": "different"}
        output = self.root / "wrong-confirmation"
        with self.assertRaises(ValueError):
            self.execute(fixture, bad, output)
        self.assertFalse(output.exists())
        alias = self.root / "input-alias"
        alias.symlink_to(fixture.folder, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.execute(fixture, confirmation, alias / "new-output")
        self.assertFalse((fixture.folder / "new-output").exists())
        fixture.plan["pins"]["code"]["execution_live_gate.py"] = "f" * 64
        fixture.bind_plan()
        fixture.save()
        with self.assertRaises(ValueError):
            self.execute(fixture, confirmation, output)
        self.assertFalse(output.exists())

    def test_known_failures_are_recorded_and_no_retry_or_fallback(self):
        for kind in ("http", "transport", "model", "output"):
            fixture, confirmation = self.prepared()
            value = wire_fixtures.body("typesafe-systemone/v1")
            if kind == "model":
                value["model"] = "unaccepted-model"
            elif kind == "output":
                value["answers"].pop("team")
            reply = {
                "response": projection(
                    503 if kind == "http" else 200,
                    canonical(value),
                    "fixture-id",
                    "placeholder-key",
                ),
                "errorClass": None,
            }
            if kind == "transport":
                reply = {"response": None, "errorClass": "ReadTimeout"}
            report = self.execute(
                fixture, confirmation, self.root / ("failed-" + kind), reply=reply
            )
            expected = {
                "http": "http-failed",
                "transport": "transport-failed",
                "model": "model-rejected",
                "output": "invalid-output",
            }[kind]
            self.assertEqual(report["taskOutcomes"][0]["final"]["status"], expected)
            self.assertEqual(self.last_calls.count("dispatch"), 1)
            self.assertEqual(report["taskOutcomes"][1]["attemptIds"], [])

    def test_checkpoint_counters_cannot_be_rehashed_or_resume_by_replay(self):
        fixture, confirmation = self.prepared()
        output = self.root / "modified"
        self.execute(fixture, confirmation, output)
        path = output / "checkpoint.json"
        original = path.read_bytes()
        saved = json.loads(original)
        saved["run"]["counts"]["knownInputTokens"] = 0
        path.write_bytes(canonical(saved))
        with self.assertRaises(ValueError):
            inspect_live(output)
        path.write_bytes(original)
        with self.assertRaises(FileExistsError):
            self.execute(fixture, confirmation, output)
        self.assertEqual(self.last_calls, [])

    def test_offline_requirements_and_inspect_cli_deny_network_and_sdks(self):
        fixture, confirmation = self.prepared()
        output = self.root / "cli-report"
        expected = self.execute(fixture, confirmation, output)
        for args in (("requirements",), ("inspect", str(output))):
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-S",
                    "-c",
                    GUARD,
                    str(ROOT / "evaluation/execution_live_cli.py"),
                    *args,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env={"PATH": os.defpath},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            if args[0] == "inspect":
                self.assertEqual(json.loads(result.stdout), expected)

    def test_run_id_cannot_be_reused_in_another_output_after_success_or_crash(self):
        for crash in (False, True):
            fixture, confirmation = self.prepared()
            original = self.root / ("claim-original-" + str(crash))

            def hook(point):
                if crash and point == "after-reservation":
                    raise KeyboardInterrupt

            if crash:
                with self.assertRaises(KeyboardInterrupt):
                    self.execute(fixture, confirmation, original, hook=hook)
            else:
                self.execute(fixture, confirmation, original)
            another = self.root / ("claim-another-" + str(crash))
            with self.assertRaises(FileExistsError):
                self.execute(fixture, confirmation, another)
            self.assertFalse(another.exists())
            self.assertEqual(self.last_calls, [])


if __name__ == "__main__":
    unittest.main()
