"""Final stop-control consumers retain unknown evidence; SDK-free and fake time only."""

import ast
import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import native_stop_resolution as native
import test_offline_native_stop as legacy
import test_offline_resumed_stop as stop_fixtures
from execution_checkpoint import reader_lock
from execution_test_support import GUARD, ROOT, ExecutionCase, canonical, sha
from import_runtime_mlflow import run
from offline_bundle import identity
from runtime_archive_format import directories
from runtime_consumer import read_archive as read_previous
from runtime_consumer_v4 import read_archive
from runtime_mlflow_projection import project
from runtime_reference import reference
from runtime_registry import registry_dry_run, verify_registry_plan
from runtime_score import score, verify_score
from runtime_score_mlflow_projection import project_score
from runtime_stop_archive import export_archive, producer_pins
from runtime_stop_capture import StopExportProjection, capture_stop
from test_offline_runtime_mlflow_cli import GUARD as SDK_GUARD


class StopConsumerTests(ExecutionCase):
    prepared = stop_fixtures.ResumedStopTests.prepared
    initial = stop_fixtures.ResumedStopTests.initial
    execute = stop_fixtures.ResumedStopTests.initial
    source = stop_fixtures.ResumedStopTests.source
    proposal = stop_fixtures.ResumedStopTests.proposal
    apply = stop_fixtures.ResumedStopTests.apply
    files = stop_fixtures.ResumedStopTests.files
    guarded = stop_fixtures.ResumedStopTests.guarded
    subfolder = stop_fixtures.ResumedStopTests.subfolder
    resumed = stop_fixtures.ResumedStopTests.resumed
    stop_proposal = stop_fixtures.ResumedStopTests.stop_proposal
    stop_guard = stop_fixtures.ResumedStopTests.stop_guard
    stop_apply = stop_fixtures.ResumedStopTests.stop_apply

    def stopped(self, *, continued=True, phase="after-response"):
        if continued:
            root = self.resumed(phase=phase)
            _, request, sample = self.stop_proposal(root)
            self.stop_apply(root, request, sample)
        else:
            root = legacy.NativeStopTests.source(self, phase)
            _, request, sample = legacy.NativeStopTests.proposal(self, root)
            with legacy.NativeStopTests.guarded(self, sample):
                native.apply_stop(
                    root, request, confirm_request_digest=sha(canonical(request))
                )
        return root

    def archive(self, *, continued=True):
        root = self.stopped(continued=continued)
        folder = self.root / ("archive-" + str(self.serial))
        export_archive(root, folder)
        return root, folder, read_archive(folder)

    def selected(self, archive):
        plan = archive.snapshot.plan
        return reference(
            archive,
            canonical(
                {
                    "schema": "normlab.runtime-reference-source/v1",
                    "revision": "synthetic-candidate/v1",
                    "status": "candidate-not-independent",
                    "planDigest": archive.snapshot.intent["planDigest"],
                    "dataset": plan["dataset"],
                    "expected": [
                        {
                            "taskKey": t["key"],
                            "questionId": t["questionIds"][0],
                            "label": "compatible"
                            if t["questionIds"][0] == "classification"
                            else "yes",
                        }
                        for t in plan["tasks"]
                    ],
                }
            ),
        )

    def view(self, *, continued=True):
        root, folder, archive = self.archive(continued=continued)
        view = score(archive, self.selected(archive))
        path = self.root / ("score-" + str(self.serial) + ".json")
        path.write_bytes(canonical(view))
        return root, folder, archive, view, path

    def test_both_controls_archive_exact_raw_bytes_and_survive_source_deletion(self):
        for continued in (False, True):
            root = self.stopped(continued=continued)
            before = self.files(root)
            folder = self.root / ("portable-" + str(self.serial))
            with self.stop_guard():
                snapshot = capture_stop(root)
                receipt = export_archive(root, folder)
                archive = read_archive(folder)
            self.assertEqual(before, self.files(root))
            self.assertTrue(receipt["durabilityAcknowledged"])
            self.assertEqual(archive.snapshot.manifest, snapshot.manifest)
            self.assertEqual(
                archive.files["source/checkpoint.json"], before["checkpoint.json"]
            )
            control = snapshot.manifest["stopControl"]
            self.assertEqual(control["controlState"], "stopped-with-unknown")
            self.assertGreater(len(control["orphanFiles"]), 0)
            for ref in control["orphanFiles"]:
                self.assertEqual(
                    archive.files["source/" + ref["path"]], before[ref["path"]]
                )
            self.assertFalse(control["adopted"])
            self.assertEqual(
                archive.projection.manifest["predictionSeal"]["status"], "unsealed"
            )
            with self.assertRaises(ValueError):
                read_previous(folder)
            shutil.rmtree(root)
            with self.stop_guard():
                self.assertEqual(read_archive(folder).summary()["stopControl"], control)

    def test_task_counts_selected_scores_and_unknown_billing_match_pre_stop_base(self):
        for continued in (False, True):
            root, folder, archive, view, path = self.view(continued=continued)
            base = archive.snapshot._base
            before = score(base, self.selected(base))
            self.assertEqual(view["summary"], before["summary"])
            self.assertEqual(view["runtimeCounts"], before["runtimeCounts"])
            self.assertEqual(view["rows"], before["rows"])
            self.assertNotEqual(view["captureRevisionId"], before["captureRevisionId"])
            self.assertEqual(view["schema"], "normlab.runtime-score-view/v4")
            self.assertEqual(view["controlState"], "stopped-with-unknown")
            self.assertEqual(view["runtimeCounts"]["unknownDispatchAttempts"], 1)
            self.assertGreater(view["summary"]["selectedUnevaluatedQuestions"], 0)
            self.assertIsNone(view["criticalErrorFreeRate"])
            self.assertFalse(view["semanticQualityEvidence"])
            self.assertEqual(verify_score(archive, view), view)
            self.assertEqual(project(base)[0], project(archive)[0])
            self.assertNotEqual(project(base)[1]["key"], project(archive)[1]["key"])
            self.assertEqual(
                project_score(archive, view)["payload"]["stopControl"],
                view["stopControl"],
            )

    def test_registry_plan_and_sdk_free_import_bind_control_and_exact_revision(self):
        root, folder, archive, view, path = self.view()
        projection = StopExportProjection(capture_stop(root))
        plan = registry_dry_run(projection)
        self.assertEqual(plan["schema"], "normlab.runtime-registry-plan/v4")
        self.assertEqual(verify_registry_plan(root, plan), plan)
        dry = run(folder, self.root / "registry", dry_run=True, score_path=path)
        self.assertEqual(dry["schema"], "normlab.runtime-mlflow-import-result/v4")
        self.assertEqual(dry["registryWritesExecuted"], 0)
        self.assertFalse((self.root / "registry").exists())
        self.assertEqual(dry["records"][2]["metrics"]["control.adoptedOutcomes"], 0)
        self.assertGreater(
            dry["records"][2]["metrics"]["control.retainedOrphanBlobs"], 0
        )
        changed = copy.deepcopy(view)
        changed["controlState"] = "complete"
        changed["scoreId"] = identity(
            "runtime-score", {k: v for k, v in changed.items() if k != "scoreId"}
        )
        with self.assertRaises(ValueError):
            verify_score(archive, changed)

    def reseal(self, folder):
        index = json.loads((folder / "archive.json").read_bytes())
        for ref in index["inventory"]:
            raw = (folder / ref["path"]).read_bytes()
            ref.update(sha256=sha(raw), bytes=len(raw))
        refs = {r["path"]: r for r in index["inventory"]}
        index.update(capture=refs["capture.json"], projection=refs["projection.json"])
        index["totals"] = {
            "contentFiles": len(refs),
            "contentBytes": sum(r["bytes"] for r in refs.values()),
            "publishedEntries": len(refs) + len(directories(refs)) + 2,
        }
        index["archiveId"] = identity(
            "archive", {k: v for k, v in index.items() if k != "archiveId"}
        )
        (folder / "archive.json").write_bytes(canonical(index))

    def test_rehashed_control_capture_projection_index_and_orphan_mutations_reject(
        self,
    ):
        root, folder, archive = self.archive()
        for name, transform in (
            ("capture.json", lambda v: v["stopControl"].update(adopted=True)),
            (
                "projection.json",
                lambda v: v["counts"].update(unknownDispatchAttempts=0),
            ),
            (
                "source/checkpoint.json",
                lambda v: v.update(resolutionId="resumed-stop-" + "0" * 64),
            ),
        ):
            copied = self.root / ("changed-" + name.replace("/", "-"))
            shutil.copytree(folder, copied)
            path = copied / name
            value = json.loads(path.read_bytes())
            transform(value)
            path.write_bytes(canonical(value))
            self.reseal(copied)
            with self.assertRaises(ValueError):
                read_archive(copied)
        marker = folder / "archive.json"
        original = marker.read_bytes()
        for key, value in (
            ("schema", "normlab.runtime-archive/v3"),
            ("evidenceKind", "mock"),
            ("sourceFormat", "unknown"),
            ("producerPins", {}),
        ):
            index = json.loads(original)
            index[key] = value
            index["archiveId"] = identity(
                "archive", {k: v for k, v in index.items() if k != "archiveId"}
            )
            marker.write_bytes(canonical(index))
            with self.assertRaises(ValueError):
                read_archive(folder)
        marker.write_bytes(original)
        ref = archive.snapshot.manifest["stopControl"]["orphanFiles"][0]
        path = folder / "source" / ref["path"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            read_archive(folder)

    def test_wrong_sources_locks_symlinks_and_extra_entries_reject(self):
        plain = self.source()
        with self.assertRaises(ValueError):
            capture_stop(plain)
        unknown = self.resumed(phase="after-response")
        with self.assertRaises(ValueError):
            capture_stop(unknown)
        root, folder, archive = self.archive()
        with reader_lock(root), self.assertRaises(BlockingIOError):
            self.stop_apply(root, {}, {})
        import fcntl

        for target in (root, folder):
            with (target / ".writer.lock").open("rb") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    capture_stop(target) if target == root else read_archive(target)
        extra = folder / "extra"
        extra.write_bytes(b"extra")
        with self.assertRaises(ValueError):
            read_archive(folder)
        extra.unlink()
        path = folder / "source/intent.json"
        raw = path.read_bytes()
        path.unlink()
        path.symlink_to(root / "intent.json")
        with self.assertRaises(ValueError):
            read_archive(folder)
        path.unlink()
        path.write_bytes(raw)

    def test_publication_faults_and_actual_exits_keep_partial_archives_closed(self):
        root = self.stopped()
        for phase, complete in (
            ("before-marker", False),
            ("marker:before-file-flush", False),
            ("marker:after-replace", True),
            ("marker:after-directory-commit", True),
        ):
            output = self.root / ("fault-" + phase.replace(":", "-"))

            def fault(point):
                if point == phase:
                    raise KeyboardInterrupt("synthetic v4 publication interruption")

            with self.assertRaises(KeyboardInterrupt):
                export_archive(root, output, hook=fault)
            if complete:
                self.assertEqual(
                    read_archive(output).summary()["controlState"],
                    "stopped-with-unknown",
                )
            else:
                with self.assertRaises((ValueError, FileNotFoundError)):
                    read_archive(output)
            with self.assertRaises(FileExistsError):
                export_archive(root, output)
        for phase in ("before-marker", "marker:after-replace"):
            output = self.root / ("exit-" + phase.replace(":", "-"))
            pid = os.fork()
            if pid == 0:

                def terminate(point):
                    if point == phase:
                        os._exit(77)

                try:
                    export_archive(root, output, hook=terminate)
                finally:
                    os._exit(88)
            _, status = os.waitpid(pid, 0)
            self.assertEqual(os.waitstatus_to_exitcode(status), 77)
            if phase == "before-marker":
                with self.assertRaises(FileNotFoundError):
                    read_archive(output)
            else:
                self.assertEqual(
                    read_archive(output).summary()["controlState"],
                    "stopped-with-unknown",
                )

    def test_copied_trusted_reader_and_sdk_guarded_cli_need_no_source_or_authority(
        self,
    ):
        root, folder, archive, view, score_path = self.view()
        before = self.files(root)

        def cli(script, args, guard=GUARD):
            return subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-S",
                    "-c",
                    guard,
                    str(ROOT / "evaluation" / script),
                    *map(str, args),
                ],
                capture_output=True,
                text=True,
                check=True,
            )

        for command in ("snapshot", "project", "registry-plan"):
            result = cli(
                "runtime_capture_cli.py",
                [command, root, "--native-stop", "--evidence-kind", "live-capture"],
            )
            self.assertEqual(json.loads(result.stdout)["executionReady"], False)
        result = cli("runtime_archive_cli.py", ["verify", folder])
        self.assertEqual(
            json.loads(result.stdout)["controlState"], "stopped-with-unknown"
        )
        cli("runtime_score_cli.py", ["verify", folder, score_path])
        cli(
            "import_runtime_mlflow.py",
            [
                folder,
                "--score",
                score_path,
                "--dry-run",
                "--storage",
                self.root / "registry",
            ],
            SDK_GUARD,
        )
        self.assertEqual(before, self.files(root))
        copied = self.root / "trusted-reader"
        copied.mkdir()
        for name in {*producer_pins(), "runtime_archive_cli.py"}:
            shutil.copyfile(ROOT / "evaluation" / name, copied / name)
        shutil.rmtree(root)
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-S",
                str(copied / "runtime_archive_cli.py"),
                "verify",
                str(folder),
            ],
            cwd=copied,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(
            json.loads(result.stdout)["stopControl"],
            archive.snapshot.manifest["stopControl"],
        )

    def test_zero_orphan_stop_is_unsealed_and_consumer_revision_is_bound(self):
        root = self.stopped(phase="after-reservation")
        self.assertEqual(capture_stop(root).manifest["stopControl"]["orphanFiles"], [])
        _, folder, archive = self.archive()
        original = Path.read_bytes
        target = ROOT / "evaluation/runtime_consumer_v4.py"

        def drift(path):
            raw = original(path)
            return raw + b"# drift" if path == target else raw

        source = self.stopped()
        previous = capture_stop(source).manifest
        with patch.object(Path, "read_bytes", drift):
            self.assertNotEqual(
                capture_stop(source).manifest["captureRevisionId"],
                previous["captureRevisionId"],
            )
            with self.assertRaises(ValueError):
                read_archive(folder)

    def test_full_corpus_keeps_288_denominator_unknowns_and_orphan_bytes(self):
        schedule = stop_fixtures.fixtures.schedule
        original = schedule.compile_stage1
        with patch.object(
            schedule,
            "compile_stage1",
            side_effect=lambda *a, **k: original(*a, profile="corpus", **k),
        ):
            folder, confirmation, clock = schedule.LiveScheduleTests.prepared(
                self, dispatches=2
            )

        def first(point):
            if point == "after-terminal":
                raise KeyboardInterrupt("synthetic first pause")

        with self.assertRaises(KeyboardInterrupt):
            schedule.LiveScheduleTests.execute(
                self, folder, confirmation, clock, hook=first
            )
        root = self.root / "output"
        _, request, clock2 = self.proposal(root)

        def second(point):
            if point == "after-response":
                raise KeyboardInterrupt("synthetic resumed unknown")

        with self.assertRaises(KeyboardInterrupt):
            self.apply(root, request, clock2, hook=second)
        _, request, sample = self.stop_proposal(root)
        self.stop_apply(root, request, sample)
        output = self.root / "corpus-v4"
        export_archive(root, output)
        archive = read_archive(output)
        manifest = archive.projection.manifest
        self.assertEqual(manifest["counts"]["plannedTasks"], 288)
        self.assertEqual(manifest["counts"]["reserved"]["dispatches"], 2)
        self.assertEqual(manifest["counts"]["unknownDispatchAttempts"], 1)
        self.assertGreater(manifest["controlMetrics"]["retainedOrphanBlobs"], 0)
        view = score(archive, self.selected(archive))
        self.assertEqual(view["summary"]["selectedQuestions"], 288)
        self.assertEqual(view["summary"]["scoredQuestions"], 1)
        self.assertEqual(view["summary"]["selectedUnevaluatedQuestions"], 287)

    def test_v4_pins_cover_complete_local_reader_import_closure(self):
        folder = ROOT / "evaluation"
        pending = ["runtime_stop_archive", "runtime_consumer_v4"]
        seen = set()
        while pending:
            name = pending.pop()
            if name in seen:
                continue
            seen.add(name)
            for node in ast.walk(ast.parse((folder / (name + ".py")).read_text())):
                names = (
                    [node.module]
                    if isinstance(node, ast.ImportFrom)
                    else [v.name for v in node.names]
                    if isinstance(node, ast.Import)
                    else []
                )
                pending.extend(
                    n for n in names if n and (folder / (n + ".py")).is_file()
                )
        self.assertEqual(len(producer_pins()), 62)
        self.assertTrue({n + ".py" for n in seen} <= set(producer_pins()))
