"""Read-only native snapshots with fake-produced checkpoints; no provider evidence."""

import json
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_offline_live_kernel as kernel_fixtures
import test_offline_live_schedule as schedule_fixtures
from execution_live_kernel import checkpoint
from execution_plan import Store
from execution_test_support import ROOT, ExecutionCase, canonical, sha
from runtime_capture import capture_runtime, verify_capture_manifest
from runtime_export import prepare_export
from test_offline_runtime_mlflow_cli import GUARD


class LiveCaptureTests(ExecutionCase):
    prepared = kernel_fixtures.LiveKernelTests.prepared
    execute = kernel_fixtures.LiveKernelTests.execute

    def capture(self, *, phase=None, reply=None):
        fixture, confirmation = self.prepared()
        root = self.root / "native"

        def hook(point):
            if point == phase:
                raise KeyboardInterrupt("synthetic fault")

        if phase:
            with self.assertRaises(KeyboardInterrupt):
                self.execute(fixture, confirmation, root, hook=hook)
        else:
            self.execute(fixture, confirmation, root, reply=reply)
        return root

    def scheduled(self):
        folder, confirmation, clock = schedule_fixtures.LiveScheduleTests.prepared(
            self, dispatches=3
        )
        schedule_fixtures.LiveScheduleTests.execute(self, folder, confirmation, clock)
        return self.root / "output"

    def test_native_snapshot_explicit_kind_exact_bytes_and_zero_authority(self):
        root = self.capture()
        with (
            patch(
                "execution_live_kernel.LinuxClock",
                side_effect=AssertionError("clock denied"),
            ),
            patch(
                "execution_live_kernel.NativeHTTP",
                side_effect=AssertionError("transport denied"),
            ),
            patch(
                "execution_live_kernel.claim_run",
                side_effect=AssertionError("authority denied"),
            ),
        ):
            snapshot = capture_runtime(root, evidence_kind="live-capture")
        self.assertEqual(snapshot.manifest["schema"], "normlab.runtime-capture/v2")
        self.assertEqual(
            snapshot.manifest["recordedDispatches"], {"observed": 1, "unknown": 0}
        )
        self.assertEqual(snapshot.report["inferenceCallsExecuted"], 0)
        self.assertFalse(snapshot.manifest["executionReady"])
        self.assertFalse(snapshot.report["nativeBoundary"]["recordedRuntimeVerified"])
        self.assertTrue(snapshot.report["nativeBoundary"]["readerRuntimePinsMatched"])
        self.assertNotIn("mock-script.json", snapshot.files)
        for name, raw in snapshot.files.items():
            self.assertEqual(raw, (root / name).read_bytes())
        self.assertEqual(
            verify_capture_manifest(
                root, snapshot.manifest, evidence_kind="live-capture"
            ).manifest,
            snapshot.manifest,
        )
        with self.assertRaises((ValueError, FileNotFoundError)):
            capture_runtime(root)
        with self.assertRaises(ValueError):
            prepare_export(
                snapshot
            )  # Mock-only until the archive extension is installed.

    def test_unknown_reservation_and_orphans_preserved_without_adoption(self):
        root = self.capture(phase="after-response")
        snapshot = capture_runtime(root, evidence_kind="live-capture")
        self.assertEqual(
            snapshot.manifest["recordedDispatches"], {"observed": 0, "unknown": 1}
        )
        self.assertEqual(snapshot.report["state"], "paused-unknown")
        (root / "unrelated.txt").write_text("not evidence")
        (root / "artifacts" / ("0" * 64 + ".blob")).write_text("orphan")
        self.assertEqual(
            capture_runtime(root, evidence_kind="live-capture").manifest,
            snapshot.manifest,
        )
        self.assertEqual(snapshot.report["counts"]["unknownUsageAttempts"], 1)
        self.assertIsNone(snapshot.report["taskOutcomes"][0]["final"])

    def test_stage1_schedule_lineage_and_permit_retained(self):
        root = self.scheduled()
        snapshot = capture_runtime(root, evidence_kind="live-capture")
        self.assertEqual(
            snapshot.manifest["checkpointSchema"], "normlab.live-checkpoint/v2"
        )
        self.assertEqual(snapshot.manifest["recordedDispatches"]["observed"], 3)
        self.assertEqual(len(snapshot.plan["tasks"]), 36)
        self.assertIn(snapshot.intent["permit"]["path"], snapshot.files)
        lineage = Store.decode_json(
            snapshot.files[snapshot.plan["pins"]["definitions"]["path"]]
        )
        self.assertTrue(all(ref["path"] in snapshot.files for ref in lineage["jobs"]))

    def test_foreign_recorded_runtime_is_preserved_and_not_attested(self):
        root = self.scheduled()
        plan = Store(root).json("plan.json")
        plan["pins"]["dependencies"]["python-stdlib-runtime"] = "f" * 64
        (root / "plan.json").write_bytes(canonical(plan))
        intent = Store.decode_json((root / "intent.json").read_bytes())
        intent["planDigest"] = sha(canonical(plan))
        permit = Store(root).value(intent["permit"])
        permit["planDigest"] = intent["planDigest"]
        raw = canonical(permit)
        intent["permit"] = {
            "path": f"artifacts/{sha(raw)}.blob",
            "sha256": sha(raw),
            "bytes": len(raw),
        }
        (root / intent["permit"]["path"]).write_bytes(raw)
        (root / "intent.json").write_bytes(canonical(intent))
        old = Store.decode_json((root / "checkpoint.json").read_bytes())
        saved = checkpoint(intent, old["journal"], Store(root), mode=old["mode"])
        saved["codePins"]["dependencies"] = plan["pins"]["dependencies"]
        (root / "checkpoint.json").write_bytes(canonical(saved))
        snapshot = capture_runtime(root, evidence_kind="live-capture")
        self.assertEqual(
            snapshot.manifest["recordedDependencies"], plan["pins"]["dependencies"]
        )
        self.assertFalse(snapshot.report["nativeBoundary"]["readerRuntimePinsMatched"])
        self.assertFalse(snapshot.report["nativeBoundary"]["recordedRuntimeVerified"])

    def test_counter_code_pin_and_evidence_kind_edits_reject(self):
        root = self.capture()
        path = root / "checkpoint.json"
        original = path.read_bytes()
        for kind in ("counts", "code", "kind"):
            saved = Store.decode_json(original)
            if kind == "counts":
                saved["run"]["counts"]["observedDispatches"] = 0
            elif kind == "code":
                saved["codePins"]["code"]["execution_live_kernel.py"] = "0" * 64
            else:
                saved["run"]["evidenceKind"] = "mock"
            path.write_bytes(canonical(saved))
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                capture_runtime(root, evidence_kind="live-capture")
        path.write_bytes(original)

    def test_live_capture_cli_sdk_network_denied(self):
        root = self.capture()
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-S",
                "-c",
                GUARD,
                str(ROOT / "evaluation/runtime_capture_cli.py"),
                "snapshot",
                str(root),
                "--evidence-kind",
                "live-capture",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            capture_runtime(root, evidence_kind="live-capture").manifest,
        )


if __name__ == "__main__":
    unittest.main()
