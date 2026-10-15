"""Verifier manifest, turn records and offline probability routing replay."""

import json
import math

from harness import digest, identifier, require
from proxyapi_config import provider_metadata

SCHEMA = "normlab.verifier-experiment/v1"
CAPTURE_SCHEMA = "normlab.verifier-capture/v1"


def validate_manifest(manifest):
    require(
        isinstance(manifest, dict)
        and set(manifest)
        == {
            "schema",
            "experimentId",
            "provider",
            "tactic",
            "state",
            "questions",
            "budget",
            "policy",
        },
        "Verifier manifest contract",
    )
    require(
        manifest["schema"] == SCHEMA and identifier(manifest["experimentId"]),
        "Verifier experiment identity",
    )
    require(
        manifest["provider"] == provider_metadata() and manifest["tactic"] == "batch",
        "Only fixed ProxyAPI batch provider is supported",
    )
    state = manifest["state"]
    require(
        isinstance(state, dict)
        and set(state) == {"sourceText"}
        and isinstance(state["sourceText"], str)
        and 0 < len(state["sourceText"]) <= 32768,
        "Immutable source text contract",
    )
    questions = manifest["questions"]
    require(
        isinstance(questions, dict) and 0 < len(questions) <= 3,
        "Bounded question count",
    )
    for name, question in questions.items():
        require(
            identifier(name)
            and isinstance(question, dict)
            and set(question) == {"type", "instructions", "criteria"},
            "Question contract",
        )
        require(
            isinstance(question["instructions"], str)
            and 0 < len(question["instructions"].strip()) <= 4096,
            "Question instruction limits",
        )
        kind, criteria = question["type"], question["criteria"]
        require(kind in {"noul", "choice", "score"}, "Question primitive")
        if kind == "score":
            require(
                isinstance(criteria, list)
                and 2 <= len(criteria) <= 10
                and all(isinstance(c, str) for c in criteria)
                and len(set(criteria)) == len(criteria),
                "Score criteria",
            )
            descriptions = criteria
        else:
            require(isinstance(criteria, dict), "Named criteria")
            require(
                set(criteria) == {"true", "false"}
                if kind == "noul"
                else 2 <= len(criteria) <= 255 and all(identifier(k) for k in criteria),
                "Primitive criteria",
            )
            descriptions = criteria.values()
        require(
            all(
                isinstance(d, str) and 0 < len(d.strip()) <= 2048 for d in descriptions
            ),
            "Criteria descriptions",
        )
    require(
        manifest["budget"]
        == {"maxCalls": 1, "maxQuestions": 3, "transportTimeoutSeconds": 10},
        "One-call smoke budget required",
    )
    require(
        all(type(v) is int for v in manifest["budget"].values()),
        "Integer budget values",
    )
    policy = manifest["policy"]
    require(
        isinstance(policy, dict) and set(policy) == {"rejectAt", "acceptAt"},
        "Routing policy contract",
    )
    require(
        all(type(v) in (int, float) and math.isfinite(v) for v in policy.values())
        and 0 <= policy["rejectAt"] < 0.5 < policy["acceptAt"] <= 1,
        "Routing thresholds",
    )
    return manifest


def probability(value):
    require(
        type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
        "Probability contract",
    )
    return value


def valid_usage(value):
    """Legacy token metadata plus the adapter's optional reported USD cost."""
    if value is None:
        return True
    if not isinstance(value, dict):
        return False
    tokens = {"input_tokens", "output_tokens"}
    if not tokens <= set(value) <= tokens | {"cost_usd"}:
        return False
    if not all(type(value[k]) is int and value[k] >= 0 for k in tokens):
        return False
    cost = value.get("cost_usd")
    return (
        cost is None
        or type(cost) is int
        and cost >= 0
        or type(cost) is float
        and math.isfinite(cost)
        and cost >= 0
    )


