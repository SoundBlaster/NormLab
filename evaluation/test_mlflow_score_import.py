"""Real pinned local MLflow score children; network transport forbidden."""

import copy
import json
import os
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_offline_runtime_reference as references
import test_offline_runtime_score as fixtures
from execution_resume import continue_mock
from execution_test_support import ROOT, ExecutionCase, canonical
from import_runtime_mlflow import run
from mlflow_registry import local_path, registry
from offline_bundle import decode, read
from runtime_archive_export import export_runtime_archive
from runtime_archive_reader import read_archive
from runtime_reference import reference
from runtime_score import score, verify_score
from runtime_score_mlflow_projection import project_score
from test_mlflow_import import NETWORK_GUARD, Interrupted, deny_network


class MLflowScoreTests(ExecutionCase):
    input = fixtures.ScoreTests.input
    output = fixtures.ScoreTests.output
    script = fixtures.ScoreTests.script
    failure = staticmethod(fixtures.ScoreTests.failure)
    paused = fixtures.ScoreTests.paused
    request = fixtures.ScoreTests.request
    orphan = fixtures.ScoreTests.orphan
    archive = fixtures.ScoreTests.archive
    view = fixtures.ScoreTests.view

    @classmethod
    def setUpClass(cls):
        sys.addaudithook(deny_network)

    def setUp(self):
        super().setUp()
        self.storage = self.root / "registry"

    def prepare(self):
        runtime, directory, archive, view = self.view()
        path = self.root / "score.json"
        path.write_bytes(canonical(view))
        return runtime, directory, archive, view, path

    def artifact(self, store, receipt):
        item = store.client.get_run(receipt["mlflowRunId"])
        return local_path(item.info.artifact_uri) / "normlab"

    def test_repeat_import_saved_archive_score_and_one_metric_history(self):
        runtime, directory, _, view, path = self.prepare()
        first = run(directory, self.storage, score_path=path)["imports"]
        second = run(directory, self.storage, score_path=path)["imports"]
        self.assertEqual(
            [r["mlflowRunId"] for r in first], [r["mlflowRunId"] for r in second]
        )
        self.assertTrue(all(r["alreadyImported"] for r in second))
        shutil.rmtree(runtime)
        shutil.rmtree(directory)
        path.unlink()
        with registry(self.storage) as store:
            saved = self.artifact(store, first[-1])
            self.assertEqual(
                verify_score(
                    read_archive(saved / "archive"), decode(read(saved / "score.json"))
                ),
                view,
            )
            child = store.client.get_run(first[-1]["mlflowRunId"])
            self.assertEqual(
                child.data.tags["mlflow.parentRunId"], first[1]["mlflowRunId"]
            )
            self.assertEqual(len(store.client.search_runs([store.experiment_id])), 4)
            for name in child.data.metrics:
                self.assertEqual(
                    len(store.client.get_metric_history(child.info.run_id, name)), 1
                )
        third = run(saved / "archive", self.storage, score_path=saved / "score.json")[
            "imports"
        ]
        self.assertTrue(all(r["alreadyImported"] for r in third))

    def test_reference_revisions_preserve_parent_and_both_score_children(self):
        _, directory, archive, view, path = self.prepare()
        first = run(directory, self.storage, score_path=path)["imports"]
        labels = references.source(archive)
        labels["revision"] = "synthetic-reference-v2"
        labels["expected"][0]["label"] = "no"
        second_view = score(archive, reference(archive, canonical(labels)))
        second_path = self.root / "second-score.json"
        second_path.write_bytes(canonical(second_view))
        second = run(directory, self.storage, score_path=second_path)["imports"]
        self.assertEqual(first[1]["mlflowRunId"], second[1]["mlflowRunId"])
        self.assertNotEqual(first[-1]["mlflowRunId"], second[-1]["mlflowRunId"])
        with registry(self.storage) as store:
            self.assertEqual(len(store.client.search_runs([store.experiment_id])), 5)
            for receipt, expected in [(first[-1], view), (second[-1], second_view)]:
                saved = self.artifact(store, receipt)
                self.assertEqual(
                    verify_score(
                        read_archive(saved / "archive"),
                        decode(read(saved / "score.json")),
                    ),
                    expected,
                )

    def test_continued_capture_adds_parent_and_score_without_replacing_original(self):
        runtime, directory, archive, view, path = self.prepare()
        first = run(directory, self.storage, score_path=path)["imports"]
        continue_mock(runtime, self.request(runtime))
        second_archive = self.output("continued-score-import")
        export_runtime_archive(runtime, second_archive)
        after = read_archive(second_archive)
        next_view = score(after, reference(after, canonical(references.source(after))))
        next_path = self.root / "continued-score.json"
        next_path.write_bytes(canonical(next_view))
        second = run(second_archive, self.storage, score_path=next_path)["imports"]
        self.assertEqual(first[0]["mlflowRunId"], second[0]["mlflowRunId"])
        self.assertNotEqual(first[1]["mlflowRunId"], second[1]["mlflowRunId"])
        self.assertNotEqual(first[-1]["mlflowRunId"], second[-1]["mlflowRunId"])
        with registry(self.storage) as store:
            self.assertEqual(len(store.client.search_runs([store.experiment_id])), 8)
            saved = self.artifact(store, first[-1])
            self.assertEqual(
                verify_score(
                    read_archive(saved / "archive"), decode(read(saved / "score.json"))
                ),
                view,
            )

    def test_score_intent_recovers_creation_metric_upload_and_finish_interruptions(
        self,
    ):
        _, directory, archive, view, _ = self.prepare()
        row = project_score(archive, view)
        for point in ["create_run", "log_metric", "log_artifacts", "set_terminated"]:
            with self.subTest(point=point):
                storage = self.root / point
                parents = run(directory, storage)["imports"]
                parent = parents[1]["mlflowRunId"]
                with registry(storage) as store:
                    original = getattr(store.client, point)
                    committed = []
                    error_type = RuntimeError if point == "log_metric" else Interrupted

                    def interrupt(*args, **kwargs):
                        result = original(*args, **kwargs)
                        committed.append(
                            result.info.run_id if point == "create_run" else args[0]
                        )
                        raise error_type("injected")

                    with patch.object(store.client, point, side_effect=interrupt):
                        with self.assertRaises(error_type):
                            store.write(
                                row,
                                directory,
                                parent,
                                runtime_archive=archive,
                                runtime_score=view,
                            )
                    receipt = store.write(
                        row,
                        directory,
                        parent,
                        runtime_archive=archive,
                        runtime_score=view,
                    )
                    self.assertEqual(receipt["mlflowRunId"], committed[0])
                    self.assertEqual(
                        len(store.client.search_runs([store.experiment_id])), 4
                    )
                    saved = store.client.get_run(receipt["mlflowRunId"])
                    for name in saved.data.metrics:
                        self.assertEqual(
                            len(
                                store.client.get_metric_history(saved.info.run_id, name)
                            ),
                            1,
                        )

    def test_completed_score_artifact_metric_parameter_and_directory_drift_reject(self):
        _, directory, _, _, path = self.prepare()
        for mutation in ["score", "metric", "param", "directory"]:
            with self.subTest(mutation=mutation):
                storage = self.root / ("drift-" + mutation)
                rows = run(directory, storage, score_path=path)["imports"]
                with registry(storage) as store:
                    receipt = rows[-1]
                    target = self.artifact(store, receipt)
                    child = store.client.get_run(receipt["mlflowRunId"])
                    if mutation == "score":
                        (target / "score.json").write_bytes(b"{}")
                    elif mutation == "metric":
                        store.client.log_metric(
                            child.info.run_id,
                            "selected.passedQuestions",
                            99,
                            timestamp=0,
                            step=0,
                        )
                    elif mutation == "param":
                        store.client.log_param(
                            child.info.run_id, "foreign", "unexpected"
                        )
                    else:
                        (target / "unexpected-empty").mkdir()
                with self.assertRaises(ValueError):
                    run(directory, storage, score_path=path)

    def test_wrong_parent_and_bool_metric_record_rejected_before_score_intent(self):
        _, directory, archive, view, _ = self.prepare()
        parents = run(directory, self.storage)["imports"]
        row = project_score(archive, view)
        with registry(self.storage) as store:
            with self.assertRaisesRegex(ValueError, "parent binding"):
                store.write(
                    row,
                    directory,
                    parents[0]["mlflowRunId"],
                    runtime_archive=archive,
                    runtime_score=view,
                )
            changed = copy.deepcopy(row)
            changed["metrics"]["selected.statusCounts.completed"] = True
            with self.assertRaisesRegex(ValueError, "record binding"):
                store.write(
                    changed,
                    directory,
                    parents[1]["mlflowRunId"],
                    runtime_archive=archive,
                    runtime_score=view,
                )
            self.assertEqual(
                store.db.execute("SELECT count(*) FROM imports").fetchone()[0], 3
            )

    def test_real_cli_score_import_and_reuse_network_denied(self):
        _, directory, _, _, path = self.prepare()
        args = [
            sys.executable,
            "-B",
            "-c",
            NETWORK_GUARD,
            str(ROOT / "evaluation/import_runtime_mlflow.py"),
            str(directory),
            "--score",
            str(path),
            "--storage",
            str(self.storage),
        ]
        results = []
        for _ in range(2):
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=30,
                env={
                    **os.environ,
                    "MLFLOW_DISABLE_TELEMETRY": "true",
                    "MLFLOW_DISABLE_AGENT_HINT": "1",
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            results.append(json.loads(result.stdout)["imports"])
        self.assertEqual(
            [r["mlflowRunId"] for r in results[0]],
            [r["mlflowRunId"] for r in results[1]],
        )
        self.assertTrue(all(r["alreadyImported"] for r in results[1]))


if __name__ == "__main__":
    unittest.main()
