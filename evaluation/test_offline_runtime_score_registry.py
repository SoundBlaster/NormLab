"""Score child identity/provenance checks with no MLflow SDK or writes."""

import copy
import unittest

import test_offline_runtime_reference as references
import test_offline_runtime_score as fixtures
from execution_mock import run_mock
from execution_test_support import ExecutionCase, canonical
from offline_bundle import identity
from runtime_archive_export import export_runtime_archive
from runtime_archive_reader import read_archive
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

    def unusual_arm(self, identifier, name):
        fixture = self.input(tasks=1)
        fixture.plan["arms"][0]["id"] = identifier
        fixture.plan["tasks"][0]["armId"] = identifier
        (fixture.folder / "plan.json").write_bytes(canonical(fixture.plan))
        runtime = self.output(name + "-runtime")
        run_mock(fixture.folder, runtime, self.script(fixture))
        target = self.output(name + "-archive")
        export_runtime_archive(runtime, target)
        archive = read_archive(target)
        view = score(archive, reference(archive, canonical(references.source(archive))))
        return target, archive, view

    def test_arbitrary_arm_ids_encode_into_bounded_backend_safe_metric_names(self):

        keys = []
        for number, arm in enumerate(
            ["provider:модель/arm", "a" * 4096, "arm-a", "arm_a"]
        ):
            _, archive, view = self.unusual_arm(arm, "arm-" + str(number))
            row = project_score(archive, view)
            component = row["payload"]["armMetricKeys"][arm]
            keys.append(component)
            self.assertIn(arm, row["payload"]["arms"])
            self.assertEqual(
                row["metrics"]["arms." + component + ".plannedQuestions"], 3
            )
            for key in row["metrics"]:
                self.assertLessEqual(len(key), 250)
                self.assertRegex(key, r"^[A-Za-z0-9_.-]+$")
            self.assertEqual(
                component, project_score(archive, view)["payload"]["armMetricKeys"][arm]
            )
        self.assertEqual(len(set(keys)), len(keys))


if __name__ == "__main__":
    unittest.main()
