"""Runtime archive format bounds and immutable original evidence."""

import copy
import unittest
from unittest.mock import patch

import test_offline_mock_execution as previous
import test_offline_mock_resume as continuation
from execution_resume import continue_mock
from execution_test_support import ExecutionCase
from offline_bundle import identity
from runtime_archive_format import check_index, prepare_archive
from runtime_capture import capture_runtime
from runtime_export import prepare_export


class ArchiveFormatTests(ExecutionCase):
    input = previous.MockExecutionTests.input
    output = previous.MockExecutionTests.output
    script = previous.MockExecutionTests.script
    failure = staticmethod(previous.MockExecutionTests.failure)
    paused = continuation.ResumeTests.paused
    request = continuation.ResumeTests.request

    def test_exact_namespaces_repeat_identity_and_copies(self):
        _, root, _, _ = self.paused("after-terminal")
        projection = prepare_export(capture_runtime(root))
        plan = prepare_archive(projection)
        self.assertEqual(plan.index, prepare_archive(projection).index)
        self.assertEqual(
            plan.files["source/checkpoint.json"],
            (root / "checkpoint.json").read_bytes(),
        )
        for name, raw in projection.files.items():
            self.assertEqual(plan.files["projection/" + name], raw)
        self.assertEqual(len(check_index(plan.index)), len(plan.files))
        edited = plan.index
        edited["executionReady"] = True
        self.assertFalse(plan.index["executionReady"])
        with self.assertRaises(TypeError):
            plan.files["capture.json"] = b"changed"

    def test_continued_revision_keeps_original_bytes(self):
        _, root, _, _ = self.paused("after-terminal")
        first = prepare_archive(prepare_export(capture_runtime(root)))
        continue_mock(root, self.request(root))
        second = prepare_archive(prepare_export(capture_runtime(root)))
        self.assertEqual(first.index["executionId"], second.index["executionId"])
        self.assertNotEqual(
            first.index["captureRevisionId"], second.index["captureRevisionId"]
        )
        self.assertNotEqual(first.index["archiveId"], second.index["archiveId"])
        self.assertEqual(
            first.files["source/checkpoint.json"],
            second.files["source/checkpoint-v1.json"],
        )

    def test_rehashed_invalid_shape_limits_and_paths_reject(self):
        _, root, _, _ = self.paused("after-terminal")
        plan = prepare_archive(prepare_export(capture_runtime(root)))
        for mutation in (
            "flags",
            "duplicate",
            "escape",
            "bytes",
            "pin",
            "metadata",
            "totals",
        ):
            with self.subTest(mutation=mutation):
                index = copy.deepcopy(plan.index)
                if mutation == "flags":
                    index["inferenceCallsExecuted"] = False
                elif mutation == "duplicate":
                    index["inventory"].append(index["inventory"][0])
                elif mutation == "escape":
                    index["inventory"][0]["path"] = "../escape"
                elif mutation == "bytes":
                    index["inventory"][0]["bytes"] = True
                elif mutation == "pin":
                    index["producerPins"] = {}
                elif mutation == "metadata":
                    index["capture"] = None
                else:
                    index["totals"]["publishedEntries"] -= 1
                index["archiveId"] = identity(
                    "archive", {k: v for k, v in index.items() if k != "archiveId"}
                )
                with self.assertRaises(ValueError):
                    check_index(index)

    def test_all_limits_count_metadata_directories_marker_and_lock(self):
        _, root, _, _ = self.paused("after-terminal")
        projection = prepare_export(capture_runtime(root))
        plan = prepare_archive(projection)
        with patch(
            "runtime_archive_format.MAX_FILES",
            plan.index["totals"]["publishedEntries"] - 1,
        ):
            with self.assertRaises(ValueError):
                prepare_archive(projection)
        with patch(
            "runtime_archive_format.MAX_TOTAL_BYTES",
            plan.index["totals"]["contentBytes"],
        ):
            with self.assertRaises(ValueError):
                prepare_archive(projection)
        with patch("runtime_archive_format.MAX_BYTES", 100):
            with self.assertRaises(ValueError):
                prepare_archive(projection)


if __name__ == "__main__":
    unittest.main()
