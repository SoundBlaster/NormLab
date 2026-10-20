"""Shared bounded semantic input validation; no SDK, credentials or network."""

import json

from provider_config import require


def payload(value):
    require(
        isinstance(value, dict) and set(value) == {"state", "questions"},
        "Smoke input requires state and questions",
    )
    require(
        isinstance(value["state"], dict)
        and len(
            json.dumps(value["state"], ensure_ascii=False, allow_nan=False).encode()
        )
        <= 32768,
        "Bounded dictionary state required",
    )
    questions = value["questions"]
    require(
        isinstance(questions, dict) and 0 < len(questions) <= 3,
        "One to three questions required",
    )
    for name, question in questions.items():
        require(
            isinstance(name, str)
            and name.isascii()
            and name.isidentifier()
            and len(name) <= 80,
            "Question ID contract",
        )
        require(
            isinstance(question, dict)
            and set(question) == {"type", "instructions", "criteria"},
            "Question fields",
        )
        kind = question["type"]
        require(kind in ("noul", "choice", "score"), "Question primitive")
        require(
            isinstance(question["instructions"], str)
            and 0 < len(question["instructions"].strip()) <= 4096,
            "Question instruction limits",
        )
        criteria = question["criteria"]
        if kind == "score":
            require(
                isinstance(criteria, list)
                and 2 <= len(criteria) <= 10
                and len(set(criteria)) == len(criteria),
                "Score rubric",
            )
            descriptions = criteria
        else:
            require(
                isinstance(criteria, dict)
                and (
                    set(criteria) == {"true", "false"}
                    if kind == "noul"
                    else 2 <= len(criteria) <= 255
                ),
                "Named criteria",
            )
            require(
                all(isinstance(k, str) and 0 < len(k) <= 128 for k in criteria),
                "Criterion label limits",
            )
            descriptions = criteria.values()
        require(
            all(
                isinstance(x, str) and 0 < len(x.strip()) <= 2048 for x in descriptions
            ),
            "Criterion description limits",
        )
    return value
