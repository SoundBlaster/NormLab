"""Offline checks for the small Clairic diagnostic; never contact the provider."""

import copy
import unittest

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


if __name__ == "__main__":
    unittest.main()
