"""Bounded closed report export/replay, no SDK/network or archive mutation."""

import copy
import fcntl
import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import test_offline_runtime_compare as fixtures
from execution_test_support import ROOT, ExecutionCase, canonical
from offline_bundle import identity
from runtime_compare import compare
from runtime_compare_cli import main
from runtime_compare_report import export, markdown, verify_export
from test_offline_runtime_mlflow_cli import GUARD


class ComparisonCLITests(ExecutionCase):
    input = fixtures.CompareTests.input
    output = fixtures.CompareTests.output
    script = fixtures.CompareTests.script
    failure = staticmethod(fixtures.CompareTests.failure)
    paused = fixtures.CompareTests.paused
    request = fixtures.CompareTests.request
    orphan = fixtures.CompareTests.orphan
    archive = fixtures.CompareTests.archive
    view = fixtures.CompareTests.view
    capture = fixtures.CompareTests.capture

    def command(self, *args):
        return subprocess.run(
            [
                sys.executable,
                "-B",
                "-S",
                "-c",
                GUARD,
                str(ROOT / "evaluation/runtime_compare_cli.py"),
                *map(str, args),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env={"PATH": os.defpath, "PYTHONNOUSERSITE": "1"},
        )

    def paths(self):
        _, a, av = self.capture("base")
        _, b, bv = self.capture("candidate", answer=0.01)
        ap, bp = self.root / "base-score.json", self.root / "candidate-score.json"
        ap.write_bytes(canonical(av))
        bp.write_bytes(canonical(bv))
        return a, av, b, bv, ap, bp

    def test_cli_export_verify_and_no_overwrite(self):
        a, av, b, bv, ap, bp = self.paths()
        directory = self.root / "comparison"
        before = dict(a.files), dict(b.files)
        args = [self.output("base-archive"), ap, self.output("candidate-archive"), bp]
        first = self.command("compare", *args, "--output", directory)
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.command("verify", *args, directory)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))
        again = self.command("compare", *args, "--output", directory)
        self.assertEqual(again.returncode, 1)
        self.assertEqual(
            verify_export(directory, a, av, b, bv)["comparisonId"],
            json.loads(first.stdout)["comparisonId"],
        )
        self.assertEqual((dict(a.files), dict(b.files)), before)

    def test_report_markdown_extra_files_and_rehashed_json_mutations_reject(self):
        a, av, b, bv, _, _ = self.paths()
        result = compare(a, av, b, bv)
        directory = self.root / "report"
        export(result, directory)
        for mutation in ["markdown", "extra", "json"]:
            original = (
                (directory / "report.md").read_bytes(),
                (directory / "report.json").read_bytes(),
            )
            if mutation == "markdown":
                (directory / "report.md").write_bytes(b"changed")
            elif mutation == "extra":
                (directory / "extra").mkdir()
            else:
                altered = copy.deepcopy(result)
                altered["summary"]["final"]["candidatePassed"] += 1
                altered["comparisonId"] = identity(
                    "runtime-comparison",
                    {k: v for k, v in altered.items() if k != "comparisonId"},
                )
                (directory / "report.json").write_bytes(canonical(altered))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                verify_export(directory, a, av, b, bv)
            (directory / "report.md").write_bytes(original[0])
            (directory / "report.json").write_bytes(original[1])
            if mutation == "extra":
                (directory / "extra").rmdir()

    def test_output_inside_either_archive_or_alias_rejected_without_mutation(self):
        a, av, b, bv, ap, bp = self.paths()
        root = self.output("base-archive")
        other = self.output("candidate-archive")
        alias = self.root / "alias"
        alias.symlink_to(other, target_is_directory=True)
        for output in [root / "report", other / "report", alias / "report"]:
            result = self.command("compare", root, ap, other, bp, "--output", output)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertFalse(output.exists())
        from runtime_archive_reader import read_archive

        self.assertEqual(read_archive(root).files, a.files)
        self.assertEqual(read_archive(other).files, b.files)

    def test_fsync_failure_has_no_committed_marker_and_existing_partial_never_overwritten(
        self,
    ):
        a, av, b, bv, _, _ = self.paths()
        directory = self.root / "failed"
        with patch("runtime_compare_report.os.fsync", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                export(compare(a, av, b, bv), directory)
        self.assertFalse((directory / "report.json").exists())
        with self.assertRaises(FileExistsError):
            export(compare(a, av, b, bv), directory)

    def test_readers_fail_fast_during_all_publication_windows(self):
        from runtime_compare_report import flush_directory

        a, av, b, bv, _, _ = self.paths()
        directory = self.root / "concurrent-report"
        failures = []
        real_flock = fcntl.flock

        def inspect():
            try:
                verify_export(directory, a, av, b, bv)
            except (FileNotFoundError, BlockingIOError, ValueError) as error:
                failures.append(type(error).__name__)
            else:
                self.fail("Unfinished publication accepted")

        def flush(path):
            inspect()
            flush_directory(path)

        def acquire(fd, operation):
            if operation == fcntl.LOCK_EX:
                # A shared reader can win before LOCK_EX but must reject the
                # still-incomplete inventory and release its lock immediately.
                inspect()
            return real_flock(fd, operation)

        with (
            patch("runtime_compare_report.flush_directory", side_effect=flush),
            patch("runtime_compare_report.fcntl.flock", side_effect=acquire),
        ):
            export(compare(a, av, b, bv), directory)
        self.assertIn("FileNotFoundError", failures)
        self.assertIn("ValueError", failures)
        self.assertIn("BlockingIOError", failures)
        self.assertEqual(verify_export(directory, a, av, b, bv), compare(a, av, b, bv))

    def test_malformed_inventory_scan_stops_after_four_entries(self):
        a, av, b, bv, _, _ = self.paths()
        directory = self.root / "bounded-inventory"
        export(compare(a, av, b, bv), directory)
        visited = []

        def entries(path):
            for number in range(100000):
                visited.append(number)
                yield path / ("extra-" + str(number))

        with patch.object(Path, "iterdir", entries), self.assertRaises(ValueError):
            verify_export(directory, a, av, b, bv)
        self.assertEqual(visited, [0, 1, 2, 3])

    def test_invalid_archive_rejected_before_any_score_file_read(self):
        a, av, b, bv, ap, bp = self.paths()
        root = self.output("base-archive")
        (root / "projection.json").write_bytes(b"{}")
        with (
            patch.object(
                sys,
                "argv",
                [
                    "compare",
                    "compare",
                    str(root),
                    str(ap),
                    str(self.output("candidate-archive")),
                    str(bp),
                ],
            ),
            patch(
                "runtime_compare_cli.read", side_effect=AssertionError("score read")
            ) as reader,
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(main(), 1)
        reader.assert_not_called()

    def test_markdown_escapes_untrusted_identifiers_and_bounds_preview(self):
        a, av, b, bv, _, _ = self.paths()
        result = compare(a, av, b, bv)
        result["rows"][0]["key"][0] = "<script>|[link](x)\nnew"
        raw = markdown(result).decode()
        self.assertNotIn("<script>", raw)
        self.assertNotIn("[link](x)", raw)
        self.assertIn("&lt;script&gt;", raw)

    def test_large_288_task_report_keeps_all_unstarted_pairs(self):
        _, root, _ = self.archive("before-reservation", tasks=288)
        import test_offline_runtime_reference as references
        from runtime_archive_reader import read_archive
        from runtime_reference import reference
        from runtime_score import score

        archive = read_archive(root)
        saved = score(
            archive, reference(archive, canonical(references.source(archive)))
        )
        result = compare(archive, saved, archive, saved)
        self.assertEqual(result["summary"]["unionQuestions"], 864)
        self.assertEqual(result["summary"]["states"], {"not-evaluated": 864})
        self.assertEqual(result["summary"]["final"]["denominator"], 0)
        directory = self.root / "large-report"
        export(result, directory)
        self.assertEqual(
            verify_export(directory, archive, saved, archive, saved), result
        )
        self.assertLessEqual(
            (directory / "report.json").stat().st_size, 2 * 1024 * 1024
        )


if __name__ == "__main__":
    unittest.main()
