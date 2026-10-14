"""Durable fresh archive publication barriers and fault preservation."""

import unittest
from unittest.mock import patch

import test_offline_mock_execution as previous
import test_offline_mock_resume as continuation
from execution_checkpoint import reader_lock
from execution_plan import Store
from execution_test_support import ExecutionCase
from runtime_archive_export import ArchiveWriter, export_archive
from runtime_archive_format import check_index, prepare_archive
from runtime_capture import capture_runtime
from runtime_export import prepare_export


class ArchiveExportTests(ExecutionCase):
    input = previous.MockExecutionTests.input
    output = previous.MockExecutionTests.output
    script = previous.MockExecutionTests.script
    failure = staticmethod(previous.MockExecutionTests.failure)
    paused = continuation.ResumeTests.paused
    request = continuation.ResumeTests.request

    def archive_plan(self):
        _, root, _, _ = self.paused("after-terminal")
        return prepare_archive(prepare_export(capture_runtime(root)))

    def test_exact_bytes_final_marker_and_fsync_barriers(self):
        plan = self.archive_plan()
        output = self.output("archive")
        points = []

        def hook(point):
            points.append(point)
            if point == "before-marker":
                self.assertFalse((output / "archive.json").exists())
                for name, raw in plan.files.items():
                    self.assertEqual((output / name).read_bytes(), raw)

        result = export_archive(plan, output, hook=hook)
        self.assertTrue(result["durabilityAcknowledged"])
        self.assertEqual((output / "archive.json").read_bytes(), plan.index_bytes)
        self.assertEqual(
            len(check_index(Store.decode_json((output / "archive.json").read_bytes()))),
            len(plan.files),
        )
        self.assertLess(
            points.index("content:after-directory-flush"), points.index("before-marker")
        )
        self.assertLess(
            points.index("marker:after-file-flush"),
            points.index("marker:after-replace"),
        )
        self.assertLess(
            points.index("marker:after-replace"),
            points.index("marker:after-directory-commit"),
        )

    def test_no_overwrite_and_exclusive_reader_lock(self):
        plan = self.archive_plan()
        output = self.output("locked")
        with ArchiveWriter(output) as writer:
            with self.assertRaises(BlockingIOError):
                with reader_lock(output):
                    pass
            writer.publish(plan)
            with self.assertRaises(ValueError):
                writer.publish(plan)
        before = (output / "archive.json").read_bytes()
        with self.assertRaises(FileExistsError):
            export_archive(plan, output)
        self.assertEqual((output / "archive.json").read_bytes(), before)

    def test_faults_do_not_publish_marker_before_content_or_resume(self):
        plan = self.archive_plan()
        points = (
            "root:after-parent-flush",
            "lock:after-flush",
            "directories:after-flush",
            "content:before-write",
            "content:after-file-flush",
            "content:after-directory-flush",
            "before-marker",
            "marker:after-file-flush",
            "marker:after-replace",
            "marker:after-directory-commit",
        )
        for number, point in enumerate(points):
            with self.subTest(point=point):
                output = self.output("fault-" + str(number))

                def hook(current):
                    if current == point:
                        raise previous.Interrupted(current)

                with self.assertRaises(previous.Interrupted):
                    export_archive(plan, output, hook=hook)
                marker = output / "archive.json"
                self.assertEqual(marker.exists(), point in points[-2:])
                if marker.exists():
                    self.assertEqual(marker.read_bytes(), plan.index_bytes)
                with self.assertRaises(FileExistsError):
                    export_archive(plan, output)

    def test_fsync_failure_aborts_and_invalid_plan_rejects_before_creation(self):
        plan = self.archive_plan()
        output = self.output("fsync")
        with patch("runtime_archive_export.os.fsync", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError):
                export_archive(plan, output)
        self.assertFalse((output / "archive.json").exists())
        invalid = self.output("invalid")
        with self.assertRaises(ValueError):
            export_archive(object(), invalid)
        self.assertFalse(invalid.exists())


if __name__ == "__main__":
    unittest.main()
