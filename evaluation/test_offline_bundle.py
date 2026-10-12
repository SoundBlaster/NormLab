"""Offline CLI round trips and coordinated reference/report mutation regressions."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/parking-pilot/evaluation-harness"
READER_FILES = (
    "offline_adapters.py",
    "offline_bundle.py",
    "offline_contract.py",
    "offline_score_contract.py",
    "offline_task_contract.py",
)
GUARD = """
import runpy, sys
from pathlib import Path
def guard(event, args):
    if event.startswith('socket.') or event == 'subprocess.Popen':
        raise AssertionError('Network/process dispatch forbidden in offline check')
    if event == 'import' and args[0].split('.')[0] in {
        'openai', 'mellea', 'jev', 'mellea_jev_adapter', 'requests', 'httpx'
    }:
        raise AssertionError('Provider SDK import forbidden in offline check')
sys.addaudithook(guard)
script = Path(sys.argv[1]).resolve()
sys.argv = sys.argv[1:]
sys.path.insert(0, str(script.parent))
runpy.run_path(str(script), run_name='__main__')
"""


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(kind, value):
    return kind + "-" + digest(canonical(value))


def load(path):
    return json.loads(path.read_bytes())


def value(folder, ref):
    return load(folder / ref["path"])


def store(folder, envelope, data):
    raw = canonical(data)
    checksum = digest(raw)
    ref = {"path": f"artifacts/{checksum}.blob", "sha256": checksum, "bytes": len(raw)}
    (folder / ref["path"]).write_bytes(raw)
    if ref not in envelope["artifacts"]:
        envelope["artifacts"].append(ref)
    return ref


def seal(folder, envelope, report):
    envelope["score"]["report"] = store(folder, envelope, report)
    envelope["score"]["id"] = identity(
        "score",
        [
            envelope["run"]["id"],
            envelope["score"]["report"]["sha256"],
            envelope["score"]["referenceId"],
            envelope["adapter"],
        ],
    )
    (folder / "bundle.json").write_bytes(canonical(envelope))


def rewrite_reference(folder, envelope, report, reference):
    ref = store(folder, envelope, reference)
    envelope["reference"].update(
        artifact=ref,
        id=identity("reference", ref["sha256"]),
        status=reference["status"],
        revision=reference.get("revision"),
    )
    envelope["score"]["referenceId"] = envelope["reference"]["id"]
    if report["schema"] == "normlab.s13-replay-report/v1":
        report.update(
            referenceDigest=ref["sha256"],
            referenceStatus=reference["status"],
            referenceRevision=reference["revision"],
        )
    else:
        report["labelsDigest"] = ref["sha256"]


class OfflineBundleTests(unittest.TestCase):
    @classmethod
    def cli(cls, *args, script=None, cwd=None):
        return subprocess.run(
            [
                sys.executable,
                "-B",
                "-S",
                "-c",
                GUARD,
                str(script or ROOT / "evaluation/offline_adapters.py"),
                *map(str, args),
            ],
            cwd=cwd or cls.root,
            env={"PATH": os.defpath, "PYTHONNOUSERSITE": "1"},
            capture_output=True,
            text=True,
            timeout=30,
        )

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.bundles = {}
        for name in ("classification", "no-labels", "s13"):
            target = cls.root / name
            result = cls.cli(*cls.export_args(name), "--output", target)
            if result.returncode != 0:
                raise AssertionError((name, result.stdout, result.stderr))
            cls.bundles[name] = target

    @staticmethod
    def export_args(name):
        if name == "s13":
            return ["s13"]
        args = ["classification", FIXTURE / "experiment.json"]
        if name == "classification":
            args.extend(["--labels", FIXTURE / "reviewer-labels.json"])
        return args

    def mutate(self, name, change, accepted=False):
        with tempfile.TemporaryDirectory(dir=self.root) as temporary:
            folder = Path(temporary) / "bundle"
            shutil.copytree(self.bundles[name], folder)
            envelope = load(folder / "bundle.json")
            report = value(folder, envelope["score"]["report"])
            change(folder, envelope, report)
            seal(folder, envelope, report)
            result = self.cli("verify", folder)
            self.assertEqual(result.returncode, 0 if accepted else 1, result.stderr)
            if not accepted:
                self.assertEqual(
                    result.stderr.strip(),
                    "Offline bundle contract validation/export failed",
                )

    def test_round_trip_and_deterministic_reexport(self):
        for name, folder in self.bundles.items():
            with self.subTest(name=name):
                first = self.cli("verify", folder)
                self.assertEqual(first.returncode, 0, first.stderr)
                second = self.root / (name + "-repeat")
                exported = self.cli(*self.export_args(name), "--output", second)
                self.assertEqual(exported.returncode, 0, exported.stderr)
                self.assertEqual(
                    (folder / "bundle.json").read_bytes(),
                    (second / "bundle.json").read_bytes(),
                )
                self.assertEqual(json.loads(first.stdout), json.loads(exported.stdout))

    def test_no_labels_changes_score_only(self):
        labeled = load(self.bundles["classification"] / "bundle.json")
        folder = self.bundles["no-labels"]
        unlabeled = load(folder / "bundle.json")
        report = value(folder, unlabeled["score"]["report"])
        self.assertEqual(labeled["run"], unlabeled["run"])
        self.assertNotEqual(labeled["score"]["id"], unlabeled["score"]["id"])
        self.assertIsNone(unlabeled["reference"])
        self.assertIsNone(report["counts"]["probePass"])
        self.assertEqual(report["expectationsStatus"], "not_evaluated")
        self.assertTrue(all(row["probePass"] is None for row in report["records"]))

    def test_classification_v2_model_metadata(self):
        folder = self.root / "classification-v2-source"
        shutil.copytree(FIXTURE, folder)
        manifest = load(folder / "experiment.json")
        manifest["schema"] = "normlab.evaluation-experiment/v2"
        manifest["provider"]["requestedModel"] = "provider/model:latest"
        for record in manifest["records"]:
            path = folder / record["capture"]["path"]
            capture = load(path)
            capture["returnedModel"] = "provider/model:2026.10"
            path.write_bytes(canonical(capture))
            record["capture"]["sha256"] = digest(path.read_bytes())
        path = folder / "experiment.json"
        path.write_bytes(canonical(manifest))
        labels_path = folder / "reviewer-labels.json"
        labels = load(labels_path)
        labels["experimentDigest"] = digest(path.read_bytes())
        labels_path.write_bytes(canonical(labels))
        output = self.root / "classification-v2-export"
        result = self.cli(
            "classification", path, "--labels", labels_path, "--output", output
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.cli("verify", output).returncode, 0)
        envelope = load(output / "bundle.json")
        report = value(output, envelope["score"]["report"])
        self.assertEqual(report["provider"]["requestedModel"], "provider/model:latest")
        self.assertTrue(
            all(
                row["returnedModel"] == "provider/model:2026.10"
                for row in report["records"]
            )
        )

    def test_s13_full_denominator_and_usage(self):
        folder = self.bundles["s13"]
        envelope = load(folder / "bundle.json")
        self.assertEqual(
            envelope["counts"],
            {
                "plannedTasks": 453,
                "plannedQuestions": 909,
                "recordedOutcomes": 19,
                "statusCounts": {
                    "completed": 13,
                    "deadline": 1,
                    "invalid-schema": 3,
                    "not-dispatched": 434,
                    "transport-failed": 2,
                },
                "knownInputTokens": 1600,
                "knownOutputTokens": 160,
                "unknownUsageOutcomes": 3,
            },
        )
        for ref in envelope["records"]:
            turn = value(folder, ref)["turn"]
            self.assertIsNone(turn["attempts"])
            self.assertIsNone(turn["latencyMs"])
            self.assertIsNone(turn["cost"])

    def test_original_bytes_preserved(self):
        folder = self.bundles["classification"]
        envelope = load(folder / "bundle.json")
        manifest = load(FIXTURE / "experiment.json")
        originals = [(envelope["source"]["manifest"], FIXTURE / "experiment.json")]
        originals += [
            (ref, FIXTURE / row["capture"]["path"])
            for ref, row in zip(envelope["source"]["captures"], manifest["records"])
        ]
        for ref, path in originals:
            self.assertEqual((folder / ref["path"]).read_bytes(), path.read_bytes())

    def test_portable_reader_without_legacy_or_sdk(self):
        reader = self.root / "portable-reader"
        reader.mkdir()
        for name in READER_FILES:
            shutil.copyfile(ROOT / "evaluation" / name, reader / name)
        for name, folder in self.bundles.items():
            with self.subTest(name=name):
                result = self.cli(
                    "verify", folder, script=reader / "offline_adapters.py", cwd=reader
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_existing_output_is_not_overwritten(self):
        folder = self.bundles["classification"]
        before = (folder / "bundle.json").read_bytes()
        result = self.cli(*self.export_args("classification"), "--output", folder)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(before, (folder / "bundle.json").read_bytes())
        self.assertEqual(self.cli("verify", folder).returncode, 0)

    def test_coordinated_classification_reference_mutations(self):
        for field, data in (
            ("status", "human-adjudicated"),
            ("status", "candidate-not-independent"),
            ("schema", "normlab.s13-reference/v1"),
            ("experimentDigest", "0" * 64),
            ("expectations", {}),
        ):
            with self.subTest(field=field, data=data):

                def change(folder, envelope, report):
                    reference = value(folder, envelope["reference"]["artifact"])
                    reference[field] = data
                    rewrite_reference(folder, envelope, report, reference)

                self.mutate("classification", change)

    def test_coordinated_s13_reference_mutations(self):
        variants = (
            {"status": "candidate"},
            {"schema": "normlab.evaluation-labels/v1"},
            {"planDigest": "0" * 64},
            {"expected": {}},
            {"status": "human-adjudicated"},
            {"status": "human-adjudicated", "revision": "review-test-v1"},
            {
                "status": "human-adjudicated",
                "revision": "review-test-v1",
                "adjudicationEvidence": [],
            },
            {
                "status": "human-adjudicated",
                "revision": "review-test-v1",
                "adjudicationEvidence": [" "],
            },
            {
                "status": "human-adjudicated",
                "adjudicationEvidence": ["test fixture declaration"],
            },
        )
        for variant in variants:
            with self.subTest(variant=variant):

                def change(folder, envelope, report):
                    reference = value(folder, envelope["reference"]["artifact"])
                    reference.update(variant)
                    rewrite_reference(folder, envelope, report, reference)

                self.mutate("s13", change)

    def test_s13_reference_question_coverage_and_labels(self):
        for variant in ("missing-question", "extra-question", "invalid-label"):
            with self.subTest(variant=variant):

                def change(folder, envelope, report):
                    reference = value(folder, envelope["reference"]["artifact"])
                    labels = next(iter(reference["expected"].values()))
                    qid = next(iter(labels))
                    if variant == "missing-question":
                        del labels[qid]
                    elif variant == "extra-question":
                        labels["invented-question"] = "yes"
                    else:
                        labels[qid] = "invented-label"
                    rewrite_reference(folder, envelope, report, reference)

                self.mutate("s13", change)

    def test_s13_declared_review_positive_control(self):
        def change(folder, envelope, report):
            reference = value(folder, envelope["reference"]["artifact"])
            reference.update(
                status="human-adjudicated",
                revision="review-test-v1",
                adjudicationEvidence=[
                    "Synthetic declaration for contract test; not actual human gold"
                ],
            )
            rewrite_reference(folder, envelope, report, reference)

        self.mutate("s13", change, accepted=True)

    def test_coordinated_report_metric_mutations(self):
        for name, field, data in (
            ("classification", "counts", {"total": 999}),
            ("classification", "expectationsStatus", "human-adjudicated"),
            ("no-labels", "expectationsStatus", "candidate"),
            ("classification", "provider", {}),
            ("classification", "criticalErrorFreeRate", 1),
            ("classification", "semanticVerifierQuality", "verified"),
            ("s13", "knownInputTokens", 999999),
            ("s13", "knownOutputTokens", 999999),
            ("s13", "unknownUsageOutcomes", 0),
            ("s13", "statusCounts", {"completed": 453}),
            ("s13", "plannedCalls", 19),
            ("s13", "plannedQuestions", 19),
            ("s13", "questionAgreementCount", 999999),
            ("s13", "questionDisagreementCount", 999999),
            ("s13", "unevaluatedQuestionCount", 0),
            ("s13", "evidenceKind", "live"),
            ("s13", "providerQualityScore", 1),
            ("s13", "wholeSourceCompleteness", "verified"),
            ("s13", "inferenceCalls", False),
        ):
            with self.subTest(name=name, field=field):
                self.mutate(
                    name, lambda folder, envelope, report: report.update({field: data})
                )

    def test_coordinated_arm_metric_mutations(self):
        for field in (
            "questionAgreementCount",
            "questionDisagreementCount",
            "unevaluatedQuestionCount",
            "falseAcceptanceCount",
            "falseRejectionCount",
            "plannedCalls",
            "plannedQuestions",
        ):
            with self.subTest(field=field):
                self.mutate(
                    "s13",
                    lambda folder, envelope, report: report["arms"]["A"].update(
                        {field: 999999}
                    ),
                )
        self.mutate(
            "s13",
            lambda folder, envelope, report: report["arms"]["D"].update(
                falseAcceptanceCount=0
            ),
        )
        self.mutate(
            "s13",
            lambda folder, envelope, report: report["arms"]["A"].update(
                selectedClaimVerdicts={"compatible": 999999}
            ),
        )
        self.mutate(
            "s13",
            lambda folder, envelope, report: report["arms"]["A"].update(
                statusCounts={"completed": 999999}
            ),
        )

    def test_coordinated_scored_status_mutations(self):
        for name in ("classification", "s13"):
            with self.subTest(name=name):

                def change(folder, envelope, report):
                    rows = report["results" if name == "s13" else "records"]
                    row = next(row for row in rows if row["status"] == "completed")
                    row["status"] = "transport-failed"
                    key = "jobId" if name == "s13" else "recordId"
                    for index, ref in enumerate(envelope["records"]):
                        task = value(folder, ref)
                        if task["originalId"] == row[key]:
                            task["turn"]["status"] = row["status"]
                            task["scoreArtifact"] = store(folder, envelope, row)
                            envelope["records"][index] = store(folder, envelope, task)
                            break
                    counts = envelope["counts"]["statusCounts"]
                    counts["completed"] -= 1
                    counts["transport-failed"] = counts.get("transport-failed", 0) + 1

                self.mutate(name, change)

    def test_network_and_sdk_guards_are_active(self):
        for name, source, marker in (
            (
                "socket-probe",
                "import socket; socket.socket()",
                "Network/process dispatch forbidden",
            ),
            ("sdk-probe", "import openai", "Provider SDK import forbidden"),
        ):
            with self.subTest(name=name):
                script = self.root / (name + ".py")
                script.write_text(source)
                result = self.cli(script=script)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(marker, result.stderr)

    def test_capture_byte_corruption(self):
        def change(folder, envelope, report):
            path = folder / envelope["source"]["captures"][0]["path"]
            path.write_bytes(path.read_bytes() + b" ")

        self.mutate("classification", change)


if __name__ == "__main__":
    unittest.main()
