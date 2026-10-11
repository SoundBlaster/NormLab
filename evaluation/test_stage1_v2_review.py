"""Integrity of nonblind regression evidence; not semantic ground truth."""

import json
import unittest
from collections import Counter
from pathlib import Path

from harness import digest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "fixtures/parking-pilot/stage1-independent-review-v2"
DATASET = ROOT / "fixtures/parking-pilot/stage1-audit-v2"


def read(name, folder=BUNDLE):
    return json.loads((folder / name).read_bytes())


class Stage1V2ReviewTests(unittest.TestCase):
    def test_all_saved_bindings(self):
        manifest = read("manifest.json")
        self.assertEqual(
            manifest["datasetManifestDigest"],
            digest((DATASET / "experiment.json").read_bytes()),
        )
        for name, expected in manifest["artifactHashes"].items():
            self.assertEqual(digest((BUNDLE / name).read_bytes()), expected)
        for name, expected in manifest["integrationPins"].items():
            self.assertEqual(digest((ROOT / name).read_bytes()), expected)
        self.assertEqual(len(read("review.json")["input_sha256"]), 4)
        for entry in read("review.json")["input_sha256"]:
            self.assertEqual(
                digest((ROOT / entry["path"]).read_bytes()), entry["sha256"]
            )

    def test_complete_record_and_case_coverage(self):
        review = read("review.json")
        labels = {
            r["recordId"]: r for r in read("reviewer-only.json", DATASET)["records"]
        }
        records = {r["record_id"]: r for r in review["record_reviews"]}
        self.assertEqual(len(records), 32)
        self.assertEqual(records.keys(), labels.keys())
        self.assertEqual(
            Counter(r["judgment"] for r in records.values()), {"agree": 32}
        )
        self.assertEqual(review["coverage"]["judgments"], {"agree": 32})
        for rid, record in records.items():
            self.assertEqual(record["case_id"], labels[rid]["caseId"])
            self.assertEqual(record["declared_expectation"], labels[rid]["expectation"])
            self.assertEqual(record["reviewer_expectation"], labels[rid]["expectation"])
            self.assertEqual(record["mutation"], labels[rid]["mutation"])
            self.assertTrue(record["declared_mutation_matches_observed_delta"])
        self.assertEqual(len(review["case_reviews"]), 16)
        self.assertEqual(
            {c["case_id"] for c in review["case_reviews"]},
            {c["id"] for c in read("sources.json", DATASET)["cases"]},
        )

    def test_literal_review_evidence(self):
        sources = {
            c["id"]: c["sourceText"] for c in read("sources.json", DATASET)["cases"]
        }
        count = 0

        def walk(value, case=None):
            nonlocal count
            if isinstance(value, dict):
                case = value.get("case_id", case)
                if {"quote", "start", "end"} <= set(value):
                    source = sources[case]
                    self.assertIs(type(value["start"]), int)
                    self.assertIs(type(value["end"]), int)
                    self.assertTrue(0 <= value["start"] < value["end"] <= len(source))
                    self.assertEqual(
                        source[value["start"] : value["end"]], value["quote"]
                    )
                    count += 1
                for item in value.values():
                    walk(item, case)
            elif isinstance(value, list):
                for item in value:
                    walk(item, case)

        walk(read("review.json"))
        self.assertEqual(
            count, read("manifest.json")["provenance"]["evidenceSpansChecked"]
        )
        self.assertGreaterEqual(count, 32)

    def test_disposition_and_audit_consistency(self):
        review, manifest = read("review.json"), read("manifest.json")
        self.assertEqual(review["new_issues"], [])
        resolved = {
            i["v1_issue"]
            for i in review["issue_resolutions"]
            if i["status"] == "resolved"
        }
        self.assertTrue(set(manifest["disposition"]["resolvedIssueIds"]) <= resolved)
        self.assertFalse(manifest["provenance"]["freshBlindReview"])
        self.assertFalse(manifest["provenance"]["humanExpertGroundTruth"])
        self.assertFalse(manifest["disposition"]["labelsPromotedToExpert"])
        self.assertFalse(manifest["disposition"]["productionPromotion"])
        self.assertIsNone(manifest["disposition"]["criticalErrorFreeRate"])
        self.assertEqual(manifest["provenance"]["paidProviderCalls"], 0)
        self.assertFalse(review["gate_recommendation"]["model_quality_metric_approved"])
        audit_rows = {
            r["caseId"]: r for r in read("audit-report.json", DATASET)["rows"]
        }
        for row in review["representability_review"]["rows"]:
            actual = audit_rows[row["case_id"]]
            for layout in ("sentence", "claim"):
                self.assertEqual(
                    row[f"{layout}_projection"], actual[f"{layout}Projection"]
                )
                self.assertEqual(row[f"{layout}_issues"], actual[f"{layout}Issues"])


if __name__ == "__main__":
    unittest.main()
