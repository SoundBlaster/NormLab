"""Consumer identity, revision preservation and private archive snapshot checks."""

import shutil
import unittest

import test_offline_runtime_archive_reader as fixtures
from execution_resume import continue_mock
from execution_test_support import ExecutionCase, canonical, sha
from runtime_archive_reader import read_archive
from runtime_mlflow_projection import archive_files, project, snapshot


class ConsumerTests(ExecutionCase):
    input = fixtures.ArchiveReaderTests.input
    output = fixtures.ArchiveReaderTests.output
    script = fixtures.ArchiveReaderTests.script
    failure = staticmethod(fixtures.ArchiveReaderTests.failure)
    paused = fixtures.ArchiveReaderTests.paused
    request = fixtures.ArchiveReaderTests.request
    orphan = fixtures.ArchiveReaderTests.orphan
    archive = fixtures.ArchiveReaderTests.archive

    def test_repeat_projection_identity_and_evidence_boundaries(self):
        _, archive, _ = self.archive()
        verified = read_archive(archive)
        records = project(verified)
        self.assertEqual(records, project(read_archive(archive)))
        self.assertEqual(len(records), 3)
        self.assertIsNone(records[0]["parentKey"])
        self.assertEqual(records[1]["parentKey"], records[0]["key"])
        self.assertEqual(records[2]["parentKey"], records[1]["key"])
        for row in records:
            self.assertEqual(row["digest"], sha(canonical(row["payload"])))
            self.assertIsNone(row["payload"]["score"])
            self.assertIsNone(row["payload"]["actualCost"])
            self.assertFalse(row["payload"]["semanticQualityEvidence"])
        self.assertTrue(records[2]["metrics"])
        self.assertNotIn("criticalErrorFreeRate", records[2]["metrics"])

    def test_continued_revision_reuses_only_execution_parent(self):
        source, first, _ = self.archive()
        before = project(read_archive(first))
        continue_mock(source, self.request(source))
        from runtime_archive_export import export_runtime_archive

        second = self.output("consumer-second")
        export_runtime_archive(source, second)
        after = project(read_archive(second))
        self.assertEqual(before[0], after[0])
        self.assertNotEqual(before[1]["key"], after[1]["key"])
        self.assertNotEqual(before[2]["key"], after[2]["key"])
        self.assertEqual(after[-1]["kind"], "runtime-prediction-seal")
        self.assertEqual(after[-1]["parentKey"], after[1]["key"])

    def test_snapshot_survives_source_deletion_and_only_contains_verified_files(self):
        source, archive, _ = self.archive()
        with snapshot(archive) as (root, verified):
            expected = archive_files(verified)
            shutil.rmtree(source)
            shutil.rmtree(archive)
            self.assertEqual(read_archive(root).index, verified.index)
            actual = {
                str(path.relative_to(root)): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(actual, expected)
        self.assertFalse(root.exists())

    def test_unverified_or_mutated_archive_rejected(self):
        with self.assertRaises(ValueError):
            project({})
        _, archive, _ = self.archive()
        (archive / "projection.json").write_bytes(b"{}")
        with self.assertRaises(ValueError):
            with snapshot(archive):
                self.fail("Mutated archive accepted")


if __name__ == "__main__":
    unittest.main()
