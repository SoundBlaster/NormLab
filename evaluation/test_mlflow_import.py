"""Pinned real MLflow/SQLite integration; network transport is forbidden."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mlflow_registry import local_path, registry
from offline_bundle import verify
from offline_mlflow_projection import project, snapshot
from test_offline_bundle import ROOT
from test_offline_mlflow_projection import bundles

NETWORK_GUARD = """
import sys, runpy
from pathlib import Path
def guard(event, args):
    if event in {'socket.connect', 'socket.connect_ex', 'socket.bind', 'socket.getaddrinfo'}:
        raise AssertionError('Network transport forbidden in local MLflow check')
sys.addaudithook(guard)
script = Path(sys.argv[1]).resolve()
sys.argv = sys.argv[1:]
sys.path.insert(0, str(script.parent))
runpy.run_path(str(script), run_name='__main__')
"""


def deny_network(event, _):
    if event in {
        "socket.connect",
        "socket.connect_ex",
        "socket.bind",
        "socket.getaddrinfo",
    }:
        raise AssertionError("Network transport forbidden in local MLflow check")


class Interrupted(BaseException):
    pass


class MLflowImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["MLFLOW_DISABLE_TELEMETRY"] = "true"
        os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"
        sys.addaudithook(deny_network)
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.bundles = bundles(cls.root)

    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(dir=self.root))
        self.storage = self.directory / "registry"

    def import_bundle(self, name="classification", folder=None):
        with snapshot(folder or self.bundles[name]) as (root, envelope, digest):
            parent, view = project(root, envelope, digest)
            with registry(self.storage) as store:
                capture = store.write(parent, root)
                score = store.write(view, root, capture["mlflowRunId"])
            return capture, score

    def test_repeated_import_has_one_metric_history_item_and_portable_raw_bundle(self):
        first = self.import_bundle()
        second = self.import_bundle()
        self.assertEqual(
            [x["mlflowRunId"] for x in first], [x["mlflowRunId"] for x in second]
        )
        self.assertTrue(all(x["alreadyImported"] for x in second))
        with registry(self.storage) as store:
            runs = store.client.search_runs([store.experiment_id])
            self.assertEqual(len(runs), 2)
            for run in runs:
                self.assertEqual(run.info.status, "FINISHED")
                for name in run.data.metrics:
                    self.assertEqual(
                        len(store.client.get_metric_history(run.info.run_id, name)), 1
                    )
            score = store.client.get_run(first[1]["mlflowRunId"])
            verify(local_path(score.info.artifact_uri) / "normlab/bundle")

    def test_all_adapters_and_multiple_score_views_preserve_capture_parent(self):
        results = {name: self.import_bundle(name) for name in self.bundles}
        for left, right in (
            ("classification", "no-labels"),
            ("stage1", "stage1-scored"),
        ):
            self.assertEqual(
                results[left][0]["mlflowRunId"], results[right][0]["mlflowRunId"]
            )
            self.assertNotEqual(
                results[left][1]["mlflowRunId"], results[right][1]["mlflowRunId"]
            )
        with registry(self.storage) as store:
            runs = store.client.search_runs([store.experiment_id])
            self.assertEqual(len(runs), 8)
            for name, (parent, score) in results.items():
                run = store.client.get_run(score["mlflowRunId"])
                self.assertEqual(
                    run.data.tags["mlflow.parentRunId"], parent["mlflowRunId"]
                )
                self.assertNotIn(
                    "selected_reference.criticalErrorFreeRate", run.data.metrics
                )
                if name in {"no-labels", "stage1"}:
                    self.assertNotIn(
                        "selected_reference.agreementAmongScored", run.data.metrics
                    )

    def test_failure_after_metric_commit_resumes_same_run_without_duplicate_history(
        self,
    ):
        with snapshot(self.bundles["classification"]) as (root, envelope, digest):
            parent, view = project(root, envelope, digest)
            with registry(self.storage) as store:
                capture = store.write(parent, root)
                original = store.client.log_metric

                def fail_after_write(*args, **kwargs):
                    original(*args, **kwargs)
                    raise RuntimeError("Injected interruption after metric commit")

                with patch.object(
                    store.client, "log_metric", side_effect=fail_after_write
                ):
                    with self.assertRaises(RuntimeError):
                        store.write(view, root, capture["mlflowRunId"])
                row = store.db.execute(
                    "SELECT mlflow_id,state FROM imports WHERE key=?", (view["key"],)
                ).fetchone()
                self.assertEqual(row[1], "failed")
        recovered = self.import_bundle()[1]
        self.assertEqual(recovered["mlflowRunId"], row[0])
        with registry(self.storage) as store:
            run = store.client.get_run(row[0])
            for name in run.data.metrics:
                self.assertEqual(len(store.client.get_metric_history(row[0], name)), 1)

    def test_interrupt_after_create_before_ledger_binding_recovers_by_unique_tag(self):
        with snapshot(self.bundles["classification"]) as (root, envelope, digest):
            parent, _ = project(root, envelope, digest)
            with registry(self.storage) as store:
                original = store.client.create_run
                created = []

                def interrupt(*args, **kwargs):
                    created.append(original(*args, **kwargs).info.run_id)
                    raise Interrupted()

                with patch.object(store.client, "create_run", side_effect=interrupt):
                    with self.assertRaises(Interrupted):
                        store.write(parent, root)
                self.assertEqual(
                    store.db.execute("SELECT mlflow_id,state FROM imports").fetchone(),
                    (None, "pending"),
                )
        capture, _ = self.import_bundle()
        self.assertEqual(capture["mlflowRunId"], created[0])

    def test_interrupt_after_finish_before_ledger_commit_reuses_run(self):
        with snapshot(self.bundles["classification"]) as (root, envelope, digest):
            parent, _ = project(root, envelope, digest)
            with registry(self.storage) as store:
                original = store.client.set_terminated

                def interrupt(*args, **kwargs):
                    original(*args, **kwargs)
                    raise Interrupted()

                with patch.object(
                    store.client, "set_terminated", side_effect=interrupt
                ):
                    with self.assertRaises(Interrupted):
                        store.write(parent, root)
                old_id = store.db.execute("SELECT mlflow_id FROM imports").fetchone()[0]
        self.assertEqual(self.import_bundle()[0]["mlflowRunId"], old_id)

    def test_failure_after_artifact_copy_is_recoverable(self):
        with snapshot(self.bundles["classification"]) as (root, envelope, digest):
            parent, _ = project(root, envelope, digest)
            with registry(self.storage) as store:
                original = store.client.log_artifacts

                def fail(*args, **kwargs):
                    original(*args, **kwargs)
                    run = store.client.get_run(args[0])
                    (
                        local_path(run.info.artifact_uri) / "normlab/projection.json"
                    ).write_text("partial copy")
                    raise RuntimeError("Injected after artifact copy")

                with patch.object(store.client, "log_artifacts", side_effect=fail):
                    with self.assertRaises(RuntimeError):
                        store.write(parent, root)
                old_id = store.db.execute("SELECT mlflow_id FROM imports").fetchone()[0]
        self.assertEqual(self.import_bundle()[0]["mlflowRunId"], old_id)

    def test_same_score_id_with_changed_bundle_bytes_rejected(self):
        self.import_bundle()
        folder = self.directory / "whitespace-bundle"
        shutil.copytree(self.bundles["classification"], folder)
        with (folder / "bundle.json").open("ab") as stream:
            stream.write(b"\n")
        verify(folder)
        with self.assertRaisesRegex(ValueError, "identity/digest conflict"):
            self.import_bundle(folder=folder)
        with registry(self.storage) as store:
            self.assertEqual(len(store.client.search_runs([store.experiment_id])), 2)

    def test_completed_artifact_drift_is_rejected(self):
        first = self.import_bundle()
        with registry(self.storage) as store:
            score = store.client.get_run(first[1]["mlflowRunId"])
            index = local_path(score.info.artifact_uri) / "normlab/bundle/bundle.json"
            index.write_text("invalid")
        with self.assertRaisesRegex(ValueError, "artifact drift"):
            self.import_bundle()

    def test_metric_history_conflict_is_not_overwritten(self):
        first = self.import_bundle()
        run_id = first[1]["mlflowRunId"]
        with registry(self.storage) as store:
            run = store.client.get_run(run_id)
            name = next(iter(run.data.metrics))
            store.client.log_metric(
                run_id, name, run.data.metrics[name] + 1, timestamp=1
            )
        with self.assertRaisesRegex(ValueError, "Metric history conflict"):
            self.import_bundle()
        with registry(self.storage) as store:
            self.assertEqual(len(store.client.get_metric_history(run_id, name)), 2)

    def test_ambiguous_duplicate_runs_are_rejected(self):
        first = self.import_bundle()
        with registry(self.storage) as store:
            run = store.client.get_run(first[0]["mlflowRunId"])
            store.client.create_run(store.experiment_id, tags=run.data.tags)
        with self.assertRaisesRegex(ValueError, "Ambiguous duplicate"):
            self.import_bundle()

    def test_concurrent_processes_create_only_one_parent_and_view(self):
        args = [
            sys.executable,
            "-B",
            "-c",
            NETWORK_GUARD,
            str(ROOT / "evaluation/import_offline_mlflow.py"),
            str(self.bundles["classification"]),
            "--storage",
            str(self.storage),
        ]
        env = {
            "PATH": os.defpath,
            "MLFLOW_DISABLE_TELEMETRY": "true",
            "MLFLOW_DISABLE_AGENT_HINT": "1",
        }
        processes = [
            subprocess.Popen(
                args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            for _ in range(2)
        ]
        self.addCleanup(lambda: [p.kill() for p in processes if p.poll() is None])
        results = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=120)
            self.assertEqual(process.returncode, 0, stderr)
            results.append(json.loads(stdout))
        self.assertEqual(
            results[0]["score"]["mlflowRunId"], results[1]["score"]["mlflowRunId"]
        )
        self.assertEqual(
            sorted(r["score"]["alreadyImported"] for r in results), [False, True]
        )
        with registry(self.storage) as store:
            self.assertEqual(len(store.client.search_runs([store.experiment_id])), 2)

    def test_remote_tracking_environment_cannot_change_local_destination(self):
        with patch.dict(
            os.environ, {"MLFLOW_TRACKING_URI": "https://invalid.example/never"}
        ):
            self.import_bundle()
        self.assertTrue((self.storage / "tracking.sqlite").is_file())

    def test_network_guard_is_active(self):
        import socket

        with self.assertRaisesRegex(AssertionError, "Network transport forbidden"):
            socket.create_connection(("127.0.0.1", 9))


if __name__ == "__main__":
    unittest.main()
