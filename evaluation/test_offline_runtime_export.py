"""Runtime export preparation preserves unknown/retry/full-denominator evidence."""

import copy
import json
import unittest

import test_offline_mock_execution as previous
import test_offline_mock_resume as continuation
from execution_mock import run_mock
from execution_resume import continue_mock
from execution_test_support import ROOT, ExecutionCase, cli
from offline_bundle import canonical
from runtime_capture import capture_runtime
from runtime_export import prepare_export, verify_export_projection


class ExportTests(ExecutionCase):
    input = previous.MockExecutionTests.input
    output = previous.MockExecutionTests.output
    script = previous.MockExecutionTests.script
    failure = staticmethod(previous.MockExecutionTests.failure)
    paused = continuation.ResumeTests.paused
    request = continuation.ResumeTests.request
    orphan = continuation.ResumeTests.orphan

    def rows(self, projection):
        return [
            json.loads(projection.files[ref["path"]])
            for ref in projection.manifest["records"]
        ]

    def test_complete_projection_seal_and_exact_context(self):
        fixture = self.input(tasks=2)
        root = self.output("complete")
        run_mock(fixture.folder, root, self.script(fixture))
        projection = prepare_export(capture_runtime(root))
        manifest = projection.manifest
        self.assertEqual(manifest["predictionSeal"]["status"], "sealed")
        self.assertEqual(manifest["counts"]["plannedQuestions"], 6)
        self.assertEqual(manifest["counts"]["statusCounts"], {"completed": 2})
        self.assertIsNone(manifest["score"])
        self.assertFalse(manifest["exportWritten"])
        for row, task in zip(self.rows(projection), fixture.plan["tasks"]):
            self.assertEqual(row["request"], task["request"])
            self.assertEqual(row["context"], task["context"])
            self.assertEqual(row["firstOutcome"], row["finalOutcome"])
        self.assertEqual(
            verify_export_projection(root, manifest, projection.files).manifest,
            manifest,
        )

    def test_unknown_and_unstarted_suffix_stay_unsealed(self):
        _, root, _, _ = self.paused("after-response")
        projection = prepare_export(capture_runtime(root))
        self.assertEqual(projection.manifest["predictionSeal"]["status"], "unsealed")
        self.assertEqual(projection.manifest["counts"]["attempts"], 1)
        rows = self.rows(projection)
        self.assertEqual(
            [row["status"] for row in rows], ["unknown-outcome", "not-dispatched"]
        )
        self.assertIsNone(rows[0]["finalOutcome"])
        self.assertEqual(rows[1]["attempts"], [])

    def test_retry_retains_first_final_and_both_charges(self):
        fixture = self.input(tasks=1)
        script = self.script(fixture)
        script["tasks"][0]["attempts"].insert(0, self.failure())
        root = self.output("retry")
        run_mock(fixture.folder, root, script)
        projection = prepare_export(capture_runtime(root))
        row = self.rows(projection)[0]
        self.assertEqual([attempt["ordinal"] for attempt in row["attempts"]], [1, 2])
        self.assertEqual(
            [attempt["status"] for attempt in row["attempts"]],
            ["transport-failed", "completed"],
        )
        self.assertNotEqual(row["firstOutcome"], row["finalOutcome"])
        self.assertEqual(projection.manifest["counts"]["reserved"]["dispatches"], 2)

    def test_adoption_reuses_original_attempt_without_synthetic_dispatch(self):
        _, root, _, _ = self.paused("after-response", tasks=1)
        original = prepare_export(capture_runtime(root))
        continue_mock(
            root,
            self.request(root, action="adopt-saved-outcome", outcome=self.orphan(root)),
        )
        adopted = prepare_export(capture_runtime(root))
        before, after = self.rows(original)[0], self.rows(adopted)[0]
        self.assertEqual(before["attempts"][0]["id"], after["attempts"][0]["id"])
        self.assertEqual(adopted.manifest["counts"]["attempts"], 1)
        self.assertEqual(adopted.manifest["predictionSeal"]["status"], "sealed")
        self.assertEqual(adopted.manifest["inferenceCallsExecuted"], 0)

    def test_rehashed_summaries_and_record_edits_reject(self):
        _, root, _, _ = self.paused("after-terminal")
        projection = prepare_export(capture_runtime(root))
        for field, value in (
            ("counts", {}),
            ("predictionSeal", {"status": "sealed"}),
            ("reference", {"status": "human-gold"}),
            ("score", {"accuracy": 1}),
            ("inferenceCallsExecuted", True),
        ):
            changed = copy.deepcopy(projection.manifest)
            changed[field] = value
            with self.assertRaises(ValueError):
                verify_export_projection(root, changed, projection.files)
        artifacts = dict(projection.files)
        ref = projection.manifest["records"][0]
        row = json.loads(artifacts[ref["path"]])
        row["attempts"] = []
        artifacts[ref["path"]] = canonical(row)
        with self.assertRaises(ValueError):
            verify_export_projection(root, projection.manifest, artifacts)

    def test_cli_project_read_only(self):
        _, root, _, _ = self.paused("after-terminal")
        result = cli("project", root, script=ROOT / "evaluation/runtime_capture_cli.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout), prepare_export(capture_runtime(root)).manifest
        )

    def test_large_unstarted_matrix_uses_separate_task_artifacts(self):
        _, root, _, _ = self.paused("before-reservation", tasks=288)
        projection = prepare_export(capture_runtime(root))
        self.assertEqual(projection.manifest["counts"]["plannedTasks"], 288)
        self.assertEqual(projection.manifest["counts"]["plannedQuestions"], 864)
        self.assertEqual(
            projection.manifest["counts"]["statusCounts"], {"not-dispatched": 288}
        )
        self.assertEqual(len(projection.manifest["records"]), 288)
        self.assertLess(len(canonical(projection.manifest)), 2 * 1024 * 1024)
        self.assertTrue(
            all(len(raw) <= 2 * 1024 * 1024 for raw in projection.files.values())
        )


if __name__ == "__main__":
    unittest.main()
