"""Integrity of saved independent review; not proof of semantic ground truth."""

import json
import unittest
from collections import Counter
from pathlib import Path

from harness import digest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "fixtures/parking-pilot/stage1-independent-review"
DATASET = ROOT / "fixtures/parking-pilot/stage1-audit"


def read(name, folder=BUNDLE):
    return json.loads((folder / name).read_bytes())


class IndependentReviewTests(unittest.TestCase):
    def test_saved_hashes_and_dataset_binding(self):
        manifest = read("manifest.json")
        self.assertEqual(
            manifest["datasetManifestDigest"],
            digest((DATASET / "experiment.json").read_bytes()),
        )
        self.assertEqual(len(manifest["artifactHashes"]), 8)
        for name, expected in manifest["artifactHashes"].items():
            self.assertEqual(digest((BUNDLE / name).read_bytes()), expected)
        for entry in read("review.json")["inputs"]:
            self.assertEqual(
                digest((ROOT / entry["path"]).read_bytes()), entry["sha256"]
            )

    def test_phase1_source_coverage_and_freeze(self):
        blind, review = read("blind.json"), read("review.json")
        source_only = {c["id"]: c["sourceText"] for c in read("source-only.json")}
        self.assertEqual(len(source_only), 16)
        self.assertEqual(
            {c["case_id"]: c["source_text"] for c in blind["cases"]}, source_only
        )
        self.assertEqual(
            review["blind_artifact"]["sha256"],
            digest((BUNDLE / "blind.json").read_bytes()),
        )
        self.assertTrue(review["blind_artifact"]["frozen_before_comparison"])
        self.assertFalse(review["blind_artifact"]["modified_after_freeze"])

    def test_all_cases_and_record_judgments(self):
        review = read("review.json")
        cases = read("sources.json", DATASET)["cases"]
        records = read("candidates.json", DATASET)["records"]
        self.assertEqual(
            {c["case_id"] for c in review["cases"]}, {c["id"] for c in cases}
        )
        self.assertEqual(len(review["cases"]), 16)
        self.assertEqual(
            {r["record_id"]: r["case_id"] for r in review["records"]},
            {r["id"]: r["caseId"] for r in records},
        )
        self.assertEqual(len(review["records"]), 32)
        counts = Counter(r["expectation_judgment"] for r in review["records"])
        self.assertEqual(
            dict(counts), review["summary"]["record_expectation_judgment_counts"]
        )
        self.assertEqual(counts, {"agree": 30, "revise": 1, "ambiguous": 1})

    def test_literal_evidence_spans(self):
        checked = 0

        def walk(value, source):
            nonlocal checked
            if isinstance(value, dict):
                if {"quote", "start", "end"} <= set(value):
                    self.assertIs(type(value["start"]), int)
                    self.assertIs(type(value["end"]), int)
                    self.assertTrue(0 <= value["start"] < value["end"] <= len(source))
                    self.assertEqual(
                        source[value["start"] : value["end"]], value["quote"]
                    )
                    checked += 1
                for item in value.values():
                    walk(item, source)
            elif isinstance(value, list):
                for item in value:
                    walk(item, source)

        for case in read("blind.json")["cases"]:
            walk(case, case["source_text"])
        self.assertEqual(checked, 25)
        sources = {
            c["id"]: c["sourceText"] for c in read("sources.json", DATASET)["cases"]
        }
        for record in read("candidates.json", DATASET)["records"]:
            walk(record["claims"], sources[record["caseId"]])
        self.assertEqual(checked, 71)
        for issue in read("review.json")["issues"]:
            for evidence in issue["evidence"]:
                walk(evidence, sources[evidence["case_id"]])

    def test_review_is_not_expert_or_quality_promotion(self):
        manifest = read("manifest.json")
        self.assertFalse(manifest["humanExpertGroundTruth"])
        self.assertEqual(manifest["gate"]["status"], "hold")
        self.assertFalse(manifest["gate"]["resolutionsApplied"])
        self.assertFalse(manifest["gate"]["expertLabelsPromoted"])
        self.assertIsNone(manifest["gate"]["criticalErrorFreeRate"])
        self.assertFalse(
            read("review.json")["recommended_gate"][
                "approved_for_fair_model_comparison"
            ]
        )
        self.assertEqual(
            {i["id"] for i in read("review.json")["issues"]},
            {"IR-001", "IR-002", "IR-003", "IR-004", "IR-005"},
        )
        self.assertEqual(
            read("reviewer-only.json", DATASET)["labelStatus"],
            "candidate-not-independent",
        )


if __name__ == "__main__":
    unittest.main()
