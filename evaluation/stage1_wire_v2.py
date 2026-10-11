"""Stage 1 wire v2 accepts rounded choice probabilities within 1e-6."""

import json
import math

from harness import require
from plan_stage1_comparison import LABELS, canonical


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def normalize(arm, response):
    """Parse representative public wire bodies; this is not SDK interoperability."""
    require(isinstance(response, dict), "Response object required")
    model = response.get("model")
    require(
        isinstance(model, str) and 0 < len(model) <= 128 and model.isprintable(),
        "Returned model required",
    )
    request_id = response.get("id")
    require(
        isinstance(request_id, str)
        and 0 < len(request_id) <= 128
        and request_id.isascii()
        and all(33 <= ord(c) <= 126 for c in request_id),
        "Fixture request ID required",
    )
    if arm == "luna-low-coreinfra":
        require(response.get("status") == "completed", "Incomplete Responses output")
        output = response.get("output")
        require(isinstance(output, list), "Responses output required")
        require(
            all(
                isinstance(x, dict) and x.get("type") in ("message", "reasoning")
                for x in output
            ),
            "Unsupported Responses output",
        )
        messages = [x for x in output if x["type"] == "message"]
        require(len(messages) == 1, "Exactly one Responses message required")
        message = messages[0]
        content = message.get("content")
        require(
            message.get("status") == "completed"
            and isinstance(content, list)
            and len(content) == 1
            and isinstance(content[0], dict)
            and content[0].get("type") == "output_text",
            "Completed output_text required",
        )

        def unique(pairs):
            require(len(dict(pairs)) == len(pairs), "Duplicate JSON keys")
            return dict(pairs)

        verdict = json.loads(content[0]["text"], object_pairs_hook=unique)
        require(
            isinstance(verdict, dict) and set(verdict) == {"overall"}, "Verdict shape"
        )
        label = verdict["overall"]
        confidence = None
        probabilities = None
    else:
        require(arm in ("jev-coreinfra", "luna-decisions-proxyapi"), "Unknown arm")
        answers = response.get("answers")
        require(
            isinstance(answers, dict) and set(answers) == {"overall"},
            "Question coverage",
        )
        answer = answers["overall"]
        require(
            isinstance(answer, dict) and answer.get("type") == "choice",
            "Choice required",
        )
        label = answer.get("choice")
        confidence = answer.get("confidence")
        probabilities = answer.get("probabilities")
        require(finite(confidence) and 0 <= confidence <= 1, "Confidence range")
        require(
            isinstance(probabilities, dict) and set(probabilities) == set(LABELS),
            "Choice labels",
        )
        require(
            all(finite(v) and 0 <= v <= 1 for v in probabilities.values()),
            "Probability range",
        )
        require(abs(sum(probabilities.values()) - 1) <= 1e-6, "Normalized distribution")
        require(
            label in LABELS
            and probabilities[label] >= max(probabilities.values()) - 1e-6,
            "Choice maximum",
        )
    require(label in LABELS, "Unknown verdict")
    usage = response.get("usage")
    require(
        usage is None
        or (
            isinstance(usage, dict)
            and all(
                type(usage.get(k)) is int and usage[k] >= 0
                for k in ("input_tokens", "output_tokens")
            )
        ),
        "Usage contract",
    )
    return {
        "label": label,
        "returnedModel": model,
        "requestId": request_id,
        "confidence": confidence,
        "probabilities": probabilities,
        "usage": None
        if usage is None
        else {k: usage[k] for k in ("input_tokens", "output_tokens")},
        "cost": None,
    }


def wire_response(
    arm, label, model, request_id, usage=None, confidence=None, probabilities=None
):
    """Public mock wire body, including a synthetic ID (not a live request ID)."""
    base = {"model": model, "id": request_id, "usage": usage}
    if arm == "luna-low-coreinfra":
        return {
            **base,
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "status": "completed",
                    "content": [
                        {"type": "output_text", "text": canonical({"overall": label})}
                    ],
                }
            ],
        }
    return {
        **base,
        "answers": {
            "overall": {
                "type": "choice",
                "choice": label,
                "confidence": confidence,
                "probabilities": probabilities,
            }
        },
    }
