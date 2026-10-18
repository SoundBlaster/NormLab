"""Continuation archive/score projections use synthetic captures and deny I/O authority."""

import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import test_offline_native_resume as fixtures
from execution_test_support import GUARD as READONLY_GUARD
from execution_test_support import ROOT, ExecutionCase, canonical
from import_runtime_mlflow import run
from offline_bundle import identity, sha
from runtime_archive_export import export_runtime_archive
from runtime_archive_reader import read_archive as read_original
from runtime_capture import capture_runtime
from runtime_consumer import read_archive
from runtime_mlflow_projection import project
from runtime_reference import reference
from runtime_registry import registry_dry_run, verify_registry_plan
from runtime_resume_archive import SCHEMA, export_archive, producer_pins
from runtime_resume_capture import ResumeExportProjection, capture_resume
from runtime_score import score, verify_score
from runtime_score_mlflow_projection import project_score
from test_offline_runtime_mlflow_cli import GUARD as SDK_GUARD


class ResumeConsumerTests(ExecutionCase):
    prepared = fixtures.NativeResumeTests.prepared
    initial = fixtures.NativeResumeTests.initial
    source = fixtures.NativeResumeTests.source
    proposal = fixtures.NativeResumeTests.proposal
    apply = fixtures.NativeResumeTests.apply
    files = fixtures.NativeResumeTests.files
    guarded = fixtures.NativeResumeTests.guarded
    subfolder = fixtures.NativeResumeTests.subfolder

    def resumed(self, *, phase=None, tasks=3):
        root = self.source(tasks=tasks)
        _, request, clock = self.proposal(root)

        def fault(point):
            if point == phase:
                raise KeyboardInterrupt("synthetic continuation interruption")

        if phase:
            with self.assertRaises(KeyboardInterrupt):
                self.apply(root, request, clock, hook=fault)
        else:
            self.apply(root, request, clock)
        return root

    def archive(self, *, phase=None, tasks=3):
        root = self.resumed(phase=phase, tasks=tasks)
        output = self.root / ("archive-" + str(self.serial))
        export_archive(root, output)
        return root, output, read_archive(output)

    def view(self, *, phase=None):
        root, folder, archive = self.archive(phase=phase)
        plan = archive.snapshot.plan
        source = {
            "schema": "normlab.runtime-reference-source/v1",
            "revision": "synthetic-candidate/v1",
            "status": "candidate-not-independent",
            "planDigest": archive.snapshot.intent["planDigest"],
            "dataset": plan["dataset"],
            "expected": [
                {"taskKey": t["key"], "questionId": t["questionIds"][0], "label": "yes"}
                for t in plan["tasks"]
            ],
        }
        view = score(archive, reference(archive, canonical(source)))
        path = self.root / ("score-" + str(self.serial) + ".json")
        path.write_bytes(canonical(view))
        return root, folder, archive, view, path

    def test_portable_archive_retains_original_base_and_raw_invocations(self):
        root = self.resumed()
        before = self.files(root)
        output = self.root / "portable"
        with self.guarded():
            original = capture_resume(root)
            receipt = export_archive(root, output)
            archive = read_archive(output)
        self.assertEqual(before, self.files(root))
        self.assertTrue(receipt["durabilityAcknowledged"])
        self.assertEqual(archive.index["schema"], SCHEMA)
        self.assertEqual(archive.snapshot.manifest, original.manifest)
        self.assertEqual(archive.snapshot.events, original.events)
        self.assertEqual(
            archive.files["source/checkpoint.json"], before["checkpoint.json"]
        )
        self.assertEqual(
            archive.files["source/native-resume-base/archive.json"],
            before["native-resume-base/archive.json"],
        )
        self.assertEqual(archive.projection.manifest["counts"]["attempts"], 3)
        self.assertEqual(
            archive.projection.manifest["predictionSeal"]["status"], "sealed"
        )
        for reader in (read_original,):
            with self.assertRaises(ValueError):
                reader(output)
        with self.assertRaises(ValueError):
            capture_runtime(root, evidence_kind="live-capture")
        shutil.rmtree(root)
        with self.guarded():
            self.assertEqual(read_archive(output).snapshot.manifest, original.manifest)

    def test_partial_and_unknown_attempts_remain_in_denominator_and_unscored(self):
        for phase, scored, unknown in (
            ("after-terminal", 2, 0),
            ("after-response", 1, 1),
        ):
            root, folder, archive, view, path = self.view(phase=phase)
            self.assertEqual(view["schema"], "normlab.runtime-score-view/v3")
            self.assertEqual(view["summary"]["plannedTasks"], 3)
            self.assertEqual(view["summary"]["scoredQuestions"], scored)
            self.assertEqual(view["runtimeCounts"]["unknownDispatchAttempts"], unknown)
            self.assertEqual(view["runtimeCounts"]["reserved"]["dispatches"], 2)
            self.assertEqual(
                view["summary"]["selectedUnevaluatedQuestions"], 3 - scored
            )
            self.assertEqual(view["predictionSeal"]["status"], "unsealed")
            self.assertIsNone(view["criticalErrorFreeRate"])
            self.assertFalse(view["semanticQualityEvidence"])
            self.assertEqual(verify_score(archive, view), view)

    def test_multiple_revisions_share_execution_but_have_distinct_capture_and_scores(
        self,
    ):
        root = self.source(tasks=4)
        basefolder = self.root / "base-export"
        export_runtime_archive(root, basefolder, evidence_kind="live-capture")
        base = project(read_archive(basefolder))
        _, request, clock = self.proposal(root)

        def fault(point):
            if point == "after-terminal":
                raise KeyboardInterrupt("synthetic partial revision")

        with self.assertRaises(KeyboardInterrupt):
            self.apply(root, request, clock, hook=fault)
        firstfolder = self.root / "revision-one"
        export_archive(root, firstfolder)
        first = project(read_archive(firstfolder))
        _, request2, clock2 = self.proposal(root)
        self.apply(root, request2, clock2)
        secondfolder = self.root / "revision-two"
        export_archive(root, secondfolder)
        second = project(read_archive(secondfolder))
        self.assertEqual(base[0], first[0])
        self.assertEqual(first[0], second[0])
        self.assertNotEqual(first[1]["key"], second[1]["key"])
        self.assertNotEqual(first[2]["key"], second[2]["key"])
        self.assertEqual(first[1]["parentKey"], second[1]["parentKey"])
        self.assertEqual(first[2]["metrics"]["runtime.attempts"], 2)
        self.assertEqual(second[2]["metrics"]["runtime.attempts"], 4)

    def test_v3_registry_projection_and_score_bind_exact_capture_revision(self):
        root, folder, archive, view, path = self.view(phase="after-terminal")
        records = project(archive)
        child = project_score(archive, view)
        self.assertEqual(
            records[0]["payload"]["schema"], "normlab.runtime-mlflow-projection/v2"
        )
        self.assertEqual(
            records[1]["payload"]["schema"], "normlab.runtime-mlflow-projection/v3"
        )
        self.assertEqual(child["payload"]["schema"], "normlab.runtime-mlflow-score/v3")
        self.assertEqual(child["parentKey"], records[1]["key"])
        projection = ResumeExportProjection(capture_resume(root))
        plan = registry_dry_run(projection)
        self.assertEqual(plan["schema"], "normlab.runtime-registry-plan/v3")
        self.assertEqual(verify_registry_plan(root, plan), plan)
        with self.guarded():
            result = run(
                folder, self.root / "unused-registry", dry_run=True, score_path=path
            )
        self.assertEqual(result["schema"], "normlab.runtime-mlflow-import-result/v3")
        self.assertEqual(result["registryWritesExecuted"], 0)
        self.assertFalse((self.root / "unused-registry").exists())
        changed = copy.deepcopy(view)
        changed["captureRevisionId"] = "capture-" + "0" * 64
        changed["scoreId"] = identity(
            "runtime-score", {k: v for k, v in changed.items() if k != "scoreId"}
        )
        with self.assertRaises(ValueError):
            verify_score(archive, changed)

    def test_archive_tamper_rehashed_manifest_and_nested_base_fail_closed(self):
        root, folder, archive = self.archive()
        marker = folder / "archive.json"
        raw = marker.read_bytes()
        for mutate in (
            lambda v: v.update(evidenceKind="mock"),
            lambda v: v.update(schema="normlab.runtime-archive/v2"),
            lambda v: v.update(sourceFormat="other"),
            lambda v: v["producerPins"].update(
                **{"runtime_resume_capture.py": "0" * 64}
            ),
        ):
            value = json.loads(raw)
            mutate(value)
            value["archiveId"] = identity(
                "archive", {k: v for k, v in value.items() if k != "archiveId"}
            )
            marker.write_bytes(canonical(value))
            with self.assertRaises(ValueError):
                read_archive(folder)
        marker.write_bytes(raw)
        for name in (
            "capture.json",
            "source/checkpoint.json",
            "source/native-resume-base/source/checkpoint.json",
        ):
            path = folder / name
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            with self.assertRaises(ValueError):
                read_archive(folder)
            path.write_bytes(original)
        alias = folder / "unexpected"
        alias.symlink_to(folder / "source/intent.json")
        with self.assertRaises(ValueError):
            read_archive(folder)

    def test_publication_faults_reject_partial_and_existing_output(self):
        root = self.resumed()
        for phase in (
            "directories:after-flush",
            "content:before-file-flush",
            "before-marker",
            "marker:after-replace",
        ):
            output = self.root / ("fault-" + phase.replace(":", "-"))

            def fail(point):
                if point == phase:
                    raise KeyboardInterrupt("synthetic archive fault")

            with self.assertRaises(KeyboardInterrupt):
                export_archive(root, output, hook=fail)
            if phase == "marker:after-replace":
                self.assertEqual(
                    read_archive(output).summary()["counts"]["attempts"], 3
                )
            else:
                with self.assertRaises((ValueError, FileNotFoundError)):
                    read_archive(output)
            with self.assertRaises(FileExistsError):
                export_archive(root, output)

    def test_cli_capture_archive_score_and_import_are_offline(self):
        root, folder, archive, view, path = self.view()
        for script, args, guard in (
            (
                "runtime_capture_cli.py",
                [
                    "snapshot",
                    str(root),
                    "--evidence-kind",
                    "live-capture",
                    "--native-continuation",
                ],
                READONLY_GUARD,
            ),
            (
                "runtime_capture_cli.py",
                [
                    "registry-plan",
                    str(root),
                    "--evidence-kind",
                    "live-capture",
                    "--native-continuation",
                ],
                READONLY_GUARD,
            ),
            ("runtime_archive_cli.py", ["verify", str(folder)], READONLY_GUARD),
            (
                "runtime_score_cli.py",
                ["verify", str(folder), str(path)],
                READONLY_GUARD,
            ),
            (
                "import_runtime_mlflow.py",
                [
                    str(folder),
                    "--score",
                    str(path),
                    "--dry-run",
                    "--storage",
                    str(self.root / "never-created"),
                ],
                SDK_GUARD,
            ),
        ):
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-S",
                    "-c",
                    guard,
                    str(ROOT / "evaluation" / script),
                    *args,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env={"PATH": os.defpath},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["inferenceCallsExecuted"], 0)
        self.assertFalse((self.root / "never-created").exists())

    def test_copied_v3_reader_is_portable_without_source_or_authority(self):
        source, folder, archive = self.archive(phase="after-response")
        shutil.rmtree(source)
        tools = self.root / "trusted-reader"
        tools.mkdir()
        for name in set(producer_pins()) | {"runtime_archive_cli.py"}:
            shutil.copyfile(ROOT / "evaluation" / name, tools / name)
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-S",
                "-c",
                READONLY_GUARD,
                str(tools / "runtime_archive_cli.py"),
                "verify",
                str(folder),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env={"PATH": os.defpath},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), archive.summary())

    def test_consumer_revision_changes_capture_identity_and_rejects_old_archive(self):
        source, folder, archive = self.archive()
        before = capture_resume(source)
        original_read = Path.read_bytes

        def drift(path):
            raw = original_read(path)
            return (
                raw + b"\n# synthetic consumer revision\n"
                if path == ROOT / "evaluation/runtime_consumer.py"
                else raw
            )

        with patch.object(Path, "read_bytes", drift):
            revised = capture_resume(source)
            self.assertNotEqual(
                before.manifest["captureRevisionId"],
                revised.manifest["captureRevisionId"],
            )
            self.assertEqual(
                before.manifest["executionId"], revised.manifest["executionId"]
            )
            self.assertEqual(
                before.manifest["sourceFiles"], revised.manifest["sourceFiles"]
            )
            with self.assertRaises(ValueError):
                read_archive(folder)

    def test_coordinated_rehashed_projection_capture_and_checkpoint_edits_reject(self):
        _, folder, archive = self.archive()
        marker = folder / "archive.json"
        original_index = marker.read_bytes()
        for name in ("projection.json", "capture.json", "source/checkpoint.json"):
            path = folder / name
            original = path.read_bytes()
            value = json.loads(original)
            if name == "projection.json":
                value["counts"]["attempts"] = 0
                value["projectionId"] = identity(
                    "runtime-view",
                    {k: v for k, v in value.items() if k != "projectionId"},
                )
            elif name == "capture.json":
                value["continuation"]["effectiveCaps"]["dispatches"] += 1
            else:
                value["run"]["counts"]["reserved"]["dispatches"] = 0
            changed = canonical(value)
            path.write_bytes(changed)
            index = json.loads(original_index)
            for ref in index["inventory"]:
                if ref["path"] == name:
                    ref.update(sha256=sha(changed), bytes=len(changed))
            if name in ("capture.json", "projection.json"):
                index[name.split(".")[0]] = next(
                    r for r in index["inventory"] if r["path"] == name
                )
            index["totals"]["contentBytes"] = sum(
                r["bytes"] for r in index["inventory"]
            )
            index["archiveId"] = identity(
                "archive", {k: v for k, v in index.items() if k != "archiveId"}
            )
            marker.write_bytes(canonical(index))
            with self.assertRaises(ValueError):
                read_archive(folder)
            path.write_bytes(original)
            marker.write_bytes(original_index)

    def test_retry_preserves_first_final_and_unknown_billing_after_success(self):
        root = self.source()
        _, request, clock = self.proposal(root)

        def temporary(body, number):
            if number == 1:
                return {"response": None, "errorClass": "ReadTimeout"}

        self.apply(root, request, clock, customize=temporary)
        folder = self.root / "retry-archive"
        export_archive(root, folder)
        archive = read_archive(folder)
        manifest = archive.projection.manifest
        task = json.loads(archive.projection.files[manifest["records"][1]["path"]])
        self.assertEqual(
            [a["status"] for a in task["attempts"]], ["transport-failed", "completed"]
        )
        self.assertNotEqual(task["firstOutcome"], task["finalOutcome"])
        self.assertEqual(manifest["counts"]["reserved"]["dispatches"], 4)
        self.assertEqual(manifest["counts"]["unknownDispatchAttempts"], 1)
        self.assertEqual(manifest["counts"]["unknownUsageAttempts"], 1)
        self.assertEqual(manifest["predictionSeal"]["status"], "sealed")

    def test_source_and_archive_active_writer_block_and_stop_only_rejects(self):
        import fcntl

        source, folder, archive = self.archive()
        for root in (source, folder):
            with (root / ".writer.lock").open("rb") as handle:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    capture_resume(root) if root == source else read_archive(root)
        plain = self.source()
        with self.assertRaises(ValueError):
            capture_resume(plain)
        root = self.source(phase="after-response")
        with self.assertRaises(ValueError):
            capture_resume(root)
        from native_stop_resolution import apply_stop, prepare_stop

        capture = fixtures.ResumeCapture(root)
        request = prepare_stop(
            root,
            attempt_id=capture.report["unknownAttemptIds"][0],
            authorization_record={
                "operatorId": "synthetic-operator",
                "authorizationRef": "a" * 64,
                "authorizedAt": capture.report["lastObservedAt"],
            },
            expires_at=capture.permit["expiresAt"],
        )
        with patch(
            "native_stop_resolution.LinuxClock", return_value=fixtures.Clock(capture)
        ):
            apply_stop(root, request, confirm_request_digest=sha(canonical(request)))
        with self.assertRaises(ValueError):
            capture_resume(root)

    def test_v3_process_exit_before_and_after_marker_preserves_readable_boundary(self):
        source = self.resumed()
        for phase in ("before-marker", "marker:after-replace"):
            output = self.root / ("exit-" + phase.replace(":", "-"))
            pid = os.fork()
            if pid == 0:

                def terminate(point):
                    if point == phase:
                        os._exit(77)

                try:
                    export_archive(source, output, hook=terminate)
                finally:
                    os._exit(88)
            _, status = os.waitpid(pid, 0)
            self.assertEqual(os.waitstatus_to_exitcode(status), 77)
            if phase == "before-marker":
                with self.assertRaises(FileNotFoundError):
                    read_archive(output)
            else:
                self.assertEqual(
                    read_archive(output).summary()["counts"]["attempts"], 3
                )

    def test_stage1_288_task_continuation_snapshot_archive_and_score_stay_bounded(self):
        schedule = fixtures.schedule
        from unittest.mock import patch

        original = schedule.compile_stage1

        def corpus(*args, **kwargs):
            return original(*args, profile="corpus", **kwargs)

        with patch.object(schedule, "compile_stage1", side_effect=corpus):
            folder, confirmation, clock = schedule.LiveScheduleTests.prepared(
                self, dispatches=2
            )

        def fault(point):
            if point == "after-terminal":
                raise KeyboardInterrupt("synthetic Stage1 pause")

        with self.assertRaises(KeyboardInterrupt):
            schedule.LiveScheduleTests.execute(
                self, folder, confirmation, clock, hook=fault
            )
        root = self.root / "output"
        _, request, clock2 = self.proposal(root)
        self.apply(root, request, clock2)
        output = self.root / "corpus-archive"
        export_archive(root, output)
        archive = read_archive(output)
        manifest = archive.projection.manifest
        self.assertEqual(manifest["counts"]["plannedTasks"], 288)
        self.assertEqual(manifest["counts"]["attempts"], 2)
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
                            "questionId": "classification",
                            "label": "compatible",
                        }
                        for t in archive.snapshot.plan["tasks"]
                    ],
                }
            ),
        )
        view = score(archive, selected)
        self.assertEqual(view["summary"]["selectedQuestions"], 288)
        self.assertEqual(view["summary"]["selectedUnevaluatedQuestions"], 286)
