"""Evaluate frozen authored safety probes without inference or output repair."""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from text_span_normalization import (
    DEFAULT_RULE_IDS,
    RULESET_VERSION,
    TextSpan,
    normalize_span,
)

ROOT = Path(__file__).resolve().parents[1]


def evaluate():
    fixture = ROOT / "fixtures/providers/quote-rules-new-cases-v1.json"
    raw_fixture = fixture.read_bytes()
    cases = json.loads(raw_fixture)["cases"]
    rows = []
    for case in cases:
        outcome = normalize_span(
            case["source"],
            TextSpan(**case["raw"]),
            coordinate_system=case["coordinate_system"],
            target=case["target"],
        )
        positive = case["expected_action"] == "apply"
        changed = outcome.status == "applied"
        correct_positive = changed and outcome.derived.value == case["expected_value"]
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "expected_action": case["expected_action"],
                "expected_value": case["expected_value"],
                "result": asdict(outcome),
                "exact_expectation_met": correct_positive if positive else not changed,
                "false_correction": changed and (not positive or not correct_positive),
                "positive_abstention": positive and not changed,
            }
        )
    return {
        "schema": "normlab.quote-rule-validation-report/v1",
        "ruleset_version": RULESET_VERSION,
        "default_enabled_rules": DEFAULT_RULE_IDS,
        "rule_source_sha256": hashlib.sha256(
            (ROOT / "scripts/text_span_normalization.py").read_bytes()
        ).hexdigest(),
        "fixture_sha256": hashlib.sha256(raw_fixture).hexdigest(),
        "http_attempts": 0,
        "case_count": len(rows),
        "exact_expectations_met": sum(row["exact_expectation_met"] for row in rows),
        "false_corrections": sum(row["false_correction"] for row in rows),
        "positive_abstentions": sum(row["positive_abstention"] for row in rows),
        "rows": rows,
        "scope": "Authored probes informed by known rule design; not blind gold, independent incidents or production error-rate estimate. ASCII semantic ambiguity cannot be resolved by quote counting alone.",
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
