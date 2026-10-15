"""Pinned local MLflow native capture/score imports; network forbidden."""

import shutil
import sys
import unittest

import test_offline_live_consumers as fixtures
from execution_test_support import ExecutionCase
from import_runtime_mlflow import run
from mlflow_registry import local_path, registry
from offline_bundle import canonical, decode, read
from runtime_archive_reader import read_archive
from runtime_score import verify_score
from test_mlflow_import import deny_network


class MLflowLiveTests(ExecutionCase):
    prepared = fixtures.LiveConsumerTests.prepared
    execute = fixtures.LiveConsumerTests.execute
    capture = fixtures.LiveConsumerTests.capture
    scheduled = fixtures.LiveConsumerTests.scheduled
    archive = fixtures.LiveConsumerTests.archive
    view = fixtures.LiveConsumerTests.view

    @classmethod
    def setUpClass(cls):
        sys.addaudithook(deny_network)

    def test_live_capture_score_repeat_import_preserves_metrics_and_saved_evidence(
        self,
    ):
        source, folder, archive, view, path = self.view()
        storage = self.root / "registry"
        first = run(folder, storage, score_path=path)["imports"]
        second = run(folder, storage, score_path=path)["imports"]
        self.assertEqual(
            [r["mlflowRunId"] for r in first], [r["mlflowRunId"] for r in second]
        )
        self.assertTrue(all(r["alreadyImported"] for r in second))
        shutil.rmtree(source)
        shutil.rmtree(folder)
        path.unlink()
        with registry(storage) as store:
            projection = store.client.get_run(first[2]["mlflowRunId"])
            self.assertEqual(projection.data.params["evidence_kind"], "live-capture")
            self.assertEqual(projection.data.metrics["runtime.observedDispatches"], 3)
            self.assertEqual(projection.data.metrics["runtime.knownInputTokens"], 300)
            child = store.client.get_run(first[-1]["mlflowRunId"])
            self.assertEqual(
                child.data.params["reference_status"], "candidate-not-independent"
            )
            self.assertEqual(
                child.data.tags["mlflow.parentRunId"], first[1]["mlflowRunId"]
            )
            for metric in child.data.metrics:
                self.assertEqual(
                    len(store.client.get_metric_history(child.info.run_id, metric)), 1
                )
            saved = local_path(child.info.artifact_uri) / "normlab"
            self.assertEqual(
                verify_score(
                    read_archive(saved / "archive"), decode(read(saved / "score.json"))
                ),
                view,
            )
            self.assertEqual(len(store.client.search_runs([store.experiment_id])), 4)

    def test_unknown_dispatch_and_usage_are_not_imported_as_zero(self):
        source, folder, archive, view, path = self.view(
            scheduled=False, phase="after-response"
        )
        storage = self.root / "registry"
        receipts = run(folder, storage, score_path=path)["imports"]
        with registry(storage) as store:
            item = store.client.get_run(receipts[2]["mlflowRunId"])
            self.assertEqual(item.data.metrics["runtime.unknownDispatchAttempts"], 1)
            self.assertEqual(item.data.metrics["runtime.unknownUsageAttempts"], 1)
            child = store.client.get_run(receipts[-1]["mlflowRunId"])
            self.assertEqual(child.data.metrics["selected.scoredQuestions"], 0)
            self.assertNotIn("selected.agreementAmongScored", child.data.metrics)

    def test_native_score_reference_revision_adds_child_without_reimporting_capture(
        self,
    ):
        source, folder, archive, view, path = self.view()
        storage = self.root / "registry"
        first = run(folder, storage, score_path=path)["imports"]
        from runtime_reference import reference
        from runtime_score import score

        raw = decode(view["referenceInputs"]["sourceUtf8"].encode())
        raw["revision"] = "synthetic-next-reference"
        revised = score(archive, reference(archive, canonical(raw)))
        path.write_bytes(canonical(revised))
        second = run(folder, storage, score_path=path)["imports"]
        self.assertTrue(all(r["alreadyImported"] for r in second[:-1]))
        self.assertNotEqual(first[-1]["mlflowRunId"], second[-1]["mlflowRunId"])
        self.assertEqual(first[1]["mlflowRunId"], second[1]["mlflowRunId"])


if __name__ == "__main__":
    unittest.main()
