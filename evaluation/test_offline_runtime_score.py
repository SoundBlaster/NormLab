"""Separate score views retain partial/failure denominators and exact source pins."""

import copy
import unittest

import test_offline_runtime_reference as fixtures
from execution_mock import run_mock
from execution_resume import continue_mock
from execution_test_support import ExecutionCase, canonical
from offline_bundle import identity
from runtime_archive_export import export_runtime_archive
from runtime_archive_reader import read_archive
from runtime_reference import reference
from runtime_score import score, verify_score


class ScoreTests(ExecutionCase):
    input = fixtures.ReferenceTests.input
    output = fixtures.ReferenceTests.output
    script = fixtures.ReferenceTests.script
    failure = staticmethod(fixtures.ReferenceTests.failure)
    paused = fixtures.ReferenceTests.paused
    request = fixtures.ReferenceTests.request
    orphan = fixtures.ReferenceTests.orphan
    archive = fixtures.ReferenceTests.archive

    def view(self, point="after-terminal", tasks=2, labels=None):
        runtime, root, _ = self.archive(point, tasks=tasks)
        archive = read_archive(root)
        labels = fixtures.source(archive) if labels is None else labels
        return (
            runtime,
            root,
            archive,
            score(archive, reference(archive, canonical(labels))),
        )

    def test_partial_then_complete_distinct_views_same_reference(self):
        runtime, root, before, view = self.view()
        self.assertEqual(view["summary"]["plannedQuestions"], 6)
        self.assertEqual(view["summary"]["scoredQuestions"], 3)
        self.assertEqual(view["summary"]["passedQuestions"], 2)
        self.assertEqual(view["summary"]["selectedUnevaluatedQuestions"], 3)
        self.assertEqual(view["predictionSeal"]["status"], "unsealed")
        original_bytes = dict(before.files)
        continue_mock(runtime, self.request(runtime))
        second = self.output("score-continued")
        export_runtime_archive(runtime, second)
        after = read_archive(second)
        new = score(after, reference(after, canonical(fixtures.source(after))))
        self.assertEqual(view["reference"], new["reference"])
        self.assertNotEqual(view["scoreId"], new["scoreId"])
        self.assertEqual(new["summary"]["scoredQuestions"], 6)
        self.assertEqual(new["predictionSeal"]["status"], "sealed")
        self.assertEqual(dict(before.files), original_bytes)
        self.assertEqual(verify_score(before, view), view)
        with self.assertRaises(ValueError):
            verify_score(after, view)

    def test_unknown_zero_scored_is_null_not_zero_accuracy(self):
        _, _, _, view = self.view("after-response", tasks=1)
        self.assertEqual(view["summary"]["scoredQuestions"], 0)
        self.assertIsNone(view["summary"]["agreementAmongScored"])
        self.assertEqual(view["summary"]["selectedUnevaluatedQuestions"], 3)
        self.assertEqual(view["rows"][0]["status"], "unknown-outcome")

    def test_partial_selection_keeps_unselected_denominator(self):
        _, root, _ = self.archive()
        archive = read_archive(root)
        labels = fixtures.source(archive)
        labels["expected"] = labels["expected"][:1]
        view = score(archive, reference(archive, canonical(labels)))
        self.assertEqual(view["summary"]["selectedQuestions"], 1)
        self.assertEqual(view["summary"]["unselectedQuestions"], 5)
        self.assertEqual(view["summary"]["agreementAmongScored"], 1)
        self.assertIsNone(view["criticalErrorFreeRate"])
        self.assertFalse(view["semanticQualityEvidence"])

    def test_rehashed_metrics_status_reference_policy_and_pins_rejected(self):
        _, _, archive, view = self.view()
        for mutation in ["metric", "status", "reference", "policy", "pins", "extra"]:
            changed = copy.deepcopy(view)
            if mutation == "metric":
                changed["summary"]["passedQuestions"] += 1
            elif mutation == "status":
                changed["rows"][0]["status"] = "refused"
            elif mutation == "reference":
                changed["reference"]["status"] = "human-adjudicated"
            elif mutation == "policy":
                changed["policy"]["noul"]["yesAtLeast"] = 0.5
            elif mutation == "pins":
                changed["scorerCodePins"]["runtime_score.py"] = "0" * 64
            else:
                changed["extra"] = True
            changed["scoreId"] = identity(
                "runtime-score", {k: v for k, v in changed.items() if k != "scoreId"}
            )
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                verify_score(archive, changed)

    def test_retry_failure_first_and_completed_final_are_separate(self):
        fixture = self.input(tasks=1)
        script = self.script(fixture)
        completed = script["tasks"][0]["attempts"][0]
        script["tasks"][0]["attempts"] = [self.failure(), completed]
        runtime = self.output("retry-score")
        run_mock(fixture.folder, runtime, script)
        target = self.output("retry-archive")
        export_runtime_archive(runtime, target)
        archive = read_archive(target)
        view = score(archive, reference(archive, canonical(fixtures.source(archive))))
        self.assertEqual(view["summary"]["firstScoredQuestions"], 0)
        self.assertEqual(view["summary"]["scoredQuestions"], 3)
        self.assertEqual(view["rows"][0]["attempts"], 2)
        self.assertEqual(view["runtimeCounts"]["attempts"], 2)
        view["policy"]["noul"]["yesAtLeast"] = 0
        fresh = score(archive, reference(archive, canonical(fixtures.source(archive))))
        self.assertEqual(fresh["policy"]["noul"]["yesAtLeast"], 0.8)

    def test_terminal_failure_retained_without_fabricated_prediction(self):
        fixture = self.input(tasks=1)
        script = self.script(fixture, attempts=[self.failure("refused")])
        runtime = self.output("refused-score")
        run_mock(fixture.folder, runtime, script)
        target = self.output("refused-archive")
        export_runtime_archive(runtime, target)
        archive = read_archive(target)
        view = score(archive, reference(archive, canonical(fixtures.source(archive))))
        self.assertEqual(view["summary"]["statusCounts"], {"refused": 1})
        self.assertEqual(view["summary"]["selectedUnevaluatedQuestions"], 3)
        self.assertTrue(
            all(q["prediction"] is None for q in view["rows"][0]["questions"])
        )


if __name__ == "__main__":
    unittest.main()
