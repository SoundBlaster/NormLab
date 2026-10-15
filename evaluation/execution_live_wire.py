"""Versioned native public response projection and deterministic normalization."""

import math
from pathlib import Path

from execution_outcomes import answers
from execution_plan import Store, public
from execution_records import integer, text
from offline_bundle import MAX_BYTES, require, sha


def adapter_revision():
    return {
        "id": "normlab-native-wire",
        "revision": "v2-stage1",
        "sha256": sha(
            Path(__file__).read_bytes()
            + Path(__file__).with_name("execution_stage1_protocol.py").read_bytes()
        ),
    }


def contains_secret(value, secret, depth=0):
    require(depth <= 32, "Credential projection nesting cap")
    if isinstance(value, str):
        return secret in value
    if isinstance(value, dict):
        return any(
            contains_secret(k, secret, depth + 1)
            or contains_secret(v, secret, depth + 1)
            for k, v in value.items()
        )
    if isinstance(value, list):
        return any(contains_secret(v, secret, depth + 1) for v in value)
    return False


def projection(status, raw, request_id, secret):
    """Retain replay fields only; error/invalid bytes retain digest and byte count."""
    require(
        type(status) is int and 100 <= status <= 599 and len(raw) <= MAX_BYTES // 2,
        "Bounded HTTP reply",
    )
    payload = None
    try:
        if status == 200:
            body = Store.decode_json(raw)
            require(isinstance(body, dict), "Native response object")
            payload = {
                k: body[k]
                for k in (
                    "id",
                    "model",
                    "usage",
                    "status",
                    "answers",
                    "choices",
                    "output",
                )
                if k in body
            }
            if isinstance(payload.get("output"), list):
                payload["output"] = [
                    v
                    for v in payload["output"]
                    if not isinstance(v, dict) or v.get("type") != "reasoning"
                ]
            public(payload)
            require(
                not contains_secret(payload, secret),
                "Response contains credential",
            )
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        payload = None
    if (
        not isinstance(request_id, str)
        or not 0 < len(request_id) <= 128
        or not all(33 <= ord(c) <= 126 for c in request_id)
        or secret in request_id
    ):
        request_id = None
    return {
        "schema": "normlab.native-wire-response/v1",
        "httpStatus": status,
        "rawDigest": sha(raw),
        "rawBytes": len(raw),
        "body": payload,
        "requestId": request_id,
    }


def probability(value):
    require(
        type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
        "Probability range",
    )
    return value


def distribution(value, labels):
    require(isinstance(value, dict) and set(value) == set(labels), "Probability labels")
    result = {k: probability(v) for k, v in value.items()}
    require(
        abs(sum(result.values()) - 1) <= 1e-6, "Normalized probability distribution"
    )
    return result


def decision(answer, definition, *, openai):
    kind = definition["type"]
    expected = "predicate" if openai and kind == "noul" else kind
    require(
        isinstance(answer, dict) and answer.get("type") == expected,
        "Native answer type",
    )
    if kind == "noul":
        return probability(answer.get("probability" if openai else "noul"))
    probability(answer.get("confidence"))
    labels = definition["labels"]
    raw = answer.get("probabilities")
    if openai:
        require(
            isinstance(raw, list) and len(raw) == len(labels),
            "Decision probability entries",
        )
        mapped = {}
        for entry in raw:
            require(isinstance(entry, dict), "Decision entry object")
            key = entry.get("value")
            if kind == "score":
                require(
                    type(key) is int
                    and 0 <= key < len(labels)
                    and entry.get("label") == labels[key],
                    "Score index/rubric",
                )
                key = str(key)
            require(
                isinstance(key, str) and key not in mapped, "Unique probability entry"
            )
            mapped[key] = entry.get("probability")
        raw = mapped
    keys = labels if kind == "choice" else [str(i) for i in range(len(labels))]
    values = distribution(raw, keys)
    if kind == "choice":
        selected = answer.get("choice")
        require(
            isinstance(selected, str)
            and selected in values
            and values[selected] >= max(values.values()) - 1e-6,
            "Choice maximum",
        )
        return selected
    value = answer.get("score")
    require(
        type(value) in (int, float)
        and math.isfinite(value)
        and 0 <= value <= len(labels) - 1,
        "Score range",
    )
    require(
        abs(value - sum(int(k) * p for k, p in values.items())) <= 0.02,
        "Score expectation",
    )
    if not openai:
        require(
            answer.get("legend") == {str(i): label for i, label in enumerate(labels)},
            "Score legend",
        )
    return value


