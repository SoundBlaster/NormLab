"""Conservative, read-only execution journal replay; no writer or dispatch path."""

from execution_decisions import permit_caps
from execution_outcomes import answer_schema, outcome, preserve_observation, retryable
from execution_plan import MISSING_CAPABILITIES, charge, prepare
from execution_records import (
    CAP_FIELDS,
    MAX_EVENTS,
    PREFIX,
    attempt_id,
    backoff_bounds,
    caps,
    integer,
    items,
    run_shape,
    utc,
)
from offline_bundle import canonical, object_keys, require, sha


def replay(store):
    plan = prepare(store)
    run, events = store.json("run.json"), store.json("journal.json")
    run_shape(run, plan)
    limits, permit = permit_caps(plan, run, store)
    questions = answer_schema(store.value(plan["pins"]["outputSchema"]))
    for task in plan["tasks"]:
        require(
            all(key in questions for key in task["questionIds"]),
            "Question schema coverage",
        )
    items(events, maximum=MAX_EVENTS)
    arms = {arm["id"]: arm for arm in plan["arms"]}
    zero = {key: 0 for key in CAP_FIELDS.split()}
    reserved, attempts, models = dict(zero), [], {}
    active, previous, head, last_utc = None, None, None, None
    position, ordinal = 0, 1
    last_clock = run["clock"]["startNs"]
    stopped, blocked, usage_violation = None, False, False
    for sequence, event in enumerate(events, 1):
        object_keys(
            event,
            "schema id runId invocationId sequence previousDigest type taskId turnId attemptId ordinal "
            "clockNs observedAt request budgetDelta outcome stopReason",
        )
        require(event["schema"] == PREFIX + "event/v1", "Event schema")
        integer(event["sequence"], 1)
        require(
            event["sequence"] == sequence
            and event["previousDigest"] == head
            and event["runId"] == run["id"],
            "Journal order/run/hash chain",
        )
        require(
            event["invocationId"] == run["initialInvocationId"],
            "Resume/reconciliation invocation unsupported in 5a",
        )
        require(
            event["id"]
            == sha(
                canonical({key: value for key, value in event.items() if key != "id"})
            ),
            "Event identity/hash",
        )
        require(stopped is None, "No events after run stop")
        integer(event["clockNs"])
        require(event["clockNs"] >= last_clock, "Clock reading regression")
        observed = utc(event["observedAt"])
        require(last_utc is None or observed >= utc(last_utc), "Wall clock ambiguity")
        caps(event["budgetDelta"])
        kind = event["type"]
        require(
            kind
            in {
                "attempt-reserved",
                "attempt-observed",
                "attempt-terminal",
                "run-stopped",
            },
            "Unsupported event policy/type",
        )
        if kind == "run-stopped":
            require(
                all(
                    event[key] is None
                    for key in (
                        "taskId",
                        "turnId",
                        "attemptId",
                        "ordinal",
                        "request",
                        "outcome",
                    )
                )
                and event["budgetDelta"] == zero,
                "Stop event fields/zero delta",
            )
            stopped = event["stopReason"]
            require(
                stopped
                in {
                    "operator-stop",
                    "deadline",
                    "budget-exhaustion",
                    "terminal-failure",
                    "complete",
                    "unknown-outcome",
                    "usage-ceiling-exceeded",
                },
                "Run stop reason",
            )
            if active is not None:
                require(
                    stopped == "unknown-outcome", "Unknown reservation remains unknown"
                )
            elif stopped == "unknown-outcome":
                require(False, "Unknown stop requires unresolved reservation")
            if stopped == "complete":
                require(
                    position == len(plan["tasks"]) and not usage_violation,
                    "Complete planned denominator without usage violation",
                )
            if stopped == "usage-ceiling-exceeded":
                require(usage_violation, "Usage ceiling violation evidence")
            if stopped == "deadline":
                require(
                    event["clockNs"] >= run["clock"]["deadlineNs"],
                    "Deadline not reached",
                )
            if stopped == "terminal-failure":
                require(blocked, "Terminal failure evidence")
            if stopped == "budget-exhaustion":
                require(position < len(plan["tasks"]), "Budget stop has pending task")
                next_charge = charge(plan, plan["tasks"][position])
                require(
                    any(
                        reserved[key] + count > limits[key]
                        for key, count in next_charge.items()
                    ),
                    "Exhausted reservation cap",
                )
        else:
            require(event["stopReason"] is None, "Attempt event has no run stop reason")
            require(position < len(plan["tasks"]), "No attempt past schedule")
            task, ids = plan["tasks"][position], run["tasks"][position]
            arm = arms[task["armId"]]
            integer(event["ordinal"], 1)
            require(
                event["taskId"] == ids["taskId"]
                and event["turnId"] == ids["turnId"]
                and event["ordinal"] == ordinal
                and event["attemptId"] == attempt_id(ids["turnId"], ordinal)
                and event["request"] == task["request"],
                "Attempt task/turn/request/ordinal binding",
            )
            if kind == "attempt-reserved":
                require(
                    active is None and not blocked and not usage_violation,
                    "No dispatch after unknown/terminal failure",
                )
                require(event["outcome"] is None, "Reservation is not an outcome")
                require(
                    event["clockNs"] < run["clock"]["deadlineNs"],
                    "Expired run deadline",
                )
                if permit is not None:
                    require(
                        utc(permit["authorization"]["authorizedAt"])
                        <= observed
                        < utc(permit["expiresAt"]),
                        "Reservation outside permit validity",
                    )
                if previous is not None:
                    require(
                        retryable(previous["outcome"], ordinal - 1), "Ineligible retry"
                    )
                    delay = previous["outcome"]["backoffNs"]
                    low, high = backoff_bounds(ordinal - 1)
                    require(
                        type(delay) is int
                        and low <= delay <= high
                        and event["clockNs"] >= previous["clockNs"] + delay,
                        "Frozen retry backoff",
                    )
                expected = charge(plan, task)
                require(event["budgetDelta"] == expected, "Reservation charge binding")
                for key, count in expected.items():
                    reserved[key] += count
                    require(reserved[key] <= limits[key], "Aggregate reservation cap")
                active = {
                    "id": event["attemptId"],
                    "taskKey": task["key"],
                    "ordinal": ordinal,
                    "outcome": None,
                    "clockNs": event["clockNs"],
                }
                attempts.append(active)
            else:
                require(active is not None, "Outcome requires active reservation")
                require(
                    event["budgetDelta"] == zero,
                    "Outcome cannot refund/recharge reservation",
                )
                saved = outcome(
                    store.value(event["outcome"]),
                    task,
                    arm,
                    questions,
                    store,
                    observation=kind == "attempt-observed",
                    mock=run["evidenceKind"] == "mock",
                )
                preserve_observation(active["outcome"], saved)
                usage_violation |= any(
                    count is not None and count > arm["requestCaps"][key]
                    for key, count in saved["usage"].items()
                )
                if saved["backoffNs"] is not None:
                    low, high = backoff_bounds(ordinal)
                    require(
                        retryable(saved, ordinal) and low <= saved["backoffNs"] <= high,
                        "Only eligible retries declare frozen backoff",
                    )
                active["outcome"] = saved
                active["clockNs"] = event["clockNs"]
                if kind == "attempt-terminal":
                    if saved["status"] == "completed":
                        require(
                            models.setdefault(arm["id"], saved["model"])
                            == saved["model"],
                            "Observed model drift requires rejection",
                        )
                        position, ordinal, previous = position + 1, 1, None
                    else:
                        if saved["status"] == "model-rejected":
                            require(
                                saved["model"] not in arm["acceptedModels"]
                                or (
                                    arm["id"] in models
                                    and models[arm["id"]] != saved["model"]
                                ),
                                "Rejected model policy evidence",
                            )
                        blocked = not retryable(saved, ordinal)
                        previous, ordinal = active, ordinal + 1
                    active = None
        head, last_clock, last_utc = event["id"], event["clockNs"], event["observedAt"]
    counts = {
        "reserved": reserved,
        "observedDispatches": 0,
        "knownInputTokens": 0,
        "knownOutputTokens": 0,
        "unknownUsageAttempts": 0,
    }
    unknown_dispatches = 0
    for attempt in attempts:
        saved = attempt["outcome"]
        if saved is None:
            unknown_dispatches += run["evidenceKind"] != "mock"
            counts["unknownUsageAttempts"] += 1
            continue
        counts["observedDispatches"] += saved["dispatchObserved"] is True
        unknown_dispatches += saved["dispatchObserved"] is None
        counts["unknownUsageAttempts"] += any(
            value is None for value in saved["usage"].values()
        )
        for token, total in (
            ("inputTokens", "knownInputTokens"),
            ("outputTokens", "knownOutputTokens"),
        ):
            if saved["usage"][token] is not None:
                counts[total] += saved["usage"][token]
    state = (
        "finished"
        if stopped is not None
        else "paused-unknown"
        if active is not None
        else "running"
        if events
        else "created"
    )
    reason = (
        stopped
        if stopped is not None
        else "unknown-outcome"
        if active is not None
        else None
    )
    require(
        run["journalHead"] == head
        and run["lastClockNs"] == last_clock
        and run["state"] == state
        and run["stopReason"] == reason
        and run["counts"] == counts,
        "Derived run view/journal counters binding",
    )
    return {
        "schema": PREFIX + "replay/v1",
        "runId": run["id"],
        "planDigest": run["planDigest"],
        "journalHead": head,
        "state": state,
        "stopReason": reason,
        "counts": counts,
        "unknownDispatchAttempts": unknown_dispatches,
        "usageCeilingExceeded": usage_violation,
        "unknownAttemptIds": [active["id"]] if active is not None else [],
        "lastObservedAt": last_utc,
        "taskOutcomes": [
            {
                "key": task["key"],
                "attemptIds": [
                    attempt["id"]
                    for attempt in attempts
                    if attempt["taskKey"] == task["key"]
                ],
                "first": next(
                    (
                        attempt["outcome"]
                        for attempt in attempts
                        if attempt["taskKey"] == task["key"]
                    ),
                    None,
                ),
                "final": next(
                    (
                        attempt["outcome"]
                        for attempt in reversed(attempts)
                        if attempt["taskKey"] == task["key"]
                    ),
                    None,
                ),
            }
            for task in plan["tasks"]
        ],
        "missingCapabilities": list(MISSING_CAPABILITIES),
        "runtimeClockVerified": False,
        "providerWireValidated": False,
        "codePinsVerified": False,
        "executionReady": False,
        "authorizedDispatches": 0,
        "inferenceCallsExecuted": 0,
        "semanticQualityEvidence": False,
        "actualCost": None,
    }
