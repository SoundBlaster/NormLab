"""Offline executor state, budget and wire parser regressions; no provider access."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import plan_stage1_comparison as planner
import stage1_executor as executor

MANIFEST = planner.ROOT / "fixtures/parking-pilot/stage1-comparison-v1/experiment.json"


class ExecutorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = planner.prepare(MANIFEST, "pilot")

    def directory(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name) / "capture"

    def run_fixture(self, mutate=None, **kwargs):
        folder = self.directory()
        fixture = executor.demo_fixture(self.plan)
        if mutate:
            mutate(fixture["responses"])
        result = executor.run(self.plan, fixture, folder, **kwargs)
        self.assertEqual(result, executor.replay(self.plan, folder))
        return folder, result

    def rewrite_turn(self, folder, number, mutate):
        index = json.loads((folder / "capture.json").read_bytes())
        path = folder / index["turnArtifacts"][number]["path"]
        turn = json.loads(path.read_bytes())
        mutate(turn)
        index["turnArtifacts"][number] = executor.write_json(path, turn)
        executor.write_json(folder / "capture.json", index)

    def test_complete_all_profiles_without_credentials(self):
        with patch.dict("os.environ", {}, clear=True):
            for profile, calls in (
                ("pilot", 24),
                ("corpus", 192),
                ("decisions-pilot", 12),
            ):
                plan = planner.prepare(MANIFEST, profile)
                before = copy.deepcopy(plan)
                folder = self.directory()
                report = executor.run(plan, executor.demo_fixture(plan), folder)
                self.assertEqual(report, executor.replay(plan, folder))
                self.assertEqual(report["fixtureCalls"], calls)
                self.assertEqual(report["networkCalls"], 0)
                self.assertIsNone(report["stopReason"])
                self.assertIsNone(report["criticalErrorFreeRate"])
                self.assertFalse(report["semanticQualityEvidence"])
                self.assertEqual(plan, before)
                self.assertEqual(plan["budget"]["authorizedCalls"], 0)
                self.assertTrue(
                    all(
                        arm["completed"] == arm["planned"]
                        for arm in report["arms"].values()
                    )
                )
                archived = json.loads(
                    (
                        MANIFEST.parent.parent
                        / "stage1-offline-executor-v1/summaries.json"
                    ).read_bytes()
                )
                self.assertEqual(report, archived[profile])

    def test_caps_include_unexecuted_denominator(self):
        for limit in (0, 1, 23, 24):
            _, report = self.run_fixture(max_calls=limit)
            self.assertEqual(report["fixtureCalls"], limit)
            self.assertEqual(sum(a["planned"] for a in report["arms"].values()), 24)
            self.assertEqual(
                sum(a.get("not-executed", 0) for a in report["arms"].values()),
                24 - limit,
            )
            self.assertEqual(
                report["stopReason"], "budget-exhaustion" if limit < 24 else None
            )
        for limit in (-1, 25, True, 1.5):
            with self.assertRaises(ValueError):
                self.run_fixture(max_calls=limit)

    def test_provider_failure_stops_and_redacts_error_body(self):
        def fail(responses):
            responses["J0002"] = {
                "httpStatus": 403,
                "body": {"error": "SECRET_NEVER_CAPTURE"},
            }

        folder, report = self.run_fixture(fail)
        self.assertEqual(report["fixtureCalls"], 2)
        self.assertEqual(report["stopReason"], "provider-error")
        self.assertEqual(
            sum(a.get("not-executed", 0) for a in report["arms"].values()), 22
        )
        self.assertFalse(
            any(
                b"SECRET_NEVER_CAPTURE" in p.read_bytes()
                for p in folder.rglob("*.json")
            )
        )

    def test_invalid_output_has_no_repair(self):
        def invalid(responses):
            responses["J0001"]["body"] = {"token": "SECRET_BAD_RESPONSE"}

        folder, report = self.run_fixture(invalid)
        self.assertEqual(report["fixtureCalls"], 1)
        self.assertEqual(report["stopReason"], "invalid-output")
        self.assertNotIn("SECRET_BAD_RESPONSE", (folder / "J0001.json").read_text())

    def test_returned_model_change_stops(self):
        arm = self.plan["jobs"][0]["armId"]
        second = next(j for j in self.plan["jobs"][1:] if j["armId"] == arm)

        def drift(responses):
            responses[second["jobId"]]["body"]["model"] += "-changed"

        _, report = self.run_fixture(drift)
        self.assertEqual(report["stopReason"], "returned-model-change")
        self.assertEqual(report["fixtureCalls"], int(second["jobId"][1:]))

    def test_wall_budget_stops_before_next_slot(self):
        ticks = iter([0, 0, 0, 0, 0, 900])
        _, report = self.run_fixture(clock=lambda: next(ticks))
        self.assertEqual(report["fixtureCalls"], 1)
        self.assertEqual(report["stopReason"], "deadline")

    def test_interrupted_sent_checkpoint_is_unknown_never_resumed(self):
        folder = self.directory()
        ticks = iter([0, 0])

        def interrupted():
            try:
                return next(ticks)
            except StopIteration:
                raise KeyboardInterrupt from None

        with self.assertRaises(KeyboardInterrupt):
            executor.run(
                self.plan, executor.demo_fixture(self.plan), folder, clock=interrupted
            )
        report = executor.replay(self.plan, folder)
        self.assertEqual(report["fixtureCalls"], 1)
        self.assertEqual(report["stopReason"], "unknown-sent-outcome")
        with self.assertRaises(FileExistsError):
            executor.run(self.plan, executor.demo_fixture(self.plan), folder)

    def test_rehashing_cannot_change_request_or_states(self):
        mutations = (
            (0, lambda t: t["request"]["body"].update(model="other/model:1.0")),
            (0, lambda t: t.update(fixtureCalls=0)),
            (0, lambda t: t.update(error="provider-error")),
            (0, lambda t: t["result"].update(cost=1.0)),
            (0, lambda t: t["result"].update(label="incompatible")),
            (1, lambda t: t.update(status="not-executed")),
        )
        for number, mutate in mutations:
            folder, _ = self.run_fixture()
            self.rewrite_turn(folder, number, mutate)
            with self.assertRaises((ValueError, KeyError, TypeError)):
                executor.replay(self.plan, folder)

    def test_inconsistent_failure_and_unused_states_rejected(self):
        folder, _ = self.run_fixture(max_calls=1)
        self.rewrite_turn(folder, 1, lambda t: t.update(httpStatus=200))
        with self.assertRaisesRegex(ValueError, "Unused turn"):
            executor.replay(self.plan, folder)
        folder, _ = self.run_fixture(lambda r: r["J0001"].update(httpStatus=403))
        self.rewrite_turn(folder, 0, lambda t: t.update(httpStatus=200))
        with self.assertRaisesRegex(ValueError, "HTTP failure invariant"):
            executor.replay(self.plan, folder)

    def test_artifact_digest_and_plan_binding(self):
        folder, _ = self.run_fixture()
        path = folder / "J0001.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            executor.replay(self.plan, folder)
        folder, _ = self.run_fixture()
        changed = copy.deepcopy(self.plan)
        changed["profile"] = "other"
        with self.assertRaisesRegex(ValueError, "Plan mismatch"):
            executor.replay(changed, folder)

    def test_fixture_coverage_and_digest_preflight(self):
        for mutation in (
            lambda f: f.update(planDigest="wrong"),
            lambda f: f["responses"].pop("J0001"),
        ):
            folder = self.directory()
            fixture = executor.demo_fixture(self.plan)
            mutation(fixture)
            with self.assertRaises(ValueError):
                executor.run(self.plan, fixture, folder)
            self.assertFalse(folder.exists())

    def test_responses_refusal_truncation_duplicate_keys_and_extra_verdict(self):
        wire = executor.wire_response(
            "luna-low-coreinfra", "compatible", "gpt-6-luna", "fixture-id"
        )
        for mutation in (
            lambda w: w.update(status="incomplete"),
            lambda w: w["output"][0]["content"][0].update(type="refusal"),
            lambda w: w["output"][0]["content"][0].update(
                text='{"overall":"compatible","overall":"incompatible"}'
            ),
            lambda w: w["output"][0]["content"][0].update(
                text='{"overall":"compatible","extra":true}'
            ),
            lambda w: w["output"].append(copy.deepcopy(w["output"][0])),
        ):
            changed = copy.deepcopy(wire)
            mutation(changed)
            with self.assertRaises(ValueError):
                executor.normalize("luna-low-coreinfra", changed)

    def test_choice_distributions_usage_and_model_names(self):
        wire = executor.wire_response(
            "jev-coreinfra",
            "compatible",
            "provider/model:1.0",
            "fixture-id",
            None,
            0.7,
            {"compatible": 0.7, "incompatible": 0.2, "indeterminate": 0.1},
        )
        self.assertEqual(
            executor.normalize("jev-coreinfra", wire)["returnedModel"],
            "provider/model:1.0",
        )
        for mutation in (
            lambda w: w["answers"]["overall"]["probabilities"].update(
                compatible=float("nan")
            ),
            lambda w: w["answers"]["overall"].update(confidence=True),
            lambda w: w["answers"]["overall"].update(choice="incompatible"),
            lambda w: w.update(usage={"input_tokens": True, "output_tokens": 0}),
            lambda w: w.update(id="bad\nid"),
        ):
            changed = copy.deepcopy(wire)
            mutation(changed)
            with self.assertRaises(ValueError):
                executor.normalize("jev-coreinfra", changed)

    def test_cli_dry_run_and_live_flag_rejected(self):
        command = [sys.executable, str(Path(executor.__file__)), str(MANIFEST)]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["callsExecuted"], 0)
        result = subprocess.run([*command, "--live"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrecognized arguments", result.stderr)


if __name__ == "__main__":
    unittest.main()
