"""Offline protocol contracts; no provider construction or semantic judge."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter, defaultdict
from pathlib import Path
from unittest.mock import patch

import plan_stage1_comparison as planner
from harness import artifact

FIXTURE = planner.ROOT / "fixtures/parking-pilot/stage1-comparison-v1"
MANIFEST = FIXTURE / "experiment.json"


class Stage1ComparisonTests(unittest.TestCase):
    def test_deterministic_profiles_and_caps(self):
        archived = json.loads((FIXTURE / "plan-summaries.json").read_bytes())
        for profile, calls, cases, families in (
            ("pilot", 24, 2, 2),
            ("corpus", 192, 16, 13),
            ("decisions-pilot", 12, 2, 2),
        ):
            plan = planner.prepare(MANIFEST, profile)
            summary = planner.summary(plan)
            self.assertEqual(summary, archived[profile])
            self.assertEqual(plan, planner.prepare(MANIFEST, profile))
            self.assertEqual(
                (summary["plannedCalls"], summary["cases"], summary["families"]),
                (calls, cases, families),
            )
            self.assertEqual(summary["plannedQuestions"], calls)
            self.assertEqual(summary["callsExecuted"], 0)
            self.assertEqual(summary["budget"]["authorizedCalls"], 0)
            self.assertIsNone(summary["criticalErrorFreeRate"])
            self.assertIsNone(summary["budget"]["monetaryCap"])

    def test_same_task_across_arms_and_repeats(self):
        jobs = planner.prepare(MANIFEST, "corpus")["jobs"]
        by_record = defaultdict(list)
        for job in jobs:
            by_record[job["recordId"]].append(job)
            self.assertEqual(
                job["taskDigest"],
                planner.digest(planner.canonical(job["task"]).encode()),
            )
        self.assertEqual(len(by_record), 32)
        for group in by_record.values():
            self.assertEqual(len(group), 6)
            self.assertEqual(len({j["taskDigest"] for j in group}), 1)
            self.assertEqual({j["repeat"] for j in group}, {1, 2, 3})

    def test_fresh_context_counterbalanced_order_and_original_claims(self):
        jobs = planner.prepare(MANIFEST, "corpus")["jobs"]
        self.assertEqual(len({j["contextId"] for j in jobs}), 192)
        sources = {
            c["id"]: c
            for c in json.loads(
                (FIXTURE.parent / "stage1-audit-v2/sources.json").read_bytes()
            )["cases"]
        }
        records = {
            r["id"]: r
            for r in json.loads(
                (FIXTURE.parent / "stage1-audit-v2/candidates.json").read_bytes()
            )["records"]
        }
        starts = Counter()
        for first, second in zip(jobs[::2], jobs[1::2]):
            self.assertEqual(
                (first["recordId"], first["repeat"]),
                (second["recordId"], second["repeat"]),
            )
            self.assertNotEqual(first["armId"], second["armId"])
            starts[first["armId"]] += 1
        self.assertEqual(starts, {"jev-coreinfra": 48, "luna-low-coreinfra": 48})
        for job in jobs:
            self.assertEqual(
                job["task"]["state"]["sourceText"], sources[job["caseId"]]["sourceText"]
            )
            self.assertEqual(
                job["task"]["state"]["candidateClaims"],
                records[job["recordId"]]["claims"],
            )
            for claim in job["task"]["state"]["candidateClaims"]:
                self.assertEqual(
                    job["task"]["state"]["sourceText"][claim["start"] : claim["end"]],
                    claim["quote"],
                )

    def test_wire_bodies_share_semantic_task(self):
        for profile in ("pilot", "decisions-pilot"):
            for job in planner.prepare(MANIFEST, profile)["jobs"]:
                body = job["request"]["body"]
                self.assertEqual(job["request"]["method"], "POST")
                if job["armId"] == "luna-low-coreinfra":
                    self.assertEqual(
                        json.loads(body["input"][0]["content"][0]["text"]), job["task"]
                    )
                    self.assertEqual(body["reasoning"], {"effort": "low"})
                    self.assertFalse(body["store"])
                    schema = body["text"]["format"]["schema"]
                    self.assertEqual(
                        schema["properties"]["overall"]["enum"], planner.LABELS
                    )
                    self.assertFalse(schema["additionalProperties"])
                else:
                    self.assertEqual(
                        {k: body[k] for k in ("state", "questions")}, job["task"]
                    )
                    self.assertEqual(body["questions"]["overall"]["type"], "choice")

    def test_no_reviewer_keys_history_or_auth_in_model_context(self):
        forbidden = {
            "expectation",
            "baselineExpectation",
            "mutation",
            "requiredTypedFields",
            "alternativeReadings",
            "notMentioned",
            "reviewStatus",
            "independentReview",
            "changedMutations",
            "lineage",
            "Authorization",
            "credentialEnvironment",
            "previous_response_id",
            "conversation",
            "messages",
        }

        def keys(value):
            if isinstance(value, dict):
                return set(value) | set().union(*(keys(v) for v in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(v) for v in value))
            return set()

        for job in planner.prepare(MANIFEST, "corpus")["jobs"]:
            self.assertFalse(keys(job["request"]["body"]) & forbidden)
            self.assertEqual(
                set(job["task"]["state"]["conventions"]), planner.SAFE_CONVENTIONS
            )

    def test_planning_never_reads_labels_or_credentials(self):
        original = planner.load_json

        def guarded(path):
            self.assertNotEqual(path.name, "reviewer-only.json")
            self.assertNotEqual(path.name, "review.json")
            return original(path)

        with (
            patch.object(planner, "load_json", side_effect=guarded),
            patch("os.getenv", side_effect=AssertionError("No credential read")),
            patch("os.environ.get", side_effect=AssertionError("No credential read")),
        ):
            self.assertEqual(len(planner.prepare(MANIFEST, "pilot")["jobs"]), 24)

    def test_changed_model_is_explicit_config_revision(self):
        manifest = json.loads(MANIFEST.read_bytes())
        manifest["providers"]["jev-coreinfra"]["requestedModel"] = "jev-future-fixture"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "experiment.json"
            path.write_text(json.dumps(manifest))
            plan = planner.prepare(path, "pilot")
        self.assertNotEqual(
            plan["manifestDigest"], planner.prepare(MANIFEST, "pilot")["manifestDigest"]
        )
        self.assertTrue(
            all(
                j["request"]["body"]["model"] == "jev-future-fixture"
                for j in plan["jobs"]
                if j["armId"] == "jev-coreinfra"
            )
        )

    def test_drift_and_malformed_protocol_rejected(self):
        mutations = [
            lambda m: m.update(mode="live"),
            lambda m: m["artifacts"]["sources"].update(sha256="0" * 64),
            lambda m: m["artifacts"]["sources"].update(path="/tmp/outside.json"),
            lambda m: m["codePins"].update(
                {"evaluation/plan_stage1_comparison.py": "0" * 64}
            ),
            lambda m: m["policy"].update(automaticRetries=1),
            lambda m: m["policy"].update(context="shared-history"),
            lambda m: m["question"].update(type="noul"),
            lambda m: m["providers"]["luna-low-coreinfra"]["settings"].update(
                reasoning={"effort": "high"}
            ),
            lambda m: m["providers"]["jev-coreinfra"].update(
                endpoint="https://other.invalid/systemone"
            ),
            lambda m: m["profiles"]["pilot"].update(caseIds=["C002", "C002"]),
            lambda m: m["profiles"]["pilot"].update(repeats=True),
            lambda m: m["profiles"]["pilot"]["budget"].update(maxCalls=25),
            lambda m: m["profiles"]["pilot"]["budget"].update(authorizedCalls=24),
        ]
        original = json.loads(MANIFEST.read_bytes())
        for i, change in enumerate(mutations):
            with self.subTest(mutation=i), tempfile.TemporaryDirectory() as temp:
                manifest = copy.deepcopy(original)
                change(manifest)
                path = Path(temp) / "experiment.json"
                path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    planner.prepare(path, "pilot")

    def test_cli_without_sdk_exports_and_refuses_overwrite(self):
        script = planner.ROOT / "evaluation/plan_stage1_comparison.py"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "plan"
            args = [
                sys.executable,
                "-S",
                str(script),
                str(MANIFEST),
                "--output",
                str(output),
            ]
            result = subprocess.run(args, check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(result.stdout)["callsExecuted"], 0)
            self.assertEqual(
                json.loads((output / "summary.json").read_bytes()),
                planner.summary(planner.prepare(MANIFEST, "pilot")),
            )
            before = (output / "plan.json").read_bytes()
            self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)
            self.assertEqual((output / "plan.json").read_bytes(), before)

    def test_full_export_reconstructs_with_bounded_artifact_loader(self):
        plan = planner.prepare(MANIFEST, "corpus")
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp).resolve() / "export"
            planner.export_plan(plan, folder)
            index, _ = planner.load_json(folder / "plan.json")
            reconstructed = {
                **index["plan"],
                "jobs": [artifact(folder, entry) for entry in index["jobArtifacts"]],
            }
            self.assertEqual(reconstructed, plan)
            self.assertEqual(
                artifact(folder, index["summaryArtifact"]), planner.summary(plan)
            )


if __name__ == "__main__":
    unittest.main()
