"""Offline positive/negative checks for the complete classification contract."""

import copy
import json
import sys
from pathlib import Path

from classification_v3 import validate


def main():
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=False)
    valid = {
        "results": {
            "fragment_1": {
                "status": "classified",
                "classifications": [
                    {
                        "predicate": "payment",
                        "stance": "unknown",
                        "valueText": "Результат оплаты неизвестен",
                    }
                ],
                "reason": "",
            }
        }
    }
    unsupported = {
        "results": {
            "fragment_1": {
                "status": "no-supported-predicate",
                "classifications": [],
                "reason": "Фрагмент содержит только приветствие",
            }
        }
    }
    missing = {"results": {}}
    unexpected = copy.deepcopy(valid)
    unexpected["results"]["fragment_2"] = unexpected["results"].pop("fragment_1")
    empty = copy.deepcopy(valid)
    empty["results"]["fragment_1"]["classifications"][0]["valueText"] = "  "
    padded_oversize = copy.deepcopy(valid)
    padded_oversize["results"]["fragment_1"]["classifications"][0]["valueText"] = (
        " " * 2048 + "x"
    )
    bounded = copy.deepcopy(valid)
    bounded["results"]["fragment_1"]["classifications"][0]["valueText"] = "x" * 2048
    duplicate = copy.deepcopy(valid)
    duplicate["results"]["fragment_1"]["classifications"] *= 2
    contradictory = copy.deepcopy(valid)
    contradictory["results"]["fragment_1"]["status"] = "no-supported-predicate"
    no_reason = copy.deepcopy(unsupported)
    no_reason["results"]["fragment_1"]["reason"] = ""
    unknown_predicate = copy.deepcopy(valid)
    unknown_predicate["results"]["fragment_1"]["classifications"][0]["predicate"] = (
        "invented"
    )
    records = []
    for name, payload, expected_valid in [
        ("explicit-unknown", valid, True),
        ("explicit-unsupported", unsupported, True),
        ("missing-id", missing, False),
        ("unexpected-id", unexpected, False),
        ("blank-value", empty, False),
        ("padded-oversize-value", padded_oversize, False),
        ("bounded-value", bounded, True),
        ("duplicate-predicate-stance", duplicate, False),
        ("unsupported-with-classification", contradictory, False),
        ("unsupported-without-reason", no_reason, False),
        ("unknown-predicate", unknown_predicate, False),
    ]:
        error = None
        try:
            validate(payload, ["fragment_1"], {"payment"})
            actual_valid = True
        except ValueError as exc:
            actual_valid = False
            error = str(exc)
        record = {
            "case": name,
            "input": payload,
            "expectedValid": expected_valid,
            "actualValid": actual_valid,
            "passed": actual_valid == expected_valid,
            "error": error,
        }
        records.append(record)
    (output / "report.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n"
    )
    (output / "checker.py.snapshot").write_bytes(Path(__file__).read_bytes())
    (output / "classifier.py.snapshot").write_bytes(
        Path(__file__).with_name("classification_v3.py").read_bytes()
    )
    print(
        f"{sum(record['passed'] for record in records)}/{len(records)} contract checks passed"
    )
    if not all(record["passed"] for record in records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
