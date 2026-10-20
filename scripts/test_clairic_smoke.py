"""Offline checks for the small Clairic diagnostic; never contact the provider."""

import copy
import json
import unittest
from pathlib import Path

import clairic_smoke as smoke


class ClairicSmokeTests(unittest.TestCase):
    def setUp(self):
        self.case = smoke.load_case("ru-unicode")

    def response(self, system="code_points"):
        answers = {
            key: {"type": "text", "value": value}
            for key, value in self.case["expected"].items()
        }
        template = smoke.anchor_diagnostics(self.case, answers, {})
        for key, info in template["fields"].items():
            answers[key]["span"] = info["expected_spans"][system]
        return {"model": "clairic", "answers": answers, "truncated": False}

    def test_codepoint_observation(self):
        report = smoke.summarize(self.response(), self.case)
        self.assertTrue(report["pass"])
        self.assertEqual(
            report["anchor_diagnostics"]["consistent_candidates"], ["code_points"]
        )

    def test_utf16_observation(self):
        report = smoke.summarize(self.response("utf16_code_units"), self.case)
        self.assertTrue(report["pass"])
        self.assertEqual(
            report["anchor_diagnostics"]["consistent_candidates"], ["utf16_code_units"]
        )

    def test_utf8_observation(self):
        report = smoke.summarize(self.response("utf8_bytes"), self.case)
        self.assertTrue(report["pass"])
        self.assertEqual(
            report["anchor_diagnostics"]["consistent_candidates"], ["utf8_bytes"]
        )

    def test_repeated_quote_wrong_occurrence(self):
        result = self.response()
        result["answers"]["viktor_statement"]["span"] = result["answers"][
            "boris_statement"
        ]["span"]
        report = smoke.summarize(result, self.case)
        self.assertTrue(all(item["pass"] for item in report["checks"].values()))
        self.assertFalse(report["pass"])

    def test_negation_is_preserved(self):
        result = self.response()
        result["answers"]["anna_statement"]["value"] = "Я оплачивала парковку"
        self.assertFalse(smoke.summarize(result, self.case)["pass"])

    def test_no_combining_mark_loss(self):
        result = self.response()
        result["answers"]["unicode_marker"]["value"] = "кафе"
        self.assertFalse(smoke.summarize(result, self.case)["pass"])

    def test_null_guess_is_not_a_fact(self):
        result = self.response()
        result["answers"]["receipt_number"]["guess"] = "09:00"
        self.assertTrue(smoke.summarize(result, self.case)["pass"])

    def test_missing_answer_is_not_null(self):
        result = self.response()
        del result["answers"]["receipt_number"]
        self.assertFalse(smoke.summarize(result, self.case)["pass"])

    def test_changed_source_basis(self):
        result = self.response()
        result["state_text"] = self.case["state"].replace("🙂", "")
        self.assertFalse(smoke.summarize(result, self.case)["pass"])

    def test_invalid_or_mixed_coordinates(self):
        for value in ([True, 66], [42], None, [-1, 66], [43, 67]):
            with self.subTest(value=value):
                result = self.response()
                result["answers"]["anna_statement"]["span"] = value
                self.assertFalse(smoke.summarize(result, self.case)["pass"])

    def test_truncation(self):
        result = self.response()
        result["truncated"] = True
        self.assertFalse(smoke.summarize(result, self.case)["pass"])

    def test_neutral_regression_and_envelope(self):
        case = smoke.load_case("neutral")
        result = {
            "truncated": False,
            "answers": {
                key: {"type": case["fields"][key]["type"], "value": value}
                for key, value in case["expected"].items()
            },
        }
        self.assertTrue(smoke.summarize({"success": True, "result": result})["pass"])
        missing = copy.deepcopy(result)
        del missing["answers"]["purchase_order"]
        self.assertFalse(smoke.summarize(missing)["pass"])

    def test_recorded_ru_live_replay(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "docs/evidence/clairic-ru-unicode-smoke-2026-10-20.json"
        )
        captured = json.loads(path.read_text())
        replayed = smoke.summarize(captured, self.case)
        self.assertEqual(replayed["checks"], captured["checks"])
        self.assertEqual(replayed["anchor_diagnostics"], captured["anchor_diagnostics"])
        self.assertEqual(captured["fixture_sha256"], self.case["fixture_sha256"])
        self.assertFalse(replayed["pass"])

    def test_ablation_controls_and_source_anchors(self):
        baseline = smoke.load_case("ablation-original")
        self.assertEqual(baseline["state"], self.case["state"])
        self.assertEqual(baseline["expected"], self.case["expected"])
        for name in smoke.ABLATION_CASES:
            with self.subTest(name=name):
                variant = smoke.load_case(name)
                self.assertEqual(variant["fields"], self.case["fields"])
                self.assertEqual(
                    variant["expected"]["anna_statement"],
                    self.case["expected"]["anna_statement"],
                )
                for key, (start, end) in variant["expected_codepoint_spans"].items():
                    self.assertEqual(
                        variant["state"][start:end], variant["expected"][key]
                    )

    def test_ablation_allows_coordinate_ambiguity_without_changing_old_scorer(self):
        self.case = smoke.load_case("ablation-unicode-clean")
        result = self.response()
        report = smoke.summarize(result, self.case)
        self.assertTrue(report["pass"])
        self.assertEqual(
            report["anchor_diagnostics"]["consistent_candidates"],
            ["code_points", "utf16_code_units"],
        )
        self.assertFalse(report["anchor_diagnostics"]["one_candidate_matches_all"])
        original_policy = dict(self.case, require_unique_coordinate_candidate=True)
        self.assertFalse(smoke.summarize(result, original_policy)["pass"])

    def test_recorded_ablation_replays(self):
        for name in ("original", "unicode-clean", "ascii-quotes", "both"):
            with self.subTest(name=name):
                path = (
                    Path(__file__).resolve().parents[1]
                    / f"docs/evidence/clairic-ablation-{name}-2026-10-20.json"
                )
                captured = json.loads(path.read_text())
                case = smoke.load_case("ablation-" + name)
                replayed = smoke.summarize(captured, case)
                self.assertEqual(captured["fixture_sha256"], case["fixture_sha256"])
                self.assertEqual(replayed["checks"], captured["checks"])
                self.assertEqual(
                    replayed["anchor_diagnostics"], captured["anchor_diagnostics"]
                )
                self.assertEqual(sum(c["pass"] for c in replayed["checks"].values()), 2)
                self.assertFalse(replayed["pass"])

    def test_linebreak_changes_only_four_separator_characters(self):
        original = smoke.load_case("linebreak-original")
        split = smoke.load_case("linebreak-sentences")
        self.assertEqual(original["state"], self.case["state"])
        self.assertEqual(split["state"], original["state"].replace(". ", ".\n"))
        self.assertEqual(split["state"].count("\n"), 4)
        self.assertEqual(len(split["state"]), len(original["state"]))
        self.assertEqual(split["fields"], original["fields"])
        self.assertEqual(split["expected"], original["expected"])
        self.assertEqual(
            split["expected_codepoint_spans"], original["expected_codepoint_spans"]
        )
        for key, (start, end) in split["expected_codepoint_spans"].items():
            self.assertEqual(split["state"][start:end], split["expected"][key])


if __name__ == "__main__":
    unittest.main()
