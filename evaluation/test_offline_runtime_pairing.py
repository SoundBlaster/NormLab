"""Logical identity and conservative runtime compatibility checks."""

import unittest

import test_offline_runtime_score as fixtures
from execution_test_support import ExecutionCase
from runtime_pairing import RuntimeView, global_reasons, pair_reasons, policy


class PairingTests(ExecutionCase):
    input = fixtures.ScoreTests.input
    output = fixtures.ScoreTests.output
    script = fixtures.ScoreTests.script
    failure = staticmethod(fixtures.ScoreTests.failure)
    paused = fixtures.ScoreTests.paused
    request = fixtures.ScoreTests.request
    orphan = fixtures.ScoreTests.orphan
    archive = fixtures.ScoreTests.archive
    view = fixtures.ScoreTests.view

    def test_same_view_has_all_questions_and_exact_compatibility(self):
        _, _, archive, score = self.view()
        view = RuntimeView(archive, score)
        self.assertEqual(len(view.rows), 6)
        selected = policy()
        self.assertEqual(global_reasons(view, view, selected), [])
        for row in view.rows.values():
            self.assertEqual(pair_reasons(view, view, row, row, selected, []), [])

    def test_policy_requires_explicit_supported_unique_variations(self):
        self.assertEqual(
            policy("same-protocol-body", ["tactic", "provider"])["vary"],
            ["provider", "tactic"],
        )
        for args in [
            ("guess-semantic", ()),
            ("strict-wire", ["provider", "provider"]),
            ("strict-wire", ["dataset"]),
        ]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                policy(*args)

    def test_dataset_and_reference_revision_differences_are_reasons(self):
        _, _, archive, score = self.view()
        left, right = RuntimeView(archive, score), RuntimeView(archive, score)
        right.plan["dataset"]["revision"] = "other"
        right.score["reference"]["revision"] = "other"
        reasons = global_reasons(left, right, policy())
        self.assertIn("dataset-differs", reasons)
        self.assertIn("reference-revision-differs", reasons)


if __name__ == "__main__":
    unittest.main()
