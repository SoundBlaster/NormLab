"""SDK-free Stage 1 snapshots: native replay, portable projection and mutations."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from offline_stage1 import READER_ASSETS, READER_FILES
from stage1_provider_executor import code_pins, empty_turn
from stage1_provider_plan import export, prepare, sha, write_json
from stage1_provider_wire import mock_response, normalize
from stage1_retry_executor_v2 import child_plan, export_plan
from stage1_retry_executor_v2 import prepare as retry_prepare
from test_offline_bundle import GUARD, ROOT, load, value

MANIFEST = ROOT / "fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json"
STAGE1_GUARD = GUARD.replace("'httpx'", "'httpx', 'httpx2', 'typesafe'")


def provider_capture(plan, folder, statuses, cap=None):
    """Construct public wire fixtures without creating a provider or SDK client."""
    export(plan, folder)
    turns = []
    for number, job in enumerate(plan["jobs"]):
        turn = empty_turn(job)
        status = statuses[number] if number < len(statuses) else "not-executed"
        if status != "not-executed":
            turn.update(status=status, dispatches=1, request=job["request"])
        if status == "completed":
            provider = plan["providers"][job["armId"]]
            response = {
                "body": mock_response(
                    provider["apiFormat"],
                    "compatible",
                    provider["model"] + "-fixture",
                    "fixture-" + job["jobId"],
                ),
                "requestId": "fixture-" + job["jobId"],
            }
            turn.update(
                httpStatus=200,
                response=response,
                result=normalize(provider["apiFormat"], response),
                latencySeconds=0.01,
            )
        elif status == "failed":
            turn.update(error="transport-error", latencySeconds=0.01)
        turns.append(write_json(folder / (job["jobId"] + ".json"), turn))
    limit = len(statuses) if cap is None else cap
    last = statuses[-1] if statuses else None
    stop = None
    if last == "failed":
        stop = "transport-error"
    elif last != "sent" and len(statuses) < len(plan["jobs"]):
        stop = "budget-exhaustion"
    write_json(
        folder / "capture.json",
        {
            "schema": "normlab.stage1-provider-capture/v1",
            "mode": "mock-http",
            "planDigest": sha(plan),
            "codePins": code_pins(),
            "dependencies": {"mellea-jev-adapter": plan["adapterVersion"]},
            "permit": None,
            "permitDigest": sha(None),
            "maxCalls": limit,
            "fault": None,
            "stopReason": stop,
            "turnArtifacts": turns,
        },
    )


def retry_capture(plan, folder, scenario):
    folder.mkdir()
    export_plan(plan, folder)
    steps = [] if scenario == "zero" else ["completed"]
    if scenario == "recover":
        steps = ["failed", "completed", "completed"]
    elif scenario == "exhaust":
        steps = ["failed"] * 3
    entries = []
    position, ordinal = 0, 1
    for number, status in enumerate(steps, 1):
        job = plan["parent"]["jobs"][position]
        entry = {
            "jobId": job["jobId"],
            "ordinal": ordinal,
            "path": f"attempt-{number:04d}",
            "exceptionClasses": ["ReadTimeout"] if status == "failed" else [],
            "backoffSeconds": 2 ** (ordinal - 1)
            if status == "failed" and number < len(steps)
            else None,
            "finished": scenario not in {"pending-child", "missing-child"},
        }
        if scenario != "missing-child":
            provider_capture(
                child_plan(plan, job, ordinal), folder / entry["path"], [status]
            )
        entries.append(entry)
        if status == "completed":
            position, ordinal = position + 1, 1
        else:
            ordinal += 1
    stop = "retries-exhausted" if scenario == "exhaust" else "budget-exhaustion"
    if scenario in {"pending-child", "missing-child"}:
        stop = None
    write_json(
        folder / "capture.json",
        {
            "schema": "normlab.stage1-retry-capture/v2",
            "planDigest": sha(plan),
            "mode": "mock-http",
            "permit": None,
            "maxCalls": len(steps),
            "scenario": None,
            "attempts": entries,
            "stopReason": stop,
            "elapsedSeconds": 0.01,
        },
    )


class OfflineStage1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.pilot = prepare(MANIFEST)
        cls.retry = retry_prepare(MANIFEST, "pilot")
        cls.sources = {}
        for scenario in (
            "recover",
            "exhaust",
            "pending-child",
            "missing-child",
            "zero",
        ):
            source = cls.root / scenario
            retry_capture(cls.retry, source, scenario)
            cls.sources[scenario] = source
        for name, statuses in (
            ("provider", ["completed"] * 3),
            ("provider-sent", ["sent"]),
            ("provider-failed", ["failed"]),
        ):
            source = cls.root / name
            provider_capture(cls.pilot, source, statuses)
            cls.sources[name] = source
        corpus = cls.root / "corpus"
        retry_capture(retry_prepare(MANIFEST, "corpus"), corpus, "zero")
        cls.sources["corpus"] = corpus

    @classmethod
    def cli(cls, *args, script=None):
        return subprocess.run(
            [
                sys.executable,
                "-B",
                "-S",
                "-c",
                STAGE1_GUARD,
                str(script or ROOT / "evaluation/offline_adapters.py"),
                *map(str, args),
            ],
            cwd=cls.root,
            env={"PATH": os.defpath, "PYTHONNOUSERSITE": "1"},
            capture_output=True,
            text=True,
            timeout=60,
        )

    def bundle(self, scenario):
        folder = Path(tempfile.mkdtemp(dir=self.root)) / "bundle"
        result = self.cli("stage1", self.sources[scenario], "--output", folder)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.cli("verify", folder).returncode, 0)
        return folder, load(folder / "bundle.json")

    def test_provider_outcomes_and_unknown_language(self):
        folder, envelope = self.bundle("provider")
        self.assertEqual(envelope["counts"]["plannedTasks"], 36)
        self.assertEqual(
            envelope["counts"]["statusCounts"], {"completed": 3, "not-executed": 33}
        )
        self.assertEqual(envelope["counts"]["knownInputTokens"], 300)
        self.assertIsNone(envelope["reference"])
        for ref in envelope["records"]:
            task = value(folder, ref)
            self.assertIsNone(task["language"])
            self.assertEqual(
                len(task["turn"]["attempts"]),
                int(task["turn"]["status"] == "completed"),
            )

    def test_retry_first_final_and_usage_once(self):
        folder, envelope = self.bundle("recover")
        counts = envelope["counts"]
        self.assertEqual(counts["attemptsStarted"], 3)
        self.assertEqual(counts["retryAttemptsStarted"], 1)
        self.assertEqual(counts["knownDispatches"], 3)
        self.assertEqual(counts["knownInputTokens"], 200)
        self.assertEqual(counts["unknownUsageAttempts"], 1)
        task = value(folder, envelope["records"][0])
        row = value(folder, task["scoreArtifact"])
        self.assertEqual(row["first"]["status"], "failed")
        self.assertEqual(row["final"]["status"], "completed")
        self.assertIsNone(row["selectedReferencePass"])
        history = task["turn"]["attempts"]
        self.assertEqual([a["ordinal"] for a in history], [1, 2])
        self.assertEqual(history[0]["scheduledBackoffSeconds"], 1)
        self.assertNotEqual(history[0]["id"], history[1]["id"])
        self.assertEqual(
            value(folder, history[1]["requestArtifact"]),
            self.pilot["jobs"][0]["request"],
        )

    def test_pending_completed_child_keeps_usage_without_verdict(self):
        folder, envelope = self.bundle("pending-child")
        self.assertEqual(envelope["counts"]["knownInputTokens"], 100)
        self.assertEqual(envelope["counts"]["unknownUsageAttempts"], 0)
        self.assertEqual(envelope["counts"]["unknownOutcomeAttempts"], 1)
        task = value(folder, envelope["records"][0])
        row = value(folder, task["scoreArtifact"])
        self.assertEqual(
            row["final"], {"status": "unknown-sent-outcome", "observed": None}
        )
        self.assertEqual(task["turn"]["attempts"][0]["originalStatus"], "completed")

    def test_missing_child_reserves_unknown_dispatch(self):
        folder, envelope = self.bundle("missing-child")
        self.assertEqual(envelope["counts"]["knownDispatches"], 0)
        self.assertEqual(envelope["counts"]["reservedUnknownDispatches"], 1)
        self.assertEqual(envelope["counts"]["unknownUsageAttempts"], 1)
        attempt = value(folder, envelope["records"][0])["turn"]["attempts"][0]
        self.assertIsNone(attempt["dispatches"])
        self.assertIsNone(attempt["requestArtifact"])

    def test_exhausted_failed_and_sent_statuses_retained(self):
        for scenario, status, attempts in (
            ("exhaust", "failed", 3),
            ("provider-failed", "failed", 1),
            ("provider-sent", "unknown-sent-outcome", 1),
        ):
            with self.subTest(scenario=scenario):
                _, envelope = self.bundle(scenario)
                self.assertEqual(envelope["counts"]["statusCounts"][status], 1)
                self.assertEqual(envelope["counts"]["attemptsStarted"], attempts)

    def test_corpus_split_plan_keeps_all_unexecuted_tasks(self):
        folder, envelope = self.bundle("corpus")
        self.assertEqual(envelope["counts"]["plannedTasks"], 288)
        self.assertEqual(envelope["counts"]["statusCounts"], {"not-executed": 288})
        self.assertEqual(envelope["counts"]["attemptsStarted"], 0)
        self.assertTrue(
            all(a["bytes"] <= 2 * 1024 * 1024 for a in envelope["artifacts"])
        )
        self.assertEqual(
            len(value(folder, envelope["source"]["manifest"])["files"]), 290
        )

    def test_portable_reader_and_comparison_without_sdk(self):
        folder, envelope = self.bundle("recover")
        portable_root = Path(tempfile.mkdtemp(dir=self.root))
        portable = portable_root / "evaluation"
        portable.mkdir()
        for name in (*READER_FILES, "offline_compare.py"):
            shutil.copyfile(ROOT / "evaluation" / name, portable / name)
        for name in READER_ASSETS:
            target = portable_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        result = self.cli("verify", folder, script=portable / "offline_adapters.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["counts"], envelope["counts"])
        result = self.cli(folder, folder, script=portable / "offline_compare.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)["summary"]
        self.assertEqual(summary["matchedTasks"], 36)
        self.assertEqual(summary["notEvaluated"], 36)
        self.assertEqual(summary["evaluatedPairs"], 0)

    def test_projected_counts_and_attempts_cannot_be_resealed(self):
        from test_offline_bundle import canonical, store

        for variant in ("usage", "unknown", "attempt"):
            folder, envelope = self.bundle("recover")
            if variant == "usage":
                envelope["counts"]["knownInputTokens"] += 100
            elif variant == "unknown":
                envelope["counts"]["unknownUsageAttempts"] = 0
            else:
                task = value(folder, envelope["records"][0])
                task["turn"]["attempts"][0]["dispatches"] = 0
                envelope["records"][0] = store(folder, envelope, task)
            (folder / "bundle.json").write_bytes(canonical(envelope))
            result = self.cli("verify", folder)
            self.assertEqual(result.returncode, 1, result.stderr)

    def test_snapshot_ignores_adjacent_files_and_rejects_escape(self):
        source = Path(tempfile.mkdtemp(dir=self.root)) / "source"
        shutil.copytree(self.sources["provider"], source)
        (source / "secret.env").write_text("MUST_NOT_BE_EXPORTED")
        target = source.parent / "bundle"
        result = self.cli("stage1", source, "--output", target)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(
            any(
                b"MUST_NOT_BE_EXPORTED" in p.read_bytes()
                for p in (target / "artifacts").iterdir()
            )
        )
        index = load(source / "capture.json")
        index["turnArtifacts"][0]["path"] = "../secret.env"
        write_json(source / "capture.json", index)
        result = self.cli("stage1", source)
        self.assertEqual(result.returncode, 1)

    def test_full_corpus_retry_tree_and_bounded_artifacts(self):
        plan = retry_prepare(MANIFEST, "corpus")
        source = Path(tempfile.mkdtemp(dir=self.root)) / "source"
        source.mkdir()
        export_plan(plan, source)
        entries = []
        for number, job in enumerate(plan["parent"]["jobs"], 1):
            name = f"attempt-{number:04d}"
            provider_capture(child_plan(plan, job, 1), source / name, ["completed"])
            entries.append(
                {
                    "jobId": job["jobId"],
                    "ordinal": 1,
                    "path": name,
                    "exceptionClasses": [],
                    "backoffSeconds": None,
                    "finished": True,
                }
            )
        write_json(
            source / "capture.json",
            {
                "schema": "normlab.stage1-retry-capture/v2",
                "planDigest": sha(plan),
                "mode": "mock-http",
                "permit": None,
                "maxCalls": 288,
                "scenario": None,
                "attempts": entries,
                "stopReason": None,
                "elapsedSeconds": 1,
            },
        )
        output = source.parent / "bundle"
        result = self.cli("stage1", source, "--output", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        envelope = load(output / "bundle.json")
        self.assertEqual(envelope["counts"]["statusCounts"], {"completed": 288})
        self.assertEqual(envelope["counts"]["knownInputTokens"], 28800)
        self.assertEqual(envelope["counts"]["knownOutputTokens"], 2880)
        self.assertEqual(envelope["counts"]["unknownUsageAttempts"], 0)
        self.assertTrue(
            all(a["bytes"] <= 2 * 1024 * 1024 for a in envelope["artifacts"])
        )
        self.assertEqual(self.cli("verify", output).returncode, 0)

    def test_missing_capture_preserves_existing_child_plan(self):
        source = Path(tempfile.mkdtemp(dir=self.root)) / "source"
        shutil.copytree(self.sources["missing-child"], source)
        child = child_plan(self.retry, self.retry["parent"]["jobs"][0], 1)
        export(child, source / "attempt-0001")
        output = source.parent / "bundle"
        result = self.cli("stage1", source, "--output", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        envelope = load(output / "bundle.json")
        attempt = value(output, envelope["records"][0])["turn"]["attempts"][0]
        self.assertIsNotNone(attempt["childPlanArtifact"])
        self.assertIsNone(attempt["childCaptureArtifact"])
        self.assertIsNone(attempt["dispatches"])

    def test_native_replay_rejects_illegal_retry_suffix_and_wire_drift(self):
        for variant in ("ordinal", "after-unknown", "wire", "code"):
            source = Path(tempfile.mkdtemp(dir=self.root)) / "source"
            shutil.copytree(self.sources["recover"], source)
            outer = load(source / "capture.json")
            if variant == "ordinal":
                outer["attempts"][1]["ordinal"] = 3
            elif variant == "after-unknown":
                outer["attempts"][0]["finished"] = False
            elif variant == "wire":
                folder = source / "attempt-0002"
                index = load(folder / "capture.json")
                turn = load(folder / index["turnArtifacts"][0]["path"])
                turn["request"]["body"]["model"] = "incorrect"
                index["turnArtifacts"][0] = write_json(
                    folder / (turn["jobId"] + ".json"), turn
                )
                write_json(folder / "capture.json", index)
            else:
                folder = source / "attempt-0001"
                index = load(folder / "capture.json")
                index["codePins"]["stage1_provider_executor.py"] = "0" * 64
                write_json(folder / "capture.json", index)
            write_json(source / "capture.json", outer)
            result = self.cli("stage1", source)
            self.assertEqual(result.returncode, 1, (variant, result.stderr))

    def test_capture_digest_binds_child_response_tree(self):
        left, baseline = self.bundle("recover")
        source = Path(tempfile.mkdtemp(dir=self.root)) / "source"
        shutil.copytree(self.sources["recover"], source)
        child = source / "attempt-0002"
        index = load(child / "capture.json")
        turn = load(child / index["turnArtifacts"][0]["path"])
        turn["response"]["body"]["usage"]["input_tokens"] += 1
        provider = self.pilot["providers"][self.pilot["jobs"][0]["armId"]]
        turn["result"] = normalize(provider["apiFormat"], turn["response"])
        index["turnArtifacts"][0] = write_json(child / (turn["jobId"] + ".json"), turn)
        write_json(child / "capture.json", index)
        output = source.parent / "bundle"
        result = self.cli("stage1", source, "--output", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        candidate = load(output / "bundle.json")
        self.assertNotEqual(
            baseline["run"]["captureDigest"], candidate["run"]["captureDigest"]
        )
        self.assertEqual(candidate["counts"]["knownInputTokens"], 201)
        result = self.cli(left, output, script=ROOT / "evaluation/offline_compare.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["sameRun"])

    def test_stage1_sdk_and_socket_guards_are_active(self):
        for code in ("import httpx2", "import socket; socket.socket()"):
            script = Path(tempfile.mkdtemp(dir=self.root)) / "blocked.py"
            script.write_text(code)
            result = self.cli(script=script)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("forbidden", result.stderr.lower())

    def test_completed_response_with_unknown_usage_is_not_zero_total_usage(self):
        source = Path(tempfile.mkdtemp(dir=self.root)) / "source"
        provider_capture(self.pilot, source, ["completed"])
        index = load(source / "capture.json")
        turn = load(source / index["turnArtifacts"][0]["path"])
        turn["response"]["body"]["usage"] = None
        turn["result"] = normalize("typesafe-systemone", turn["response"])
        index["turnArtifacts"][0] = write_json(source / (turn["jobId"] + ".json"), turn)
        write_json(source / "capture.json", index)
        output = source.parent / "bundle"
        result = self.cli("stage1", source, "--output", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        envelope = load(output / "bundle.json")
        self.assertEqual(envelope["counts"]["statusCounts"]["completed"], 1)
        self.assertEqual(envelope["counts"]["knownInputTokens"], 0)
        self.assertEqual(envelope["counts"]["unknownUsageAttempts"], 1)
        self.assertIsNone(value(output, envelope["records"][0])["turn"]["usage"])

    def test_unsupported_source_schema_has_fixed_diagnostic(self):
        source = Path(tempfile.mkdtemp(dir=self.root)) / "source"
        shutil.copytree(self.sources["recover"], source)
        index = load(source / "capture.json")
        index["schema"] = "normlab.stage1-retry-capture/v1"
        write_json(source / "capture.json", index)
        result = self.cli("stage1", source)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            result.stderr.strip(), "Offline bundle contract validation/export failed"
        )


if __name__ == "__main__":
    unittest.main()
