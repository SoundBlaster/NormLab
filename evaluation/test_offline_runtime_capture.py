"""Read-only capture revision identity and exact evidence boundaries."""

import copy
import json
import unittest

import test_offline_mock_execution as previous
import test_offline_mock_resume as continuation
from execution_mock import run_mock
from execution_resume import continue_mock
from execution_test_support import ROOT, ExecutionCase, cli
from runtime_capture import capture_runtime, verify_capture_manifest


class CaptureTests(ExecutionCase):
    input = previous.MockExecutionTests.input
    output = previous.MockExecutionTests.output
    script = previous.MockExecutionTests.script
    paused = continuation.ResumeTests.paused
    request = continuation.ResumeTests.request
    failure = staticmethod(previous.MockExecutionTests.failure)

    def test_repeat_identity_and_exact_sources(self):
        fixture = self.input(tasks=1)
        root = self.output("complete")
        run_mock(fixture.folder, root, self.script(fixture))
        first, second = capture_runtime(root), capture_runtime(root)
        self.assertEqual(first.manifest, second.manifest)
        for name, raw in first.files.items():
            self.assertEqual(raw, (root / name).read_bytes())
        self.assertNotIn(".writer.lock", first.files)
        self.assertEqual(first.manifest["evidenceKind"], "mock")
        self.assertFalse(first.manifest["semanticQualityEvidence"])
        with self.assertRaises(TypeError):
            first.files["checkpoint.json"] = b"changed"
        manifest = first.manifest
        manifest["executionId"] = "changed"
        self.assertEqual(first.manifest, second.manifest)
        report = first.report
        report["counts"]["reserved"]["dispatches"] = 0
        self.assertNotEqual(report, first.report)

    def test_continuation_changes_revision_not_execution(self):
        _, root, _, _ = self.paused("after-terminal")
        first = capture_runtime(root)
        original = dict(first.files)
        continue_mock(root, self.request(root))
        second = capture_runtime(root)
        self.assertEqual(first.manifest["executionId"], second.manifest["executionId"])
        self.assertNotEqual(
            first.manifest["captureRevisionId"], second.manifest["captureRevisionId"]
        )
        self.assertEqual(dict(first.files), original)
        self.assertEqual(first.report["state"], "running")
        with self.assertRaises(ValueError):
            verify_capture_manifest(root, first.manifest)
        self.assertEqual(
            verify_capture_manifest(root, second.manifest).manifest, second.manifest
        )

    def test_orphans_and_adjacent_files_excluded(self):
        _, root, _, _ = self.paused("after-response", tasks=1)
        before = capture_runtime(root)
        (root / "unrelated.txt").write_text("not evidence")
        (root / "artifacts" / ("0" * 64 + ".blob")).write_text("orphan")
        after = capture_runtime(root)
        self.assertEqual(before.manifest, after.manifest)
        self.assertEqual(before.files, after.files)
        # Only journal-backed outcomes count; saved orphan response is not adopted.
        self.assertIsNone(after.report["taskOutcomes"][0]["final"])

    def test_rehashed_manifest_edits_reject(self):
        _, root, _, _ = self.paused("after-terminal")
        manifest = capture_runtime(root).manifest
        for field, value in (
            ("state", "finished"),
            ("captureRevisionId", "capture-" + "0" * 64),
            ("inferenceCallsExecuted", True),
            ("sourceFiles", []),
            ("extra", None),
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(manifest)
                changed[field] = value
                with self.assertRaises(ValueError):
                    verify_capture_manifest(root, changed)

    def test_cli_read_only_and_no_sdk(self):
        _, root, _, _ = self.paused("after-terminal")
        result = cli(
            "snapshot", root, script=ROOT / "evaluation/runtime_capture_cli.py"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), capture_runtime(root).manifest)


if __name__ == "__main__":
    unittest.main()
