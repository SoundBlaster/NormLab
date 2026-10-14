"""Dry-run projects verified archives without provider SDKs or registry writes."""

import json
import os
import subprocess
import sys
import unittest

import test_offline_runtime_mlflow_projection as fixtures
from execution_test_support import ROOT, ExecutionCase
from import_runtime_mlflow import run
from runtime_archive_reader import read_archive
from runtime_mlflow_projection import project

GUARD = """
import sys, runpy
from pathlib import Path
def guard(event, args):
    if event.startswith('socket.'):
        raise AssertionError('No network in runtime dry-run')
    if event == 'import' and args[0].split('.')[0] in {
        'mlflow', 'openai', 'mellea', 'mellea_jev_adapter', 'requests', 'httpx'
    }:
        raise AssertionError('No SDK in runtime dry-run')
sys.addaudithook(guard)
script = Path(sys.argv[1]).resolve()
sys.argv = sys.argv[1:]
sys.path.insert(0, str(script.parent))
runpy.run_path(str(script), run_name='__main__')
"""


class RuntimeCLITests(ExecutionCase):
    input = fixtures.ConsumerTests.input
    output = fixtures.ConsumerTests.output
    script = fixtures.ConsumerTests.script
    failure = staticmethod(fixtures.ConsumerTests.failure)
    paused = fixtures.ConsumerTests.paused
    request = fixtures.ConsumerTests.request
    orphan = fixtures.ConsumerTests.orphan
    archive = fixtures.ConsumerTests.archive

    def test_dry_run_contract_and_no_storage(self):
        _, archive, _ = self.archive()
        storage = self.root / "should-not-exist"
        value = run(archive, storage, dry_run=True)
        self.assertEqual(value["records"], project(read_archive(archive)))
        self.assertEqual(value["registryWritesExecuted"], 0)
        self.assertFalse(storage.exists())

    def test_cli_sdk_network_denied_and_error_sanitized(self):
        _, archive, _ = self.archive()
        storage = self.root / "cli-storage"
        args = [
            sys.executable,
            "-B",
            "-S",
            "-c",
            GUARD,
            str(ROOT / "evaluation/import_runtime_mlflow.py"),
            str(archive),
            "--dry-run",
            "--storage",
            str(storage),
        ]
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=20,
            env={"PATH": os.defpath, "PYTHONNOUSERSITE": "1"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["registryWritesExecuted"], 0)
        self.assertFalse(storage.exists())
        (archive / "projection.json").write_text("PRIVATE-SENTINEL")
        result = subprocess.run(args, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("PRIVATE-SENTINEL", result.stderr)
        self.assertFalse(storage.exists())


if __name__ == "__main__":
    unittest.main()
