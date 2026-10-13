"""5a authorization, clock, IO and exact-context boundaries under active guards."""

import json
import os
import shutil
import unittest
from unittest.mock import patch

from execution_plan import Store, new_run
from execution_test_support import NANO, ROOT, ExecutionCase, canonical, cli


class ExecutionBoundaryTests(ExecutionCase):
    def test_allocate_live_intent_before_binding_a_permit(self):
        fixture = self.fixture()
        allocated = new_run(
            fixture.plan, fixture.run["clock"], evidence_kind="live-capture"
        )
        second = new_run(
            fixture.plan, fixture.run["clock"], evidence_kind="live-capture"
        )
        self.assertNotEqual(allocated["id"], second["id"])
        self.assertNotEqual(allocated["id"], allocated["initialInvocationId"])
        self.assertIsNone(allocated["permit"])
        expected_tasks = allocated["tasks"]
        fixture.run = allocated
        fixture.permit = None
        fixture.bind_plan()
        self.assertEqual(fixture.run["tasks"], expected_tasks)
        fixture.save()
        self.rejected(fixture)
        fixture.permit = {
            "schema": "normlab.execution-permit/v1",
            "runId": allocated["id"],
            "planDigest": None,
            "scopeDigest": None,
            "caps": dict(fixture.plan["caps"]),
            "expiresAt": "2026-01-01T00:01:00.000000Z",
            "authorization": fixture.authorization(),
            "externalSpending": {
                "currency": "USD",
                "ceilingMicros": 100000,
                "confirmationRef": "f" * 64,
                "provenance": "operator-asserted",
            },
        }
        fixture.bind_plan()
        fixture.save()
        self.accepted(fixture)

    def test_full_288_task_synthetic_journal_keeps_denominator(self):
        fixture = self.fixture(tasks=288)
        fixture.plan["caps"] = {
            "dispatches": 1000,
            "questions": 3000,
            "inputTokens": 100000,
            "outputTokens": 50000,
        }
        fixture.permit["caps"] = dict(fixture.plan["caps"])
        fixture.bind_plan()
        for task in range(288):
            fixture.completed(task)
        fixture.event("run-stopped", reason="complete")
        fixture.save()
        report = self.accepted(fixture)
        self.assertEqual(len(report["taskOutcomes"]), 288)
        self.assertEqual(report["counts"]["reserved"]["dispatches"], 288)
        self.assertEqual(report["counts"]["reserved"]["questions"], 864)
        self.assertEqual(report["counts"]["knownInputTokens"], 288 * 17)

    def test_guards_have_positive_controls(self):
        fixture = self.fixture()
        probes = {
            "network": (
                "import socket; socket.socket()",
                "Offline network/process guard active",
            ),
            "process": (
                "import subprocess; subprocess.run(['no-such-program'])",
                "Offline network/process guard active",
            ),
            "sdk": ("import openai", "Offline SDK guard active"),
            "write": (
                "from pathlib import Path; Path('forbidden').write_text('bad')",
                "Offline write guard active",
            ),
            "labels": (
                "open('reviewer-only.json').read()",
                "Offline label-read guard active",
            ),
        }
        for name, (source, message) in probes.items():
            with self.subTest(name=name):
                script = fixture.folder / f"probe-{name}.py"
                script.write_text(source)
                result = cli("unused", fixture.folder, script=script)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("AssertionError: " + message, result.stderr)
                self.assertFalse((fixture.folder / "forbidden").exists())

    def test_readers_are_portable_without_repository_or_provider_modules(self):
        folder = self.root / "reader"
        folder.mkdir()
        for name in (
            "execution_contract_cli.py",
            "execution_records.py",
            "execution_plan.py",
            "execution_outcomes.py",
            "execution_replay.py",
            "execution_decisions.py",
            "offline_bundle.py",
        ):
            shutil.copyfile(ROOT / "evaluation" / name, folder / name)
        fixture = self.fixture()
        fixture.completed(0)
        fixture.save()
        result = cli(
            "replay", fixture.folder, script=folder / "execution_contract_cli.py"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["counts"]["knownInputTokens"], 17)

    def test_zero_caps_budget_stop_and_effective_permit_minima(self):
        fixture = self.fixture()
        fixture.plan["caps"] = {key: 0 for key in fixture.plan["caps"]}
        fixture.bind_plan()
        fixture.event("run-stopped", reason="budget-exhaustion")
        fixture.save()
        self.assertEqual(self.accepted(fixture, "dry-run")["ceilings"]["dispatches"], 0)
        self.assertEqual(self.accepted(fixture)["counts"]["reserved"]["dispatches"], 0)
        fixture = self.fixture()
        fixture.permit["caps"]["dispatches"] = 1
        fixture.run["permit"] = fixture.put(fixture.permit)
        fixture.completed(0)
        fixture.event("run-stopped", reason="budget-exhaustion")
        fixture.save()
        self.accepted(fixture)
        fixture.events.pop()
        fixture.completed(1)
        fixture.save()
        self.rejected(fixture)

    def test_permit_scope_identity_type_and_expiry_mutations(self):
        mutations = {
            "plan": lambda p: p.update(planDigest="a" * 64),
            "run": lambda p: p.update(runId="10000000-0000-4000-8000-000000000099"),
            "scope": lambda p: p.update(scopeDigest="b" * 64),
            "boolean": lambda p: p["caps"].update(dispatches=True),
            "external-claim": lambda p: p["externalSpending"].update(
                provenance="provider-enforced"
            ),
            "negative-currency": lambda p: p["externalSpending"].update(
                ceilingMicros=-1
            ),
            "expired-at-reserve": lambda p: p.update(
                expiresAt="2026-01-01T00:00:00.000001Z"
            ),
            "authorization-after-expiry": lambda p: p["authorization"].update(
                authorizedAt="2027-01-01T00:00:00.000000Z"
            ),
        }
        for name, change in mutations.items():
            with self.subTest(name=name):
                fixture = self.fixture()
                fixture.completed()
                change(fixture.permit)
                fixture.run["permit"] = fixture.put(fixture.permit)
                fixture.save()
                self.rejected(fixture)

    def test_terminal_after_expiry_is_retained_but_reservation_before_authorization_rejects(
        self,
    ):
        fixture = self.fixture()
        fixture.completed()
        fixture.events[-1]["observedAt"] = "2026-01-01T00:02:00.000000Z"
        fixture.save()
        self.accepted(fixture)
        fixture.events[0]["observedAt"] = "2025-12-31T23:59:59.000000Z"
        fixture.save()
        self.rejected(fixture)

    def test_mock_cannot_consume_live_permit(self):
        fixture = self.fixture()
        with self.assertRaisesRegex(ValueError, "Mocks cannot consume a live permit"):
            new_run(
                fixture.plan,
                fixture.run["clock"],
                evidence_kind="mock",
                permit=fixture.run["permit"],
            )
        self.assertIsNone(
            new_run(fixture.plan, fixture.run["clock"], evidence_kind="mock")["permit"]
        )
        fixture.run["evidenceKind"] = "mock"
        fixture.save()
        self.rejected(fixture)

    def test_clock_capability_units_source_deadline_mutations(self):
        for key, value in (
            ("suspendAware", False),
            ("source", "linux:CLOCK_MONOTONIC"),
            ("units", "seconds"),
            ("epoch", "not-an-epoch"),
            ("deadlineNs", 32 * NANO),
        ):
            with self.subTest(key=key):
                fixture = self.fixture()
                fixture.run["clock"][key] = value
                fixture.save()
                self.rejected(fixture)

    def test_deadline_boundary_and_simulated_suspension_jump(self):
        fixture = self.fixture()
        deadline = fixture.run["clock"]["deadlineNs"]
        fixture.event("attempt-reserved", clock=deadline - 1)
        fixture.event("attempt-terminal", outcome=fixture.outcome(), clock=deadline + 1)
        fixture.event("run-stopped", reason="deadline", clock=deadline + 2)
        fixture.save()
        self.accepted(fixture)
        fixture.events[0]["clockNs"] = deadline
        fixture.save()
        self.rejected(fixture)
        fixture = self.fixture()
        fixture.event("run-stopped", reason="deadline", clock=40 * NANO)
        fixture.save()
        self.assertEqual(self.accepted(fixture)["counts"]["reserved"]["dispatches"], 0)

    def test_stale_and_invalid_resolution_bindings(self):
        mutations = {
            "head": lambda d: d.update(journalHead="a" * 64),
            "attempt": lambda d: d.update(attemptId="attempt-" + "a" * 64),
            "run": lambda d: d.update(runId="10000000-0000-4000-8000-000000000099"),
            "action": lambda d: d.update(action="retry"),
            "missing-adoption-evidence": lambda d: d.update(
                action="adopt-saved-outcome"
            ),
            "old-authorization": lambda d: d["authorization"].update(
                authorizedAt="2025-01-01T00:00:00.000000Z"
            ),
        }
        for name, change in mutations.items():
            with self.subTest(name=name):
                fixture = self.fixture()
                fixture.event("attempt-reserved")
                fixture.save()
                decision = fixture.resolution()
                change(decision)
                (fixture.folder / "resolution.json").write_bytes(canonical(decision))
                self.rejected(fixture, "resolution")
        fixture = self.fixture()
        fixture.event("attempt-reserved")
        fixture.save()
        fixture.resolution()
        fixture.event(
            "attempt-observed",
            outcome=fixture.outcome("unknown-outcome", observed=None),
        )
        fixture.save()
        self.rejected(fixture, "resolution")

    def test_resolution_for_completed_attempt_or_changed_evidence_rejects(self):
        fixture = self.fixture()
        fixture.completed()
        fixture.save()
        fixture.resolution()
        self.rejected(fixture, "resolution")
        fixture = self.fixture()
        fixture.event("attempt-reserved")
        fixture.save()
        decision = fixture.resolution("adopt-saved-outcome")
        (fixture.folder / decision["evidence"][0]["path"]).write_bytes(b"tampered")
        self.rejected(fixture, "resolution")

    def test_partial_observation_cannot_lose_identity_or_known_usage(self):
        for key in ("model", "providerRequestId", "usage"):
            with self.subTest(key=key):
                fixture = self.fixture()
                fixture.event("attempt-reserved")
                fixture.event(
                    "attempt-observed",
                    outcome=fixture.outcome(
                        "unknown-outcome",
                        usage={"inputTokens": 17, "outputTokens": None},
                        observed=True,
                    ),
                )
                fixture.event("attempt-terminal", outcome=fixture.outcome())
                fixture.change_outcome(
                    2,
                    lambda value: value.update(
                        {
                            key: {"inputTokens": 0, "outputTokens": 5}
                            if key == "usage"
                            else None
                        }
                    ),
                )
                fixture.save()
                self.rejected(fixture)
        fixture = self.fixture()
        fixture.event("attempt-reserved")
        fixture.event(
            "attempt-observed",
            outcome=fixture.outcome(
                "unknown-outcome",
                usage={"inputTokens": 17, "outputTokens": None},
                observed=True,
            ),
        )
        fixture.event("attempt-terminal", outcome=fixture.outcome())
        fixture.save()
        self.assertEqual(self.accepted(fixture)["counts"]["knownInputTokens"], 17)

    def test_retry_certificate_short_backoff_and_early_reservation_reject(self):
        for name in ("certificate", "short-backoff", "early-reservation"):
            with self.subTest(name=name):
                fixture = self.retry_fixture()
                if name == "certificate":
                    fixture.change_outcome(
                        1,
                        lambda value: value.update(
                            errorClasses=["CertificateError"], backoffNs=None
                        ),
                    )
                elif name == "short-backoff":
                    fixture.change_outcome(
                        1, lambda value: value.update(backoffNs=NANO - 1)
                    )
                else:
                    fixture.events[2]["clockNs"] = (
                        fixture.events[1]["clockNs"] + NANO - 1
                    )
                fixture.save()
                self.rejected(fixture)

    def rewrite_request(self, fixture, change):
        task = fixture.plan["tasks"][0]
        request = fixture.value(task["request"])
        change(request)
        task["request"] = fixture.put(request, ordered=True)
        context = fixture.value(task["context"])
        context["requestDigest"] = task["request"]["sha256"]
        task["context"] = fixture.put(context)
        fixture.bind_plan()
        fixture.save()

    def test_rehashed_context_wire_settings_and_secret_mutations(self):
        changes = {
            "model": lambda r: r["body"].update(model="unplanned"),
            "sampling": lambda r: r["body"].update(temperature=0),
            "credentials": lambda r: r["body"]["state"].update(api_key="DO_NOT_PRINT"),
            "headers": lambda r: r["headers"].update(Authorization="DO_NOT_PRINT"),
            "question-order": lambda r: r["body"].update(
                questions=dict(reversed(list(r["body"]["questions"].items())))
            ),
            "choice-labels": lambda r: r["body"]["questions"]["team"].update(
                criteria={"other": "Not planned"}
            ),
            "score-scale": lambda r: r["body"]["questions"]["urgency"].update(
                criteria=["now", "week", "later"]
            ),
            "null-state": lambda r: r["body"].update(state=None),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                fixture = self.fixture()
                self.rewrite_request(fixture, change)
                self.rejected(fixture, "plan")
        for field in ("history", "parentTurnIds"):
            fixture = self.fixture()
            task = fixture.plan["tasks"][0]
            context = fixture.value(task["context"])
            context[field] = ["hidden-history"]
            task["context"] = fixture.put(context)
            fixture.bind_plan()
            fixture.save()
            self.rejected(fixture, "plan")

    def test_normalized_answer_shape_range_and_model_drift_reject(self):
        mutations = {
            "boolean-noul": lambda r: r["answers"][0].update(value=True),
            "range": lambda r: r["answers"][0].update(value=1.01),
            "unknown-choice": lambda r: r["answers"][1].update(value="other"),
            "score-overflow": lambda r: r["answers"][2].update(value=3),
            "order": lambda r: r["answers"].reverse(),
            "normalizer": lambda r: r["normalizer"].update(revision="other"),
        }
        for name, change in mutations.items():
            with self.subTest(name=name):
                fixture = self.fixture()
                fixture.completed()
                saved = fixture.value(fixture.events[1]["outcome"])
                result = fixture.value(saved["result"])
                change(result)
                saved["result"] = fixture.put(result)
                fixture.events[1]["outcome"] = fixture.put(saved)
                fixture.save()
                self.rejected(fixture)
        fixture = self.fixture()
        fixture.completed(0)
        fixture.completed(1, model="other-model")
        fixture.save()
        self.rejected(fixture)

    def test_corrupt_duplicate_nonfinite_utf8_and_truncated_json_reject(self):
        for kind in ("duplicate", "overflow", "nan", "utf8", "utf16", "tail"):
            with self.subTest(kind=kind):
                fixture = self.fixture()
                fixture.save()
                if kind == "tail":
                    (fixture.folder / "journal.json").write_bytes(b"[")
                else:
                    raw = canonical(fixture.plan)
                    if kind == "duplicate":
                        raw = b'{"schema":"normlab.execution-plan/v1",' + raw[1:]
                    elif kind in {"overflow", "nan"}:
                        raw = raw.replace(
                            b'"wallTimeNs":30000000000',
                            b'"wallTimeNs":'
                            + (b"1e999" if kind == "overflow" else b"NaN"),
                        )
                    elif kind == "utf8":
                        raw = b"\xff"
                    else:
                        raw = raw.decode().encode("utf-16")
                    (fixture.folder / "plan.json").write_bytes(raw)
                self.rejected(fixture)

    def test_symlink_fifo_and_artifact_tamper_reject_without_hanging(self):
        for kind in ("leaf-symlink", "parent-symlink", "fifo", "artifact"):
            with self.subTest(kind=kind):
                fixture = self.fixture()
                fixture.save()
                if kind == "leaf-symlink":
                    plan = fixture.folder / "plan.json"
                    plan.rename(fixture.folder / "real-plan")
                    plan.symlink_to("real-plan")
                elif kind == "parent-symlink":
                    artifacts = fixture.folder / "artifacts"
                    artifacts.rename(fixture.folder / "real-artifacts")
                    artifacts.symlink_to("real-artifacts", target_is_directory=True)
                elif kind == "fifo":
                    (fixture.folder / "plan.json").unlink()
                    os.mkfifo(fixture.folder / "plan.json")
                else:
                    (
                        fixture.folder / fixture.plan["tasks"][0]["source"]["path"]
                    ).write_bytes(b"changed")
                self.rejected(fixture, "plan")

    def test_separate_journal_cap_and_bounded_regular_file_reads(self):
        fixture = self.fixture()
        fixture.save()
        (fixture.folder / "journal.json").write_bytes(
            b" " * (2 * 1024 * 1024 + 100) + b"[]"
        )
        self.accepted(fixture)
        for name, size in (
            ("plan.json", 2 * 1024 * 1024 + 1),
            ("journal.json", 16 * 1024 * 1024 + 1),
        ):
            fixture = self.fixture()
            fixture.save()
            with (fixture.folder / name).open("wb") as handle:
                handle.truncate(size)
            self.rejected(fixture)

    def test_total_file_and_cache_bounds_with_small_controlled_limits(self):
        fixture = self.fixture()
        fixture.save()
        store = Store(fixture.folder)
        raw = store.read("plan.json")
        (fixture.folder / "plan.json").write_bytes(b"changed")
        self.assertEqual(store.read("plan.json"), raw)
        with patch("execution_plan.MAX_FILES", 0):
            with self.assertRaisesRegex(ValueError, "file count cap"):
                Store(fixture.folder).read("plan.json")
        with patch("execution_plan.MAX_TOTAL_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "byte cap"):
                Store(fixture.folder).read("plan.json")


if __name__ == "__main__":
    unittest.main()
