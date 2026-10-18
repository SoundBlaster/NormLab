"""Resumed unknown-stop safety uses synthetic clocks/HTTP and real local files."""

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

import test_offline_native_resume as fixtures
import test_offline_resume_consumers as consumers
from execution_checkpoint import reader_lock
from execution_records import utc
from execution_test_support import GUARD, ROOT, ExecutionCase, canonical, sha
from native_resumed_stop import (
    BASE,
    apply_stop,
    code_pins,
    inspect_stop,
    prepare_stop,
)
from offline_bundle import identity
from runtime_resume_archive import producer_pins, read_archive
from runtime_resume_capture import capture_resume


class ResumedStopTests(ExecutionCase):
    prepared = fixtures.NativeResumeTests.prepared
    initial = fixtures.NativeResumeTests.initial
    source = fixtures.NativeResumeTests.source
    proposal = fixtures.NativeResumeTests.proposal
    apply = fixtures.NativeResumeTests.apply
    files = fixtures.NativeResumeTests.files
    guarded = fixtures.NativeResumeTests.guarded
    subfolder = fixtures.NativeResumeTests.subfolder
    resumed = consumers.ResumeConsumerTests.resumed

    def stop_proposal(self, root):
        snapshot = capture_resume(root)
        authorized = utc(snapshot.events[-1]["observedAt"]) + timedelta(seconds=1)
        request = prepare_stop(
            root,
            attempt_id=snapshot.report["unknownAttemptIds"][0],
            authorization_record={
                "operatorId": "synthetic-operator",
                "authorizationRef": "a" * 64,
                "authorizedAt": authorized.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            },
            expires_at=(authorized + timedelta(seconds=60)).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
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

    def stop_guard(self, sample=None):
        stack = ExitStack()
        for target in (
            "execution_live_kernel.NativeHTTP",
            "execution_live_kernel.claim_run",
            "socket.create_connection",
            "os.environ.get",
        ):
            stack.enter_context(
                patch(target, side_effect=AssertionError("No I/O grant"))
            )
        stack.enter_context(
            patch(
                "native_resumed_stop.LinuxClock",
                return_value=SimpleNamespace(sample=lambda: copy.deepcopy(sample)),
            )
            if sample is not None
            else patch(
                "native_resumed_stop.LinuxClock", side_effect=AssertionError("No clock")
            )
        )
        return stack

    def stop_apply(self, root, request, sample, hook=None):
        with self.stop_guard(sample):
            return apply_stop(
                root, request, confirm_request_digest=sha(canonical(request)), hook=hook
            )

    def test_stop_preserves_all_history_unknowns_charges_and_original_bytes(self):
        for phase in ("after-reservation", "after-response"):
            root = self.resumed(phase=phase)
            before = self.files(root)
            snapshot, request, sample = self.stop_proposal(root)
            self.assertEqual(before, self.files(root))
            report = self.stop_apply(root, request, sample)
            for name, raw in before.items():
                if name != "checkpoint.json":
                    self.assertEqual((root / name).read_bytes(), raw)
            archive = read_archive(root / BASE)
            self.assertEqual(
                archive.files["source/checkpoint.json"], before["checkpoint.json"]
            )
            self.assertEqual(archive.snapshot.manifest, snapshot.manifest)
            self.assertEqual(archive.snapshot.events, snapshot.events)
            self.assertEqual(report["counts"], snapshot.report["counts"])
            self.assertEqual(report["taskOutcomes"], snapshot.report["taskOutcomes"])
            self.assertEqual(report["continuation"], snapshot.manifest["continuation"])
            self.assertEqual(report["unknownAttemptIds"], [request["attemptId"]])
            self.assertEqual(report["counts"]["reserved"]["dispatches"], 2)
            self.assertEqual(report["unknownDispatchAttempts"], 1)
            self.assertEqual(report["controlState"], "stopped-with-unknown")
            self.assertFalse(report["resumeSupported"])
            self.assertFalse(report["adoptionSupported"])
            self.assertFalse(report["executionReady"])
            self.assertEqual(report["dispatchAttemptsInvoked"], 0)
            with self.assertRaises(ValueError):
                capture_resume(root)
            with self.assertRaises(ValueError):
                self.proposal(root)

    def test_read_only_prepare_inspect_idempotence_and_guarded_cli(self):
        root = self.resumed(phase="after-response")
        before = self.files(root)
        with self.stop_guard():
            _, request, sample = self.stop_proposal(root)
        self.assertEqual(before, self.files(root))
        auth = self.root / "auth.json"
        auth.write_bytes(canonical(request["authorization"]))
        script = str(ROOT / "evaluation/native_resumed_stop_cli.py")
        prepare = subprocess.run(
            [
                sys.executable,
                "-B",
                "-S",
                "-c",
                GUARD,
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
        self.assertEqual(json.loads(prepare.stdout), request)
        self.assertEqual(before, self.files(root))
        self.stop_apply(root, request, sample)
        before = self.files(root)
        with self.stop_guard():
            report = inspect_stop(root)
            repeated = apply_stop(
                root, request, confirm_request_digest=sha(canonical(request))
            )
        self.assertEqual(repeated["operation"], "already-applied")
        self.assertEqual(repeated["resolutionId"], report["resolutionId"])
        process = subprocess.run(
            [sys.executable, "-B", "-S", "-c", GUARD, script, "inspect", str(root)],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(json.loads(process.stdout), report)
        self.assertEqual(before, self.files(root))

    def test_wrong_binding_confirmation_actions_and_competing_decisions_reject(self):
        root = self.resumed(phase="after-response")
        _, request, sample = self.stop_proposal(root)
        before = self.files(root)
        for key, value in (
            ("schema", "normlab.native-stop-request/v1"),
            ("runId", "00000000-0000-4000-8000-000000000000"),
            ("planDigest", "0" * 64),
            ("checkpointDigest", "0" * 64),
            ("captureRevisionId", "capture-" + "0" * 64),
            ("journalHead", "0" * 64),
            ("attemptId", "another-attempt"),
            ("action", "adopt"),
            ("action", "resume"),
            ("extra", True),
        ):
            changed = {**request, key: value}
            with self.stop_guard(), self.assertRaises(ValueError):
                apply_stop(
                    root, changed, confirm_request_digest=sha(canonical(changed))
                )
        with self.stop_guard(), self.assertRaises(ValueError):
            apply_stop(root, request, confirm_request_digest="0" * 64)
        self.assertEqual(before, self.files(root))
        self.stop_apply(root, request, sample)
        before = self.files(root)
        changed = copy.deepcopy(request)
        changed["authorization"]["operatorId"] = "someone-else"
        with self.assertRaises(ValueError):
            self.stop_apply(root, changed, sample)
        self.assertEqual(before, self.files(root))

    def test_clock_expiry_epoch_and_regression_reject_before_new_files(self):
        root = self.resumed(phase="after-reservation")
        snapshot, request, sample = self.stop_proposal(root)
        before = self.files(root)
        for key, value in (
            ("epoch", "f" * 64),
            ("source", "unverified"),
            ("suspendAware", False),
            ("clockNs", 0),
            ("clockNs", True),
            ("observedAt", request["expiresAt"]),
            ("observedAt", "2020-01-01T00:00:00.000000Z"),
        ):
            with self.assertRaises(ValueError):
                self.stop_apply(root, request, {**sample, key: value})
        self.assertEqual(before, self.files(root))
        expired = {**sample, "clockNs": snapshot.intent["clock"]["deadlineNs"] + 1}
        report = self.stop_apply(root, request, expired)
        self.assertEqual(
            report["originalDeadlineNs"], snapshot.intent["clock"]["deadlineNs"]
        )
        self.assertFalse(report["executionReady"])

    def test_rechecks_clock_and_private_root_before_final_publication(self):
        for mutate in ("expiry", "clock", "permissions"):
            root = self.resumed(phase="after-response")
            _, request, sample = self.stop_proposal(root)
            original = (root / "checkpoint.json").read_bytes()
            changed = copy.deepcopy(sample)
            changed["observedAt"] = (
                request["expiresAt"] if mutate == "expiry" else sample["observedAt"]
            )
            if mutate == "clock":
                changed["clockNs"] -= 1

            def fault(point):
                if point == "after-resumed-stop-base" and mutate == "permissions":
                    root.chmod(0o777)

            with (
                patch(
                    "native_resumed_stop.LinuxClock",
                    return_value=SimpleNamespace(
                        sample=iter([sample, changed]).__next__
                    ),
                ),
                self.assertRaises(ValueError),
            ):
                apply_stop(
                    root,
                    request,
                    confirm_request_digest=sha(canonical(request)),
                    hook=fault,
                )
            root.chmod(0o700)
            self.assertEqual((root / "checkpoint.json").read_bytes(), original)
            self.assertEqual(
                self.stop_apply(root, request, sample)["controlState"],
                "stopped-with-unknown",
            )

    def test_locks_symlinks_permissions_and_wrong_source_reject(self):
        root = self.resumed(phase="after-response")
        _, request, sample = self.stop_proposal(root)
        before = self.files(root)
        with reader_lock(root), self.assertRaises(BlockingIOError):
            self.stop_apply(root, request, sample)
        alias = root / "alias"
        alias.symlink_to(root / "intent.json")
        with self.assertRaises(ValueError):
            self.stop_apply(root, request, sample)
        alias.unlink()
        for mode in (0o770, 0o707):
            root.chmod(mode)
            with self.assertRaises(ValueError):
                self.stop_apply(root, request, sample)
        root.chmod(0o700)
        self.assertEqual(before, self.files(root))
        for source in (
            self.source(phase="after-response"),
            self.resumed(),
            self.fixture().folder,
        ):
            with self.assertRaises((ValueError, FileNotFoundError)):
                prepare_stop(
                    source,
                    attempt_id="unknown",
                    authorization_record={},
                    expires_at=request["expiresAt"],
                )

    def test_atomic_faults_reuse_only_complete_matching_base(self):
        for phase, committed in (
            ("before-marker", False),
            ("after-resumed-stop-base", False),
            ("resumed-stop-request:before-file-flush", False),
            ("resumed-stop:before-file-flush", False),
            ("resumed-stop:after-replace", True),
            ("resumed-stop:after-directory-flush", True),
        ):
            root = self.resumed(phase="after-response")
            _, request, sample = self.stop_proposal(root)
            original = (root / "checkpoint.json").read_bytes()

            def fault(point):
                if point == phase:
                    raise KeyboardInterrupt("synthetic stop interruption")

            with self.subTest(phase=phase), self.assertRaises(KeyboardInterrupt):
                self.stop_apply(root, request, sample, fault)
            if committed:
                self.assertEqual(
                    inspect_stop(root)["controlState"], "stopped-with-unknown"
                )
            else:
                self.assertEqual((root / "checkpoint.json").read_bytes(), original)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    inspect_stop(root)
            if phase == "before-marker":
                with self.assertRaises((ValueError, FileNotFoundError)):
                    self.stop_apply(root, request, sample)
            else:
                report = self.stop_apply(root, request, sample)
                self.assertEqual(
                    report["operation"],
                    "already-applied" if committed else "apply-stop",
                )

    def test_process_exit_preserves_history_and_releases_writer_lock(self):
        for phase in ("after-resumed-stop-base", "resumed-stop:after-replace"):
            root = self.resumed(phase="after-reservation")
            _, request, sample = self.stop_proposal(root)
            pid = os.fork()
            if pid == 0:

                def terminate(point):
                    if point == phase:
                        os._exit(77)

                try:
                    self.stop_apply(root, request, sample, terminate)
                finally:
                    os._exit(88)
            _, status = os.waitpid(pid, 0)
            self.assertEqual(os.waitstatus_to_exitcode(status), 77)
            report = self.stop_apply(root, request, sample)
            self.assertEqual(report["unknownDispatchAttempts"], 1)
            self.assertEqual(report["counts"]["reserved"]["dispatches"], 2)

    def test_rehashed_resolution_base_and_original_source_mutations_reject(self):
        root = self.resumed(phase="after-response")
        _, request, sample = self.stop_proposal(root)
        self.stop_apply(root, request, sample)
        checkpoint = root / "checkpoint.json"
        original = checkpoint.read_bytes()
        for field, value in (
            ("runId", "00000000-0000-4000-8000-000000000000"),
            ("checkpointDigest", "0" * 64),
            ("baseArchiveId", "archive-" + "0" * 64),
            ("codePins", {"native_resumed_stop.py": "0" * 64}),
        ):
            saved = json.loads(original)
            saved[field] = value
            saved["resolutionId"] = identity(
                "resumed-stop", {k: v for k, v in saved.items() if k != "resolutionId"}
            )
            checkpoint.write_bytes(canonical(saved))
            with self.assertRaises(ValueError):
                inspect_stop(root)
        checkpoint.write_bytes(original)
        for target in (root / "plan.json", root / BASE / "source/checkpoint.json"):
            raw = target.read_bytes()
            target.write_bytes(raw + b" ")
            with self.assertRaises(ValueError):
                inspect_stop(root)
            target.write_bytes(raw)

    def test_copy_inspection_and_base_survive_original_deletion(self):
        root = self.resumed(phase="after-response")
        _, request, sample = self.stop_proposal(root)
        self.stop_apply(root, request, sample)
        expected = inspect_stop(root)
        copied = self.root / "copied-stop"
        shutil.copytree(root, copied)
        shutil.rmtree(root)
        with self.stop_guard():
            self.assertEqual(inspect_stop(copied), expected)
            self.assertEqual(
                read_archive(copied / BASE).snapshot.report["unknownDispatchAttempts"],
                1,
            )

    def test_stop_pins_cover_local_import_closure_and_consumer_drift(self):
        pins = code_pins()
        self.assertEqual(len(producer_pins()), 57)
        self.assertEqual(len(pins), 59)
        folder = ROOT / "evaluation"
        pending = ["native_resumed_stop", "native_resumed_stop_cli"]
        seen = set()
        while pending:
            name = pending.pop()
            if name in seen:
                continue
            seen.add(name)
            for node in ast.walk(ast.parse((folder / (name + ".py")).read_text())):
                names = (
                    [node.module]
                    if isinstance(node, ast.ImportFrom)
                    else [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else []
                )
                pending.extend(
                    n for n in names if n and (folder / (n + ".py")).is_file()
                )
        self.assertTrue({n + ".py" for n in seen} <= set(pins))
        root = self.resumed(phase="after-response")
        _, request, sample = self.stop_proposal(root)
        self.stop_apply(root, request, sample)
        original_read = Path.read_bytes
        for name in pins:

            def changed(path):
                raw = original_read(path)
                return raw + b"# synthetic drift" if path == folder / name else raw

            with (
                patch.object(Path, "read_bytes", changed),
                self.assertRaises(ValueError),
            ):
                inspect_stop(root)

    def test_stage1_full_corpus_stop_preserves_288_tasks_and_cumulative_charges(self):
        schedule = fixtures.schedule
        original = schedule.compile_stage1
        with patch.object(
            schedule,
            "compile_stage1",
            side_effect=lambda *a, **k: original(*a, profile="corpus", **k),
        ):
            folder, confirmation, clock = schedule.LiveScheduleTests.prepared(
                self, dispatches=2
            )

        def first(point):
            if point == "after-terminal":
                raise KeyboardInterrupt("synthetic pause")

        with self.assertRaises(KeyboardInterrupt):
            schedule.LiveScheduleTests.execute(
                self, folder, confirmation, clock, hook=first
            )
        root = self.root / "output"
        _, resume_request, clock2 = self.proposal(root)

        def second(point):
            if point == "after-reservation":
                raise KeyboardInterrupt("synthetic resumed unknown")

        with self.assertRaises(KeyboardInterrupt):
            self.apply(root, resume_request, clock2, hook=second)
        snapshot, request, sample = self.stop_proposal(root)
        report = self.stop_apply(root, request, sample)
        self.assertEqual(len(report["taskOutcomes"]), 288)
        self.assertEqual(report["counts"], snapshot.report["counts"])
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 2)
        self.assertEqual(report["unknownDispatchAttempts"], 1)
