"""Dedicated 5a CLI/runtime positives and coordinated journal mutation checks."""

import unittest

from execution_test_support import NANO, ExecutionCase, canonical


class ExecutionRecordsTests(ExecutionCase):
    def test_plan_dry_run_all_protocols_and_no_authorization_reads(self):
        for protocol in (
            "typesafe-systemone/v1",
            "openai-decisions/v1",
            "openai-chat-completions/v1",
            "openai-responses/v1",
        ):
            with self.subTest(protocol=protocol):
                fixture = self.fixture(protocol=protocol)
                fixture.save()
                for name in (
                    "run.json",
                    "journal.json",
                    "resolution.json",
                    "reviewer-only.json",
                ):
                    (fixture.folder / name).write_text("DO_NOT_PRINT invalid JSON")
                first = self.accepted(fixture, "plan")
                self.assertEqual(first, self.accepted(fixture, "dry-run"))
                self.assertEqual(
                    (first["tasks"], first["turns"], first["questions"]), (2, 2, 6)
                )
                self.assertEqual(
                    first["ceilings"],
                    {
                        "dispatches": 6,
                        "questions": 18,
                        "inputTokens": 600,
                        "outputTokens": 300,
                    },
                )

    def test_empty_mock_and_live_shaped_captures(self):
        for mock in (False, True):
            with self.subTest(mock=mock):
                fixture = self.fixture(mock=mock)
                fixture.save()
                report = self.accepted(fixture)
                self.assertEqual(report["state"], "created")
                self.assertEqual(report["counts"]["reserved"]["dispatches"], 0)
                self.assertEqual(report["unknownAttemptIds"], [])
                self.assertTrue(
                    all(
                        task["first"] is None and task["final"] is None
                        for task in report["taskOutcomes"]
                    )
                )

    def test_completed_three_question_requests_charge_usage_once(self):
        for mock in (False, True):
            with self.subTest(mock=mock):
                fixture = self.fixture(mock=mock)
                fixture.completed(0)
                fixture.completed(1)
                fixture.event("run-stopped", reason="complete")
                fixture.save()
                report = self.accepted(fixture)
                self.assertEqual(report["state"], "finished")
                self.assertEqual(
                    report["counts"]["reserved"],
                    {
                        "dispatches": 2,
                        "questions": 6,
                        "inputTokens": 200,
                        "outputTokens": 100,
                    },
                )
                self.assertEqual(
                    report["counts"]["knownInputTokens"], 0 if mock else 34
                )
                self.assertEqual(
                    report["counts"]["knownOutputTokens"], 0 if mock else 10
                )
                self.assertEqual(
                    report["counts"]["observedDispatches"], 0 if mock else 2
                )
                self.assertEqual(report["unknownDispatchAttempts"], 0)

    def test_unknown_reservation_and_partial_usage_remain_unknown(self):
        for observed in (False, True):
            with self.subTest(partial_observation=observed):
                fixture = self.fixture()
                fixture.event("attempt-reserved")
                if observed:
                    fixture.event(
                        "attempt-observed",
                        outcome=fixture.outcome(
                            "unknown-outcome",
                            usage={"inputTokens": 17, "outputTokens": None},
                            observed=None,
                        ),
                    )
                fixture.save()
                report = self.accepted(fixture)
                self.assertEqual(report["state"], "paused-unknown")
                self.assertEqual(report["unknownDispatchAttempts"], 1)
                self.assertEqual(report["counts"]["unknownUsageAttempts"], 1)
                self.assertEqual(
                    report["counts"]["knownInputTokens"], 17 if observed else 0
                )
                self.assertEqual(report["counts"]["reserved"]["dispatches"], 1)
                self.assertEqual(report["taskOutcomes"][1]["attemptIds"], [])

    def test_known_failure_categories_stop_with_evidence(self):
        for status in (
            "http-failed",
            "invalid-output",
            "refused",
            "model-rejected",
            "transport-failed",
        ):
            with self.subTest(status=status):
                fixture = self.fixture()
                fixture.event("attempt-reserved")
                fixture.event(
                    "attempt-terminal",
                    outcome=fixture.outcome(
                        status,
                        model="unexpected-model"
                        if status == "model-rejected"
                        else "mock-model",
                        errors=["CertificateError"],
                    ),
                )
                fixture.event("run-stopped", reason="terminal-failure")
                fixture.save()
                report = self.accepted(fixture)
                self.assertEqual(report["taskOutcomes"][0]["final"]["status"], status)
                self.assertIsNone(report["taskOutcomes"][1]["final"])

    def test_retries_first_final_and_exhaustion(self):
        for exhausted in (False, True):
            with self.subTest(exhausted=exhausted):
                report = self.accepted(self.retry_fixture(exhausted=exhausted))
                attempts = 3 if exhausted else 2
                self.assertEqual(len(report["taskOutcomes"][0]["attemptIds"]), attempts)
                self.assertEqual(
                    report["taskOutcomes"][0]["first"]["status"], "transport-failed"
                )
                self.assertEqual(
                    report["taskOutcomes"][0]["final"]["status"],
                    "transport-failed" if exhausted else "completed",
                )
                self.assertEqual(report["counts"]["knownInputTokens"], attempts * 17)

    def test_usage_ceiling_breach_is_retained_and_stops_later_work(self):
        fixture = self.fixture()
        fixture.completed(usage={"inputTokens": 101, "outputTokens": 51})
        fixture.event("run-stopped", reason="usage-ceiling-exceeded")
        fixture.save()
        report = self.accepted(fixture)
        self.assertTrue(report["usageCeilingExceeded"])
        self.assertEqual(report["counts"]["knownInputTokens"], 101)
        fixture.events.pop()
        fixture.completed(1)
        fixture.save()
        self.rejected(fixture)

    def test_resolution_preflight_never_applies_stop_or_adoption(self):
        for action in ("stop", "adopt-saved-outcome"):
            with self.subTest(action=action):
                fixture = self.fixture()
                fixture.event("attempt-reserved")
                fixture.save()
                fixture.resolution(action)
                report = self.accepted(fixture, "resolution")
                self.assertEqual(report["state"], "paused-unknown")
                self.assertFalse(report["resolution"]["applied"])
                self.assertFalse(report["resolution"]["adoptionValidated"])
                self.assertEqual(report["resolution"]["authorizedDispatches"], 0)

    def test_false_dispatch_usage_invariant_and_positive_null_dispatch(self):
        for status in ("unknown-outcome", "transport-failed"):
            for usage in (
                {"inputTokens": 17, "outputTokens": 0},
                {"inputTokens": 0, "outputTokens": 5},
                {"inputTokens": None, "outputTokens": 0},
            ):
                with self.subTest(status=status, usage=usage):
                    fixture = self.fixture()
                    fixture.event("attempt-reserved")
                    fixture.event(
                        "attempt-observed"
                        if status == "unknown-outcome"
                        else "attempt-terminal",
                        outcome=fixture.outcome(status, observed=False, usage=usage),
                    )
                    fixture.save()
                    self.rejected(fixture)
        for observed in (False, None, True):
            fixture = self.fixture()
            fixture.event("attempt-reserved")
            fixture.event(
                "attempt-observed",
                outcome=fixture.outcome(
                    "unknown-outcome",
                    observed=observed,
                    usage={
                        "inputTokens": 0 if observed is False else 17,
                        "outputTokens": 0,
                    },
                ),
            )
            fixture.save()
            report = self.accepted(fixture)
            self.assertEqual(report["unknownDispatchAttempts"], int(observed is None))

    def test_rehashed_journal_mutations_reject(self):
        mutations = {
            "sequence-gap": lambda f: f.events[1].update(sequence=5),
            "duplicate-reserve": lambda f: f.events.insert(1, dict(f.events[0])),
            "wrong-task": lambda f: f.events[0].update(
                taskId=f.run["tasks"][1]["taskId"]
            ),
            "wrong-turn": lambda f: f.events[0].update(turnId="turn-" + "a" * 64),
            "wrong-ordinal": lambda f: f.events[0].update(ordinal=2),
            "wrong-question-charge": lambda f: f.events[0]["budgetDelta"].update(
                questions=2
            ),
            "hidden-refund": lambda f: f.events[1]["budgetDelta"].update(dispatches=1),
            "clock-regression": lambda f: f.events[1].update(clockNs=NANO),
            "UTC-regression": lambda f: f.events[1].update(
                observedAt="2025-12-31T00:00:00.000000Z"
            ),
            "unsupported-invocation": lambda f: f.events[0].update(
                invocationId="10000000-0000-4000-8000-000000000099"
            ),
            "unsupported-resume": lambda f: f.events[0].update(type="resume"),
            "after-stop": lambda f: f.events.append(dict(f.events[0])),
        }
        for name, change in mutations.items():
            with self.subTest(name=name):
                fixture = self.fixture()
                fixture.completed()
                fixture.event("run-stopped", reason="operator-stop")
                change(fixture)
                fixture.save(renumber=name in {"duplicate-reserve", "after-stop"})
                self.rejected(fixture)

    def test_unknown_suffix_rejects_after_rehash_and_recount(self):
        fixture = self.fixture()
        fixture.event("attempt-reserved")
        fixture.event("attempt-reserved", task=1)
        fixture.save()
        self.rejected(fixture)

    def test_saved_summary_mutations_reject(self):
        for field, value in (
            ("state", "finished"),
            ("stopReason", "complete"),
            ("journalHead", "a" * 64),
            ("lastClockNs", NANO),
            ("planDigest", "b" * 64),
        ):
            with self.subTest(field=field):
                fixture = self.fixture()
                fixture.completed()
                fixture.save()
                fixture.run[field] = value
                (fixture.folder / "run.json").write_bytes(canonical(fixture.run))
                self.rejected(fixture)
        fixture = self.fixture()
        fixture.completed()
        fixture.save()
        fixture.run["counts"]["knownInputTokens"] = 0
        (fixture.folder / "run.json").write_bytes(canonical(fixture.run))
        self.rejected(fixture)

    def test_plan_policy_and_type_mutations_reject_after_rebinding(self):
        changes = {
            "context-policy": lambda p: p.update(contextPolicy="sequential-history/v1"),
            "retry-policy": lambda p: p.update(retryPolicy="unbounded/v1"),
            "clock-policy": lambda p: p.update(
                clockPolicy="same-host-boot-monotonic/v1"
            ),
            "boolean-cap": lambda p: p["caps"].update(dispatches=True),
            "negative-cap": lambda p: p["caps"].update(questions=-1),
            "duplicate-question": lambda p: p["tasks"][0].update(
                questionIds=["supported", "supported"]
            ),
            "duplicate-coordinate": lambda p: p["tasks"][1].update(
                caseId=p["tasks"][0]["caseId"]
            ),
            "extra-field": lambda p: p.update(unplanned=True),
            "credential-url": lambda p: p["arms"][0].update(
                endpoint="https://user:DO_NOT_PRINT@example.invalid/"
            ),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                fixture = self.fixture()
                change(fixture.plan)
                fixture.bind_plan()
                fixture.save()
                self.rejected(fixture, "plan")


if __name__ == "__main__":
    unittest.main()
