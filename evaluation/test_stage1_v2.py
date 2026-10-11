"""V2 conventions and integrity regressions; no semantic-quality estimate."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from audit_stage1_v2 import audit
from harness import digest
from mellea_candidate import bound_fragments, parse_candidate

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/parking-pilot/stage1-audit-v2"


def read(name, root=FIXTURE):
    return json.loads((root / name).read_bytes())


class Stage1V2Tests(unittest.TestCase):
    def test_deterministic_report_and_evidence_boundary(self):
        report = audit(FIXTURE / "experiment.json")
        self.assertEqual(report, read("audit-report.json"))
        self.assertEqual(report, audit(FIXTURE / "experiment.json"))
        self.assertEqual(
            (report["cases"], report["families"], report["candidateRecords"]),
            (16, 13, 32),
        )
        self.assertEqual(report["liveCalls"], 0)
        self.assertIsNone(report["criticalErrorFreeRate"])
        self.assertFalse(report["independentReviewCompleted"])
        self.assertEqual(
            report["counts"]["claimProjection"], {"lossy": 15, "representable": 1}
        )

    def test_identity_scope_and_ambiguity_regressions(self):
        reviews = {c["caseId"]: c for c in read("reviewer-only.json")["cases"]}
        rows = {r["caseId"]: r for r in audit(FIXTURE / "experiment.json")["rows"]}
        for claim in reviews["C014"]["claims"]:
            self.assertIsNone(claim["subject"])
            self.assertIsNone(claim["aboutEntity"])
            self.assertEqual(claim["actor"], "person_1")
        self.assertIn("unresolved-subject-reference", rows["C014"]["claimIssues"])
        for cid in ("C002", "C013", "C014"):
            self.assertTrue(
                all(c["scope"] == "actor-payment" for c in reviews[cid]["claims"])
            )
            self.assertIn("no-typed-field:actor", rows[cid]["claimIssues"])
        self.assertEqual(reviews["C005"]["claims"][1]["scope"], "episode-payment")
        self.assertEqual(reviews["C016"]["claims"][0]["predicate"], "standing")
        self.assertIn("predicate-outside-catalog:standing", rows["C016"]["claimIssues"])
        for cid in ("C007", "C016"):
            self.assertTrue(rows[cid]["sourceAmbiguity"])
            self.assertEqual(rows[cid]["baselineExpectation"], "compatible")
            self.assertEqual(rows[cid]["claimProjection"], "lossy")

    def test_replaced_mutations_are_single_stance_changes(self):
        labels = {r["recordId"]: r for r in read("reviewer-only.json")["records"]}
        for rid in ("R007", "R015", "R019"):
            self.assertEqual(labels[rid]["mutation"]["field"], "stance")
            self.assertEqual(labels[rid]["expectation"], "incompatible")
        # audit also validates every candidate, including all 16 mutations.
        audit(FIXTURE / "experiment.json")

    def test_rehashed_invalid_artifacts_rejected(self):
        changes = [
            ("reviewer-only", lambda d: d["cases"][0].update(independentReview=True)),
            ("reviewer-only", lambda d: d["cases"][0].update(requiredTypedFields=[])),
            ("candidates", lambda d: d["records"][0]["claims"][0].update(start=True)),
            (
                "candidates",
                lambda d: d["records"][0]["claims"][0].update(scope="proposition"),
            ),
            ("conventions", lambda d: d.update(qualityMetricAllowed=True)),
            ("classification-schema", lambda d: d.update(type="array")),
        ]
        for name, mutate in changes:
            with self.subTest(artifact=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "dataset"
                shutil.copytree(FIXTURE, root)
                value = read(f"{name}.json", root)
                mutate(value)
                path = root / f"{name}.json"
                path.write_text(json.dumps(value, ensure_ascii=False))
                manifest = read("experiment.json", root)
                manifest["artifacts"][name]["sha256"] = digest(path.read_bytes())
                (root / "experiment.json").write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    audit(root / "experiment.json")

    def test_only_representable_case_fits_actual_consumer(self):
        case = next(c for c in read("sources.json")["cases"] if c["id"] == "C004")
        claims = next(
            c for c in read("reviewer-only.json")["cases"] if c["caseId"] == "C004"
        )["claims"]
        for sentence_layout in (True, False):
            fragments, results = [], {}
            groups = [claims] if sentence_layout else [[c] for c in claims]
            for i, group in enumerate(groups, 1):
                fid = f"fragment_{i}"
                first = group[0]
                fragments.append(
                    {
                        "fragmentId": fid,
                        "quote": case["sentences"][0]["quote"]
                        if sentence_layout
                        else first["quote"],
                        "attributes": {
                            "subject": first["subject"],
                            "aboutEpisode": first["episode"],
                            "speaker": first["claimant"],
                        },
                    }
                )
                results[fid] = {
                    "status": "classified",
                    "classifications": [
                        {
                            "predicate": c["predicate"],
                            "stance": c["stance"],
                            "valueText": c["quote"],
                        }
                        for c in group
                    ],
                    "reason": "",
                }
            _, frozen = bound_fragments(
                {"narrative": case["sourceText"], "sourceDigest": case["sourceDigest"]},
                {"sourceDigest": case["sourceDigest"], "fragments": fragments},
            )
            flat, _ = parse_candidate(json.dumps({"results": results}), frozen)
            self.assertEqual(len(flat), 2)
        # Unmentioned vehicles cannot be silently converted into production IDs.
        fragments[0]["attributes"]["subject"] = None
        with self.assertRaises(ValueError):
            bound_fragments(
                {"narrative": case["sourceText"], "sourceDigest": case["sourceDigest"]},
                {"sourceDigest": case["sourceDigest"], "fragments": fragments},
            )

    def test_model_artifacts_have_no_reviewer_metadata(self):
        forbidden = {
            "expectation",
            "baselineExpectation",
            "mutation",
            "requiredTypedFields",
            "focus",
            "alternativeReadings",
        }

        def keys(value):
            if isinstance(value, dict):
                return set(value) | set().union(*(keys(v) for v in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(v) for v in value))
            return set()

        for name in ("sources.json", "candidates.json"):
            self.assertFalse(forbidden & keys(read(name)))

    def test_cli_without_sdk_or_site_packages(self):
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                str(FIXTURE.parents[2] / "evaluation/audit_stage1_v2.py"),
                str(FIXTURE / "experiment.json"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(result.stdout)["liveCalls"], 0)


if __name__ == "__main__":
    unittest.main()
