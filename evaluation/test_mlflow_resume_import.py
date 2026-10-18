"""Real local pinned MLflow continuation imports; no network or inference."""

import shutil
import sys
from unittest.mock import patch

import test_offline_resume_consumers as fixtures
from execution_test_support import ExecutionCase, canonical
from import_runtime_mlflow import run
from mlflow_registry import local_path, registry
from offline_bundle import decode, read
from runtime_archive_export import export_runtime_archive
from runtime_consumer import read_archive
from runtime_reference import reference
from runtime_resume_archive import export_archive
from runtime_score import score, verify_score
from test_mlflow_import import deny_network


class MLflowResumeTests(ExecutionCase):
    prepared = fixtures.ResumeConsumerTests.prepared
    initial = fixtures.ResumeConsumerTests.initial
    source = fixtures.ResumeConsumerTests.source
    proposal = fixtures.ResumeConsumerTests.proposal
    apply = fixtures.ResumeConsumerTests.apply
    files = fixtures.ResumeConsumerTests.files
    guarded = fixtures.ResumeConsumerTests.guarded
    resumed = fixtures.ResumeConsumerTests.resumed
    archive = fixtures.ResumeConsumerTests.archive
    view = fixtures.ResumeConsumerTests.view

    @classmethod
    def setUpClass(cls):
        sys.addaudithook(deny_network)

    def test_idempotent_score_import_and_recovery_preserve_portable_v3_artifacts(self):
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
            self.assertEqual(projection.data.metrics["runtime.attempts"], 3)
            child = store.client.get_run(first[-1]["mlflowRunId"])
            self.assertEqual(
                child.data.tags["mlflow.parentRunId"], first[1]["mlflowRunId"]
            )
            for record in first:
                for metric in store.client.get_run(record["mlflowRunId"]).data.metrics:
                    self.assertEqual(
                        len(
                            store.client.get_metric_history(
                                record["mlflowRunId"], metric
                            )
                        ),
                        1,
                    )
            saved = local_path(child.info.artifact_uri) / "normlab"
            self.assertEqual(
                verify_score(
                    read_archive(saved / "archive"), decode(read(saved / "score.json"))
                ),
                view,
            )
            self.assertEqual(len(store.client.search_runs([store.experiment_id])), 5)

    def test_original_and_two_resumed_revisions_share_execution_without_overwrite(self):
        root = self.source(tasks=4)
        storage = self.root / "registry"
        basefolder = self.root / "original"
        export_runtime_archive(root, basefolder, evidence_kind="live-capture")
        base = run(basefolder, storage)["imports"]
        _, request, clock = self.proposal(root)

        def fault(point):
            if point == "after-terminal":
                raise KeyboardInterrupt("synthetic partial revision")

        with self.assertRaises(KeyboardInterrupt):
            self.apply(root, request, clock, hook=fault)
        firstfolder = self.root / "partial"
        export_archive(root, firstfolder)
        first = run(firstfolder, storage)["imports"]
        _, request2, clock2 = self.proposal(root)
        self.apply(root, request2, clock2)
        secondfolder = self.root / "complete"
        export_archive(root, secondfolder)
        second = run(secondfolder, storage)["imports"]
        self.assertEqual(base[0]["mlflowRunId"], first[0]["mlflowRunId"])
        self.assertEqual(first[0]["mlflowRunId"], second[0]["mlflowRunId"])
        self.assertNotEqual(first[1]["mlflowRunId"], second[1]["mlflowRunId"])
        self.assertNotEqual(first[2]["mlflowRunId"], second[2]["mlflowRunId"])
        again = run(firstfolder, storage)["imports"]
        self.assertTrue(all(r["alreadyImported"] for r in again))
        with registry(storage) as store:
            self.assertEqual(
                store.client.get_run(first[2]["mlflowRunId"]).data.metrics[
                    "runtime.attempts"
                ],
                2,
            )
            self.assertEqual(
                store.client.get_run(second[2]["mlflowRunId"]).data.metrics[
                    "runtime.attempts"
                ],
                4,
            )

    def test_unknown_capture_and_new_reference_revision_do_not_invent_usage_or_reimport(
        self,
    ):
        root, folder, archive, view, path = self.view(phase="after-response")
        storage = self.root / "registry"
        first = run(folder, storage, score_path=path)["imports"]
        raw = decode(view["referenceInputs"]["sourceUtf8"].encode())
        raw["revision"] = "next-synthetic-reference"
        revised = score(archive, reference(archive, canonical(raw)))
        path.write_bytes(canonical(revised))
        second = run(folder, storage, score_path=path)["imports"]
        self.assertTrue(all(r["alreadyImported"] for r in second[:-1]))
        self.assertNotEqual(first[-1]["mlflowRunId"], second[-1]["mlflowRunId"])
        with registry(storage) as store:
            parent = store.client.get_run(first[2]["mlflowRunId"])
            self.assertEqual(parent.data.metrics["runtime.unknownDispatchAttempts"], 1)
            self.assertEqual(parent.data.metrics["runtime.unknownUsageAttempts"], 1)
            child = store.client.get_run(first[-1]["mlflowRunId"])
            self.assertEqual(child.data.metrics["selected.scoredQuestions"], 1)
            self.assertEqual(
                child.data.metrics["selected.selectedUnevaluatedQuestions"], 2
            )

    def test_interruption_after_metric_commit_reuses_same_capture_without_duplicates(
        self,
    ):
        root, folder, archive, view, path = self.view(phase="after-terminal")
        storage = self.root / "registry"
        from runtime_mlflow_projection import project, snapshot

        with snapshot(folder) as (private, verified):
            records = project(verified)
            with registry(storage) as store:
                parent = store.write(records[0], private, runtime_archive=verified)
                capture = store.write(
                    records[1], private, parent["mlflowRunId"], runtime_archive=verified
                )
                original = store.client.log_metric

                def fail(*args, **kwargs):
                    original(*args, **kwargs)
                    raise RuntimeError("synthetic post-metric interruption")

                with (
                    patch.object(store.client, "log_metric", side_effect=fail),
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
            for metric in store.client.get_run(result[2]["mlflowRunId"]).data.metrics:
                self.assertEqual(
                    len(
                        store.client.get_metric_history(
                            result[2]["mlflowRunId"], metric
                        )
                    ),
                    1,
                )
