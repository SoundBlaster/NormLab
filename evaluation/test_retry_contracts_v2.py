"""Offline regressions for bounded corpus export and pending-child accounting."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness import MAX_BYTES, load_json
from score_stage1_providers import save_new
from score_stage1_retries_v2 import score, seal
from stage1_provider_plan import write_json
from stage1_retry_executor_v2 import prepare, read_plan, replay, run

MANIFEST = (
    Path(__file__).parents[1]
    / "fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json"
)


class RetryContractsV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pilot = prepare(MANIFEST, "pilot")
        cls.corpus = prepare(MANIFEST, "corpus")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / "capture"
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.network = patch(
            "httpx2.HTTPTransport.handle_request",
            side_effect=AssertionError("Network forbidden"),
        )
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_corpus_zero_cap_exports_bounded_artifacts_and_replays(self):
        summary = run(self.corpus, self.folder, mock=True, max_mock_calls=0)
        self.assertEqual(summary["mockHttpCalls"], 0)
        self.assertEqual(summary["stopReason"], "budget-exhaustion")
        self.assertEqual(read_plan(self.folder), self.corpus)
        self.assertEqual(len(list(self.folder.glob("planned-*.json"))), 288)
        self.assertTrue(
            all(p.stat().st_size <= MAX_BYTES for p in self.folder.glob("*.json"))
        )
        self.assertEqual(replay(self.corpus, self.folder), summary)

    def test_corpus_completes_and_scores_all_288_jobs(self):
        summary = run(self.corpus, self.folder, mock=True)
        self.assertIsNone(summary["stopReason"])
        self.assertEqual(summary["mockHttpCalls"], 288)
        saved = Path(self.temp.name) / "seal.json"
        save_new(saved, seal(self.corpus, self.folder))
        report = score(MANIFEST, self.corpus, self.folder, saved)
        self.assertEqual(
            sum(a["final"]["completedJobs"] for a in report["arms"].values()), 288
        )

    def test_recovery_counts_attempts_separately(self):
        summary = run(self.pilot, self.folder, mock=True, scenario="recover")
        self.assertEqual(summary["mockHttpCalls"], 37)
        self.assertIsNone(summary["stopReason"])

    def test_terminal_failures_and_caps_do_not_retry(self):
        for scenario, cap, expected_calls, reason in (
            ("exhaust", None, 3, "retries-exhausted"),
            ("http", None, 1, "provider-error"),
            ("invalid", None, 1, "invalid-output"),
            ("recover", 1, 1, "budget-exhaustion"),
        ):
            with self.subTest(scenario=scenario, cap=cap):
                summary = run(
                    self.pilot,
                    self.folder.with_name(scenario + str(cap)),
                    mock=True,
                    max_mock_calls=cap,
                    scenario=scenario,
                )
                self.assertEqual(summary["mockHttpCalls"], expected_calls)
                self.assertEqual(summary["stopReason"], reason)

    def test_pending_completed_child_keeps_usage_but_no_verdict(self):
        run(self.pilot, self.folder, mock=True, max_mock_calls=1)
        index, _ = load_json(self.folder / "capture.json")
        index["attempts"][0]["finished"] = False
        index["stopReason"] = None
        write_json(self.folder / "capture.json", index)
        self.assertEqual(
            replay(self.pilot, self.folder)["stopReason"], "unknown-sent-outcome"
        )
        saved = Path(self.temp.name) / "seal.json"
        save_new(saved, seal(self.pilot, self.folder))
        report = score(MANIFEST, self.pilot, self.folder, saved)
        arm = report["arms"][self.pilot["parent"]["jobs"][0]["armId"]]
        self.assertEqual(arm["final"]["completedJobs"], 0)
        self.assertGreater(arm["knownInputTokens"], 0)
        self.assertGreater(arm["knownOutputTokens"], 0)
        self.assertEqual(arm["dispatchedAttemptsWithoutUsage"], 0)

    def test_split_job_tampering_is_rejected(self):
        run(self.corpus, self.folder, mock=True, max_mock_calls=0)
        job = next(self.folder.glob("planned-*.json"))
        value, _ = load_json(job)
        value["jobId"] = "changed"
        write_json(job, value)
        with self.assertRaises(ValueError):
            replay(self.corpus, self.folder)

    def test_seal_binds_exported_header_bytes(self):
        run(self.pilot, self.folder, mock=True, max_mock_calls=0)
        saved = Path(self.temp.name) / "seal.json"
        save_new(saved, seal(self.pilot, self.folder))
        header = self.folder / "plan.json"
        value, _ = load_json(header)
        header.write_text(json.dumps(value))
        replay(self.pilot, self.folder)
        with self.assertRaisesRegex(ValueError, "changed after sealing"):
            score(MANIFEST, self.pilot, self.folder, saved)


if __name__ == "__main__":
    unittest.main()
