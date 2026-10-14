"""SDK-free score import preparation and invalid-input pre-write rejection."""

import copy
import unittest

import test_offline_runtime_score as fixtures
from execution_test_support import ExecutionCase, canonical
from import_runtime_mlflow import run


class ScoreImportPreparationTests(ExecutionCase):
    input = fixtures.ScoreTests.input
    output = fixtures.ScoreTests.output
    script = fixtures.ScoreTests.script
    failure = staticmethod(fixtures.ScoreTests.failure)
    paused = fixtures.ScoreTests.paused
    request = fixtures.ScoreTests.request
    orphan = fixtures.ScoreTests.orphan
    archive = fixtures.ScoreTests.archive
    view = fixtures.ScoreTests.view

    def test_dry_run_includes_score_child_without_storage(self):
        _, root, _, view = self.view()
        score_path = self.root / "selected-score.json"
        score_path.write_bytes(canonical(view))
        storage = self.root / "absent-registry"
        prepared = run(root, storage, dry_run=True, score_path=score_path)
        self.assertFalse(storage.exists())
        self.assertEqual(prepared["records"][-1]["kind"], "runtime-score")
        self.assertEqual(
            prepared["records"][-1]["parentKey"], prepared["records"][1]["key"]
        )
        self.assertEqual(prepared["registryWritesExecuted"], 0)

    def test_invalid_score_rejected_before_registry_creation(self):
        _, root, _, view = self.view()
        altered = copy.deepcopy(view)
        altered["summary"]["passedQuestions"] += 1
        score_path = self.root / "bad-score.json"
        score_path.write_bytes(canonical(altered))
        storage = self.root / "absent-registry"
        with self.assertRaises(ValueError):
            run(root, storage, score_path=score_path)
        self.assertFalse(storage.exists())


if __name__ == "__main__":
    unittest.main()
