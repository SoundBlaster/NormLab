"""New model metadata acceptance with frozen identifiers and historical source pins."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from harness_v2 import digest, identifier, model_metadata, prepare, replay

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/parking-pilot/evaluation-harness"


class ModelMetadataTests(unittest.TestCase):
    def test_model_names_are_bounded_metadata_only(self):
        for value in (
            "gpt-6.1",
            "openai/gpt-oss-20b",
            "provider/model:latest",
            "a" * 256,
        ):
            self.assertTrue(model_metadata(value), value)
        for value in (
            None,
            1,
            "",
            "a" * 257,
            " leading",
            "trailing ",
            "m\n",
            "m\x00",
            "m?key=secret",
            "модель",
        ):
            self.assertFalse(model_metadata(value), repr(value))
        for value in ("gpt-6.1", "provider/model", "model:latest", "a" * 81):
            self.assertFalse(identifier(value), value)

    def test_requested_and_returned_models_replay_without_metadata_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "dataset"
            shutil.copytree(FIXTURE, root)
            path = root / "experiment.json"
            manifest = json.loads(path.read_text())
            manifest["schema"] = "normlab.evaluation-experiment/v2"
            manifest["experimentId"] = "model-metadata-v2-regression"
            manifest["provider"]["requestedModel"] = "openai/gpt-oss-20b"
            for record in manifest["records"]:
                capture_path = root / record["capture"]["path"]
                capture = json.loads(capture_path.read_text())
                capture["returnedModel"] = "provider/model:2026.10"
                capture_path.write_text(json.dumps(capture))
                record["capture"]["sha256"] = digest(capture_path.read_bytes())
            path.write_text(json.dumps(manifest))
            labels_path = root / "reviewer-labels.json"
            labels = json.loads(labels_path.read_text())
            labels["experimentDigest"] = digest(path.read_bytes())
            labels_path.write_text(json.dumps(labels))
            report = replay(prepare(path, labels_path))
            self.assertEqual(report["schema"], "normlab.evaluation-replay/v2")
            self.assertEqual(report["provider"]["requestedModel"], "openai/gpt-oss-20b")
            self.assertTrue(
                all(
                    r["returnedModel"] == "provider/model:2026.10"
                    for r in report["records"]
                )
            )
            self.assertEqual(report["counts"]["liveCalls"], 0)
            for field in ("id", "route"):
                manifest["provider"][field] = "provider/model"
                path.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, "Provider identity"):
                    prepare(path)
                manifest["provider"][field] = "fixture"

    def test_v1_input_is_explicitly_rescored_as_v2_and_snapshot_replays(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "first"
            command = [sys.executable, str(ROOT / "evaluation/harness_v2.py")]
            subprocess.run(
                command
                + [
                    str(FIXTURE / "experiment.json"),
                    "--labels",
                    str(FIXTURE / "reviewer-labels.json"),
                    "--output",
                    str(output),
                ],
                check=True,
                capture_output=True,
            )
            second = Path(directory) / "second"
            subprocess.run(
                command
                + [
                    str(output / "dataset/experiment.json"),
                    "--labels",
                    str(output / "reviewer-labels.json"),
                    "--output",
                    str(second),
                ],
                check=True,
                capture_output=True,
            )
            self.assertEqual(
                (output / "report.json").read_bytes(),
                (second / "report.json").read_bytes(),
            )
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["inputSchema"], "normlab.evaluation-experiment/v1")
            self.assertEqual(report["replayContract"], "model-metadata/v2")
            self.assertTrue((output / "harness_v2.py").is_file())
            self.assertTrue((output / "mellea_candidate_v2.py").is_file())

    def test_frozen_source_pins_remain_exact(self):
        for name in ("stage1-audit", "stage1-audit-v2", "stage1-comparison-v1"):
            manifest = json.loads(
                (ROOT / "fixtures/parking-pilot" / name / "experiment.json").read_text()
            )
            for path, expected in manifest["codePins"].items():
                self.assertEqual(digest((ROOT / path).read_bytes()), expected, path)


if __name__ == "__main__":
    unittest.main()
