"""Native reference/score/MLflow projections retain source observations, offline."""

import copy
import json
import os
import subprocess
import sys
import unittest

import test_offline_live_archive as archive_fixtures
from execution_test_support import ROOT, ExecutionCase, canonical
from import_runtime_mlflow import run
from offline_bundle import identity
from runtime_archive_reader import read_archive
from runtime_mlflow_projection import project
from runtime_reference import reference
from runtime_registry import execution_binding
from runtime_score import score, verify_score
from runtime_score_mlflow_projection import project_score
from test_offline_runtime_mlflow_cli import GUARD


class LiveConsumerTests(ExecutionCase):
    prepared = archive_fixtures.LiveArchiveTests.prepared
    execute = archive_fixtures.LiveArchiveTests.execute
    capture = archive_fixtures.LiveArchiveTests.capture
    scheduled = archive_fixtures.LiveArchiveTests.scheduled
    archive = archive_fixtures.LiveArchiveTests.archive

    def view(self, *, scheduled=True, phase=None):
        source, folder = self.archive(scheduled=scheduled, phase=phase)
        archive = read_archive(folder)
        tasks = archive.snapshot.plan["tasks"]
        selected = reference(
            archive,
            canonical(
                {
                    "schema": "normlab.runtime-reference-source/v1",
                    "revision": "synthetic-candidate/v1",
                    "status": "candidate-not-independent",
                    "planDigest": archive.snapshot.intent["planDigest"],
                    "dataset": archive.snapshot.plan["dataset"],
                    "expected": [
                        {
                            "taskKey": t["key"],
                            "questionId": t["questionIds"][0],
                            "label": "compatible" if scheduled else "yes",
                        }
                        for t in tasks
                    ],
                }
            ),
        )
        view = score(archive, selected)
        path = self.root / "score.json"
        path.write_bytes(canonical(view))
        return source, folder, archive, view, path

    def test_partial_live_score_preserves_denominator_and_candidate_status(self):
        source, folder, archive, view, path = self.view()
        self.assertEqual(view["schema"], "normlab.runtime-score-view/v2")
        self.assertEqual(view["evidenceKind"], "live-capture")
        self.assertEqual(view["summary"]["selectedQuestions"], 36)
        self.assertEqual(view["summary"]["scoredQuestions"], 3)
        self.assertEqual(view["summary"]["selectedUnevaluatedQuestions"], 33)
        self.assertEqual(view["reference"]["status"], "candidate-not-independent")
        self.assertIsNone(view["criticalErrorFreeRate"])
        self.assertFalse(view["semanticQualityEvidence"])
        self.assertEqual(verify_score(archive, view), view)
        changed = copy.deepcopy(view)
        changed["evidenceKind"] = "mock"
        changed["scoreId"] = identity(
            "runtime-score", {k: v for k, v in changed.items() if k != "scoreId"}
        )
        with self.assertRaises(ValueError):
            verify_score(archive, changed)

    def test_unknown_reservation_remains_unscored_in_live_view(self):
        source, folder, archive, view, path = self.view(
            scheduled=False, phase="after-response"
        )
        self.assertEqual(view["summary"]["scoredQuestions"], 0)
        self.assertEqual(view["runtimeCounts"]["unknownDispatchAttempts"], 1)
        self.assertEqual(view["runtimeCounts"]["unknownUsageAttempts"], 1)
        self.assertEqual(
            view["rows"][0]["questions"][0]["notEvaluatedReason"], "unknown-outcome"
        )

    def test_mlflow_projection_has_no_mock_script_or_fabricated_cost(self):
        source, folder, archive, view, path = self.view()
        records = project(archive)
        self.assertNotIn("scriptDigest", execution_binding(archive.projection))
        self.assertEqual(
            records[0]["payload"]["evidence"]["dependencyPins"],
            archive.snapshot.plan["pins"]["dependencies"],
        )
        child = project_score(archive, view)
        for record in [*records, child]:
            self.assertEqual(record["payload"]["evidenceKind"], "live-capture")
            self.assertEqual(record["params"]["evidence_kind"], "live-capture")
            self.assertEqual(record["payload"]["inferenceCallsExecuted"], 0)
            self.assertIsNone(record["payload"]["actualCost"])
        self.assertEqual(records[2]["metrics"]["runtime.observedDispatches"], 3)
        self.assertEqual(child["parentKey"], records[1]["key"])
        result = run(
            folder, self.root / "unused-registry", dry_run=True, score_path=path
        )
        self.assertEqual(result["evidenceKind"], "live-capture")
        self.assertEqual(result["registryWritesExecuted"], 0)
        self.assertFalse((self.root / "unused-registry").exists())

    def test_score_and_import_cli_have_no_provider_or_registry_access(self):
        source, folder, archive, view, path = self.view()
        for script, arguments in (
            ("runtime_score_cli.py", ["verify", str(folder), str(path)]),
            (
                "import_runtime_mlflow.py",
                [str(folder), "--dry-run", "--score", str(path)],
            ),
        ):
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-S",
                    "-c",
                    GUARD,
                    str(ROOT / "evaluation" / script),
                    *arguments,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env={"PATH": os.defpath},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["inferenceCallsExecuted"], 0)


if __name__ == "__main__":
    unittest.main()
