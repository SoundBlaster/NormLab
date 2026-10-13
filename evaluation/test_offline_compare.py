"""Saved-view comparison regressions: policies, exclusions and portable CLI."""

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import test_offline_bundle as bundle_helpers
from offline_compare import SavedView, compare, markdown
from test_offline_bundle import FIXTURE, READER_FILES, ROOT, load


class OfflineCompareTests(unittest.TestCase):
    cli = classmethod(bundle_helpers.OfflineBundleTests.cli.__func__)

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.folders = {}
        for name, args in (
            ("s13", ["s13"]),
            (
                "classification",
                [
                    "classification",
                    FIXTURE / "experiment.json",
                    "--labels",
                    FIXTURE / "reviewer-labels.json",
                ],
            ),
            ("unlabeled", ["classification", FIXTURE / "experiment.json"]),
        ):
            target = cls.root / name
            result = cls.cli(*args, "--output", target)
            if result.returncode:
                raise AssertionError(result.stderr)
            cls.folders[name] = target
        cls.views = {name: SavedView(path) for name, path in cls.folders.items()}

    def test_s13_self_preserves_denominators_and_reused_evidence(self):
        report = compare(self.views["s13"], self.views["s13"])
        summary = report["summary"]
        self.assertEqual(summary["matchedTasks"], 453)
        self.assertEqual(summary["evaluatedPairs"], 13)
        self.assertEqual(summary["notEvaluated"], 440)
        self.assertEqual(summary["unchanged"], 13)
        self.assertEqual(summary["selectedReferenceAgreement"]["baselineNumerator"], 9)
        self.assertEqual(
            summary["plannedStatusCounts"]["baseline"]["not-dispatched"], 434
        )
        self.assertTrue(report["sameRun"] and report["sameCaptureSet"])
        self.assertTrue(report["sameScoreView"])
        self.assertEqual(report["executionIndependence"], "not-established")
        self.assertIsNone(report["criticalErrorFreeRate"])
        self.assertIsNone(report["uncertaintyIntervals"])

    def test_legacy_context_strict_and_explicit_diagnostic(self):
        view = self.views["classification"]
        strict = compare(view, view)
        self.assertEqual(strict["summary"]["evaluatedPairs"], 0)
        self.assertEqual(strict["summary"]["notEvaluated"], 3)
        self.assertIsNone(
            strict["summary"]["selectedReferenceAgreement"]["candidateMinusBaseline"]
        )
        diagnostic = compare(view, view, "legacy-logical-diagnostic")
        self.assertEqual(diagnostic["summary"]["evaluatedPairs"], 2)
        self.assertEqual(diagnostic["summary"]["notEvaluated"], 1)
        self.assertEqual(diagnostic["summary"]["uniqueCases"], 1)

    def test_missing_reference_is_not_a_false_quality_score(self):
        report = compare(
            self.views["classification"],
            self.views["unlabeled"],
            "legacy-logical-diagnostic",
        )
        self.assertEqual(report["summary"]["notEvaluated"], 3)
        self.assertEqual(report["summary"]["evaluatedPairs"], 0)
        self.assertTrue(
            all("reference-unavailable" in r["reasons"] for r in report["rows"])
        )

    def test_global_reasons_visible_without_any_matched_rows(self):
        report = compare(self.views["classification"], self.views["s13"])
        self.assertEqual(report["summary"]["matchedTasks"], 0)
        self.assertEqual(report["summary"]["incompatible"], 0)
        self.assertEqual(report["summary"]["baselineOnly"], 3)
        self.assertEqual(report["summary"]["candidateOnly"], 453)
        text = markdown(report)
        self.assertIn("## Global incompatibilities", text)
        self.assertIn("counts matched rows only", text)
        for reason in report["globalIncompatibilities"]:
            self.assertIn(f"- `{reason}`", text)
        self.assertNotIn(
            "## Global incompatibilities",
            markdown(compare(self.views["s13"], self.views["s13"])),
        )

    def test_declared_provider_variable_and_policy_binding(self):
        # Pure comparison-policy checks on an already verified view projection.
        left = self.views["s13"]
        right = copy.deepcopy(left)
        right.envelope["experiment"]["provider"] = {"model": "synthetic-variable"}
        excluded = compare(left, right)
        self.assertEqual(excluded["summary"]["incompatible"], 453)
        accepted = compare(left, right, vary=["provider"])
        self.assertEqual(accepted["summary"]["evaluatedPairs"], 13)
        self.assertNotEqual(excluded["policyDigest"], accepted["policyDigest"])
        right.envelope["experiment"]["policy"]["orderSeed"] = "different-seed"
        self.assertEqual(
            compare(left, right, vary=["provider"])["summary"]["incompatible"], 453
        )

    def test_strict_binding_mismatches_remain_incompatible(self):
        left = self.views["s13"]
        for field in ("dataset", "scorer", "reference", "task", "context"):
            with self.subTest(field=field):
                right = copy.deepcopy(left)
                if field == "dataset":
                    right.envelope["dataset"]["digest"] = "0" * 64
                elif field == "scorer":
                    right.envelope["score"]["scorer"]["id"] = "different"
                elif field == "reference":
                    right.reference["revision"] = "different"
                else:
                    for task in right.tasks.values():
                        if field == "task":
                            task["taskDigest"] = "0" * 64
                        else:
                            task["context"]["policy"] = "different"
                report = compare(left, right, "legacy-logical-diagnostic")
                self.assertEqual(report["summary"]["incompatible"], 453)
                self.assertEqual(report["summary"]["evaluatedPairs"], 0)

    def test_unpaired_keys_retained_in_both_directions(self):
        left = self.views["classification"]
        right = copy.deepcopy(left)
        right.tasks.pop(next(iter(right.tasks)))
        forward = compare(left, right, "legacy-logical-diagnostic")
        backward = compare(right, left, "legacy-logical-diagnostic")
        self.assertEqual(forward["summary"]["baselineOnly"], 1)
        self.assertEqual(backward["summary"]["candidateOnly"], 1)
        self.assertEqual(forward["summary"]["unionTasks"], 3)
        self.assertEqual(forward["summary"]["matchedTasks"], 2)

    def test_offsetting_regression_and_rescue_are_not_hidden(self):
        left = self.views["s13"]
        right = copy.deepcopy(left)
        original = right.outcome

        def changed(task):
            outcome = original(task)
            if task["originalId"] in {"S13-1-046", "S13-1-091"}:
                outcome["selectedReferencePass"] = not outcome["selectedReferencePass"]
            return outcome

        right.outcome = changed
        report = compare(left, right)
        self.assertEqual(report["summary"]["regressions"], 1)
        self.assertEqual(report["summary"]["rescues"], 1)
        self.assertEqual(report["summary"]["unchanged"], 11)
        self.assertEqual(
            report["summary"]["selectedReferenceAgreement"]["candidateMinusBaseline"], 0
        )

    def test_invalid_policy_rejected(self):
        for kwargs in ({"context": "guess"}, {"vary": ["dataset"]}):
            with self.assertRaises(ValueError):
                compare(self.views["s13"], self.views["s13"], **kwargs)

    def test_cli_portable_deterministic_and_exclusive_output(self):
        portable = self.root / "portable"
        portable.mkdir()
        for name in (*READER_FILES, "offline_compare.py"):
            shutil.copyfile(ROOT / "evaluation" / name, portable / name)
        outputs = []
        for name, script in (
            ("repository", ROOT / "evaluation/offline_compare.py"),
            ("portable", portable / "offline_compare.py"),
        ):
            output = self.root / (name + "-report")
            result = self.cli(
                self.folders["s13"],
                self.folders["s13"],
                "--output",
                output,
                script=script,
                cwd=portable,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(output)
        for filename in ("report.json", "report.md"):
            self.assertEqual(
                (outputs[0] / filename).read_bytes(),
                (outputs[1] / filename).read_bytes(),
            )
        before = (outputs[0] / "report.json").read_bytes()
        rejected = self.cli(
            self.folders["s13"],
            self.folders["s13"],
            "--output",
            outputs[0],
            script=portable / "offline_compare.py",
        )
        self.assertEqual(rejected.returncode, 1)
        self.assertEqual((outputs[0] / "report.json").read_bytes(), before)
        self.assertEqual(json.loads(before)["inferenceCallsExecuted"], 0)

    def test_cli_rejects_artifact_tampering(self):
        damaged = self.root / "damaged"
        shutil.copytree(self.folders["classification"], damaged)
        envelope = load(damaged / "bundle.json")
        (damaged / envelope["records"][0]["path"]).write_bytes(b"{}")
        result = self.cli(
            damaged,
            self.folders["classification"],
            script=ROOT / "evaluation/offline_compare.py",
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            result.stderr.strip(), "Offline comparison validation/export failed"
        )


if __name__ == "__main__":
    unittest.main()
