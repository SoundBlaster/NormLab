"""New rounded-choice behavior without changing frozen v1 executor evidence."""

import json
import tempfile
import unittest
from pathlib import Path

import plan_stage1_comparison as planner
import stage1_executor_v2 as executor
from harness import digest
from plan_stage1_comparison import LABELS
from stage1_wire_v2 import normalize

MANIFEST = planner.ROOT / "fixtures/parking-pilot/stage1-comparison-v1/experiment.json"


class Stage1ExecutorV2Tests(unittest.TestCase):
    def test_choice_rounding_tolerance_is_used_by_versioned_executor(self):
        probabilities = {label: 0.0 for label in LABELS}
        probabilities[LABELS[0]] = 0.49999975
        probabilities[LABELS[1]] = 0.50000025
        body = {
            "model": "fixture-model",
            "id": "fixture-request",
            "usage": None,
            "answers": {
                "overall": {
                    "type": "choice",
                    "choice": LABELS[0],
                    "confidence": 0.7,
                    "probabilities": probabilities,
                }
            },
        }
        self.assertEqual(normalize("jev-coreinfra", body)["label"], LABELS[0])

        plan = planner.prepare(MANIFEST, "pilot")
        fixture = executor.demo_fixture(plan)
        job = next(item for item in plan["jobs"] if item["armId"] == "jev-coreinfra")
        fixture["responses"][job["jobId"]]["body"]["answers"]["overall"].update(
            choice=LABELS[0], confidence=0.7, probabilities=probabilities
        )
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "capture"
            report = executor.run(plan, fixture, folder)
            self.assertEqual(report, executor.replay(plan, folder))
            self.assertEqual(report["networkCalls"], 0)
            self.assertIsNone(report["stopReason"])
            index = json.loads((folder / "capture.json").read_bytes())
            self.assertEqual(index["schema"], "normlab.stage1-offline-capture/v2")
            self.assertEqual(
                index["codePins"]["stage1_executor_v2.py"],
                digest(Path(executor.__file__).read_bytes()),
            )
            self.assertEqual(
                index["codePins"]["stage1_wire_v2.py"],
                digest(
                    Path(executor.__file__).with_name("stage1_wire_v2.py").read_bytes()
                ),
            )

    def test_choice_outside_rounding_tolerance_is_rejected(self):
        probabilities = {label: 0.0 for label in LABELS}
        probabilities[LABELS[0]] = 0.499998
        probabilities[LABELS[1]] = 0.500002
        body = {
            "model": "fixture-model",
            "id": "fixture-request",
            "usage": None,
            "answers": {
                "overall": {
                    "type": "choice",
                    "choice": LABELS[0],
                    "confidence": 0.7,
                    "probabilities": probabilities,
                }
            },
        }
        with self.assertRaisesRegex(ValueError, "Choice maximum"):
            normalize("jev-coreinfra", body)


if __name__ == "__main__":
    unittest.main()
