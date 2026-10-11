"""Dataset integrity checks, not independent semantic labeling."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from audit_stage1 import audit
from harness import digest
from mellea_candidate import bound_fragments, parse_candidate

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/parking-pilot/stage1-audit"


class Stage1AuditTests(unittest.TestCase):
    def test_deterministic_candidate_audit(self):
        first = audit(FIXTURE / "experiment.json")
        self.assertEqual(first, audit(FIXTURE / "experiment.json"))
        self.assertEqual(
            first, json.loads((FIXTURE / "audit-report.json").read_bytes())
        )
        self.assertEqual(
            (first["cases"], first["families"], first["candidateRecords"]), (16, 13, 32)
        )
        self.assertEqual(first["liveCalls"], 0)
        self.assertIsNone(first["criticalErrorFreeRate"])
        self.assertFalse(first["independentReviewCompleted"])
        rows = {r["caseId"]: r for r in first["rows"]}
        self.assertEqual(rows["C006"]["sentenceProjection"], "lossy")
        self.assertEqual(rows["C006"]["claimProjection"], "representable")
        self.assertEqual(rows["C009"]["claimProjection"], "lossy")
        self.assertEqual(rows["C007"]["claimProjection"], "ambiguous")
        self.assertEqual(rows["C003"]["claimProjection"], "representable")
        self.assertIn("payment", rows["C004"]["notMentioned"])

    def test_tampering_and_semantic_status_boundaries(self):
        mutations = [
            ("sources", lambda d: d["cases"][0].update(sourceText="Changed")),
            ("sources", lambda d: d["cases"][0]["sentences"][0].update(start=True)),
            ("reviewer-only", lambda d: d["cases"][0].update(independentReview=True)),
            ("candidates", lambda d: d["records"][0]["claims"][0].update(start=1)),
            ("classification-schema", lambda d: d.update(type="array")),
        ]
        for artifact_name, mutate in mutations:
            with (
                self.subTest(artifact=artifact_name),
                tempfile.TemporaryDirectory() as temp,
            ):
                root = Path(temp) / "dataset"
                shutil.copytree(FIXTURE, root)
                path = root / f"{artifact_name}.json"
                value = json.loads(path.read_bytes())
                mutate(value)
                path.write_text(json.dumps(value, ensure_ascii=False))
                # Even a freshly rehashed artifact must pass semantic-contract integrity.
                manifest = json.loads((root / "experiment.json").read_bytes())
                manifest["artifacts"][artifact_name]["sha256"] = digest(
                    path.read_bytes()
                )
                (root / "experiment.json").write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    audit(root / "experiment.json")

    def test_oracle_projections_fit_real_v3_contract(self):
        report = audit(FIXTURE / "experiment.json")
        sources = json.loads((FIXTURE / "sources.json").read_bytes())["cases"]
        reviews = {
            r["caseId"]: r
            for r in json.loads((FIXTURE / "reviewer-only.json").read_bytes())["cases"]
        }
        for layout in ("sentenceProjection", "claimProjection"):
            for row in report["rows"]:
                if row[layout] != "representable":
                    continue
                case = next(c for c in sources if c["id"] == row["caseId"])
                groups = {}
                for claim in reviews[case["id"]]["claims"]:
                    key = (
                        claim["sentenceId"]
                        if layout == "sentenceProjection"
                        else claim["id"]
                    )
                    groups.setdefault(key, []).append(claim)
                fragments, decisions = [], {}
                for i, (key, claims) in enumerate(groups.items(), 1):
                    name = f"fragment_{i}"
                    quote = (
                        next(s["quote"] for s in case["sentences"] if s["id"] == key)
                        if layout == "sentenceProjection"
                        else claims[0]["quote"]
                    )
                    claim = claims[0]
                    fragments.append(
                        {
                            "fragmentId": name,
                            "quote": quote,
                            "attributes": {
                                "subject": claim["subject"],
                                "aboutEpisode": claim["episode"],
                                "speaker": claim["claimant"],
                            },
                        }
                    )
                    decisions[name] = {
                        "status": "classified",
                        "classifications": [
                            {
                                "predicate": c["predicate"],
                                "stance": c["stance"],
                                "valueText": c["quote"],
                            }
                            for c in claims
                        ],
                        "reason": "",
                    }
                _, frozen = bound_fragments(
                    {
                        "narrative": case["sourceText"],
                        "sourceDigest": case["sourceDigest"],
                    },
                    {"sourceDigest": case["sourceDigest"], "fragments": fragments},
                )
                flat, _ = parse_candidate(json.dumps({"results": decisions}), frozen)
                self.assertEqual(len(flat), len(reviews[case["id"]]["claims"]))

    def test_manifest_digest_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dataset"
            shutil.copytree(FIXTURE, root)
            path = root / "candidates.json"
            path.write_text(path.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                audit(root / "experiment.json")

    def test_model_artifacts_exclude_reviewer_labels(self):
        sources = json.loads((FIXTURE / "sources.json").read_bytes())
        candidates = json.loads((FIXTURE / "candidates.json").read_bytes())
        forbidden = {
            "expectation",
            "mutation",
            "focus",
            "notMentioned",
            "alternativeReadings",
            "independentReview",
        }

        def keys(value):
            if isinstance(value, dict):
                return set(value) | set().union(*(keys(v) for v in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(v) for v in value))
            return set()

        self.assertFalse(forbidden & keys(sources))
        self.assertFalse(forbidden & keys(candidates))

    def test_cli_without_site_packages(self):
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                str(FIXTURE.parents[2] / "evaluation/audit_stage1.py"),
                str(FIXTURE / "experiment.json"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(result.stdout)["liveCalls"], 0)


if __name__ == "__main__":
    unittest.main()
