"""Native archive replay remains portable, bounded, read-only and zero-authority."""

import copy
import json
import shutil
import unittest

import test_offline_live_capture as captures
from execution_test_support import ROOT, ExecutionCase, canonical, cli, sha
from offline_bundle import identity
from runtime_archive_export import export_runtime_archive
from runtime_archive_format import pin_modules
from runtime_archive_reader import read_archive
from runtime_capture import capture_runtime


class LiveArchiveTests(ExecutionCase):
    prepared = captures.LiveCaptureTests.prepared
    execute = captures.LiveCaptureTests.execute
    capture = captures.LiveCaptureTests.capture
    scheduled = captures.LiveCaptureTests.scheduled

    def archive(self, *, phase=None, scheduled=False):
        root = self.scheduled() if scheduled else self.capture(phase=phase)
        output = self.root / "archive"
        export_runtime_archive(root, output, evidence_kind="live-capture")
        return root, output

    def test_roundtrip_without_original_source_preserves_live_usage_and_suffix(self):
        source, folder = self.archive(scheduled=True)
        before = capture_runtime(source, evidence_kind="live-capture")
        shutil.rmtree(source)
        archive = read_archive(folder)
        self.assertEqual(archive.snapshot.manifest, before.manifest)
        self.assertEqual(archive.index["schema"], "normlab.runtime-archive/v2")
        self.assertEqual(archive.index["evidenceKind"], "live-capture")
        counts = archive.summary()["counts"]
        self.assertEqual(counts["plannedTasks"], 36)
        self.assertEqual(counts["observedDispatches"], 3)
        self.assertEqual(counts["knownInputTokens"], 300)
        self.assertEqual(counts["statusCounts"], {"completed": 3, "not-dispatched": 33})
        self.assertEqual(archive.summary()["inferenceCallsExecuted"], 0)
        self.assertFalse(archive.summary()["executionReady"])
        self.assertNotIn("source/mock-script.json", archive.files)

    def test_unknown_keeps_denominator_and_omits_orphan_response(self):
        source, folder = self.archive(phase="after-response")
        archive = read_archive(folder)
        self.assertEqual(archive.summary()["counts"]["unknownDispatchAttempts"], 1)
        self.assertEqual(archive.summary()["counts"]["unknownUsageAttempts"], 1)
        self.assertEqual(archive.summary()["predictionSeal"]["status"], "unsealed")
        self.assertEqual(
            archive.summary()["counts"]["statusCounts"],
            {"unknown-outcome": 1, "not-dispatched": 1},
        )

    def test_portable_copied_reader_has_no_clock_transport_or_authority(self):
        source, folder = self.archive(scheduled=True)
        shutil.rmtree(source)
        tools = self.root / "tools"
        tools.mkdir()
        for name in pin_modules("live-capture") + (
            "runtime_archive_export",
            "runtime_archive_reader",
            "runtime_archive_cli",
        ):
            shutil.copyfile(
                ROOT / "evaluation" / (name + ".py"), tools / (name + ".py")
            )
        result = cli("verify", folder, script=tools / "runtime_archive_cli.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), read_archive(folder).summary())

    def test_rehashed_counts_kind_and_checkpoint_counter_changes_reject(self):
        _, folder = self.archive()
        original_index = (folder / "archive.json").read_bytes()
        index = json.loads(original_index)
        for name in ("projection.json", "capture.json", "source/checkpoint.json"):
            original = (folder / name).read_bytes()
            value = json.loads(original)
            if name == "projection.json":
                value["counts"]["observedDispatches"] = 0
            elif name == "capture.json":
                value["recordedDispatches"]["observed"] = 0
            else:
                value["run"]["counts"]["observedDispatches"] = 0
            raw = canonical(value)
            (folder / name).write_bytes(raw)
            edited = copy.deepcopy(index)
            for ref in edited["inventory"]:
                if ref["path"] == name:
                    ref.update(sha256=sha(raw), bytes=len(raw))
            if name in ("projection.json", "capture.json"):
                edited[name.split(".")[0]] = next(
                    r for r in edited["inventory"] if r["path"] == name
                )
            edited["totals"]["contentBytes"] = sum(
                r["bytes"] for r in edited["inventory"]
            )
            edited["archiveId"] = identity(
                "archive", {k: v for k, v in edited.items() if k != "archiveId"}
            )
            (folder / "archive.json").write_bytes(canonical(edited))
            with self.subTest(name=name), self.assertRaises(ValueError):
                read_archive(folder)
            (folder / name).write_bytes(original)
        wrong_kind = copy.deepcopy(index)
        wrong_kind.update(evidenceKind="mock", schema="normlab.runtime-archive/v1")
        wrong_kind["archiveId"] = identity(
            "archive", {k: v for k, v in wrong_kind.items() if k != "archiveId"}
        )
        (folder / "archive.json").write_bytes(canonical(wrong_kind))
        with self.assertRaises(ValueError):
            read_archive(folder)
        (folder / "archive.json").write_bytes(original_index)
        self.assertEqual(read_archive(folder).index, index)

    def test_failed_publication_has_no_readable_archive_or_overwrite(self):
        source = self.capture()
        output = self.root / "partial"

        def crash(point):
            if point == "before-marker":
                raise KeyboardInterrupt("synthetic interruption")

        with self.assertRaises(KeyboardInterrupt):
            export_runtime_archive(
                source, output, evidence_kind="live-capture", hook=crash
            )
        with self.assertRaises(FileNotFoundError):
            read_archive(output)
        with self.assertRaises(FileExistsError):
            export_runtime_archive(source, output, evidence_kind="live-capture")

    def test_source_and_archive_reader_reject_active_writers(self):
        import fcntl

        source, folder = self.archive()
        for root in (source, folder):
            with (root / ".writer.lock").open("rb") as stream:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    if root == source:
                        capture_runtime(root, evidence_kind="live-capture")
                    else:
                        read_archive(root)

    def test_unadapted_consumers_reject_live_archives_explicitly(self):
        from runtime_mlflow_projection import project
        from runtime_reference import reference
        from runtime_registry import registry_nodes
        from runtime_score import score

        _, folder = self.archive()
        archive = read_archive(folder)
        selected = reference(
            archive,
            canonical(
                {
                    "schema": "normlab.runtime-reference-source/v1",
                    "revision": "synthetic/v1",
                    "status": "candidate-not-independent",
                    "planDigest": archive.snapshot.intent["planDigest"],
                    "dataset": archive.snapshot.plan["dataset"],
                    "expected": [
                        {
                            "taskKey": archive.snapshot.plan["tasks"][0]["key"],
                            "questionId": "supported",
                            "label": "yes",
                        }
                    ],
                }
            ),
        )
        for action in (
            lambda: score(archive, selected),
            lambda: registry_nodes(archive.projection),
            lambda: project(archive),
        ):
            with self.assertRaisesRegex(ValueError, "Mock-only"):
                action()

    def test_rehashed_provider_format_settings_and_configuration_changes_reject(self):
        from execution_plan import Store
        from runtime_live_stage1 import verify

        root = self.scheduled()
        store = Store(root)
        plan = store.json("plan.json")
        original = store.value(plan["pins"]["definitions"])
        verify(store, plan)
        for kind in ("format", "settings", "low-settings", "key", "valid-key", "extra"):
            lineage = copy.deepcopy(original)
            providers = lineage["metadata"]["providers"]
            if kind == "format":
                providers["jev-coreinfra"]["apiFormat"] = "openai-responses"
            elif kind == "settings":
                providers["jev-coreinfra"]["settings"] = {"temperature": 1}
            elif kind == "low-settings":
                providers["luna-low-coreinfra"]["settings"]["reasoning"]["effort"] = (
                    "high"
                )
            elif kind == "key":
                providers["jev-coreinfra"]["keyEnvironment"] = "not-a-variable"
            elif kind == "valid-key":
                providers["jev-coreinfra"]["keyEnvironment"] = (
                    "ANOTHER_VALID_ENVIRONMENT"
                )
            else:
                providers["jev-coreinfra"]["unexpected"] = True
            source = {
                **lineage["metadata"],
                "jobs": [store.value(ref) for ref in lineage["jobs"]],
            }
            lineage["sourcePlanDigest"] = sha(canonical(source))
            raw = canonical(lineage)
            edited = copy.deepcopy(plan)
            ref = {
                "path": f"artifacts/{sha(raw)}.blob",
                "sha256": sha(raw),
                "bytes": len(raw),
            }
            (root / ref["path"]).write_bytes(raw)
            edited["pins"]["definitions"] = ref
            edited["tactic"]["sha256"] = lineage["sourcePlanDigest"]
            with (
                self.subTest(kind=kind),
                self.assertRaisesRegex(ValueError, "provider|fields"),
            ):
                verify(Store(root), edited)


if __name__ == "__main__":
    unittest.main()