def replay_verifier(manifest, raw, capture):
    validate_manifest(manifest)
    require(
        isinstance(capture, dict)
        and set(capture)
        == {
            "schema",
            "manifestDigest",
            "sourceDigest",
            "provider",
            "dependencies",
            "turn",
        },
        "Verifier capture contract",
    )
    require(
        capture["schema"] == CAPTURE_SCHEMA
        and capture["manifestDigest"] == digest(raw)
        and capture["sourceDigest"] == digest(manifest["state"]["sourceText"].encode())
        and capture["provider"] == manifest["provider"],
        "Verifier capture binding",
    )
    require(
        isinstance(capture["dependencies"], dict)
        and all(
            isinstance(k, str) and isinstance(v, str)
            for k, v in capture["dependencies"].items()
        ),
        "Dependency provenance",
    )
    turn = capture["turn"]
    require(
        isinstance(turn, dict)
        and set(turn)
        == {
            "id",
            "stage",
            "status",
            "request",
            "response",
            "error",
            "httpStatus",
            "calls",
            "questions",
            "latencyMs",
            "cost",
        },
        "Verifier turn contract",
    )
    require(
        turn["id"] == "turn_1"
        and turn["stage"] == "verification"
        and turn["status"] in {"prepared", "sent", "completed", "failed"},
        "Verifier turn status",
    )
    require(
        type(turn["calls"]) is int
        and 0 <= turn["calls"] <= 1
        and turn["questions"] == len(manifest["questions"]),
        "Turn budget",
    )
    require(
        turn["cost"] is None
        and (
            turn["latencyMs"] is None
            or type(turn["latencyMs"]) in (int, float)
            and math.isfinite(turn["latencyMs"])
            and turn["latencyMs"] >= 0
        ),
        "Measured values contract",
    )
    expected = {
        "model": manifest["provider"]["model"],
        "state": manifest["state"],
        "questions": manifest["questions"],
    }
    require(
        turn["request"] is None
        or turn["request"]
        == {
            "method": "POST",
            "endpoint": manifest["provider"]["endpoint"],
            "body": expected,
        },
        "Actual request differs from manifest",
    )
    verdicts, usage, model, request_id = {}, None, None, None
    if turn["status"] == "completed":
        require(
            turn["calls"] == 1
            and turn["request"] is not None
            and turn["error"] is None
            and turn["httpStatus"] == 200,
            "Completed turn contract",
        )
        response = turn["response"]
        require(
            isinstance(response, dict)
            and set(response) == {"answers", "model", "request_id", "usage"}
            and set(response["answers"]) == set(manifest["questions"]),
            "Response/answer coverage",
        )
        model, request_id, usage = (
            response["model"],
            response["request_id"],
            response["usage"],
        )
        require(
            isinstance(model, str)
            and model.strip()
            and isinstance(request_id, str)
            and request_id.isascii()
            and request_id
            and not any(
                c.isspace() or ord(c) < 33 or ord(c) == 127 for c in request_id
            ),
            "Returned model/request identity",
        )
        require(
            valid_usage(usage),
            "Usage contract",
        )
        for name, question in manifest["questions"].items():
            answer = response["answers"][name]
            require(
                isinstance(answer, dict)
                and answer.get("model") == model
                and answer.get("request_id") == request_id
                and answer.get("usage") == usage,
                "Answer metadata consistency",
            )
            if question["type"] == "noul":
                require(
                    set(answer) == {"p_yes", "model", "request_id", "usage"},
                    "Noul answer fields",
                )
                p = probability(answer["p_yes"])
                outcome = (
                    "pass"
                    if p >= manifest["policy"]["acceptAt"]
                    else "fail"
                    if p <= manifest["policy"]["rejectAt"]
                    else "uncertain"
                )
                verdicts[name] = {"type": "noul", "pYes": p, "outcome": outcome}
            else:
                field = "choice" if question["type"] == "choice" else "score"
                extra = set() if field == "choice" else {"legend"}
                require(
                    set(answer)
                    == {
                        field,
                        "confidence",
                        "probabilities",
                        "model",
                        "request_id",
                        "usage",
                    }
                    | extra,
                    "Choice/Score answer fields",
                )
                confidence = probability(answer["confidence"])
                labels = (
                    set(question["criteria"])
                    if field == "choice"
                    else {str(i) for i in range(len(question["criteria"]))}
                )
                probabilities = answer["probabilities"]
                require(
                    isinstance(probabilities, dict)
                    and set(probabilities) == labels
                    and math.isclose(
                        sum(probability(v) for v in probabilities.values()),
                        1,
                        abs_tol=1e-6,
                    ),
                    "Complete normalized distribution",
                )
                if field == "choice":
                    require(
                        answer[field] in labels
                        and probabilities[answer[field]]
                        >= max(probabilities.values()) - 1e-6,
                        "Choice label contract",
                    )
                else:
                    require(
                        answer["legend"]
                        == {
                            str(i): label
                            for i, label in enumerate(question["criteria"])
                        },
                        "Score legend contract",
                    )
                    require(
                        type(answer[field]) in (int, float)
                        and math.isfinite(answer[field])
                        and math.isclose(
                            answer[field],
                            sum(int(k) * v for k, v in probabilities.items()),
                            abs_tol=1e-6,
                        ),
                        "Weighted score contract",
                    )
                verdicts[name] = {
                    "type": question["type"],
                    field: answer[field],
                    "confidence": confidence,
                    "probabilities": probabilities,
                    "outcome": "recorded",
                }
    elif turn["status"] == "prepared":
        require(
            turn["calls"] == 0
            and turn["request"] is None
            and turn["response"] is None
            and turn["error"] is None
            and turn["httpStatus"] is None
            and turn["latencyMs"] is None,
            "Prepared turn state",
        )
    elif turn["status"] == "sent":
        require(
            turn["calls"] == 1
            and turn["request"] is not None
            and turn["response"] is None
            and turn["error"] is None
            and turn["httpStatus"] is None
            and turn["latencyMs"] is None,
            "Sent turn state",
        )
    else:
        require(
            turn["response"] is None
            and turn["error"]
            in {"http", "protocol", "transport", "configuration", "unknown"}
            and turn["latencyMs"] is not None,
            "Failed turn state",
        )
        require(
            (turn["calls"] == 0 and turn["request"] is None)
            or (turn["calls"] == 1 and turn["request"] is not None),
            "Failed call/request state",
        )
        require(
            turn["httpStatus"] is None
            or type(turn["httpStatus"]) is int
            and 100 <= turn["httpStatus"] <= 599,
            "Failed HTTP status",
        )
        require(
            (
                turn["error"] == "configuration"
                and turn["calls"] == 0
                and turn["httpStatus"] is None
            )
            or (
                turn["error"] == "transport"
                and turn["calls"] == 1
                and turn["httpStatus"] is None
            )
            or (
                turn["error"] == "http"
                and turn["calls"] == 1
                and turn["httpStatus"] not in (None, 200)
            )
            or (
                turn["error"] == "protocol"
                and turn["calls"] == 1
                and turn["httpStatus"] == 200
            )
            or (
                turn["error"] == "unknown"
                and (
                    turn["calls"] == 1
                    or (turn["calls"] == 0 and turn["httpStatus"] is None)
                )
            ),
            "Failure/error/HTTP state",
        )
    return {
        "schema": "normlab.verifier-replay/v1",
        "experimentId": manifest["experimentId"],
        "manifestDigest": digest(raw),
        "sourceDigest": capture["sourceDigest"],
        "captureDigest": digest(
            json.dumps(capture, sort_keys=True, ensure_ascii=False).encode()
        ),
        "provider": capture["provider"],
        "dependencies": capture["dependencies"],
        "status": turn["status"],
        "error": turn["error"],
        "httpStatus": turn["httpStatus"],
        "calls": turn["calls"],
        "questions": turn["questions"],
        "returnedModel": model,
        "requestId": request_id,
        "usage": usage,
        "latencyMs": turn["latencyMs"],
        "cost": None,
        "verdicts": verdicts,
        "criticalErrorFreeRate": None,
        "quality": "not_evaluated",
    }
