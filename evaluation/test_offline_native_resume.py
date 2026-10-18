"""Native resume uses synthetic clocks, local claims and fake HTTP only."""

import ast
import copy
import json
import os
import shutil
import subprocess
import sys
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import execution_live_kernel as kernel
import test_offline_live_kernel as fixtures
import test_offline_live_schedule as schedule
import test_offline_live_wire as wire
from execution_checkpoint import reader_lock
from execution_live_kernel import inspect_live
from execution_live_wire import projection
from execution_records import utc
from execution_test_support import GUARD as READONLY_GUARD
from execution_test_support import ROOT, ExecutionCase, canonical, sha
from native_resume_capture import (
    BASE,
    ResumeCapture,
    code_pins,
    inspect_resume,
    prepare_resume,
)
from native_resume_execution import resume_native
from runtime_archive_reader import read_archive
from test_offline_runtime_mlflow_cli import GUARD as SDK_GUARD


class Clock:
    def __init__(self, capture):
        self.now = capture.saved["run"]["lastClockNs"] + 200_000_000
        self.origin = capture.saved["run"]["lastClockNs"]
        self.utc = utc(
            capture.report["lastObservedAt"]
            or capture.permit["authorization"]["authorizedAt"]
        )
        self.fields = {
            key: capture.intent["clock"][key]
            for key in ("policy", "source", "units", "suspendAware", "epoch")
        }
        self.change = None

    def sample(self):
        self.now += 1_000_000
        result = {
            **self.fields,
            "clockNs": self.now,
            "observedAt": (
                self.utc + timedelta(microseconds=(self.now - self.origin) // 1000)
            ).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }
        if self.change:
            self.change(result)
        return result

    def sleep(self, seconds):
        self.now += int(seconds * 1_000_000_000)


class NativeResumeTests(ExecutionCase):
    prepared = fixtures.LiveKernelTests.prepared
    initial = fixtures.LiveKernelTests.execute
    subfolder = schedule.LiveScheduleTests.subfolder

    def source(
        self, *, phase=None, tasks=3, protocol="typesafe-systemone/v1", reply=None
    ):
        fixture, confirmation = self.prepared(tasks=tasks, protocol=protocol)
        root = self.root / ("native-" + str(self.serial))

        def hook(point):
            if point == phase:
                raise KeyboardInterrupt("synthetic initial interruption")

        if phase:
            with self.assertRaises(KeyboardInterrupt):
                self.initial(fixture, confirmation, root, hook=hook, reply=reply)
        else:
            self.initial(fixture, confirmation, root, reply=reply)
        return root

    def proposal(self, root, *, limits=None):
        capture = ResumeCapture(root)
        previous = (
            capture.report["lastObservedAt"]
            or capture.permit["authorization"]["authorizedAt"]
        )
        auth = {
            "operatorId": "synthetic-operator",
            "authorizationRef": "a" * 64,
            "authorizedAt": (utc(previous) + timedelta(milliseconds=50)).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
        }
        keys = {arm["id"]: "NORMLAB_OFFLINE_KEY" for arm in capture.plan["arms"]}
        if capture.base.checkpoint.get("mode") is not None:
            keys = {
                arm: value["keyEnvironment"]
                for arm, value in capture.store.value(
                    capture.plan["pins"]["definitions"]
                )["metadata"]["providers"].items()
            }
        request = prepare_resume(
            root,
            authorization_record=auth,
            expires_at=capture.permit["expiresAt"],
            key_environments=keys,
            limits=limits,
        )
        return capture, request, Clock(capture)

    def files(self, root):
        return {
            str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }

    def apply(self, root, request, clock, *, hook=None, customize=None, with_key=True):
        calls = []
        self.calls = calls
        test = self

        class Transport:
            def dispatch(self, raw, secret, check):
                check()
                checkpoint = json.loads((root / "checkpoint.json").read_bytes())
                test.assertEqual(checkpoint["journal"][-1]["type"], "attempt-reserved")
                request_value = json.loads(raw)
                calls.append(request_value)
                capture = ResumeCapture(root)
                task_id = checkpoint["journal"][-1]["taskId"]
                index = next(
                    i
                    for i, ids_ in enumerate(capture.intent["tasks"])
                    if ids_["taskId"] == task_id
                )
                task = capture.plan["tasks"][index]
                arm = next(a for a in capture.plan["arms"] if a["id"] == task["armId"])
                body = wire.body(arm["protocol"])
                if task["questionIds"] == ["classification"]:
                    common = {
                        "model": request_value["body"]["model"],
                        "id": "synthetic-stage1",
                        "usage": {"input_tokens": 100, "output_tokens": 20},
                    }
                    answer = {
                        "type": "choice",
                        "choice": "compatible",
                        "confidence": 1.0,
                        "probabilities": {
                            "compatible": 1.0,
                            "incompatible": 0.0,
                            "indeterminate": 0.0,
                        },
                    }
                    if arm["protocol"] == "typesafe-systemone/v1":
                        body = {**common, "answers": {"classification": answer}}
                    elif arm["protocol"] == "openai-decisions-input/v1":
                        answer["probabilities"] = [
                            {"value": k, "probability": v}
                            for k, v in answer["probabilities"].items()
                        ]
                        body = {
                            **common,
                            "answers": [{**answer, "name": "classification"}],
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
                if customize:
                    changed = customize(body, len(calls))
                    if changed is not None:
                        return changed
                return {
                    "response": projection(
                        200, canonical(body), "synthetic-resume", secret
                    ),
                    "errorClass": None,
                }

        with (
            patch("execution_live_kernel.LinuxClock", return_value=clock),
            patch("execution_live_kernel.NativeHTTP", Transport),
            patch(
                "execution_live_authority.AUTHORITY_ROOT",
                self.root.resolve() / "authority",
            ),
            patch(
                "execution_live_kernel.claim_run",
                side_effect=AssertionError("No new claim"),
            ),
            patch("socket.create_connection", side_effect=AssertionError("No network")),
            patch("native_resume_execution.time.sleep", side_effect=clock.sleep),
            patch.dict(
                os.environ,
                {
                    key: "offline-placeholder-key"
                    for key in request["keyEnvironments"].values()
                }
                if with_key
                else {},
                clear=True,
            ),
        ):
            return resume_native(
                root, request, confirm_request_digest=sha(canonical(request)), hook=hook
            )

    def guarded(self):
        stack = ExitStack()
        for target in (
            "execution_live_kernel.LinuxClock",
            "execution_live_kernel.NativeHTTP",
            "native_resume_execution.verify_claim",
            "os.environ.get",
            "socket.create_connection",
        ):
            stack.enter_context(
                patch(target, side_effect=AssertionError("Read-only operation"))
            )
        return stack

    def test_clean_operator_stop_continues_only_unreserved_suffix(self):
        for protocol in (
            "typesafe-systemone/v1",
            "openai-decisions/v1",
            "openai-chat-completions/v1",
            "openai-responses/v1",
        ):
            root = self.source(protocol=protocol)
            before = self.files(root)
            capture, request, clock = self.proposal(root)
            report = self.apply(root, request, clock)
            with self.subTest(protocol=protocol):
                self.assertEqual(len(self.calls), 2)
                self.assertEqual(report["runId"], capture.intent["id"])
                self.assertEqual(report["stopReason"], "complete")
                self.assertEqual(report["counts"]["reserved"]["dispatches"], 3)
                self.assertEqual(report["counts"]["knownInputTokens"], 51)
                self.assertEqual(
                    report["originalDeadlineNs"], capture.intent["clock"]["deadlineNs"]
                )
                self.assertEqual(
                    report["taskOutcomes"][0], capture.report["taskOutcomes"][0]
                )
                self.assertEqual(
                    read_archive(root / BASE).files["source/checkpoint.json"],
                    before["checkpoint.json"],
                )
                saved = json.loads((root / "checkpoint.json").read_bytes())
                self.assertEqual(
                    saved["journal"][: len(capture.events)], capture.events
                )
                for name, raw in before.items():
                    if name != "checkpoint.json":
                        self.assertEqual((root / name).read_bytes(), raw)
                self.assertTrue(
                    all(
                        b"offline-placeholder-key" not in raw
                        for raw in self.files(root).values()
                    )
                )
                self.assertFalse(report["executionReady"])
                self.assertFalse(report["semanticQualityEvidence"])
                with self.assertRaises(ValueError):
                    inspect_live(root)

    def test_readonly_prepare_inspect_and_stale_request_reject(self):
        root = self.source()
        with self.guarded():
            capture, request, clock = self.proposal(root)
        self.apply(root, request, clock)
        before = self.files(root)
        with self.guarded():
            inspected = inspect_resume(root)
        self.assertEqual(inspected["inferenceCallsExecuted"], 0)
        self.assertEqual(before, self.files(root))
        with self.assertRaises(ValueError):
            self.apply(root, request, clock)
        self.assertEqual(self.calls, [])
        self.assertEqual(before, self.files(root))

    def test_unknown_reservation_and_orphan_response_block_resume(self):
        for phase in ("after-reservation", "after-response"):
            root = self.source(phase=phase)
            before = self.files(root)
            with self.guarded(), self.assertRaises(ValueError):
                self.proposal(root)
            self.assertEqual(before, self.files(root))

    def test_created_checkpoint_and_interrupted_invocation_can_resume(self):
        root = self.source(phase="initial:after-replace", tasks=2)
        capture, request, clock = self.proposal(root)
        self.assertEqual(capture.report["counts"]["reserved"]["dispatches"], 0)

        def fault(point):
            if point == "after-invocation":
                raise KeyboardInterrupt("synthetic empty invocation interruption")

        with self.assertRaises(KeyboardInterrupt):
            self.apply(root, request, clock, hook=fault)
        self.assertEqual(inspect_resume(root)["state"], "running")
        _, fresh, clock2 = self.proposal(root)
        report = self.apply(root, fresh, clock2)
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 2)
        self.assertEqual(report["inferenceCallsExecuted"], 2)

    def test_stopped_unknown_control_and_unrecorded_retry_cannot_resume(self):
        from native_stop_resolution import apply_stop, prepare_stop

        root = self.source(phase="after-response")
        capture = ResumeCapture(root)
        clock = Clock(capture)
        auth = {
            "operatorId": "synthetic-operator",
            "authorizationRef": "a" * 64,
            "authorizedAt": capture.report["lastObservedAt"],
        }
        request = prepare_stop(
            root,
            attempt_id=capture.report["unknownAttemptIds"][0],
            authorization_record=auth,
            expires_at=capture.permit["expiresAt"],
        )
        with patch("native_stop_resolution.LinuxClock", return_value=clock):
            apply_stop(root, request, confirm_request_digest=sha(canonical(request)))
        with self.assertRaises(ValueError):
            self.proposal(root)
        # The one-attempt producer has no recorded schedule retry/backoff decision.
        root = self.source(reply={"response": None, "errorClass": "ReadTimeout"})
        with self.assertRaises(ValueError):
            self.proposal(root)

    def test_retry_exhaustion_certificate_and_http_failures_never_implicitly_retry(
        self,
    ):
        for kind, expected in (("transient", 3), ("certificate", 1), ("http", 1)):
            root = self.source(tasks=2)
            _, request, clock = self.proposal(root)

            def failure(body, number):
                if kind == "http":
                    return {
                        "response": projection(
                            503,
                            canonical(body),
                            "synthetic-failure",
                            "offline-placeholder-key",
                        ),
                        "errorClass": None,
                    }
                return {
                    "response": None,
                    "errorClass": "SSLCertVerificationError"
                    if kind == "certificate"
                    else "ReadTimeout",
                }

            report = self.apply(root, request, clock, customize=failure)
            self.assertEqual(len(self.calls), expected)
            self.assertEqual(report["stopReason"], "terminal-failure")
            self.assertEqual(report["counts"]["reserved"]["dispatches"], expected + 1)

    def test_current_deadline_and_utc_rollback_between_dispatch_boundaries(self):
        for kind in ("deadline", "utc-rollback", "claim"):
            root = self.source()
            capture, request, clock = self.proposal(root)

            def change(point):
                if point == "before-dispatch":
                    if kind == "deadline":
                        clock.now = capture.intent["clock"]["deadlineNs"]
                    elif kind == "utc-rollback":
                        clock.change = lambda s: s.update(
                            observedAt=request["authorization"]["authorizedAt"]
                        )
                    else:
                        (
                            self.root / "authority" / (capture.intent["id"] + ".json")
                        ).unlink()

            with self.assertRaises((ValueError, FileNotFoundError)):
                self.apply(root, request, clock, hook=change)
            self.assertEqual(self.calls, [])
            self.assertEqual(len(inspect_resume(root)["unknownAttemptIds"]), 1)

    def test_wrong_binding_action_caps_confirmation_reject_before_clock(self):
        root = self.source()
        _, request, _ = self.proposal(root)
        before = self.files(root)
        for mutate in (
            lambda r: r.update(runId="00000000-0000-4000-8000-000000000000"),
            lambda r: r.update(planDigest="0" * 64),
            lambda r: r.update(baseCheckpointDigest="0" * 64),
            lambda r: r.update(checkpointDigest="0" * 64),
            lambda r: r.update(journalHead="0" * 64),
            lambda r: r.update(action="adopt-saved-outcome"),
            lambda r: r.update(extra=True),
            lambda r: r["caps"].update(dispatches=11),
            lambda r: r["caps"].update(dispatches=0),
            lambda r: r["caps"].update(dispatches=True),
            lambda r: r.update(externalCeilingMicros=1),
            lambda r: r.update(expiresAt="2027-01-01T00:00:00.000000Z"),
            lambda r: r["keyEnvironments"].update(**{"arm-a": "not a variable"}),
        ):
            changed = copy.deepcopy(request)
            mutate(changed)
            with self.guarded(), self.assertRaises(ValueError):
                resume_native(
                    root, changed, confirm_request_digest=sha(canonical(changed))
                )
        with self.guarded(), self.assertRaises(ValueError):
            resume_native(root, request, confirm_request_digest="0" * 64)
        self.assertEqual(before, self.files(root))

    def test_clock_and_expiry_reject_before_mutation_or_transport(self):
        root = self.source()
        _, request, clock = self.proposal(root)
        before = self.files(root)
        for mutate in (
            lambda s: s.update(epoch="f" * 64),
            lambda s: s.update(source="unverified"),
            lambda s: s.update(suspendAware=False),
            lambda s: s.update(clockNs=0),
            lambda s: s.update(clockNs=True),
            lambda s: s.update(clockNs=31_000_000_000),
            lambda s: s.update(observedAt=request["expiresAt"]),
            lambda s: s.update(observedAt="2020-01-01T00:00:00.000000Z"),
        ):
            clock.change = mutate
            with self.assertRaises(ValueError):
                self.apply(root, request, clock)
            self.assertEqual(self.calls, [])
        self.assertEqual(before, self.files(root))

    def test_missing_changed_or_copied_claim_reject_without_creating_claim(self):
        root = self.source()
        capture, request, clock = self.proposal(root)
        claim = self.root / "authority" / (capture.intent["id"] + ".json")
        original = claim.read_bytes()
        claim.unlink()
        before = self.files(root)
        with self.assertRaises(FileNotFoundError):
            self.apply(root, request, clock)
        self.assertFalse(claim.exists())
        self.assertEqual(before, self.files(root))
        claim.write_bytes(original)
        claim.chmod(0o600)
        value = json.loads(original)
        value["output"] = str(self.root / "elsewhere")
        claim.write_bytes(canonical(value))
        with self.assertRaises(ValueError):
            self.apply(root, request, clock)
        claim.write_bytes(original)
        copied = self.root / "copy"
        shutil.copytree(root, copied)
        with self.assertRaises(ValueError):
            self.apply(copied, request, clock)
        self.assertEqual(before, self.files(root))

    def test_fault_after_reservation_or_response_cannot_resume_unknown(self):
        for phase in ("after-reservation", "after-dispatch", "after-response"):
            root = self.source()
            _, request, clock = self.proposal(root)

            def fault(point):
                if point == phase:
                    raise KeyboardInterrupt("synthetic resume interruption")

            with self.assertRaises(KeyboardInterrupt):
                self.apply(root, request, clock, hook=fault)
            report = inspect_resume(root)
            self.assertEqual(report["counts"]["reserved"]["dispatches"], 2)
            self.assertEqual(len(report["unknownAttemptIds"]), 1)
            self.assertIsNone(report["taskOutcomes"][1]["final"])
            with self.assertRaises(ValueError):
                self.proposal(root)

    def test_clean_terminal_crash_can_resume_again_without_resetting_caps(self):
        root = self.source(tasks=4)
        before, request, clock = self.proposal(root)

        def fault(point):
            if point == "after-terminal":
                raise KeyboardInterrupt("synthetic clean terminal interruption")

        with self.assertRaises(KeyboardInterrupt):
            self.apply(root, request, clock, hook=fault)
        report = inspect_resume(root)
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 2)
        _, request2, clock2 = self.proposal(root)
        self.assertNotEqual(request["checkpointDigest"], request2["checkpointDigest"])
        report = self.apply(root, request2, clock2)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 4)
        self.assertEqual(report["runId"], before.intent["id"])
        self.assertEqual(len(report["invocationIds"]), 2)

    def test_narrower_caps_remain_cumulative_and_cannot_be_raised(self):
        root = self.source(tasks=4)
        limits = dict(ResumeCapture(root).limits)
        limits["dispatches"] = 2
        _, request, clock = self.proposal(root, limits=limits)
        report = self.apply(root, request, clock)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 2)
        self.assertEqual(report["effectiveCaps"]["dispatches"], 2)
        self.assertEqual(report["stopReason"], "operator-stop")
        increased = dict(limits)
        increased["dispatches"] = 3
        with self.assertRaises(ValueError):
            self.proposal(root, limits=increased)
        _, request2, clock2 = self.proposal(root)
        before = self.files(root)
        with self.assertRaises(ValueError):
            self.apply(root, request2, clock2)
        self.assertEqual(self.calls, [])
        self.assertEqual(before, self.files(root))

    def test_transport_retry_preserves_request_ordinal_charge_and_backoff(self):
        root = self.source(tasks=2)
        _, request, clock = self.proposal(root)

        def temporary(body, number):
            if number == 1:
                return {"response": None, "errorClass": "ReadTimeout"}

        report = self.apply(root, request, clock, customize=temporary)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.calls[0], self.calls[1])
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 3)
        self.assertEqual(len(report["taskOutcomes"][1]["attemptIds"]), 2)
        self.assertEqual(
            report["taskOutcomes"][1]["first"]["status"], "transport-failed"
        )
        self.assertEqual(report["taskOutcomes"][1]["final"]["status"], "completed")
        self.assertEqual(report["unknownDispatchAttempts"], 1)
        self.assertIsNone(report["inferenceCallsExecuted"])
        capture = ResumeCapture(root)
        terminal = next(
            e
            for e in capture.events
            if e["type"] == "attempt-terminal"
            and e["ordinal"] == 1
            and e["invocationId"] == request["invocationId"]
        )
        retry = next(
            e
            for e in capture.events
            if e["type"] == "attempt-reserved" and e["ordinal"] == 2
        )
        self.assertGreaterEqual(retry["clockNs"] - terminal["clockNs"], 1_000_000_000)

    def test_resume_during_retry_backoff_obeys_original_terminal_time(self):
        root = self.source(tasks=2)
        _, request, clock = self.proposal(root)

        def fault(point):
            if point == "after-terminal":
                raise KeyboardInterrupt("synthetic during backoff")

        def temporary(body, number):
            return {"response": None, "errorClass": "ReadTimeout"}

        with self.assertRaises(KeyboardInterrupt):
            self.apply(root, request, clock, hook=fault, customize=temporary)
        capture, request2, clock2 = self.proposal(root)
        previous = capture.events[-1]
        report = self.apply(root, request2, clock2)
        self.assertEqual(len(self.calls), 1)
        retry = next(
            e
            for e in ResumeCapture(root).events
            if e["type"] == "attempt-reserved" and e["ordinal"] == 2
        )
        self.assertGreaterEqual(retry["clockNs"], previous["clockNs"] + 1_000_000_000)
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 3)
        # Historical unknown billing does not hide the known current invocation.
        self.assertEqual(report["inferenceCallsExecuted"], 1)

    def test_model_drift_and_usage_violations_block_further_tasks(self):
        for field in ("model", "usage"):
            root = self.source()
            _, request, clock = self.proposal(root)

            def change(body, number):
                if field == "model":
                    body["model"] = "other-model"
                else:
                    body["usage"]["input_tokens"] = 101

            report = self.apply(root, request, clock, customize=change)
            self.assertEqual(len(self.calls), 1)
            self.assertEqual(report["taskOutcomes"][2]["attemptIds"], [])
            self.assertEqual(
                report["stopReason"],
                "terminal-failure" if field == "model" else "usage-ceiling-exceeded",
            )
            with self.assertRaises(ValueError):
                self.proposal(root)

    def test_archive_and_invocation_publication_faults_require_fresh_head(self):
        for phase, changed in (
            ("before-marker", False),
            ("after-resume-base", False),
            ("resume-request:before-file-flush", False),
            ("invocation-started:before-file-flush", False),
            ("invocation-started:after-replace", True),
            ("after-invocation", True),
        ):
            root = self.source()
            _, request, clock = self.proposal(root)
            original = (root / "checkpoint.json").read_bytes()

            def fault(point):
                if point == phase:
                    raise KeyboardInterrupt("synthetic publication boundary")

            with self.assertRaises(KeyboardInterrupt):
                self.apply(root, request, clock, hook=fault)
            self.assertEqual(self.calls, [])
            self.assertEqual(
                (root / "checkpoint.json").read_bytes() != original, changed
            )
            if phase == "before-marker":
                with self.assertRaises((ValueError, FileNotFoundError)):
                    self.apply(root, request, clock)
            elif changed:
                with self.assertRaises(ValueError):
                    self.apply(root, request, clock)
                _, fresh, clock2 = self.proposal(root)
                self.assertEqual(
                    self.apply(root, fresh, clock2)["stopReason"], "complete"
                )
            else:
                self.assertEqual(
                    self.apply(root, request, clock)["stopReason"], "complete"
                )

    def test_current_expiry_after_archive_or_reservation_never_dispatches(self):
        for phase in ("after-resume-base", "after-reservation", "before-dispatch"):
            root = self.source()
            _, request, clock = self.proposal(root)

            def expire(point):
                if point == phase:
                    clock.change = lambda s: s.update(observedAt=request["expiresAt"])

            with self.assertRaises(ValueError):
                self.apply(root, request, clock, hook=expire)
            self.assertEqual(self.calls, [])
            report = inspect_resume(root)
            self.assertEqual(
                len(report["unknownAttemptIds"]),
                0 if phase == "after-resume-base" else 1,
            )

    def test_writer_reader_symlink_and_claim_permissions_fail_closed(self):
        root = self.source()
        capture, request, clock = self.proposal(root)
        before = self.files(root)
        with reader_lock(root), self.assertRaises(BlockingIOError):
            self.apply(root, request, clock)
        alias = root / "alias"
        alias.symlink_to(root / "intent.json")
        with self.assertRaises(ValueError):
            self.apply(root, request, clock)
        alias.unlink()
        claim = self.root / "authority" / (capture.intent["id"] + ".json")
        claim.chmod(0o644)
        with self.assertRaises(ValueError):
            self.apply(root, request, clock)
        self.assertEqual(before, self.files(root))

    def test_nonprivate_or_foreign_output_rejects_before_publication_and_dispatch(self):
        root = self.source()
        _, request, clock = self.proposal(root)
        before = self.files(root)
        original_mode = root.stat().st_mode & 0o777
        for mode in (0o770, 0o777):
            try:
                root.chmod(mode)
                with self.assertRaises(ValueError):
                    self.apply(root, request, clock)
                self.assertEqual(self.calls, [])
                self.assertEqual(before, self.files(root))
            finally:
                root.chmod(original_mode)
        original_lstat = Path.lstat

        def foreign(path, *args, **kwargs):
            info = original_lstat(path, *args, **kwargs)
            if path == root:
                return SimpleNamespace(st_mode=info.st_mode, st_uid=os.geteuid() + 1)
            return info

        # Simulate chown without privileged filesystem mutation.
        with patch.object(Path, "lstat", foreign), self.assertRaises(ValueError):
            self.apply(root, request, clock)
        self.assertEqual(self.calls, [])
        self.assertEqual(before, self.files(root))

    def test_output_permissions_rechecked_immediately_before_dispatch(self):
        root = self.source()
        _, request, clock = self.proposal(root)
        original_mode = root.stat().st_mode & 0o777

        def expose(point):
            if point == "before-dispatch":
                root.chmod(0o777)

        try:
            with self.assertRaises(ValueError):
                self.apply(root, request, clock, hook=expose)
            self.assertEqual(self.calls, [])
        finally:
            root.chmod(original_mode)
        report = inspect_resume(root)
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 2)
        self.assertEqual(len(report["unknownAttemptIds"]), 1)

    def test_pin_set_covers_local_import_closure_and_dependency_drift(self):
        root = self.source()
        _, request, clock = self.proposal(root)
        self.apply(root, request, clock)
        pins = code_pins()
        folder = ROOT / "evaluation"
        pending, seen = ["native_resume_cli"], set()
        while pending:
            name = pending.pop()
            if name in seen:
                continue
            seen.add(name)
            tree = ast.parse((folder / (name + ".py")).read_text())
            for node in ast.walk(tree):
                imports = (
                    [node.module]
                    if isinstance(node, ast.ImportFrom)
                    else [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else []
                )
                pending.extend(
                    value
                    for value in imports
                    if value
                    and (folder / (value + ".py")).is_file()
                    and value not in seen
                )
        self.assertTrue({name + ".py" for name in seen} <= set(pins))
        original_read = Path.read_bytes
        before = self.files(root)
        for name in pins:

            def changed(path):
                raw = original_read(path)
                return (
                    raw + b"\n# synthetic dependency drift\n"
                    if path == folder / name
                    else raw
                )

            with self.subTest(module=name), patch.object(Path, "read_bytes", changed):
                altered = code_pins()
                self.assertEqual(set(altered), set(pins))
                self.assertNotEqual(altered[name], pins[name])
                with self.guarded(), self.assertRaises(ValueError):
                    inspect_resume(root)
        self.assertEqual(before, self.files(root))

    def test_rehashed_wrong_event_and_control_binding_cannot_inspect(self):
        root = self.source()
        _, request, clock = self.proposal(root)
        self.apply(root, request, clock)
        path = root / "checkpoint.json"
        original = path.read_bytes()
        for mutate in (
            lambda r: r.update(baseArchiveId="archive-" + "0" * 64),
            lambda r: r["codePins"].update(**{"native_resume_capture.py": "0" * 64}),
            lambda r: r["run"]["counts"]["reserved"].update(dispatches=0),
            lambda r: r["journal"][3].update(
                invocationId="00000000-0000-4000-8000-000000000000"
            ),
            lambda r: r["journal"][4].update(clockNs=0),
            lambda r: r["journal"][3].update(control=None),
        ):
            value = json.loads(original)
            mutate(value)
            for index in range(3, len(value["journal"])):
                event = value["journal"][index]
                event["previousDigest"] = value["journal"][index - 1]["id"]
                event["id"] = sha(
                    canonical({k: v for k, v in event.items() if k != "id"})
                )
            value["run"]["journalHead"] = value["journal"][-1]["id"]
            path.write_bytes(canonical(value))
            with self.assertRaises((ValueError, TypeError)):
                inspect_resume(root)
        path.write_bytes(original)
        self.assertEqual(inspect_resume(root)["stopReason"], "complete")

    def test_empty_continuation_checkpoint_and_changed_runtime_cannot_execute(self):
        root = self.source()
        capture, request, clock = self.proposal(root)
        changed = kernel.requirements()
        changed["dependencies"] = {"python-stdlib-runtime": "0" * 64}
        before = self.files(root)
        with (
            patch.object(kernel, "requirements", return_value=changed),
            self.guarded(),
            self.assertRaises(ValueError),
        ):
            resume_native(root, request, confirm_request_digest=sha(canonical(request)))
        self.assertEqual(before, self.files(root))
        self.apply(root, request, clock)
        capture = ResumeCapture(root)
        # A supported continuation frame must contain an actual invocation.
        empty = capture.frame(capture.base.events, capture.base.report)
        (root / "checkpoint.json").write_bytes(canonical(empty))
        with self.assertRaises(ValueError):
            inspect_resume(root)

    def test_process_exit_at_invocation_reservation_and_terminal_releases_lock(self):
        for phase, charged, unknown in (
            ("after-resume-base", 1, False),
            ("after-invocation", 1, False),
            ("after-reservation", 2, True),
            ("after-terminal", 2, False),
        ):
            root = self.source()
            _, request, clock = self.proposal(root)
            pid = os.fork()
            if pid == 0:

                def terminate(point):
                    if point == phase:
                        os._exit(77)

                try:
                    self.apply(root, request, clock, hook=terminate)
                finally:
                    os._exit(88)
            _, status = os.waitpid(pid, 0)
            self.assertEqual(os.waitstatus_to_exitcode(status), 77)
            report = inspect_resume(root)
            self.assertEqual(report["counts"]["reserved"]["dispatches"], charged)
            self.assertEqual(bool(report["unknownAttemptIds"]), unknown)
            if unknown:
                with self.assertRaises(ValueError):
                    self.proposal(root)
            else:
                _, fresh, clock2 = self.proposal(root)
                self.assertEqual(
                    self.apply(root, fresh, clock2)["stopReason"], "complete"
                )

    def test_cli_prepare_inspect_sdk_free_and_apply_rejects_real_host(self):
        root = self.source()
        _, request, clock = self.proposal(root)
        auth = self.root / "authorization.json"
        keys = self.root / "keys.json"
        auth.write_bytes(canonical(request["authorization"]))
        keys.write_bytes(canonical(request["keyEnvironments"]))
        script = str(ROOT / "evaluation/native_resume_cli.py")
        before = self.files(root)
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-S",
                "-c",
                READONLY_GUARD,
                script,
                "prepare",
                str(root),
                "--authorization",
                str(auth),
                "--expires-at",
                request["expiresAt"],
                "--key-environments",
                str(keys),
            ],
            capture_output=True,
            text=True,
            env={"PATH": os.defpath},
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["checkpointDigest"], request["checkpointDigest"])
        self.assertEqual(before, self.files(root))
        saved = self.root / "request.json"
        saved.write_bytes(canonical(request))
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-S",
                "-c",
                SDK_GUARD,
                script,
                "apply",
                str(root),
                str(saved),
                "--confirm-request-digest",
                sha(canonical(request)),
            ],
            capture_output=True,
            text=True,
            env={"PATH": os.defpath},
            timeout=30,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIsNone(json.loads(result.stderr)["inferenceCallsExecuted"])
        self.assertEqual(before, self.files(root))
        self.apply(root, request, clock)
        before = self.files(root)
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-S",
                "-c",
                READONLY_GUARD,
                script,
                "inspect",
                str(root),
            ],
            capture_output=True,
            text=True,
            env={"PATH": os.defpath},
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), inspect_resume(root))
        self.assertEqual(before, self.files(root))

    def test_stage1_pilot_and_corpus_preserve_full_denominator(self):
        for profile, denominator in (("pilot", 36), ("corpus", 288)):
            with self.subfolder(profile):
                original = schedule.compile_stage1

                def compile_profile(*args, **kwargs):
                    return original(*args, profile=profile, **kwargs)

                with patch.object(
                    schedule, "compile_stage1", side_effect=compile_profile
                ):
                    folder, confirmation, clock = schedule.LiveScheduleTests.prepared(
                        self, dispatches=2
                    )

                def fault(point):
                    if point == "after-terminal":
                        raise KeyboardInterrupt("synthetic Stage1 clean interruption")

                with self.assertRaises(KeyboardInterrupt):
                    schedule.LiveScheduleTests.execute(
                        self, folder, confirmation, clock, hook=fault
                    )
                root = self.root / "output"
                before, request, clock2 = self.proposal(root)
                report = self.apply(root, request, clock2)
                self.assertEqual(len(report["taskOutcomes"]), denominator)
                self.assertEqual(report["counts"]["reserved"]["dispatches"], 2)
                self.assertEqual(len(self.calls), 1)
                self.assertEqual(
                    report["taskOutcomes"][0], before.report["taskOutcomes"][0]
                )
