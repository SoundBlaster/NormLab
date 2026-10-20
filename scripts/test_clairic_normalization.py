"""Offline boundary-rule checks; fixtures are known development data, not gold."""

import hashlib
import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

import clairic_smoke as smoke
from text_span_normalization import TextSpan, normalize_span

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = (
    ("ru-unicode", "clairic-ru-unicode-smoke-2026-10-20.json"),
    *(
        ("ablation-" + name, f"clairic-ablation-{name}-2026-10-20.json")
        for name in ("original", "unicode-clean", "ascii-quotes", "both")
    ),
    *(
        ("linebreak-" + name, f"clairic-linebreak-{name}-2026-10-20.json")
        for name in ("original", "sentences")
    ),
    ("quote-inner", "clairic-quote-inner-2026-10-20.json"),
)


def replay_known_captures():
    """Separate raw/derived development counts; never rewrite provider captures."""
    rows = []
    for case_name, filename in CAPTURES:
        path = ROOT / "docs/evidence" / filename
        before = path.read_bytes()
        capture = json.loads(before)
        case = smoke.load_case(case_name)
        assert capture["fixture_sha256"] == case["fixture_sha256"]
        records = {}
        for name, expected in case["expected"].items():
            answer = capture["answers"][name]
            if answer["value"] is None:
                records[name] = {
                    "status": "null_passthrough",
                    "derived_matches_expected": expected is None,
                }
                continue
            raw = TextSpan(answer["value"], *answer["span"])
            outcome = normalize_span(
                case["state"],
                raw,
                coordinate_system="code_points",
                target="inner_content",
            )
            span = outcome.derived
            records[name] = {
                "status": outcome.status,
                "rules": outcome.applied_rules,
                "raw_value": raw.value,
                "raw_span": [raw.start, raw.end],
                "derived_value": span.value if span else None,
                "derived_span": [span.start, span.end] if span else None,
                "derived_matches_expected": span is not None and span.value == expected,
                "derived_anchor_matches_expected": span is not None
                and [span.start, span.end] == case["expected_codepoint_spans"][name],
            }
        assert path.read_bytes() == before
        rows.append(
            {
                "case": case_name,
                "capture": filename,
                "capture_sha256": hashlib.sha256(before).hexdigest(),
                "raw_value_matches": sum(c["pass"] for c in capture["checks"].values()),
                "derived_value_matches": sum(
                    c["derived_matches_expected"] for c in records.values()
                ),
                "derived_anchor_matches": sum(
                    c.get("derived_anchor_matches_expected", False)
                    for c in records.values()
                ),
                "fields": records,
            }
        )
    return rows


