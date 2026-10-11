"""Native provider wire normalization for SDK-free Stage 1 replay."""

import json

from harness import require
from plan_stage1_comparison import LABELS
from stage1_wire_v2 import normalize as historical_normalize


def decode(raw):
    def unique(pairs):
        require(len(dict(pairs)) == len(pairs), "Duplicate JSON keys")
        return dict(pairs)

    def invalid_constant(value):
        raise ValueError("Non-finite JSON")

    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)


def normalize(api_format, response):
    require(set(response) == {"body", "requestId"}, "Public response envelope")
    body = response["body"]
    require(isinstance(body, dict), "Response object")
    common = {
        "model": body.get("model"),
        "id": response["requestId"],
        "usage": body.get("usage"),
    }
    if api_format == "openai-responses":
        require(body.get("id") == response["requestId"], "Responses ID binding")
        return historical_normalize("luna-low-coreinfra", {**body, **common})
    if api_format == "typesafe-systemone":
        answers = body.get("answers")
        require(
            isinstance(answers, dict) and set(answers) == {"classification"},
            "TypeSafe answer coverage",
        )
        answer = answers["classification"]
    else:
        require(api_format == "openai-decisions", "Known API format")
        require(isinstance(body.get("usage"), dict), "Decisions usage required")
        answers = body.get("answers")
        require(
            isinstance(answers, list) and len(answers) == 1, "Decisions answer coverage"
        )
        answer = answers[0]
        require(
            isinstance(answer, dict) and answer.get("name") == "classification",
            "Decisions question binding",
        )
        entries = answer.get("probabilities")
        require(
            isinstance(entries, list) and len(entries) == len(LABELS),
            "Decisions distribution",
        )
        require(
            all(
                isinstance(x, dict) and isinstance(x.get("value"), str) for x in entries
            ),
            "Decisions labels",
        )
        values = [x["value"] for x in entries]
        require(len(set(values)) == len(values), "Duplicate Decisions labels")
        answer = {
            **answer,
            "probabilities": {x["value"]: x.get("probability") for x in entries},
        }
    return historical_normalize(
        "jev-coreinfra", {**common, "answers": {"overall": answer}}
    )


def public_response(api_format, body, request_id):
    # Keep the replayable fields, never encrypted reasoning or HTTP headers.
    selected = {
        k: body[k]
        for k in ("model", "usage", "answers", "id", "status", "output")
        if k in body
    }
    if api_format == "openai-responses" and isinstance(selected.get("output"), list):
        selected["output"] = [
            {"type": "reasoning"}
            if isinstance(x, dict) and x.get("type") == "reasoning"
            else x
            for x in selected["output"]
        ]
    return {"body": selected, "requestId": request_id}


def mock_response(api_format, label, model, request_id):
    """Synthetic transport response, not a model prediction or reviewer label."""
    usage = {
        "input_tokens": 100,
        "output_tokens": 10,
        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 0},
        "total_tokens": 110,
    }
    probabilities = {x: float(x == label) for x in LABELS}
    answer = {
        "type": "choice",
        "choice": label,
        "confidence": 1.0,
        "probabilities": probabilities,
    }
    common = {"model": model, "usage": usage}
    if api_format == "typesafe-systemone":
        return {**common, "answers": {"classification": answer}}
    if api_format == "openai-decisions":
        return {
            **common,
            "answers": [
                {
                    **answer,
                    "name": "classification",
                    "probabilities": [
                        {"value": x, "probability": p} for x, p in probabilities.items()
                    ],
                }
            ],
        }
    return {
        **common,
        "id": request_id,
        "status": "completed",
        "output": [
            {
                "type": "message",
                "status": "completed",
                "content": [
                    {"type": "output_text", "text": json.dumps({"overall": label})}
                ],
            }
        ],
    }
