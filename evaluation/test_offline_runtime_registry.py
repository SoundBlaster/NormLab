"""Revision-aware registry planning, without SDK or actual registry writes."""

import copy
import json
import unittest

import test_offline_mock_execution as previous
import test_offline_mock_resume as continuation
from execution_mock import run_mock
from execution_resume import continue_mock
from execution_test_support import ROOT, ExecutionCase, cli
from runtime_capture import capture_runtime
from runtime_export import prepare_export
from runtime_registry import registry_dry_run, verify_registry_plan


class RegistryTests(ExecutionCase):
    input = previous.MockExecutionTests.input
    output = previous.MockExecutionTests.output
    script = previous.MockExecutionTests.script
    failure = staticmethod(previous.MockExecutionTests.failure)
    paused = continuation.ResumeTests.paused
    request = continuation.ResumeTests.request

    def test_same_revision_reuses_all_keys(self):
        fixture = self.input(tasks=1)
        root = self.output("complete")
        run_mock(fixture.folder, root, self.script(fixture))
        projection = prepare_export(capture_runtime(root))
        first = registry_dry_run(projection)
        second = registry_dry_run(projection, first["nodes"])
        self.assertEqual(first["nodes"], second["nodes"])
        self.assertTrue(
            all(action["action"] == "reuse" for action in second["actions"])
        )
        self.assertEqual(second["registryWritesExecuted"], 0)
        self.assertEqual(second["inferenceCallsExecuted"], 0)
        self.assertIsNone(second["score"])
        self.assertEqual(verify_registry_plan(root, second, first["nodes"]), second)

    def test_new_revision_reuses_execution_retains_old_capture(self):
        _, root, _, _ = self.paused("after-terminal")
        before = registry_dry_run(prepare_export(capture_runtime(root)))
        receipts = copy.deepcopy(before["nodes"])
        continue_mock(root, self.request(root))
        after = registry_dry_run(prepare_export(capture_runtime(root)), receipts)
        self.assertEqual(before["nodes"][0], after["nodes"][0])
        self.assertEqual(after["actions"][0]["action"], "reuse")
        self.assertTrue(
            all(action["action"] == "create" for action in after["actions"][1:])
        )
        self.assertNotEqual(before["nodes"][1]["key"], after["nodes"][1]["key"])
        self.assertEqual(receipts, before["nodes"])
        self.assertEqual(before["metrics"]["attempts"], 1)
        self.assertEqual(after["metrics"]["attempts"], 2)

    def test_partial_and_unknown_have_no_seal_or_score_node(self):
        _, root, _, _ = self.paused("after-response")
        plan = registry_dry_run(prepare_export(capture_runtime(root)))
        self.assertEqual(
            [node["kind"] for node in plan["nodes"]],
            ["execution", "capture", "projection"],
        )
        self.assertEqual(plan["metrics"]["unknownUsageAttempts"], 1)
        self.assertEqual(plan["metrics"]["plannedTasks"], 2)
        self.assertIsNone(plan["actualCost"])
        self.assertFalse(plan["semanticQualityEvidence"])

    def test_receipt_conflicts_duplicates_and_wrong_kind_reject(self):
        _, root, _, _ = self.paused("after-terminal")
        projection = prepare_export(capture_runtime(root))
        first = registry_dry_run(projection)
        for field, value in (
            ("bindingDigest", "0" * 64),
            ("parentKey", "other-parent"),
            ("kind", "prediction-seal"),
        ):
            receipts = copy.deepcopy(first["nodes"])
            receipts[0][field] = value
            with self.assertRaises(ValueError):
                registry_dry_run(projection, receipts)
        with self.assertRaises(ValueError):
            registry_dry_run(projection, first["nodes"] + [first["nodes"][0]])

    def test_changed_actions_or_metrics_reject(self):
        _, root, _, _ = self.paused("after-terminal")
        original = registry_dry_run(prepare_export(capture_runtime(root)))
        for field, value in (
            ("actions", []),
            ("metrics", {}),
            ("registryWritesExecuted", 1),
            ("releaseApproved", True),
        ):
            changed = copy.deepcopy(original)
            changed[field] = value
            with self.assertRaises(ValueError):
                verify_registry_plan(root, changed)

    def test_cli_registry_plan_read_only_and_sdk_free(self):
        _, root, _, _ = self.paused("after-terminal")
        result = cli(
            "registry-plan", root, script=ROOT / "evaluation/runtime_capture_cli.py"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            registry_dry_run(prepare_export(capture_runtime(root))),
        )


if __name__ == "__main__":
    unittest.main()
