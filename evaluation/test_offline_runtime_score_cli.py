"""Offline export/verify with bounded writes, no SDK/network and immutable inputs."""

import copy
import io
import json
import os
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

import test_offline_runtime_reference as references
import test_offline_runtime_score as fixtures
from execution_test_support import ROOT, ExecutionCase, canonical
from offline_bundle import identity
from runtime_archive_reader import read_archive
from runtime_score_cli import main, publish
from test_offline_runtime_mlflow_cli import GUARD


class ScoreCLITests(ExecutionCase):
    input = fixtures.ScoreTests.input
    output = fixtures.ScoreTests.output
    script = fixtures.ScoreTests.script
    failure = staticmethod(fixtures.ScoreTests.failure)
    paused = fixtures.ScoreTests.paused
    request = fixtures.ScoreTests.request
    orphan = fixtures.ScoreTests.orphan
    archive = fixtures.ScoreTests.archive
    view = fixtures.ScoreTests.view

    def command(self, *args):
        return subprocess.run(
            [
                sys.executable,
                "-B",
                "-S",
                "-c",
                GUARD,
                str(ROOT / "evaluation/runtime_score_cli.py"),
                *map(str, args),
            ],
            env={"PATH": os.defpath, "PYTHONNOUSERSITE": "1"},
            capture_output=True,
            text=True,
            timeout=20,
        )

    def test_score_verify_after_label_and_original_runtime_deletion(self):
        runtime, root, _ = self.archive()
        archive = read_archive(root)
        original = dict(archive.files)
        labels = self.root / "labels.json"
        labels.write_bytes(canonical(references.source(archive)))
        output = self.root / "score.json"
        first = self.command("score", root, labels, "--output", output)
        self.assertEqual(first.returncode, 0, first.stderr)
        labels.unlink()
        shutil.rmtree(runtime)
        second = self.command("verify", root, output)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))
        self.assertEqual(read_archive(root).files, original)

    def test_no_overwrite_and_failed_publication_has_no_partial_marker(self):
        _, _, _, view = self.view()
        output = self.root / "fresh.json"
        publish(view, output)
        before = output.read_bytes()
        with self.assertRaises(FileExistsError):
            publish({}, output)
        self.assertEqual(output.read_bytes(), before)
        other = self.root / "failed.json"
        with patch("runtime_score_cli.os.fsync", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                publish(view, other)
        self.assertFalse(other.exists())
        self.assertFalse(list(self.root.glob(".runtime-score-*")))

    def test_rehashed_summary_rejected_through_cli(self):
        _, root, _, view = self.view()
        changed = copy.deepcopy(view)
        changed["summary"]["passedQuestions"] += 1
        changed["scoreId"] = identity(
            "runtime-score", {k: v for k, v in changed.items() if k != "scoreId"}
        )
        path = self.root / "changed.json"
        path.write_bytes(canonical(changed))
        result = self.command("verify", root, path)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "Runtime score failed: ValueError\n")

    def test_invalid_archive_rejected_before_label_read(self):
        _, root, _ = self.archive()
        (root / "projection.json").write_bytes(b"{}")
        with (
            patch.object(
                sys,
                "argv",
                [
                    "runtime-score",
                    "score",
                    str(root),
                    "private-labels",
                    "--output",
                    str(self.root / "out.json"),
                ],
            ),
            patch(
                "runtime_score_cli.read", side_effect=AssertionError("labels read")
            ) as reader,
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(main(), 1)
        reader.assert_not_called()

    def test_full_288_task_plan_is_bounded_and_all_unstarted_questions_unevaluated(
        self,
    ):
        _, root, _ = self.archive("before-reservation", tasks=288)
        archive = read_archive(root)
        labels = self.root / "full-labels.json"
        labels.write_bytes(canonical(references.source(archive)))
        output = self.root / "full-score.json"
        result = self.command("score", root, labels, "--output", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)["summary"]
        self.assertEqual(summary["plannedTasks"], 288)
        self.assertEqual(summary["selectedQuestions"], 864)
        self.assertEqual(summary["selectedUnevaluatedQuestions"], 864)
        self.assertIsNone(summary["agreementAmongScored"])
        self.assertLess(output.stat().st_size, 2 * 1024 * 1024)
        checked = self.command("verify", root, output)
        self.assertEqual(checked.returncode, 0, checked.stderr)


if __name__ == "__main__":
    unittest.main()
