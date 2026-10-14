"""Common denominators, exclusions and runtime context compatibility regressions."""

import copy
import unittest

import test_offline_runtime_pairing as fixtures
import test_offline_runtime_reference as references
from execution_mock import run_mock
from execution_resume import continue_mock
from execution_test_support import ExecutionCase, canonical
from offline_bundle import identity
from runtime_archive_export import export_runtime_archive
from runtime_archive_reader import read_archive
from runtime_compare import compare, verify_comparison
from runtime_reference import reference
from runtime_score import score


class CompareTests(ExecutionCase):
    input = fixtures.PairingTests.input
    output = fixtures.PairingTests.output
    script = fixtures.PairingTests.script
    failure = staticmethod(fixtures.PairingTests.failure)
    paused = fixtures.PairingTests.paused
    request = fixtures.PairingTests.request
    orphan = fixtures.PairingTests.orphan
    archive = fixtures.PairingTests.archive
    view = fixtures.PairingTests.view

    def capture(
        self,
        name,
        *,
        model="mock-model",
        provider="synthetic-provider",
        answer=0.92,
        tasks=1,
        rename=False,
        protocol="typesafe-systemone/v1",
        configure=None,
    ):
        fixture = self.input(tasks=tasks, protocol=protocol)
        if configure is not None:
            configure(fixture)
        arm = fixture.plan["arms"][0]
        arm["provider"] = provider
        arm["model"] = model
        for task in fixture.plan["tasks"]:
            if rename:
                task["key"] = "renamed-" + task["key"]
            request = fixture.value(task["request"])
            request["body"]["model"] = model
            task["request"] = fixture.put(request, ordered=True)
            context = fixture.value(task["context"])
            context["requestDigest"] = task["request"]["sha256"]
            task["context"] = fixture.put(context)
        (fixture.folder / "plan.json").write_bytes(canonical(fixture.plan))
        script = self.script(fixture)
        questions = {t["key"]: set(t["questionIds"]) for t in fixture.plan["tasks"]}
        for entry in script["tasks"]:
            entry["attempts"][0]["model"] = model
            values = entry["attempts"][0]["answers"]
            entry["attempts"][0]["answers"] = [
                v for v in values if v["questionId"] in questions[entry["key"]]
            ]
            for value in entry["attempts"][0]["answers"]:
                if value["questionId"] == "supported":
                    value["value"] = answer
        runtime = self.output(name + "-runtime")
        run_mock(fixture.folder, runtime, script)
        target = self.output(name + "-archive")
        export_runtime_archive(runtime, target)
        archive = read_archive(target)
        labels = references.source(archive)
        labels["expected"] = [
            v for v in labels["expected"] if v["questionId"] in questions[v["taskKey"]]
        ]
        saved = score(archive, reference(archive, canonical(labels)))
        return target, archive, saved

    def test_self_compare_partial_retains_unevaluated_and_task_counts(self):
        _, _, archive, saved = self.view()
        result = compare(archive, saved, archive, saved)
        self.assertEqual(result["summary"]["unionQuestions"], 6)
        self.assertEqual(
            result["summary"]["states"], {"evaluated": 3, "not-evaluated": 3}
        )
        self.assertEqual(result["summary"]["final"]["denominator"], 3)
        self.assertEqual(result["baseline"]["summary"]["plannedTasks"], 2)
        self.assertEqual(result["baseline"]["runtimeCounts"]["attempts"], 1)
        self.assertTrue(result["sameCapture"])
        self.assertEqual(result["executionIndependence"], "not-established")
        self.assertEqual(
            verify_comparison(archive, saved, archive, saved, result), result
        )

    def test_regressions_and_rescues_use_same_paired_question_denominator(self):
        _, a, av = self.capture("yes", answer=0.92)
        _, b, bv = self.capture("no", answer=0.01, rename=True)
        result = compare(a, av, b, bv)
        self.assertEqual(
            result["summary"]["finalTransitions"], {"regression": 1, "unchanged": 2}
        )
        self.assertEqual(result["summary"]["final"]["denominator"], 3)
        self.assertEqual(result["summary"]["final"]["delta"], -1 / 3)
        reverse = compare(b, bv, a, av)
        self.assertEqual(
            reverse["summary"]["finalTransitions"], {"rescue": 1, "unchanged": 2}
        )

    def test_continuation_completed_is_operational_recovery_not_semantic_rescue(self):
        runtime, _, before, first = self.view("after-response", tasks=1)
        continue_mock(
            runtime,
            self.request(
                runtime, action="adopt-saved-outcome", outcome=self.orphan(runtime)
            ),
        )
        target = self.output("adopted-compare")
        export_runtime_archive(runtime, target)
        after = read_archive(target)
        second = score(after, reference(after, canonical(references.source(after))))
        result = compare(before, first, after, second)
        self.assertEqual(result["summary"]["final"]["denominator"], 0)
        self.assertIsNone(result["summary"]["final"]["delta"])
        self.assertEqual(result["summary"]["finalTransitions"], {})
        self.assertEqual(
            result["baseline"]["summary"]["statusCounts"], {"unknown-outcome": 1}
        )
        self.assertEqual(
            result["candidate"]["summary"]["statusCounts"], {"completed": 1}
        )
        self.assertEqual(result["operational"]["completionDelta"], 1)
        self.assertEqual(result["operational"]["baseline"]["attempts"], 1)
        self.assertEqual(result["operational"]["candidate"]["attempts"], 1)

    def test_unpaired_questions_and_reference_change_are_visible(self):
        _, a, av = self.capture("one", tasks=1)
        _, b, bv = self.capture("two", tasks=2)
        result = compare(a, av, b, bv)
        self.assertEqual(
            result["summary"]["states"], {"candidate-only": 3, "evaluated": 3}
        )
        labels = references.source(a)
        labels["expected"][0]["label"] = "no"
        changed = score(a, reference(a, canonical(labels)))
        result = compare(a, av, a, changed)
        self.assertEqual(
            result["summary"]["states"], {"evaluated": 2, "incompatible": 1}
        )
        self.assertIn(
            "reference-selection-or-expectation-differs",
            result["rows"][0]["reasons"]
            + result["rows"][1]["reasons"]
            + result["rows"][2]["reasons"],
        )

    def test_explicit_logical_same_protocol_model_change_preserves_strict_exclusions(
        self,
    ):
        _, a, av = self.capture("model-a")
        _, b, bv = self.capture(
            "model-b", model="other-model", provider="other-provider"
        )
        strict = compare(a, av, b, bv, vary=["provider"])
        self.assertEqual(strict["summary"]["states"], {"incompatible": 3})
        logical = compare(a, av, b, bv, context="same-protocol-body", vary=["provider"])
        self.assertEqual(logical["summary"]["states"], {"evaluated": 3})
        undeclared = compare(a, av, b, bv, context="same-protocol-body")
        self.assertEqual(undeclared["summary"]["states"], {"incompatible": 3})

    def test_rehashed_derived_metrics_status_policy_and_source_bindings_reject(self):
        _, _, archive, saved = self.view()
        original = compare(archive, saved, archive, saved)
        for field in ["metrics", "status", "policy", "source", "flags"]:
            result = copy.deepcopy(original)
            if field == "metrics":
                result["summary"]["final"]["baselinePassed"] += 1
            elif field == "status":
                result["rows"][0]["state"] = "incompatible"
            elif field == "policy":
                result["policy"]["unit"] = "whole-case"
            elif field == "source":
                result["baseline"]["captureRevisionId"] = "foreign"
            else:
                result["semanticQualityEvidence"] = True
            result["comparisonId"] = identity(
                "runtime-comparison",
                {k: v for k, v in result.items() if k != "comparisonId"},
            )
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify_comparison(archive, saved, archive, saved, result)

    def test_protocol_and_prompt_changes_never_gain_implicit_compatibility(self):
        _, a, av = self.capture("wire-a")
        _, b, bv = self.capture("wire-b", protocol="openai-decisions/v1")
        result = compare(a, av, b, bv, context="same-protocol-body", vary=["provider"])
        self.assertEqual(result["summary"]["states"], {"incompatible": 3})
        self.assertTrue(
            all("wire-protocol-differs" in r["reasons"] for r in result["rows"])
        )

        def prompt(fixture):
            fixture.plan["pins"]["prompt"] = fixture.put("Changed prompt")

        _, c, cv = self.capture("prompt-change", configure=prompt)
        result = compare(a, av, c, cv, vary=["strategy"])
        self.assertIn("prompt-pins-differ", result["globalIncompatibilities"])
        self.assertEqual(result["summary"]["final"]["denominator"], 0)

    def test_changed_execution_caps_disclose_conditions_and_suppress_operational_delta(
        self,
    ):
        _, a, av = self.capture("caps-a")

        def caps(fixture):
            fixture.plan["caps"]["dispatches"] += 1

        _, b, bv = self.capture("caps-b", configure=caps)
        result = compare(a, av, b, bv)
        self.assertEqual(result["summary"]["final"]["denominator"], 3)
        self.assertFalse(result["executionConditionsMatch"])
        self.assertIsNone(result["operational"]["completionDelta"])
        self.assertIn(
            "execution-conditions-differ",
            result["operational"]["deltaUnavailableReasons"],
        )

    def test_disjoint_question_batches_never_share_operational_denominators(self):
        def subset(ids):
            def configure(fixture):
                task = fixture.plan["tasks"][0]
                task["questionIds"] = ids
                request = fixture.value(task["request"])
                request["body"]["questions"] = {
                    k: v for k, v in request["body"]["questions"].items() if k in ids
                }
                task["request"] = fixture.put(request, ordered=True)
                context = fixture.value(task["context"])
                context["questionIds"] = ids
                context["requestDigest"] = task["request"]["sha256"]
                task["context"] = fixture.put(context)

            return configure

        _, a, av = self.capture("subset-a", configure=subset(["supported"]))
        _, b, bv = self.capture("subset-b", configure=subset(["team", "urgency"]))
        result = compare(a, av, b, bv)
        self.assertEqual(result["summary"]["matchedQuestions"], 0)
        self.assertFalse(result["operational"]["samePlannedTaskTargets"])
        self.assertIsNone(result["operational"]["completionDelta"])
        self.assertIn(
            "planned-task-targets-differ",
            result["operational"]["deltaUnavailableReasons"],
        )

    def test_declared_provider_variation_does_not_hide_arm_limits(self):
        _, a, av = self.capture("arm-limits-a")
        for field in ("timeoutNs", "requestCaps"):

            def configure(fixture):
                arm = fixture.plan["arms"][0]
                if field == "timeoutNs":
                    arm[field] += 1000
                else:
                    arm[field]["inputTokens"] += 1

            _, b, bv = self.capture("arm-" + field, configure=configure)
            result = compare(a, av, b, bv, vary=["provider"])
            with self.subTest(field=field):
                self.assertEqual(result["summary"]["final"]["denominator"], 3)
                self.assertFalse(result["executionConditionsMatch"])
                self.assertIsNone(result["operational"]["completionDelta"])
                self.assertIn(
                    "execution-conditions-differ",
                    result["operational"]["deltaUnavailableReasons"],
                )


if __name__ == "__main__":
    unittest.main()