def normalized(response, task, arm, questions):
    """Return normalized answers; model/HTTP/usage policy is enforced by the kernel."""
    require(arm["adapter"] == adapter_revision(), "Installed native normalizer pin")
    body = response["body"]
    require(
        isinstance(body, dict) and response["httpStatus"] == 200,
        "Successful projected response",
    )
    protocol = arm["protocol"]
    if protocol in {
        "typesafe-systemone/v1",
        "openai-decisions/v1",
        "openai-decisions-input/v1",
    }:
        supplied = body.get("answers")
        openai = protocol in {"openai-decisions/v1", "openai-decisions-input/v1"}
        if openai:
            require(
                isinstance(supplied, list)
                and len(supplied) == len(task["questionIds"]),
                "Decision answer coverage",
            )
            mapped = {}
            for answer in supplied:
                require(
                    isinstance(answer, dict)
                    and isinstance(answer.get("name"), str)
                    and answer["name"] not in mapped,
                    "Unique decision name",
                )
                mapped[answer["name"]] = answer
            supplied = mapped
        require(
            isinstance(supplied, dict) and set(supplied) == set(task["questionIds"]),
            "Native question coverage",
        )
        result = [
            {
                "questionId": q,
                "type": questions[q]["type"],
                "value": decision(supplied[q], questions[q], openai=openai),
            }
            for q in task["questionIds"]
        ]
    else:
        if protocol == "openai-chat-completions/v1":
            choices = body.get("choices")
            require(
                isinstance(choices, list)
                and len(choices) == 1
                and isinstance(choices[0], dict)
                and choices[0].get("finish_reason") == "stop",
                "One completed chat choice",
            )
            message = choices[0].get("message")
            require(
                isinstance(message, dict) and not message.get("refusal"), "Chat refusal"
            )
            output = message.get("content")
        else:
            require(
                protocol in {"openai-responses/v1", "openai-responses-stage1/v1"}
                and body.get("status") == "completed",
                "Completed Responses state",
            )
            messages = body.get("output")
            require(
                isinstance(messages, list)
                and len(messages) == 1
                and isinstance(messages[0], dict)
                and messages[0].get("type") == "message"
                and messages[0].get("status") == "completed",
                "One completed Responses message",
            )
            content = messages[0].get("content")
            require(
                isinstance(content, list)
                and len(content) == 1
                and isinstance(content[0], dict)
                and content[0].get("type") == "output_text",
                "One output_text",
            )
            output = content[0].get("text")
        require(
            isinstance(output, str) and len(output.encode()) <= MAX_BYTES // 2,
            "Bounded structured output",
        )
        value = Store.decode_json(output.encode())
        if protocol == "openai-responses-stage1/v1":
            from execution_stage1_protocol import overall

            result = overall(value, task, questions)
        else:
            require(
                isinstance(value, dict) and set(value) == {"answers"},
                "Structured answer wrapper",
            )
            result = value["answers"]
    value = {
        "schema": "normlab.execution-answers/v1",
        "normalizer": arm["adapter"],
        "answers": result,
    }
    answers(value, task, arm, questions)
    return value


def metadata(response, protocol):
    body = response.get("body") or {}
    model = body.get("model")
    if model is not None:
        text(model)
    request_id = response["requestId"]
    if protocol in {
        "openai-responses/v1",
        "openai-chat-completions/v1",
        "openai-responses-stage1/v1",
    }:
        request_id = body.get("id")
        if request_id is not None:
            text(request_id)
    raw = body.get("usage")
    fields = (
        ("prompt_tokens", "completion_tokens")
        if protocol == "openai-chat-completions/v1"
        else ("input_tokens", "output_tokens")
    )
    usage = {}
    for key, field in zip(("inputTokens", "outputTokens"), fields):
        count = raw.get(field) if isinstance(raw, dict) else None
        if count is not None:
            integer(count)
        usage[key] = count
    return model, request_id, usage
