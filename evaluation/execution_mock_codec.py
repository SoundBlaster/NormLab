"""Pure mock evidence codec, shared by dispatch and explicit response adoption."""

from execution_outcomes import retryable
from execution_plan import charge
from execution_records import PREFIX, attempt_id, backoff_bounds
from offline_bundle import canonical, sha


def reference(raw):
    return {"path": f"artifacts/{sha(raw)}.blob", "sha256": sha(raw), "bytes": len(raw)}


def model_rejected(model, arm, models):
    return model not in arm["acceptedModels"] or (
        arm["id"] in models and models[arm["id"]] != model
    )


def normalize_mock(spec, task, arm, attempt, ordinal, models):
    status = spec["status"]
    if status == "completed" and model_rejected(spec["model"], arm, models):
        status = "model-rejected"
    blobs, response, result = [], None, None
    if status not in {"transport-failed", "unknown-outcome"}:
        raw = canonical(
            {
                "schema": "normlab.mock-response/v1",
                "attemptId": attempt,
                "scripted": spec,
            }
        )
        response = reference(raw)
        blobs.append(("response", raw))
    if status == "completed":
        raw = canonical(
            {
                "schema": PREFIX + "answers/v1",
                "normalizer": arm["adapter"],
                "answers": spec["answers"],
            }
        )
        result = reference(raw)
        blobs.append(("result", raw))
    saved = {
        "schema": PREFIX + "outcome/v1",
        "status": status,
        "requestDigest": task["request"]["sha256"],
        "contextDigest": task["context"]["sha256"],
        "model": spec["model"],
        "providerRequestId": "mock-" + attempt,
        "dispatchObserved": False,
        "usage": {"inputTokens": 0, "outputTokens": 0},
        "response": response,
        "result": result,
        "errorClasses": [spec["errorClass"]] if status == "transport-failed" else [],
        "backoffNs": None,
        "statusCode": spec["statusCode"],
    }
    if retryable(saved, ordinal):
        saved["backoffNs"] = backoff_bounds(ordinal)[0]
    return saved, blobs


def make_event(
    intent,
    events,
    clock,
    plan,
    kind,
    *,
    task_index=0,
    ordinal=1,
    outcome=None,
    reason=None,
    invocation=None,
    control=None,
    version=1,
):
    marker = kind in {"run-stopped", "invocation-started"}
    task, ids = plan["tasks"][task_index], intent["tasks"][task_index]
    event = {
        "schema": PREFIX + f"event/v{version}",
        "id": None,
        "runId": intent["id"],
        "invocationId": invocation or intent["initialInvocationId"],
        "sequence": len(events) + 1,
        "previousDigest": events[-1]["id"] if events else None,
        "type": kind,
        "taskId": None if marker else ids["taskId"],
        "turnId": None if marker else ids["turnId"],
        "attemptId": None if marker else attempt_id(ids["turnId"], ordinal),
        "ordinal": None if marker else ordinal,
        "clockNs": clock.value,
        "observedAt": clock.timestamp(),
        "request": None if marker else task["request"],
        "budgetDelta": charge(plan, task)
        if kind == "attempt-reserved"
        else {key: 0 for key in plan["caps"]},
        "outcome": outcome,
        "stopReason": reason,
    }
    if version == 2:
        event["control"] = control
    event["id"] = sha(canonical({k: v for k, v in event.items() if k != "id"}))
    return event
