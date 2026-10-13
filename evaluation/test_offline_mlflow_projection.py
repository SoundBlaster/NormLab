"""SDK-free verified projections and dry-run contracts for the local registry."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import test_offline_bundle as fixtures
import test_offline_stage1 as stage1
from offline_bundle import Builder
from offline_mlflow_projection import numeric, project, snapshot
from offline_stage1 import export


def bundles(root):
    result = {}
    for name in ("classification", "no-labels", "s13"):
        folder = root / name
        saved = fixtures.OfflineBundleTests.cli(
            *fixtures.OfflineBundleTests.export_args(name), "--output", folder, cwd=root
        )
        if saved.returncode:
            raise AssertionError(saved.stderr)
        result[name] = folder
    source = root / "stage1-source"
    plan = stage1.prepare(stage1.MANIFEST)
    stage1.provider_capture(plan, source, ["completed", "failed"])
    for scored in (False, True):
        from score_stage1_providers import save_new, score, seal

        name = "stage1-scored" if scored else "stage1"
        paths = ()
        if scored:
            seal_path, score_path = root / "seal.json", root / "score.json"
            save_new(seal_path, seal(plan, source))
            save_new(score_path, score(stage1.MANIFEST, plan, source, seal_path))
            paths = (stage1.MANIFEST, seal_path, score_path)
        builder = Builder()
        envelope = export(builder, source, *paths)
        folder = root / name
        builder.export(envelope, folder)
        result[name] = folder
    return result


class OfflineMLflowProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.bundles = bundles(cls.root)

    def test_all_adapters_have_conditional_metrics_and_navigation(self):
        for name, folder in self.bundles.items():
            with (
                self.subTest(adapter=name),
                snapshot(folder) as (root, envelope, digest),
            ):
                parent, view = project(root, envelope, digest)
                summary = view["payload"]["summary"]
                self.assertEqual(summary["planned"], envelope["counts"]["plannedTasks"])
                self.assertEqual(
                    summary["notEvaluated"], summary["planned"] - summary["scored"]
                )
                self.assertNotIn(
                    "selected_reference.criticalErrorFreeRate", view["metrics"]
                )
                navigation = view["payload"]["navigation"]
                for path in [
                    navigation["bundleIndex"],
                    navigation["nativeReport"],
                    *navigation["rawCaptures"],
                ]:
                    self.assertTrue((root / Path(path).relative_to("bundle")).is_file())
                self.assertEqual(parent["originalId"], envelope["run"]["id"])
                if name in {"no-labels", "stage1"}:
                    self.assertEqual(summary["scored"], 0)
                    self.assertIsNone(summary["agreementAmongScored"])
                    self.assertNotIn(
                        "selected_reference.agreementAmongScored", view["metrics"]
                    )

    def test_new_score_view_reuses_capture_projection(self):
        for names in (("classification", "no-labels"), ("stage1", "stage1-scored")):
            projections = []
            for name in names:
                with snapshot(self.bundles[name]) as (root, envelope, digest):
                    projections.append(project(root, envelope, digest))
            self.assertEqual(projections[0][0], projections[1][0])
            self.assertNotEqual(projections[0][1]["key"], projections[1][1]["key"])

    def test_dry_run_needs_no_mlflow_sdk_or_storage(self):
        storage = self.root / "unused-storage"
        result = fixtures.OfflineBundleTests.cli(
            self.bundles["s13"],
            "--dry-run",
            "--storage",
            storage,
            script=fixtures.ROOT / "evaluation/import_offline_mlflow.py",
            cwd=self.root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["dryRun"])
        self.assertFalse(storage.exists())

    def test_invalid_bundle_rejected_before_storage(self):
        folder = self.root / "invalid"
        shutil.copytree(self.bundles["classification"], folder)
        index = fixtures.load(folder / "bundle.json")
        (folder / index["artifacts"][0]["path"]).write_bytes(b"invalid")
        storage = self.root / "invalid-storage"
        result = fixtures.OfflineBundleTests.cli(
            folder,
            "--storage",
            storage,
            script=fixtures.ROOT / "evaluation/import_offline_mlflow.py",
            cwd=self.root,
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(storage.exists())
        self.assertNotIn("Traceback", result.stderr)

    def test_snapshot_isolated_from_later_source_mutation(self):
        folder = self.root / "later-mutation"
        shutil.copytree(self.bundles["classification"], folder)
        with snapshot(folder) as (root, envelope, digest):
            before = project(root, envelope, digest)
            (folder / "bundle.json").write_text("invalid")
            self.assertEqual(project(root, envelope, digest), before)

    def test_null_boolean_and_non_numeric_values_do_not_become_metrics(self):
        self.assertEqual(
            numeric(
                {
                    "unknown": None,
                    "reviewed": False,
                    "scope": "candidate",
                    "counts": {"failed": 2},
                },
                "test",
            ),
            {"test.counts.failed": 2},
        )


if __name__ == "__main__":
    unittest.main()
