"""Real pinned local MLflow final-control import; network and inference denied."""

import shutil
import sys
from unittest.mock import patch

import test_offline_stop_consumers as fixtures
from execution_test_support import ExecutionCase
from import_runtime_mlflow import run
from mlflow_registry import local_path, registry
from offline_bundle import decode, read
from runtime_consumer_v4 import read_archive
from runtime_mlflow_projection import project, snapshot
from runtime_score import verify_score
from test_mlflow_import import deny_network


class MLflowStopTests(ExecutionCase):
    prepared = fixtures.StopConsumerTests.prepared
    initial = fixtures.StopConsumerTests.initial
    execute = fixtures.StopConsumerTests.execute
    source = fixtures.StopConsumerTests.source
    proposal = fixtures.StopConsumerTests.proposal
    apply = fixtures.StopConsumerTests.apply
    files = fixtures.StopConsumerTests.files
    guarded = fixtures.StopConsumerTests.guarded
    subfolder = fixtures.StopConsumerTests.subfolder
    resumed = fixtures.StopConsumerTests.resumed
    stop_proposal = fixtures.StopConsumerTests.stop_proposal
    stop_guard = fixtures.StopConsumerTests.stop_guard
    stop_apply = fixtures.StopConsumerTests.stop_apply
    stopped = fixtures.StopConsumerTests.stopped
    archive = fixtures.StopConsumerTests.archive
    selected = fixtures.StopConsumerTests.selected
    view = fixtures.StopConsumerTests.view

    @classmethod
    def setUpClass(cls):
        sys.addaudithook(deny_network)

    def test_both_controls_repeat_import_without_metric_duplicates_and_remain_portable(
        self,
    ):
        for continued in (False, True):
            source, folder, archive, view, score_path = self.view(continued=continued)
            storage = self.root / ("registry-" + str(self.serial))
            first = run(folder, storage, score_path=score_path)["imports"]
            again = run(folder, storage, score_path=score_path)["imports"]
            self.assertEqual(
                [r["mlflowRunId"] for r in first], [r["mlflowRunId"] for r in again]
            )
            self.assertTrue(all(r["alreadyImported"] for r in again))
            self.assertEqual(len(first), 4)
            shutil.rmtree(source)
            shutil.rmtree(folder)
            score_path.unlink()
            with registry(storage) as store:
                for receipt in first:
                    imported = store.client.get_run(receipt["mlflowRunId"])
                    for name in imported.data.metrics:
                        self.assertEqual(
                            len(
                                store.client.get_metric_history(
                                    imported.info.run_id, name
                                )
                            ),
                            1,
                        )
                child = store.client.get_run(first[-1]["mlflowRunId"])
                saved = local_path(child.info.artifact_uri) / "normlab"
                restored = read_archive(saved / "archive")
                self.assertEqual(
                    verify_score(restored, decode(read(saved / "score.json"))), view
                )
                self.assertFalse(restored.snapshot.manifest["stopControl"]["adopted"])
                self.assertGreater(
                    len(restored.snapshot.manifest["stopControl"]["orphanFiles"]), 0
                )
                projection = store.client.get_run(first[2]["mlflowRunId"])
                self.assertEqual(
                    projection.data.metrics["runtime.unknownDispatchAttempts"], 1
                )
                self.assertEqual(projection.data.metrics["control.adoptedOutcomes"], 0)
                self.assertEqual(
                    child.data.tags["mlflow.parentRunId"], first[1]["mlflowRunId"]
                )

    def test_pre_stop_and_final_control_share_execution_parent_but_not_capture(self):
        for continued in (False, True):
            root, folder, archive, view, path = self.view(continued=continued)
            prefix = (
                "native-resumed-stop-base/capture" if continued else "native-stop-base"
            )
            storage = self.root / ("parents-" + str(self.serial))
            base = run(root / prefix, storage)["imports"]
            stopped = run(folder, storage, score_path=path)["imports"]
            self.assertEqual(base[0]["mlflowRunId"], stopped[0]["mlflowRunId"])
            self.assertNotEqual(base[1]["mlflowRunId"], stopped[1]["mlflowRunId"])
            self.assertNotEqual(base[2]["mlflowRunId"], stopped[2]["mlflowRunId"])
            older = run(root / prefix, storage)["imports"]
            self.assertTrue(all(r["alreadyImported"] for r in older))

    def test_interrupted_projection_import_recovers_exact_capture_and_metric_history(
        self,
    ):
        root, folder, archive, view, path = self.view()
        storage = self.root / "recovery"
        with snapshot(folder) as (private, verified):
            records = project(verified)
            with registry(storage) as store:
                parent = store.write(records[0], private, runtime_archive=verified)
                capture = store.write(
                    records[1], private, parent["mlflowRunId"], runtime_archive=verified
                )
                original = store.client.log_metric

                def interrupted(*args, **kwargs):
                    original(*args, **kwargs)
                    raise RuntimeError("synthetic metric interruption")

                with (
                    patch.object(store.client, "log_metric", side_effect=interrupted),
                    self.assertRaises(RuntimeError),
                ):
                    store.write(
                        records[2],
                        private,
                        capture["mlflowRunId"],
                        runtime_archive=verified,
                    )
        result = run(folder, storage, score_path=path)["imports"]
        with registry(storage) as store:
            imported = store.client.get_run(result[2]["mlflowRunId"])
            for metric in imported.data.metrics:
                self.assertEqual(
                    len(store.client.get_metric_history(imported.info.run_id, metric)),
                    1,
                )
