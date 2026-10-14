"""Pinned real local MLflow runtime revision/recovery checks, network forbidden."""

import copy
import json
import os
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_offline_runtime_mlflow_projection as fixtures
from execution_resume import continue_mock
from execution_test_support import ROOT, ExecutionCase
from import_runtime_mlflow import run
from mlflow_registry import local_path, registry
from runtime_archive_export import export_runtime_archive
from runtime_archive_reader import read_archive
from runtime_mlflow_projection import project, snapshot
from test_mlflow_import import NETWORK_GUARD, Interrupted, deny_network


class RuntimeImportTests(ExecutionCase):
    input = fixtures.ConsumerTests.input
    output = fixtures.ConsumerTests.output
    script = fixtures.ConsumerTests.script
    failure = staticmethod(fixtures.ConsumerTests.failure)
    paused = fixtures.ConsumerTests.paused
    request = fixtures.ConsumerTests.request
    orphan = fixtures.ConsumerTests.orphan
    archive = fixtures.ConsumerTests.archive

    @classmethod
    def setUpClass(cls):
        sys.addaudithook(deny_network)

    def setUp(self):
        super().setUp()
        self.storage = self.root / "registry"

    def write_records(self, store, root, archive):
        imported = {}
        for row in project(archive):
            parent = imported.get(row["parentKey"])
            receipt = store.write(
                row,
                root,
                parent["mlflowRunId"] if parent else None,
                runtime_archive=archive,
            )
            imported[row["key"]] = receipt
        return list(imported.values())

    def saved_archive(self, store, receipt):
        saved = store.client.get_run(receipt["mlflowRunId"])
        return local_path(saved.info.artifact_uri) / "normlab/archive"

    def test_repeat_import_one_history_and_portable_saved_archive(self):
        source, archive, _ = self.archive()
        expected = read_archive(archive).index
        first = run(archive, self.storage)["imports"]
        second = run(archive, self.storage)["imports"]
        self.assertEqual(
            [row["mlflowRunId"] for row in first],
            [row["mlflowRunId"] for row in second],
        )
        self.assertTrue(all(row["alreadyImported"] for row in second))
        shutil.rmtree(source)
        shutil.rmtree(archive)
        with registry(self.storage) as store:
            saved = self.saved_archive(store, first[2])
            self.assertEqual(read_archive(saved).index, expected)
            runs = store.client.search_runs([store.experiment_id])
            self.assertEqual(len(runs), 3)
            for item in runs:
                self.assertEqual(item.info.status, "FINISHED")
                for name in item.data.metrics:
                    self.assertEqual(
                        len(store.client.get_metric_history(item.info.run_id, name)), 1
                    )
        # The registry artifact itself is a valid independently importable archive.
        third = run(saved, self.storage)["imports"]
        self.assertTrue(all(row["alreadyImported"] for row in third))

    def test_original_and_continued_revisions_preserve_execution_and_both_archives(
        self,
    ):
        source, first_archive, _ = self.archive()
        original = read_archive(first_archive)
        first = run(first_archive, self.storage)["imports"]
        continue_mock(source, self.request(source))
        second_archive = self.output("continued")
        export_runtime_archive(source, second_archive)
        continued = read_archive(second_archive)
        second = run(second_archive, self.storage)["imports"]
        self.assertEqual(first[0]["mlflowRunId"], second[0]["mlflowRunId"])
        self.assertTrue(second[0]["alreadyImported"])
        self.assertEqual(len(second), 4)
        self.assertNotEqual(first[1]["mlflowRunId"], second[1]["mlflowRunId"])
        with registry(self.storage) as store:
            self.assertEqual(len(store.client.search_runs([store.experiment_id])), 6)
            self.assertEqual(
                read_archive(self.saved_archive(store, first[2])).index, original.index
            )
            self.assertEqual(
                read_archive(self.saved_archive(store, second[2])).index,
                continued.index,
            )
            seal = store.client.get_run(second[3]["mlflowRunId"])
            self.assertEqual(
                seal.data.tags["mlflow.parentRunId"], second[1]["mlflowRunId"]
            )
        self.assertTrue(
            all(
                row["alreadyImported"]
                for row in run(first_archive, self.storage)["imports"]
            )
        )

    def test_failure_after_metric_commit_recovers_same_run_and_one_history(self):
        _, directory, _ = self.archive()
        with snapshot(directory) as (root, archive), registry(self.storage) as store:
            original = store.client.log_metric
            calls = []

            def fail_after_commit(*args, **kwargs):
                original(*args, **kwargs)
                calls.append(args[0])
                raise RuntimeError("Injected local fault")

            with patch.object(
                store.client, "log_metric", side_effect=fail_after_commit
            ):
                with self.assertRaises(RuntimeError):
                    self.write_records(store, root, archive)
            receipts = self.write_records(store, root, archive)
            self.assertEqual(receipts[2]["mlflowRunId"], calls[0])
            saved = store.client.get_run(calls[0])
            for name in saved.data.metrics:
                self.assertEqual(
                    len(store.client.get_metric_history(calls[0], name)), 1
                )

    def test_interruption_after_creation_before_ledger_binding_recovers_unique_run(
        self,
    ):
        _, directory, _ = self.archive()
        with snapshot(directory) as (root, archive), registry(self.storage) as store:
            original = store.client.create_run
            created = []

            def interrupt(*args, **kwargs):
                created.append(original(*args, **kwargs).info.run_id)
                raise Interrupted()

            with patch.object(store.client, "create_run", side_effect=interrupt):
                with self.assertRaises(Interrupted):
                    self.write_records(store, root, archive)
            receipts = self.write_records(store, root, archive)
            self.assertEqual(receipts[0]["mlflowRunId"], created[0])
            self.assertEqual(len(store.client.search_runs([store.experiment_id])), 3)

    def test_interruption_after_projection_upload_recovers_existing_artifacts(self):
        _, directory, _ = self.archive()
        with snapshot(directory) as (root, archive), registry(self.storage) as store:
            original = store.client.log_artifacts
            interrupted = []

            def interrupt(run_id, path, **kwargs):
                original(run_id, path, **kwargs)
                if (
                    store.client.get_run(run_id).data.tags["normlab.kind"]
                    == "runtime-projection"
                ):
                    interrupted.append(run_id)
                    raise Interrupted()

            with patch.object(store.client, "log_artifacts", side_effect=interrupt):
                with self.assertRaises(Interrupted):
                    self.write_records(store, root, archive)
            receipts = self.write_records(store, root, archive)
            self.assertEqual(receipts[2]["mlflowRunId"], interrupted[0])
            self.assertEqual(
                read_archive(self.saved_archive(store, receipts[2])).index,
                archive.index,
            )

    def test_completed_artifact_and_parent_drift_rejected(self):
        _, directory, _ = self.archive()
        receipts = run(directory, self.storage)["imports"]
        with registry(self.storage) as store:
            saved = self.saved_archive(store, receipts[2])
            path = saved / "projection.json"
            raw = path.read_bytes()
            path.write_bytes(b"{}")
        with self.assertRaises(ValueError):
            run(directory, self.storage)
        path.write_bytes(raw)
        with registry(self.storage) as store:
            store.client.set_tag(
                receipts[0]["mlflowRunId"], "mlflow.parentRunId", "foreign"
            )
        with self.assertRaisesRegex(ValueError, "parent conflict"):
            run(directory, self.storage)

    def test_changed_runtime_record_or_wrong_parent_rejected_before_intent(self):
        _, directory, _ = self.archive()
        with snapshot(directory) as (root, archive), registry(self.storage) as store:
            rows = project(archive)
            changed = copy.deepcopy(rows[0])
            changed["payload"]["executionReady"] = True
            with self.assertRaisesRegex(ValueError, "record binding"):
                store.write(changed, root, runtime_archive=archive)
            with self.assertRaisesRegex(ValueError, "parent binding"):
                store.write(rows[1], root, "foreign", runtime_archive=archive)
            self.assertEqual(
                store.db.execute("SELECT count(*) FROM imports").fetchone()[0], 0
            )
            self.assertFalse(store.client.search_runs([store.experiment_id]))

    def test_checkpoint_over_two_mib_import_and_reimport(self):
        _, source, _, _ = self.paused("after-terminal")
        path = source / "checkpoint.json"
        path.write_bytes(path.read_bytes() + b" " * (2 * 1024 * 1024 + 1))
        directory = self.output("large-checkpoint-import")
        export_runtime_archive(source, directory)
        receipts = run(directory, self.storage)["imports"]
        self.assertTrue(
            all(
                row["alreadyImported"]
                for row in run(directory, self.storage)["imports"]
            )
        )
        with registry(self.storage) as store:
            saved = read_archive(self.saved_archive(store, receipts[2]))
            self.assertEqual(saved.files["source/checkpoint.json"], path.read_bytes())

    def test_unknown_and_adopted_capture_keep_attempt_count_and_null_cost(self):
        source, unknown, _ = self.archive("after-response", tasks=1)
        first = run(unknown, self.storage)["imports"]
        continue_mock(
            source,
            self.request(
                source, action="adopt-saved-outcome", outcome=self.orphan(source)
            ),
        )
        adopted = self.output("adopted-import")
        export_runtime_archive(source, adopted)
        second = run(adopted, self.storage)["imports"]
        with registry(self.storage) as store:
            before = read_archive(self.saved_archive(store, first[2])).summary()
            after = read_archive(self.saved_archive(store, second[2])).summary()
            self.assertEqual(before["state"], "paused-unknown")
            self.assertEqual(after["state"], "finished")
            self.assertEqual(before["counts"]["attempts"], 1)
            self.assertEqual(after["counts"]["attempts"], 1)
            self.assertIsNone(before["actualCost"])
            self.assertIsNone(after["actualCost"])
            self.assertFalse(after["semanticQualityEvidence"])

    def test_interruption_after_finish_before_ledger_commit_recovers(self):
        _, directory, _ = self.archive()
        with snapshot(directory) as (root, archive), registry(self.storage) as store:
            original = store.client.set_terminated
            finished = []

            def interrupt(run_id, **kwargs):
                original(run_id, **kwargs)
                finished.append(run_id)
                raise Interrupted()

            with patch.object(store.client, "set_terminated", side_effect=interrupt):
                with self.assertRaises(Interrupted):
                    self.write_records(store, root, archive)
            receipts = self.write_records(store, root, archive)
            self.assertEqual(receipts[0]["mlflowRunId"], finished[0])
            self.assertEqual(len(store.client.search_runs([store.experiment_id])), 3)

    def test_real_cli_network_denied_and_repeat(self):
        _, directory, _ = self.archive()
        args = [
            sys.executable,
            "-B",
            "-c",
            NETWORK_GUARD,
            str(ROOT / "evaluation/import_runtime_mlflow.py"),
            str(directory),
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
            [row["mlflowRunId"] for row in results[0]],
            [row["mlflowRunId"] for row in results[1]],
        )
        self.assertTrue(all(row["alreadyImported"] for row in results[1]))

    def test_completed_extra_empty_directory_rejected(self):
        _, directory, _ = self.archive()
        receipts = run(directory, self.storage)["imports"]
        with registry(self.storage) as store:
            saved = self.saved_archive(store, receipts[2])
            (saved / "unexpected-empty").mkdir()
        with self.assertRaisesRegex(ValueError, "artifact directory"):
            run(directory, self.storage)


if __name__ == "__main__":
    unittest.main()
