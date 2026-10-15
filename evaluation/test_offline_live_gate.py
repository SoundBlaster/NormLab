"""Current permit/clock faults without keys, SDKs or provider requests."""

import copy
import unittest
from unittest.mock import patch

from execution_live_gate import LinuxClock, current_gate
from execution_plan import Store, prepare
from execution_test_support import ExecutionCase


class LiveGateTests(ExecutionCase):
    def setup_gate(self):
        fixture = self.fixture(mock=False, tasks=1)
        fixture.save()
        store = Store(fixture.folder)
        plan = prepare(store)
        run = store.json("run.json")
        permit = store.value(run["permit"])
        confirmation = {
            "runId": run["id"],
            "planDigest": run["planDigest"],
            "permitDigest": run["permit"]["sha256"],
            "invocationId": run["initialInvocationId"],
            "externalCeilingMicros": permit["externalSpending"]["ceilingMicros"],
        }
        sample = {
            k: run["clock"][k]
            for k in ("policy", "source", "units", "suspendAware", "epoch")
        }
        sample.update(
            clockNs=run["clock"]["startNs"],
            observedAt=permit["authorization"]["authorizedAt"],
        )
        return plan, run, store, confirmation, sample

    def test_current_confirmation_is_exact_and_positive(self):
        plan, run, store, confirmation, sample = self.setup_gate()
        self.assertGreater(
            current_gate(plan, run, store, confirmation, sample)["timeoutNs"], 0
        )
        for field in confirmation:
            changed = dict(confirmation)
            changed[field] = 0 if field == "externalCeilingMicros" else "different"
            with self.subTest(field=field), self.assertRaises(ValueError):
                current_gate(plan, run, store, changed, sample)

    def test_suspension_expiry_epoch_source_and_regressions_reject(self):
        plan, run, store, confirmation, sample = self.setup_gate()
        mutations = [
            {"clockNs": run["clock"]["deadlineNs"]},
            {"epoch": "f" * 64},
            {"source": "monotonic"},
            {"suspendAware": False},
            {"clockNs": sample["clockNs"] - 1},
            {"observedAt": "2099-01-01T00:00:00.000000Z"},
        ]
        for change in mutations:
            with self.subTest(change=change), self.assertRaises(ValueError):
                current_gate(plan, run, store, confirmation, {**sample, **change})
        earlier = {**sample, "observedAt": "2000-01-01T00:00:00.000000Z"}
        with self.assertRaises(ValueError):
            current_gate(plan, run, store, confirmation, earlier, last_sample=sample)

    def test_mock_saved_declaration_and_exhausted_caps_do_not_authorize(self):
        plan, run, store, confirmation, sample = self.setup_gate()
        changed = copy.deepcopy(run)
        changed["evidenceKind"] = "mock"
        with self.assertRaises(ValueError):
            current_gate(plan, changed, store, confirmation, sample)
        run["counts"]["reserved"]["dispatches"] = plan["caps"]["dispatches"]
        with self.assertRaises(ValueError):
            current_gate(plan, run, store, confirmation, sample)

    def test_unsupported_host_never_falls_back_to_monotonic(self):
        with (
            patch("execution_live_gate.sys.platform", "darwin"),
            patch("execution_live_gate.time.monotonic", side_effect=AssertionError),
        ):
            with self.assertRaises(ValueError):
                LinuxClock().sample()

    def test_post_reservation_recheck_requires_baseline_and_rejects_backward_utc(self):
        plan, run, store, confirmation, sample = self.setup_gate()
        with self.assertRaises(ValueError):
            current_gate(plan, run, store, confirmation, sample, reserve=False)
        last = {**sample, "observedAt": "2026-01-01T00:00:00.000010Z"}
        rolled_back = {**sample, "observedAt": "2026-01-01T00:00:00.000005Z"}
        with self.assertRaises(ValueError):
            current_gate(
                plan,
                run,
                store,
                confirmation,
                rolled_back,
                last_sample=last,
                reserve=False,
            )
        self.assertGreater(
            current_gate(
                plan, run, store, confirmation, last, last_sample=sample, reserve=False
            )["timeoutNs"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
