"""Serialized local MLflow 3.16.1 projection with resumable import intents."""

import fcntl
import os
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import unquote, urlparse

from offline_bundle import canonical, read, require

EXPERIMENT = "NormLab verified offline evidence v1"


@contextmanager
def registry(storage):
    """The OS releases the lock after interruption; all writers share this root."""
    root = storage.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (root / "import.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"
        os.environ["MLFLOW_DISABLE_TELEMETRY"] = "true"
        os.environ["MLFLOW_ENABLE_OTLP_EXPORTER"] = "false"
        from importlib.metadata import version

        require(version("mlflow") == "3.16.1", "Pinned MLflow runtime required")
        from mlflow.tracking import MlflowClient

        client = MlflowClient(tracking_uri="sqlite:///" + str(root / "tracking.sqlite"))
        artifact_root = root / "artifacts"
        require(
            artifact_root.resolve() == artifact_root,
            "Artifact root cannot escape storage",
        )
        artifact_root.mkdir(exist_ok=True)
        experiment = client.get_experiment_by_name(EXPERIMENT)
        if experiment is None:
            experiment_id = client.create_experiment(
                EXPERIMENT, artifact_location=artifact_root.as_uri()
            )
        else:
            require(
                experiment.lifecycle_stage == "active", "Active experiment required"
            )
            require(
                local_path(experiment.artifact_location) == artifact_root,
                "Local artifact root",
            )
            experiment_id = experiment.experiment_id
        with sqlite3.connect(root / "imports.sqlite") as db:
            db.execute("""CREATE TABLE IF NOT EXISTS imports (
                key TEXT PRIMARY KEY, kind TEXT NOT NULL, original_id TEXT NOT NULL,
                digest TEXT NOT NULL, mlflow_id TEXT, state TEXT NOT NULL,
                error_type TEXT)""")
            db.commit()
            yield Registry(root, client, db, experiment_id)


def local_path(uri):
    parsed = urlparse(uri)
    require(
        parsed.scheme == "file"
        and not parsed.netloc
        and not parsed.query
        and not parsed.fragment,
        "Local file URI",
    )
    return Path(unquote(parsed.path)).resolve()


class Registry:
    def __init__(self, root, client, db, experiment_id):
        self.root, self.client, self.db, self.experiment_id = (
            root,
            client,
            db,
            experiment_id,
        )

    def intent(self, record, parent):
        key = record["key"]
        row = self.db.execute(
            "SELECT kind, original_id, digest, mlflow_id, state FROM imports WHERE key=?",
            (key,),
        ).fetchone()
        require(
            row is None
            or row[:3] == (record["kind"], record["originalId"], record["digest"]),
            "Import identity/digest conflict",
        )
        if row is None:
            self.db.execute(
                "INSERT INTO imports VALUES (?, ?, ?, ?, NULL, 'pending', NULL)",
                (key, record["kind"], record["originalId"], record["digest"]),
            )
            self.db.commit()  # Durable intent before creating any MLflow run.
        runs = self.client.search_runs(
            [self.experiment_id],
            filter_string=f"tags.`normlab.import_key` = '{key}'",
            run_view_type=3,
            max_results=2,
        )
        require(len(runs) <= 1, "Ambiguous duplicate MLflow runs")
        if row and row[3]:
            require(
                len(runs) == 1 and runs[0].info.run_id == row[3], "Ledger/run conflict"
            )
        tags = {
            "normlab.import_key": key,
            "normlab.original_id": record["originalId"],
            "normlab.projection_digest": record["digest"],
            "normlab.kind": record["kind"],
            "normlab.release_approved": "false",
            "normlab.inference_calls_executed": "0",
        }
        if parent:
            tags["mlflow.parentRunId"] = parent
        if runs:
            run = runs[0]
            require(
                run.info.lifecycle_stage == "active",
                "Deleted import requires intervention",
            )
            require(
                all(run.data.tags.get(k) == v for k, v in tags.items()),
                "MLflow identity/tag conflict",
            )
            require(
                run.data.tags.get("mlflow.parentRunId") == parent,
                "MLflow parent conflict",
            )
        else:
            run = self.client.create_run(
                self.experiment_id,
                tags={**tags, "normlab.import_state": "pending"},
                run_name=record["originalId"],
            )
        self.db.execute(
            "UPDATE imports SET mlflow_id=? WHERE key=?", (run.info.run_id, key)
        )
        self.db.commit()
        return run, bool(row and row[4] == "completed")

    def artifact_root(self, run):
        target = local_path(run.info.artifact_uri)
        require(
            target.is_relative_to(self.root / "artifacts"), "Run artifact containment"
        )
        return target

    def write(self, record, snapshot, parent=None, *, runtime_archive=None):
        archive_payload = {}
        if record["kind"].startswith("runtime-") or runtime_archive is not None:
            from offline_bundle import MAX_BYTES
            from runtime_mlflow_projection import archive_files, project

            require(
                record in project(runtime_archive), "Verified runtime record binding"
            )
            require(
                len(canonical(record["payload"])) <= MAX_BYTES,
                "Runtime consumer projection byte cap",
            )
            parent_key = record["parentKey"]
            if parent_key is None:
                require(parent is None, "Runtime execution has no parent")
            else:
                parent_row = self.db.execute(
                    "SELECT mlflow_id, state FROM imports WHERE key=?", (parent_key,)
                ).fetchone()
                require(
                    parent is not None and parent_row == (parent, "completed"),
                    "Completed runtime parent binding required",
                )
            if record["kind"] == "runtime-projection":
                archive_payload = archive_files(runtime_archive)
        # Bound the entire import payload before creating a durable registry intent.
        if archive_payload:
            from offline_bundle import MAX_FILES, MAX_TOTAL_BYTES
            from runtime_archive_format import directories

            require(
                len(archive_payload) + len(directories(archive_payload)) + 2
                <= MAX_FILES,
                "Runtime import entry cap",
            )
            require(
                sum(map(len, archive_payload.values()))
                + len(canonical(record["payload"]))
                <= MAX_TOTAL_BYTES,
                "Runtime import byte cap",
            )
        run, completed = self.intent(record, parent)
        run_id, key = run.info.run_id, record["key"]
        try:
            require(
                set(run.data.metrics) <= set(record["metrics"]),
                "Unexpected registry metrics",
            )
            require(
                set(run.data.params) <= set(record["params"]),
                "Unexpected registry parameters",
            )
            if completed:
                require(
                    run.info.status == "FINISHED"
                    and run.data.tags.get("normlab.import_state") == "completed",
                    "Completed run state drift",
                )
            else:
                self.db.execute(
                    "UPDATE imports SET state='pending', error_type=NULL WHERE key=?",
                    (key,),
                )
                self.db.commit()
                self.client.update_run(run_id, status="RUNNING")
                self.client.set_tag(run_id, "normlab.import_state", "pending")
            # A crash after a metric commit does not append another history item.
            for name, number in record["metrics"].items():
                history = self.client.get_metric_history(run_id, name)
                if history:
                    require(
                        len(history) == 1
                        and history[0].value == number
                        and history[0].step == 0
                        and history[0].timestamp == 0,
                        "Metric history conflict",
                    )
                else:
                    require(not completed, "Completed metric missing")
                    self.client.log_metric(run_id, name, number, timestamp=0, step=0)
            for name, value in record["params"].items():
                if name in run.data.params:
                    require(run.data.params[name] == value, "Parameter conflict")
                else:
                    require(not completed, "Completed parameter missing")
                    self.client.log_param(run_id, name, value)
            with tempfile.TemporaryDirectory() as temporary:
                payload = Path(temporary)
                (payload / "projection.json").write_bytes(canonical(record["payload"]))
                if record["kind"] == "score":
                    shutil.copytree(snapshot, payload / "bundle")
                for name, raw in archive_payload.items():
                    target = payload / "archive" / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
                destination = self.artifact_root(run) / "normlab"
                expected_files = {
                    path.relative_to(payload)
                    for path in payload.rglob("*")
                    if path.is_file()
                }
                expected_directories = {
                    path.relative_to(payload)
                    for path in payload.rglob("*")
                    if path.is_dir()
                }
                actual_files = set()
                actual_directories = set()
                require(not destination.is_symlink(), "Artifact entry type")
                for path in destination.rglob("*"):
                    require(
                        not path.is_symlink() and (path.is_dir() or path.is_file()),
                        "Artifact entry type",
                    )
                    if path.is_file():
                        relative = path.relative_to(destination)
                        require(relative in expected_files, "Unexpected artifact file")
                        actual_files.add(relative)
                    elif archive_payload:
                        relative = path.relative_to(destination)
                        require(
                            relative in expected_directories,
                            "Unexpected runtime artifact directory",
                        )
                        actual_directories.add(relative)
                if completed:
                    require(actual_files == expected_files, "Completed artifact drift")
                    if archive_payload:
                        require(
                            actual_directories == expected_directories,
                            "Completed runtime directory drift",
                        )
                matches = True
                for source in payload.rglob("*"):
                    if not source.is_file():
                        continue
                    target = destination / source.relative_to(payload)
                    require(
                        target.resolve().is_relative_to(self.root / "artifacts"),
                        "Artifact path escape",
                    )
                    relative = source.relative_to(payload)
                    if archive_payload and relative.parts[0] == "archive":
                        from execution_checkpoint import bounded_read
                        from runtime_archive_format import file_limit

                        name = str(relative.relative_to("archive"))
                        limit = (
                            len(archive_payload[name])
                            if name in {"archive.json", ".writer.lock"}
                            else file_limit(name)
                        )
                        content_matches = (
                            target.is_file()
                            and bounded_read(target, limit) == archive_payload[name]
                        )
                    else:
                        content_matches = target.is_file() and read(target) == read(
                            source
                        )
                    if not content_matches:
                        matches = False
                if completed:
                    require(matches, "Completed artifact drift")
                elif not matches:
                    self.client.log_artifacts(
                        run_id, str(payload), artifact_path="normlab"
                    )
            if not completed:
                self.client.set_tag(run_id, "normlab.import_state", "completed")
                self.client.set_terminated(run_id, status="FINISHED")
                self.db.execute(
                    "UPDATE imports SET state='completed', error_type=NULL WHERE key=?",
                    (key,),
                )
                self.db.commit()
            return {"mlflowRunId": run_id, "alreadyImported": completed, "key": key}
        except Exception as error:
            if not completed:
                self.db.execute(
                    "UPDATE imports SET state='failed', error_type=? WHERE key=?",
                    (type(error).__name__, key),
                )
                self.db.commit()
                self.client.set_tag(run_id, "normlab.import_state", "failed")
                self.client.set_terminated(run_id, status="FAILED")
            raise
