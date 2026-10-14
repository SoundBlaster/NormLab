"""Source/review provenance and selected-question reference checks."""

import copy
import json
import unittest

import test_offline_runtime_mlflow_projection as fixtures
from execution_resume import continue_mock
from execution_test_support import ExecutionCase, canonical, sha
from runtime_archive_export import export_runtime_archive
from runtime_archive_reader import read_archive
from runtime_reference import REVIEW_SCHEMA, SOURCE_SCHEMA, reference


def source(archive, status="candidate-not-independent"):
    return {
        "schema": SOURCE_SCHEMA,
        "revision": "synthetic-review-v1",
        "status": status,
        "planDigest": archive.projection.manifest["planDigest"],
        "dataset": archive.snapshot.plan["dataset"],
        "expected": [
            {"taskKey": task["key"], "questionId": qid, "label": label}
            for task in archive.snapshot.plan["tasks"]
            for qid, label in [
                ("supported", "yes"),
                ("team", "billing"),
                ("urgency", 2),
            ]
        ],
    }


def review(labels):
    return canonical(
        {
            "schema": REVIEW_SCHEMA,
            "reviewer": "synthetic-reviewer",
            "method": "fixture-only",
            "sourceDigest": sha(canonical(labels)),
            "planDigest": labels["planDigest"],
            "dataset": labels["dataset"],
            "scope": "selected-questions-only",
            "approved": True,
        }
    )


class ReferenceTests(ExecutionCase):
    input = fixtures.ConsumerTests.input
    output = fixtures.ConsumerTests.output
    script = fixtures.ConsumerTests.script
    failure = staticmethod(fixtures.ConsumerTests.failure)
    paused = fixtures.ConsumerTests.paused
    request = fixtures.ConsumerTests.request
    orphan = fixtures.ConsumerTests.orphan
    archive = fixtures.ConsumerTests.archive

    def test_candidate_identity_provenance_and_defensive_copies(self):
        _, root, _ = self.archive()
        archive = read_archive(root)
        raw = canonical(source(archive))
        first = reference(archive, raw)
        self.assertEqual(first.document, reference(archive, raw).document)
        self.assertEqual(first.document["provenance"]["source"]["sha256"], sha(raw))
        changed = first.document
        changed["status"] = "human-adjudicated"
        self.assertEqual(first.document["status"], "candidate-not-independent")
        with self.assertRaises(TypeError):
            first.files["foreign"] = b""

    def test_reference_reusable_across_capture_revisions(self):
        runtime, root, _ = self.archive()
        before = read_archive(root)
        raw = canonical(source(before))
        continue_mock(runtime, self.request(runtime))
        second = self.output("reference-continued")
        export_runtime_archive(runtime, second)
        self.assertEqual(
            reference(before, raw).document,
            reference(read_archive(second), raw).document,
        )

    def test_human_declaration_requires_bound_review_but_is_not_authenticated(self):
        _, root, _ = self.archive()
        archive = read_archive(root)
        labels = source(archive, "human-adjudicated")
        with self.assertRaises(ValueError):
            reference(archive, canonical(labels))
        result = reference(archive, canonical(labels), [review(labels)]).document
        self.assertFalse(result["reviewAuthenticated"])
        self.assertFalse(result["semanticQualityEvidence"])
        candidate = source(archive)
        with self.assertRaises(ValueError):
            reference(archive, canonical(candidate), [review(candidate)])

    def test_wrong_plan_coverage_labels_and_duplicate_selection_rejected(self):
        _, root, _ = self.archive()
        archive = read_archive(root)
        base = source(archive)
        for key in [
            "plan",
            "dataset",
            "duplicate",
            "task",
            "question",
            "bool",
            "empty",
        ]:
            labels = copy.deepcopy(base)
            if key == "plan":
                labels["planDigest"] = "0" * 64
            elif key == "dataset":
                labels["dataset"]["revision"] = "other"
            elif key == "duplicate":
                labels["expected"].append(labels["expected"][0])
            elif key == "task":
                labels["expected"][0]["taskKey"] = "foreign"
            elif key == "question":
                labels["expected"][0]["questionId"] = "foreign"
            elif key == "bool":
                labels["expected"][2]["label"] = True
            else:
                labels["expected"] = []
            with self.subTest(key=key), self.assertRaises(ValueError):
                reference(archive, canonical(labels))

    def test_review_digest_scope_duplicates_and_caps_rejected(self):
        _, root, _ = self.archive()
        archive = read_archive(root)
        labels = source(archive, "human-adjudicated")
        for field, value in [
            ("sourceDigest", "0" * 64),
            ("scope", "whole-case"),
            ("approved", 1),
        ]:
            altered = json.loads(review(labels))
            altered[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                reference(archive, canonical(labels), [canonical(altered)])
        with self.assertRaises(ValueError):
            reference(archive, canonical(labels), [review(labels)] * 2)
        with self.assertRaises(ValueError):
            reference(archive, b" " * (2 * 1024 * 1024 + 1))


if __name__ == "__main__":
    unittest.main()
