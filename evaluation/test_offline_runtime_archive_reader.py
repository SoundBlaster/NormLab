"""Portable archive replay, mutation and independent process-crash boundaries."""

import copy
import json
import os
import selectors
import shutil
import subprocess
import sys
import unittest

import test_offline_mock_execution as previous
import test_offline_mock_resume as continuation
from execution_resume import continue_mock
from execution_test_support import ROOT, ExecutionCase, canonical, cli, sha
from offline_bundle import identity
from runtime_archive_export import export_archive
from runtime_archive_format import PIN_MODULES, prepare_archive
from runtime_archive_reader import read_archive
from runtime_capture import capture_runtime
from runtime_export import prepare_export


class ArchiveReaderTests(ExecutionCase):
    input = previous.MockExecutionTests.input
    output = previous.MockExecutionTests.output
    script = previous.MockExecutionTests.script
    failure = staticmethod(previous.MockExecutionTests.failure)
    paused = continuation.ResumeTests.paused
    request = continuation.ResumeTests.request
    orphan = continuation.ResumeTests.orphan

    def archive(self, point="after-terminal", *, tasks=2):
        _, source, _, _ = self.paused(point, tasks=tasks)
        plan = prepare_archive(prepare_export(capture_runtime(source)))
        target = self.output(
            "archive-" + str(len(list(self.root.glob("output-archive*"))))
        )
        export_archive(plan, target)
        return source, target, plan

    def test_round_trip_original_and_continued_after_source_deletion(self):
        source, first, original = self.archive()
        continue_mock(source, self.request(source))
        second_plan = prepare_archive(prepare_export(capture_runtime(source)))
        second = self.output("second")
        export_archive(second_plan, second)
        shutil.rmtree(source)
        a, b = read_archive(first), read_archive(second)
        self.assertEqual(a.index, original.index)
        self.assertEqual(a.index["executionId"], b.index["executionId"])
        self.assertNotEqual(a.index["captureRevisionId"], b.index["captureRevisionId"])
        self.assertEqual(a.summary()["state"], "running")
        self.assertEqual(b.summary()["state"], "finished")
        self.assertEqual(
            a.files["source/checkpoint.json"], b.files["source/checkpoint-v1.json"]
        )

    def test_unknown_then_adopted_revision_without_extra_attempt(self):
        source, unknown, _ = self.archive("after-response", tasks=1)
        continue_mock(
            source,
            self.request(
                source, action="adopt-saved-outcome", outcome=self.orphan(source)
            ),
        )
        adopted = self.output("adopted")
        export_archive(
            prepare_archive(prepare_export(capture_runtime(source))), adopted
        )
        shutil.rmtree(source)
        before, after = read_archive(unknown).summary(), read_archive(adopted).summary()
        self.assertEqual(before["counts"]["attempts"], 1)
        self.assertEqual(after["counts"]["attempts"], 1)
        self.assertEqual(before["state"], "paused-unknown")
        self.assertEqual(after["state"], "finished")
        self.assertFalse(after["semanticQualityEvidence"])
        self.assertEqual(after["inferenceCallsExecuted"], 0)

    def test_portable_copied_reader_outside_repo_write_network_sdk_denied(self):
        source, archive, _ = self.archive()
        shutil.rmtree(source)
        tools = self.root / "trusted-tools"
        tools.mkdir()
        for name in PIN_MODULES + (
            "runtime_archive_export",
            "runtime_archive_reader",
            "runtime_archive_cli",
        ):
            shutil.copyfile(
                ROOT / "evaluation" / (name + ".py"), tools / (name + ".py")
            )
        result = cli("verify", archive, script=tools / "runtime_archive_cli.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), read_archive(archive).summary())

    def test_digest_and_regenerated_projection_reject_coordinated_edits(self):
        _, archive, plan = self.archive()
        original = (archive / "archive.json").read_bytes()
        for name in ("capture.json", "projection.json"):
            with self.subTest(name=name):
                content = plan.files[name]
                edited = json.loads(content)
                if name == "capture.json":
                    edited["state"] = "finished"
                else:
                    edited["counts"]["plannedTasks"] = 0
                raw = canonical(edited)
                (archive / name).write_bytes(raw)
                index = copy.deepcopy(plan.index)
                for ref in index["inventory"]:
                    if ref["path"] == name:
                        ref.update(sha256=sha(raw), bytes=len(raw))
                index["capture" if name == "capture.json" else "projection"] = next(
                    ref for ref in index["inventory"] if ref["path"] == name
                )
                index["totals"]["contentBytes"] = sum(
                    ref["bytes"] for ref in index["inventory"]
                )
                index["archiveId"] = identity(
                    "archive", {k: v for k, v in index.items() if k != "archiveId"}
                )
                (archive / "archive.json").write_bytes(canonical(index))
                with self.assertRaises(ValueError):
                    read_archive(archive)
                (archive / name).write_bytes(content)
        (archive / "archive.json").write_bytes(original)
        self.assertEqual(read_archive(archive).index, plan.index)

    def test_missing_extra_symlink_fifo_and_oversized_files_reject(self):
        for mutation in ("missing", "extra", "symlink", "fifo", "oversized"):
            with self.subTest(mutation=mutation):
                _, archive, _ = self.archive()
                path = archive / "capture.json"
                if mutation == "missing":
                    path.unlink()
                elif mutation == "extra":
                    (archive / "extra").write_bytes(b"x")
                elif mutation == "symlink":
                    path.unlink()
                    path.symlink_to(archive / "projection.json")
                elif mutation == "fifo":
                    path.unlink()
                    os.mkfifo(path)
                else:
                    with path.open("wb") as handle:
                        handle.truncate(2 * 1024 * 1024 + 1)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    read_archive(archive)

    def test_trusted_producer_pin_mismatch_and_changed_lock_reject(self):
        _, archive, plan = self.archive()
        index = plan.index
        index["producerPins"][PIN_MODULES[0]] = "0" * 64
        index["archiveId"] = identity(
            "archive", {k: v for k, v in index.items() if k != "archiveId"}
        )
        (archive / "archive.json").write_bytes(canonical(index))
        with self.assertRaisesRegex(ValueError, "producer revision"):
            read_archive(archive)
        (archive / "archive.json").write_bytes(plan.index_bytes)
        (archive / ".writer.lock").write_bytes(b"unexpected")
        with self.assertRaises(ValueError):
            read_archive(archive)

    def test_process_exit_before_and_after_final_marker(self):
        _, source, _, _ = self.paused("after-terminal")
        program = (
            previous.MOCK_GUARD
            + r"""
from runtime_archive_export import export_runtime_archive
def hook(point):
    if point == sys.argv[4]: os._exit(86)
export_runtime_archive(sys.argv[2], sys.argv[3], hook=hook)
"""
        )
        points = (
            "content:after-file-flush",
            "before-marker",
            "marker:after-file-flush",
            "marker:after-replace",
            "marker:after-directory-commit",
        )
        for number, point in enumerate(points):
            with self.subTest(point=point):
                archive = self.output("exit-" + str(number))
                result = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        "-S",
                        "-c",
                        program,
                        str(ROOT / "evaluation"),
                        str(source),
                        str(archive),
                        point,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=20,
                    env={"PATH": os.defpath},
                )
                self.assertEqual(result.returncode, 86, result.stderr)
                if point in points[-2:]:
                    self.assertTrue(read_archive(archive).summary()["archiveVerified"])
                else:
                    with self.assertRaises((ValueError, FileNotFoundError)):
                        read_archive(archive)

    def test_retry_preserves_first_final_and_usage_accounting(self):
        _, source, _, _ = self.paused("during-backoff", tasks=1, retry=True)
        continue_mock(source, self.request(source))
        plan = prepare_archive(prepare_export(capture_runtime(source)))
        archive = self.output("retry-archive")
        export_archive(plan, archive)
        shutil.rmtree(source)
        verified = read_archive(archive)
        ref = verified.projection.manifest["records"][0]
        task = json.loads(verified.projection.files[ref["path"]])
        self.assertEqual(
            [a["status"] for a in task["attempts"]], ["transport-failed", "completed"]
        )
        self.assertNotEqual(task["firstOutcome"], task["finalOutcome"])
        self.assertEqual(verified.summary()["counts"]["reserved"]["dispatches"], 2)

    def test_checkpoint_over_ordinary_file_limit_round_trips(self):
        _, source, _, _ = self.paused("after-terminal")
        path = source / "checkpoint.json"
        path.write_bytes(path.read_bytes() + b" " * (2 * 1024 * 1024 + 1))
        plan = prepare_archive(prepare_export(capture_runtime(source)))
        archive = self.output("large-checkpoint")
        export_archive(plan, archive)
        shutil.rmtree(source)
        self.assertEqual(
            read_archive(archive).files["source/checkpoint.json"],
            plan.files["source/checkpoint.json"],
        )

    def test_large_unstarted_archive_keeps_split_task_records(self):
        source, archive, _ = self.archive("before-reservation", tasks=288)
        shutil.rmtree(source)
        result = read_archive(archive)
        self.assertEqual(result.summary()["counts"]["plannedTasks"], 288)
        self.assertEqual(result.summary()["counts"]["plannedQuestions"], 864)
        self.assertEqual(len(result.projection.manifest["records"]), 288)
        self.assertEqual(result.summary()["predictionSeal"]["status"], "unsealed")

    def test_source_counter_edit_rehashed_index_still_fails_replay(self):
        _, archive, plan = self.archive()
        name = "source/checkpoint.json"
        checkpoint = json.loads(plan.files[name])
        checkpoint["run"]["counts"]["reserved"]["dispatches"] = 0
        raw = canonical(checkpoint)
        (archive / name).write_bytes(raw)
        index = plan.index
        for ref in index["inventory"]:
            if ref["path"] == name:
                ref.update(sha256=sha(raw), bytes=len(raw))
        index["totals"]["contentBytes"] = sum(
            ref["bytes"] for ref in index["inventory"]
        )
        index["archiveId"] = identity(
            "archive", {k: v for k, v in index.items() if k != "archiveId"}
        )
        (archive / "archive.json").write_bytes(canonical(index))
        with self.assertRaisesRegex(ValueError, "counters binding"):
            read_archive(archive)

    def test_independent_writer_lock_blocks_reader_before_marker(self):
        _, source, _, _ = self.paused("after-terminal")
        archive = self.output("held")
        program = (
            previous.MOCK_GUARD
            + r"""
from runtime_archive_export import export_runtime_archive
def hook(point):
    if point == 'before-marker':
        print('LOCKED', flush=True)
        sys.stdin.readline()
print(json.dumps(export_runtime_archive(sys.argv[2], sys.argv[3], hook=hook)), flush=True)
"""
        )
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-S",
                "-c",
                program,
                str(ROOT / "evaluation"),
                str(source),
                str(archive),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={"PATH": os.defpath},
        )
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(10))
                self.assertEqual(process.stdout.readline().strip(), "LOCKED")
            with self.assertRaises(BlockingIOError):
                read_archive(archive)
            stdout, stderr = process.communicate("continue\n", timeout=20)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertTrue(json.loads(stdout)["durabilityAcknowledged"])
            self.assertTrue(read_archive(archive).summary()["archiveVerified"])
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=10)

    def test_export_cli_with_network_sdk_denied(self):
        _, source, _, _ = self.paused("after-terminal")
        archive = self.output("cli-export")
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
                str(ROOT / "evaluation/runtime_archive_cli.py"),
                "export",
                str(source),
                str(archive),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            env={"PATH": os.defpath},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["archiveVerified"])
        self.assertTrue(json.loads(result.stdout)["durabilityAcknowledged"])


if __name__ == "__main__":
    unittest.main()
