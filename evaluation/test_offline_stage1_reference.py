"""SDK-free seal/reference/native-score imports and portable comparison checks."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import score_stage1_providers as provider
import score_stage1_retries_v2 as retry
import test_offline_stage1 as fixtures
from offline_stage1 import READER_ASSETS, READER_FILES
from test_offline_bundle import ROOT, canonical, identity, load, seal, store, value


class OfflineStage1ReferenceTests(unittest.TestCase):
    cli = classmethod(fixtures.OfflineStage1Tests.cli.__func__)

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.pilot = fixtures.prepare(fixtures.MANIFEST)
        cls.retry = fixtures.retry_prepare(fixtures.MANIFEST, "pilot")
        cls.sources = {}
        for name in ("recover", "exhaust", "pending-child", "missing-child", "zero"):
            capture = cls.root / name
            fixtures.retry_capture(cls.retry, capture, name)
            cls.sources[name] = (capture, retry, cls.retry)
        for name, statuses in (
            ("provider", ["completed"] * 3),
            ("provider-sent", ["sent"]),
            ("provider-failed", ["failed"]),
        ):
            capture = cls.root / name
            fixtures.provider_capture(cls.pilot, capture, statuses)
            cls.sources[name] = (capture, provider, cls.pilot)
        for name, (capture, scorer, plan) in cls.sources.items():
            seal_path, score_path = cls.paths(name)
            provider.save_new(seal_path, scorer.seal(plan, capture))
            provider.save_new(
                score_path, scorer.score(fixtures.MANIFEST, plan, capture, seal_path)
            )

    @classmethod
    def paths(cls, scenario):
        return cls.root / (scenario + "-seal.json"), cls.root / (
            scenario + "-score.json"
        )

    def bundle(self, scenario="recover"):
        folder = Path(tempfile.mkdtemp(dir=self.root)) / "bundle"
        capture, _, _ = self.sources[scenario]
        seal_path, score_path = self.paths(scenario)
        result = self.cli(
            "stage1",
            capture,
            "--manifest",
            fixtures.MANIFEST,
            "--seal",
            seal_path,
            "--native-score",
            score_path,
            "--output",
            folder,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.cli("verify", folder).returncode, 0)
        return folder, load(folder / "bundle.json")

    def test_native_score_parity_and_raw_bytes_for_all_capture_states(self):
        for name in self.sources:
            with self.subTest(scenario=name):
                folder, envelope = self.bundle(name)
                report = value(folder, envelope["score"]["report"])
                seal_path, score_path = self.paths(name)
                self.assertEqual(
                    (folder / report["nativeScoreArtifact"]["path"]).read_bytes(),
                    score_path.read_bytes(),
                )
                self.assertEqual(
                    (folder / report["nativeSealArtifact"]["path"]).read_bytes(),
                    seal_path.read_bytes(),
                )
                self.assertEqual(
                    envelope["reference"]["status"], "candidate-not-independent"
                )
                self.assertFalse(report["semanticQualityEvidence"])
                self.assertIsNone(report["criticalErrorFreeRate"])
                self.assertEqual(envelope["counts"]["plannedTasks"], 36)
                for task_ref in envelope["records"]:
                    task = value(folder, task_ref)
                    row = value(folder, task["scoreArtifact"])
                    for phase in ("first", "final"):
                        observed = row[phase]["observed"]
                        self.assertEqual(
                            row[phase]["selectedReferencePass"],
                            observed == row["expected"]
                            if observed is not None
                            else None,
                        )

    def test_scoring_does_not_change_run_capture_or_task_identity(self):
        folder, scored = self.bundle()
        unscored_folder = folder.parent / "unscored"
        result = self.cli(
            "stage1", self.sources["recover"][0], "--output", unscored_folder
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        unscored = load(unscored_folder / "bundle.json")
        self.assertEqual(scored["run"], unscored["run"])
        self.assertEqual(scored["counts"], unscored["counts"])
        self.assertNotEqual(scored["score"]["id"], unscored["score"]["id"])
        self.assertEqual(
            [value(folder, ref)["id"] for ref in scored["records"]],
            [value(unscored_folder, ref)["id"] for ref in unscored["records"]],
        )

    def test_scored_self_comparison_is_conditional_and_portable(self):
        folder, envelope = self.bundle("provider")
        portable_root = Path(tempfile.mkdtemp(dir=self.root))
        portable = portable_root / "evaluation"
        portable.mkdir()
        for name in (*READER_FILES, "offline_compare.py"):
            shutil.copyfile(ROOT / "evaluation" / name, portable / name)
        for name in READER_ASSETS:
            target = portable_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        result = self.cli("verify", folder, script=portable / "offline_adapters.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli(folder, folder, script=portable / "offline_compare.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)["summary"]
        self.assertEqual(summary["evaluatedPairs"], 3)
        self.assertEqual(summary["notEvaluated"], 33)
        self.assertEqual(summary["selectedReferenceAgreement"]["denominator"], 3)
        self.assertEqual(summary["unionTasks"], envelope["counts"]["plannedTasks"])

    def test_cli_requires_all_scoring_paths(self):
        capture, _, _ = self.sources["recover"]
        seal_path, score_path = self.paths("recover")
        for option, path in (
            ("--manifest", fixtures.MANIFEST),
            ("--seal", seal_path),
            ("--native-score", score_path),
        ):
            result = self.cli("stage1", capture, option, path)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(
                result.stderr.strip(),
                "Offline bundle contract validation/export failed",
            )

    def test_declared_provider_change_keeps_identical_label_provenance_comparable(self):
        folder, _ = self.bundle("provider")
        root = Path(tempfile.mkdtemp(dir=self.root))
        manifest = load(fixtures.MANIFEST)
        manifest["providers"]["jev-coreinfra"]["model"] += "-alternate"
        manifest_path = root / "experiment.json"
        manifest_path.write_bytes(canonical(manifest))
        plan = fixtures.prepare(manifest_path)
        capture = root / "capture"
        fixtures.provider_capture(plan, capture, ["completed"] * 3)
        seal_path, score_path = root / "seal.json", root / "score.json"
        provider.save_new(seal_path, provider.seal(plan, capture))
        provider.save_new(
            score_path, provider.score(manifest_path, plan, capture, seal_path)
        )
        output = root / "bundle"
        result = self.cli(
            "stage1",
            capture,
            "--manifest",
            manifest_path,
            "--seal",
            seal_path,
            "--native-score",
            score_path,
            "--output",
            output,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        script = ROOT / "evaluation/offline_compare.py"
        result = self.cli(folder, output, "--vary", "provider", script=script)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)["summary"]
        self.assertEqual(summary["evaluatedPairs"], 3)
        self.assertEqual(summary["incompatible"], 0)
        result = self.cli(folder, output, script=script)
        self.assertEqual(json.loads(result.stdout)["summary"]["incompatible"], 36)

    def test_full_corpus_native_score_import_stays_bounded(self):
        root = Path(tempfile.mkdtemp(dir=self.root))
        capture = root / "capture"
        plan = fixtures.retry_prepare(fixtures.MANIFEST, "corpus")
        fixtures.retry_capture(plan, capture, "zero")
        entries = []
        for number, job in enumerate(plan["parent"]["jobs"], 1):
            name = f"attempt-{number:04d}"
            fixtures.provider_capture(
                fixtures.child_plan(plan, job, 1), capture / name, ["completed"]
            )
            entries.append(
                {
                    "jobId": job["jobId"],
                    "ordinal": 1,
                    "path": name,
                    "exceptionClasses": [],
                    "backoffSeconds": None,
                    "finished": True,
                }
            )
        index = load(capture / "capture.json")
        index.update(attempts=entries, maxCalls=288, stopReason=None)
        fixtures.write_json(capture / "capture.json", index)
        seal_path, score_path = root / "seal.json", root / "score.json"
        provider.save_new(seal_path, retry.seal(plan, capture))
        provider.save_new(
            score_path, retry.score(fixtures.MANIFEST, plan, capture, seal_path)
        )
        output = root / "bundle"
        result = self.cli(
            "stage1",
            capture,
            "--manifest",
            fixtures.MANIFEST,
            "--seal",
            seal_path,
            "--native-score",
            score_path,
            "--output",
            output,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        envelope = load(output / "bundle.json")
        self.assertEqual(envelope["counts"]["plannedTasks"], 288)
        self.assertEqual(envelope["counts"]["knownInputTokens"], 28800)
        self.assertEqual(envelope["counts"]["statusCounts"], {"completed": 288})
        self.assertLessEqual(len(envelope["artifacts"]), 4096)
        self.assertTrue(
            all(ref["bytes"] <= 2 * 1024 * 1024 for ref in envelope["artifacts"])
        )
        self.assertEqual(self.cli("verify", output).returncode, 0)

    def test_rehashed_reference_status_and_expectation_changes_are_rejected(self):
        for variant in ("status", "expected", "provenance", "duplicate-record"):
            folder, envelope = self.bundle("provider")
            report = value(folder, envelope["score"]["report"])
            reference = value(folder, envelope["reference"]["artifact"])
            if variant == "status":
                reference["status"] = "human-reviewed"
            elif variant == "expected":
                first = next(iter(reference["expected"]))
                reference["expected"][first] = "indeterminate"
            elif variant == "provenance":
                reference["labelsDigest"] = "0" * 64
            else:
                entry = next(
                    e for e in envelope["source"]["inputs"] if e["role"] == "labels"
                )
                labels = value(folder, entry["artifact"])
                labels["records"].append(labels["records"][0])
                entry["artifact"] = store(folder, envelope, labels)
            ref = store(folder, envelope, reference)
            envelope["reference"].update(
                artifact=ref,
                id=identity("reference", ref["sha256"]),
                status=reference["status"],
            )
            envelope["score"]["referenceId"] = envelope["reference"]["id"]
            seal(folder, envelope, report)
            result = self.cli("verify", folder)
            self.assertEqual(result.returncode, 1, (variant, result.stderr))
            self.assertNotIn("Traceback", result.stderr)

    def test_rehashed_native_metrics_and_rows_are_rejected(self):
        for variant in ("arms", "paired", "row", "binding", "seal"):
            folder, envelope = self.bundle()
            report = value(folder, envelope["score"]["report"])
            role = "seal" if variant == "seal" else "score"
            entry = next(e for e in envelope["source"]["inputs"] if e["role"] == role)
            data = value(folder, entry["artifact"])
            if variant == "arms":
                next(iter(data["arms"].values()))["knownInputTokens"] += 1
            elif variant == "paired":
                data["paired"]["final"][0]["bothCompleted"] += 1
            elif variant == "row":
                data["rows"][0]["final"]["matches"] = not data["rows"][0]["final"][
                    "matches"
                ]
            elif variant == "binding":
                data["sealDigest"] = "0" * 64
            else:
                data["captureDigest"] = "0" * 64
            entry["artifact"] = store(folder, envelope, data)
            report[
                "nativeSealArtifact" if role == "seal" else "nativeScoreArtifact"
            ] = entry["artifact"]
            seal(folder, envelope, report)
            result = self.cli("verify", folder)
            self.assertEqual(result.returncode, 1, (variant, result.stderr))
            self.assertNotIn("Traceback", result.stderr)

    def test_derived_agreement_cannot_be_resealed(self):
        folder, envelope = self.bundle("provider")
        task = value(folder, envelope["records"][0])
        row = value(folder, task["scoreArtifact"])
        row["selectedReferencePass"] = not row["selectedReferencePass"]
        task["scoreArtifact"] = store(folder, envelope, row)
        envelope["records"][0] = store(folder, envelope, task)
        (folder / "bundle.json").write_bytes(canonical(envelope))
        self.assertEqual(self.cli("verify", folder).returncode, 1)

    def test_native_score_drift_fails_before_export(self):
        capture, _, _ = self.sources["provider"]
        seal_path, score_path = self.paths("provider")
        bad = load(score_path)
        next(iter(bad["arms"].values()))["candidateMatches"] += 1
        path = self.root / "bad-score.json"
        path.write_bytes(canonical(bad))
        output = self.root / "bad-output"
        result = self.cli(
            "stage1",
            capture,
            "--manifest",
            fixtures.MANIFEST,
            "--seal",
            seal_path,
            "--native-score",
            path,
            "--output",
            output,
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