class QuoteNormalizationTests(unittest.TestCase):
    def normalize(
        self,
        source,
        value,
        *,
        occurrence=0,
        target="inner_content",
        coordinate_system="code_points",
        rules=None,
    ):
        start = source.index(value) if occurrence == 0 else source.rindex(value)
        kwargs = {} if rules is None else {"enabled_rules": rules}
        return normalize_span(
            source,
            TextSpan(value, start, start + len(value)),
            coordinate_system=coordinate_system,
            target=target,
            **kwargs,
        )

    def test_guillemet(self):
        result = self.normalize("🙂 «Не оплачивал!»", "Не оплачивал!»")
        self.assertEqual(result.status, "applied")
        self.assertEqual(result.derived.value, "Не оплачивал!")
        self.assertEqual(result.raw.value, "Не оплачивал!»")
        self.assertEqual(result.supporting_quote_span, (2, 17))

    def test_ascii_quote(self):
        result = self.normalize('He said "No payment".', 'No payment"')
        self.assertEqual(result.status, "applied")
        self.assertEqual(result.derived.value, "No payment")

    def test_one_character_body(self):
        self.assertEqual(self.normalize("«x»", "x»").derived.value, "x")

    def test_single_closer_is_unchanged(self):
        self.assertEqual(self.normalize("«»", "»").status, "unchanged")

    def test_full_quote_is_not_stripped(self):
        self.assertEqual(self.normalize("«x»", "«x»").status, "unchanged")

    def test_whole_target_does_not_apply_inner_rule(self):
        self.assertEqual(
            self.normalize("«x»", "x»", target="whole_quote").status, "unchanged"
        )

    def test_inches_are_not_repaired(self):
        self.assertEqual(self.normalize('Screen 12"', '12"').status, "review")

    def test_two_inches_do_not_form_a_quote_pair(self):
        self.assertEqual(self.normalize('12" and 24"', ' and 24"').status, "review")

    def test_literal_closer_without_opening(self):
        self.assertEqual(self.normalize("literal x»", "x»").status, "review")

    def test_nested_and_mixed_quotes_abstain(self):
        for source, value in [("«outer «x»»", "x»"), ('«x"»', 'x"»')]:
            with self.subTest(source=source):
                self.assertEqual(self.normalize(source, value).status, "review")

    def test_unbalanced_source_abstains(self):
        self.assertEqual(self.normalize("«x» and «open", "x»").status, "review")

    def test_escaped_ascii_quote_abstains(self):
        self.assertEqual(self.normalize('"x" and \\"', 'x"').status, "review")

    def test_empty_whitespace_content_abstains(self):
        self.assertEqual(self.normalize("« »", " »").status, "review")

    def test_disabled_rules(self):
        self.assertEqual(self.normalize("«x»", "x»", rules=()).status, "unchanged")

    def test_coordinates_must_be_explicit(self):
        self.assertEqual(
            self.normalize("🙂 «x»", "x»", coordinate_system="utf16_code_units").status,
            "review",
        )

    def test_source_mismatch(self):
        result = normalize_span(
            "«x»",
            TextSpan("y»", 1, 3),
            coordinate_system="code_points",
            target="inner_content",
        )
        self.assertEqual(result.status, "review")
        self.assertIsNone(result.derived)

    def test_invalid_spans(self):
        for start, end in [(-1, 2), (3, 1), (1, 99), (True, 3)]:
            with self.subTest(start=start):
                result = normalize_span(
                    "«x»",
                    TextSpan("x»", start, end),
                    coordinate_system="code_points",
                    target="inner_content",
                )
                self.assertEqual(result.status, "review")

    def test_repeated_occurrence_does_not_move(self):
        result = self.normalize("«x» then «x»", "x»", occurrence=1)
        self.assertEqual(result.derived, TextSpan("x", 10, 11))

    def test_unicode_and_negation_preserved(self):
        result = self.normalize("🙂 «Не кафе́»", "Не кафе́»")
        self.assertEqual(result.derived.value, "Не кафе́")

    def test_idempotent_and_frozen(self):
        result = self.normalize("«x»", "x»")
        again = normalize_span(
            "«x»",
            result.derived,
            coordinate_system="code_points",
            target="inner_content",
        )
        self.assertEqual(again.status, "unchanged")
        self.assertEqual(again.derived, result.derived)
        with self.assertRaises(FrozenInstanceError):
            result.raw.value = "changed"

    def test_unknown_policy_or_rule_rejected(self):
        for kwargs in ({"target": "typo"}, {"enabled_rules": ("typo",)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                normalize_span(
                    "«x»",
                    TextSpan("x»", 1, 3),
                    coordinate_system="code_points",
                    **({"target": "inner_content"} | kwargs),
                )

    def test_existing_capture_replay(self):
        rows = replay_known_captures()
        self.assertEqual(len(rows), 8)
        for row in rows:
            with self.subTest(case=row["case"]):
                self.assertEqual(row["raw_value_matches"], 2)
                self.assertEqual(row["derived_value_matches"], 6)
                self.assertEqual(row["derived_anchor_matches"], 5)
                self.assertEqual(
                    sum(r["status"] == "applied" for r in row["fields"].values()), 4
                )


if __name__ == "__main__":
    unittest.main()
