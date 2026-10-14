"""Score child identity/provenance checks with no MLflow SDK or writes."""

import copy
import unittest

import test_offline_runtime_reference as references
import test_offline_runtime_score as fixtures
from execution_test_support import ExecutionCase, canonical
from offline_bundle import identity
from runtime_mlflow_projection import project
from runtime_reference import reference
from runtime_score import score
from runtime_score_mlflow_projection import project_score


class ScoreRegistryTests(ExecutionCase):
    input = fixtures.ScoreTests.input
    output = fixtures.ScoreTests.output
    script = fixtures.ScoreTests.script
    failure = staticmethod(fixtures.ScoreTests.failure)
    paused = fixtures.ScoreTests.paused
    request = fixtures.ScoreTests.request
    orphan = fixtures.ScoreTests.orphan
    archive = fixtures.ScoreTests.archive
    view = fixtures.ScoreTests.view

    def test_repeat_child_parent_and_explicit_selected_metrics(self):
        _, _, archive, view = self.view()
        row = project_score(archive, view)
        self.assertEqual(row, project_score(archive, view))
        self.assertEqual(row["parentKey"], project(archive)[1]["key"])
        self.assertEqual(row["metrics"]["selected.plannedQuestions"], 6)
        self.assertNotIn("selected.criticalErrorFreeRate", row["metrics"])
        self.assertEqual(row["params"]["reference_status"], "candidate-not-independent")
        self.assertFalse(row["payload"]["semanticQualityEvidence"])

    def test_reference_revision_adds_child_without_changing_capture(self):
        _, _, archive, view = self.view()
        labels = references.source(archive)
        labels["revision"] = "synthetic-review-v2"
        labels["expected"][0]["label"] = "no"
        second = score(archive, reference(archive, canonical(labels)))
        a, b = project_score(archive, view), project_score(archive, second)
        self.assertEqual(a["parentKey"], b["parentKey"])
        self.assertNotEqual(a["key"], b["key"])
        self.assertNotEqual(a["params"]["reference_id"], b["params"]["reference_id"])

    def test_wrong_capture_and_rehashed_score_rejected(self):
        _, _, archive, view = self.view()
        changed = copy.deepcopy(view)
        changed["summary"]["passedQuestions"] += 1
        changed["scoreId"] = identity(
            "runtime-score", {k: v for k, v in changed.items() if k != "scoreId"}
        )
        with self.assertRaises(ValueError):
            project_score(archive, changed)
        _, _, other, _ = self.view("after-response", tasks=1)
        with self.assertRaises(ValueError):
            project_score(other, view)


if __name__ == "__main__":
    unittest.main()
