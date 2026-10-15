"""Native stop decisions use fake-produced evidence/time; no provider access."""

import copy
import json
import os
import subprocess
import sys
from contextlib import ExitStack
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import test_offline_live_kernel as fixtures
import test_offline_live_schedule as schedule
from execution_checkpoint import reader_lock
from execution_records import utc
from execution_test_support import ROOT, ExecutionCase, canonical, sha
from native_stop_resolution import (
    BASE,
    apply_stop,
    inspect_stop,
    prepare_stop,
)
from offline_bundle import identity
from runtime_archive_reader import read_archive
from runtime_capture import capture_runtime


class NativeStopTests(ExecutionCase):
    prepared = fixtures.LiveKernelTests.prepared
    execute = fixtures.LiveKernelTests.execute

    def source(self, phase="after-response"):
        fixture, confirmation = self.prepared()
        root = self.root / ("native-" + str(self.serial))

        def fault(point):
            if point == phase:
                raise KeyboardInterrupt("synthetic interruption")

        with self.assertRaises(KeyboardInterrupt):
            self.execute(fixture, confirmation, root, hook=fault)
        return root

    def proposal(self, root):
        snapshot = capture_runtime(root, evidence_kind="live-capture")
        authorized = utc(snapshot.events[-1]["observedAt"]) + timedelta(seconds=1)
        expires = authorized + timedelta(seconds=60)
        request = prepare_stop(
            root,
            attempt_id=snapshot.report["unknownAttemptIds"][0],
            authorization_record={
                "operatorId": "synthetic-operator",
                "authorizationRef": "a" * 64,
                "authorizedAt": authorized.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            },
            expires_at=expires.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        )
        sample = {
            k: snapshot.intent["clock"][k]
            for k in ("policy", "source", "units", "suspendAware", "epoch")
        }
        sample.update(
            clockNs=snapshot.events[-1]["clockNs"] + 2_000_000_000,
            observedAt=(authorized + timedelta(seconds=1)).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
        )
        return snapshot, request, sample

    def guarded(self, sample=None):
        stack = ExitStack()
        for target in (
            "execution_live_kernel.NativeHTTP",
            "execution_live_kernel.claim_run",
            "socket.create_connection",
            "os.environ.get",
        ):
            stack.enter_context(
                patch(target, side_effect=AssertionError("No transport/key/authority"))
            )
        stack.enter_context(
            patch(
                "native_stop_resolution.LinuxClock",
                return_value=SimpleNamespace(sample=lambda: copy.deepcopy(sample)),
            )
            if sample is not None
            else patch(
                "native_stop_resolution.LinuxClock",
                side_effect=AssertionError("No clock"),
            )
        )
        return stack

    def apply(self, root, request, sample, hook=None):
        with self.guarded(sample):
            return apply_stop(
                root, request, confirm_request_digest=sha(canonical(request)), hook=hook
            )

    def files(self, root):
        return {
            str(p.relative_to(root)): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file()
        }

    def test_stop_preserves_base_original_bytes_and_all_unknown_charges(self):
        root = self.source()
        before = self.files(root)
        snapshot, request, sample = self.proposal(root)
        self.assertEqual(before, self.files(root))
        report = self.apply(root, request, sample)
        for name, raw in before.items():
            if name != "checkpoint.json":
                self.assertEqual((root / name).read_bytes(), raw)
        base = read_archive(root / BASE)
        self.assertEqual(
            base.files["source/checkpoint.json"], before["checkpoint.json"]
        )
        self.assertEqual(base.snapshot.manifest, snapshot.manifest)
        self.assertEqual(report["counts"], snapshot.report["counts"])
        self.assertEqual(
            report["unknownAttemptIds"], snapshot.report["unknownAttemptIds"]
        )
        self.assertEqual(report["unknownDispatchAttempts"], 1)
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 1)
        self.assertIsNone(report["taskOutcomes"][0]["final"])
        self.assertEqual(report["taskOutcomes"][1]["attemptIds"], [])
        self.assertEqual(report["controlState"], "stopped-with-unknown")
        self.assertFalse(report["resumeSupported"])
        self.assertFalse(report["adoptionSupported"])
        self.assertFalse(report["executionReady"])
        self.assertEqual(report["inferenceCallsExecuted"], 0)
        with self.assertRaises(ValueError):
            capture_runtime(root, evidence_kind="live-capture")

    def test_read_only_prepare_inspect_and_idempotent_apply_need_no_clock(self):
        root = self.source("after-reservation")
        _, request, sample = self.proposal(root)
        self.apply(root, request, sample)
        before = self.files(root)
        with self.guarded():
            report = inspect_stop(root)
            repeated = apply_stop(
                root, request, confirm_request_digest=sha(canonical(request))
            )
        self.assertEqual(repeated["operation"], "already-applied")
        self.assertEqual(report["resolutionId"], repeated["resolutionId"])
        self.assertEqual(before, self.files(root))
        process = subprocess.run(
            [
                sys.executable,
                "-B",
                "-S",
                str(ROOT / "evaluation/native_stop_cli.py"),
                "inspect",
                str(root),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(json.loads(process.stdout), report)

    def test_wrong_head_confirmation_action_and_target_reject_before_clock(self):
        root = self.source()
        _, request, _ = self.proposal(root)
        before = self.files(root)
        mutations = (
            lambda r: r.update(runId="00000000-0000-4000-8000-000000000000"),
            lambda r: r.update(planDigest="0" * 64),
            lambda r: r.update(checkpointDigest="0" * 64),
            lambda r: r.update(captureRevisionId="capture-" + "0" * 64),
            lambda r: r.update(journalHead="0" * 64),
            lambda r: r.update(attemptId="other-attempt"),
            lambda r: r.update(action="adopt-saved-outcome"),
            lambda r: r.update(action="resume"),
            lambda r: r.update(extra=True),
        )
        with self.guarded():
            for mutate in mutations:
                changed = copy.deepcopy(request)
                mutate(changed)
                with self.assertRaises(ValueError):
                    apply_stop(
                        root, changed, confirm_request_digest=sha(canonical(changed))
                    )
            with self.assertRaises(ValueError):
                apply_stop(root, request, confirm_request_digest="0" * 64)
        self.assertEqual(before, self.files(root))

    def test_expiry_epoch_clock_and_wall_rollback_reject_without_new_files(self):
        root = self.source()
        _, request, sample = self.proposal(root)
        before = self.files(root)
        for mutate in (
            lambda s: s.update(epoch="f" * 64),
            lambda s: s.update(source="unverified"),
            lambda s: s.update(suspendAware=False),
            lambda s: s.update(clockNs=0),
            lambda s: s.update(clockNs=True),
            lambda s: s.update(observedAt=request["expiresAt"]),
            lambda s: s.update(observedAt="2020-01-01T00:00:00.000000Z"),
        ):
            value = copy.deepcopy(sample)
            mutate(value)
            with self.assertRaises(ValueError):
                self.apply(root, request, value)
        self.assertEqual(before, self.files(root))

    def test_expired_inference_deadline_can_be_closed_without_renewing_it(self):
        root = self.source()
        snapshot, request, sample = self.proposal(root)
        sample["clockNs"] = snapshot.intent["clock"]["deadlineNs"] + 1
        report = self.apply(root, request, sample)
        self.assertEqual(
            report["originalDeadlineNs"], snapshot.intent["clock"]["deadlineNs"]
        )
        self.assertFalse(report["executionReady"])

    def test_active_writer_or_reader_blocks_mutation(self):
        root = self.source()
        _, request, sample = self.proposal(root)
        before = self.files(root)
        with reader_lock(root), self.assertRaises(BlockingIOError):
            self.apply(root, request, sample)
        self.assertEqual(before, self.files(root))

    def test_faults_before_and_after_atomic_decision_remain_fail_closed(self):
        for phase, committed in (
            ("before-marker", False),
            ("after-stop-base", False),
            ("stop-request:before-file-flush", False),
            ("native-stop:before-file-flush", False),
            ("native-stop:after-replace", True),
            ("native-stop:after-directory-flush", True),
        ):
            root = self.source()
            _, request, sample = self.proposal(root)
            original = (root / "checkpoint.json").read_bytes()

            def fault(point):
                if point == phase:
                    raise KeyboardInterrupt("synthetic stop interruption")

            with self.subTest(phase=phase), self.assertRaises(KeyboardInterrupt):
                self.apply(root, request, sample, fault)
            if committed:
                self.assertEqual(
                    inspect_stop(root)["controlState"], "stopped-with-unknown"
                )
                self.assertEqual(
                    self.apply(root, request, sample)["operation"], "already-applied"
                )
            else:
                self.assertEqual((root / "checkpoint.json").read_bytes(), original)
                with self.assertRaises(ValueError):
                    inspect_stop(root)
                if phase == "before-marker":
                    with self.assertRaises((ValueError, FileNotFoundError)):
                        self.apply(root, request, sample)
                else:
                    self.assertEqual(
                        self.apply(root, request, sample)["controlState"],
                        "stopped-with-unknown",
                    )

    def test_rehashed_derived_resolution_and_base_mutations_reject(self):
        root = self.source()
        _, request, sample = self.proposal(root)
        self.apply(root, request, sample)
        original = (root / "checkpoint.json").read_bytes()
        for field, value in (
            ("runId", "00000000-0000-4000-8000-000000000000"),
            ("checkpointDigest", "0" * 64),
            ("baseArchiveId", "archive-" + "0" * 64),
            ("codePins", {"native_stop_resolution.py": "0" * 64}),
        ):
            saved = json.loads(original)
            saved[field] = value
            saved["resolutionId"] = identity(
                "native-stop", {k: v for k, v in saved.items() if k != "resolutionId"}
            )
            (root / "checkpoint.json").write_bytes(canonical(saved))
            with self.assertRaises(ValueError):
                inspect_stop(root)
        (root / "checkpoint.json").write_bytes(original)
        base_path = root / BASE / "source/checkpoint.json"
        base_path.write_bytes(base_path.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            inspect_stop(root)

    def test_mock_and_finished_native_sources_cannot_be_resolved(self):
        mock = self.fixture()
        fixture, confirmation = self.prepared()
        known = self.root / "known"
        self.execute(fixture, confirmation, known)
        for root in (mock.folder, known):
            with self.assertRaises((ValueError, FileNotFoundError)):
                prepare_stop(
                    root,
                    attempt_id="unknown",
                    authorization_record={},
                    expires_at="2026-01-02T00:00:00.000000Z",
                )

    def test_stage1_checkpoint_stop_retains_full_task_denominator(self):
        folder, confirmation, clock = schedule.LiveScheduleTests.prepared(self)

        def fault(point):
            if point == "after-reservation":
                raise KeyboardInterrupt("synthetic Stage1 interruption")

        with self.assertRaises(KeyboardInterrupt):
            schedule.LiveScheduleTests.execute(
                self, folder, confirmation, clock, hook=fault
            )
        root = self.root / "output"
        before, request, sample = self.proposal(root)
        self.assertEqual(
            before.manifest["checkpointSchema"], "normlab.live-checkpoint/v2"
        )
        report = self.apply(root, request, sample)
        self.assertEqual(len(report["taskOutcomes"]), 36)
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 1)
        self.assertEqual(
            report["unknownAttemptIds"], before.report["unknownAttemptIds"]
        )

    def test_process_exit_preserves_base_or_committed_stop_and_releases_lock(self):
        for phase, committed in (
            ("after-stop-base", False),
            ("native-stop:after-replace", True),
        ):
            root = self.source()
            _, request, sample = self.proposal(root)
            original = (root / "checkpoint.json").read_bytes()
            pid = os.fork()
            if pid == 0:

                def terminate(point):
                    if point == phase:
                        os._exit(77)

                try:
                    self.apply(root, request, sample, terminate)
                finally:
                    os._exit(88)
            _, status = os.waitpid(pid, 0)
            self.assertEqual(os.waitstatus_to_exitcode(status), 77)
            if not committed:
                self.assertEqual((root / "checkpoint.json").read_bytes(), original)
            report = self.apply(root, request, sample)
            self.assertEqual(report["controlState"], "stopped-with-unknown")
            self.assertEqual(report["counts"]["reserved"]["dispatches"], 1)

    def test_cli_preparation_is_read_only_and_real_host_cannot_accept_synthetic_clock(
        self,
    ):
        root = self.source()
        _, request, _ = self.proposal(root)
        auth = self.root / "authorization.json"
        auth.write_bytes(canonical(request["authorization"]))
        script = str(ROOT / "evaluation/native_stop_cli.py")
        before = self.files(root)
        process = subprocess.run(
            [
                sys.executable,
                "-B",
                "-S",
                script,
                "prepare",
                str(root),
                "--attempt-id",
                request["attemptId"],
                "--authorization",
                str(auth),
                "--expires-at",
                request["expiresAt"],
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(json.loads(process.stdout), request)
        saved = self.root / "stop-request.json"
        saved.write_bytes(canonical(request))
        process = subprocess.run(
            [
                sys.executable,
                "-B",
                "-S",
                script,
                "apply",
                str(root),
                str(saved),
                "--confirm-request-digest",
                sha(canonical(request)),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(process.returncode, 2)
        error = json.loads(process.stderr)
        self.assertEqual(error["inferenceCallsExecuted"], 0)
        self.assertEqual(before, self.files(root))

    def test_competing_decision_and_symlink_inventory_cannot_replace_stop(self):
        root = self.source()
        _, request, sample = self.proposal(root)
        alias = root / "alias"
        alias.symlink_to(root / "intent.json")
        with self.assertRaises(ValueError):
            self.apply(root, request, sample)
        alias.unlink()
        self.apply(root, request, sample)
        before = self.files(root)
        changed = copy.deepcopy(request)
        changed["authorization"]["operatorId"] = "another-operator"
        with self.assertRaises(ValueError):
            self.apply(root, changed, sample)
        self.assertEqual(before, self.files(root))

    def test_corpus_288_task_stop_stays_within_shared_inventory_bounds(self):
        original = schedule.compile_stage1

        def corpus(*args, **kwargs):
            return original(*args, profile="corpus", **kwargs)

        with patch.object(schedule, "compile_stage1", side_effect=corpus):
            folder, confirmation, clock = schedule.LiveScheduleTests.prepared(
                self, dispatches=1
            )

        def fault(point):
            if point == "after-reservation":
                raise KeyboardInterrupt("synthetic corpus interruption")

        with self.assertRaises(KeyboardInterrupt):
            schedule.LiveScheduleTests.execute(
                self, folder, confirmation, clock, hook=fault
            )
        root = self.root / "output"
        _, request, sample = self.proposal(root)
        report = self.apply(root, request, sample)
        self.assertEqual(len(report["taskOutcomes"]), 288)
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 1)
        self.assertEqual(len(report["unknownAttemptIds"]), 1)
