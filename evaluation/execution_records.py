"""Closed execution record shapes and identities; stdlib, no execution authority."""

import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import UUID

from offline_bundle import canonical, digest_value, identity, object_keys, require, sha

PREFIX = "normlab.execution-"
CONTEXT = "independent-public-request/v1"
CLOCK = "same-host-boot-suspend-aware/v1"
CLOCK_SOURCES = {"linux:CLOCK_BOOTTIME"}
RETRY = "stage1-transient-transport/v1"
PROTOCOL_FIELDS = {
    "typesafe-systemone/v1": {"state", "questions"},
    "openai-decisions/v1": {"state", "questions"},
    "openai-chat-completions/v1": {"messages", "response_format"},
    "openai-responses/v1": {"input", "text"},
}
MAX_ITEMS = 1024
MAX_ATTEMPTS = 3
MAX_EVENTS = 8192
MAX_INTEGER = 2**63 - 1
CAP_FIELDS = "dispatches questions inputTokens outputTokens"
TRANSIENT = frozenset(
    {
        "ConnectError",
        "ConnectTimeout",
        "ReadError",
        "ReadTimeout",
        "WriteError",
        "WriteTimeout",
        "RemoteProtocolError",
        "SSLEOFError",
    }
)
ERROR_CLASSES = TRANSIENT | {
    "SSLCertVerificationError",
    "CertificateError",
    "OtherError",
}


def text(value):
    require(isinstance(value, str) and 0 < len(value) <= 4096, "Bounded text")


def integer(value, minimum=0):
    require(type(value) is int and minimum <= value <= MAX_INTEGER, "Bounded integer")


def digest(value):
    require(digest_value(value), "SHA-256 digest")


def items(value, minimum=0, maximum=MAX_ITEMS):
    require(isinstance(value, list) and minimum <= len(value) <= maximum, "List cap")


def revision(value):
    object_keys(value, "id revision sha256")
    text(value["id"])
    text(value["revision"])
    digest(value["sha256"])


def run_id(value):
    text(value)
    parsed = UUID(value)
    require(parsed.version == 4 and str(parsed) == value, "Canonical runtime UUID4")


def utc(value):
    require(
        isinstance(value, str)
        and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z", value),
        "UTC microsecond timestamp",
    )
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
        tzinfo=timezone.utc
    )


def caps(value):
    object_keys(value, CAP_FIELDS)
    for count in value.values():
        integer(count)


def clock(value, wall_time):
    object_keys(value, "policy source units suspendAware epoch startNs deadlineNs")
    require(value["policy"] == CLOCK, "Unsupported clock policy")
    require(value["source"] in CLOCK_SOURCES, "Unsupported suspend-aware clock source")
    require(
        value["units"] == "nanoseconds" and value["suspendAware"] is True,
        "Suspend-aware clock capability required",
    )
    # Source support/epoch must be attested by a later runtime, never by this reader.
    digest(value["epoch"])
    integer(value["startNs"])
    integer(value["deadlineNs"])
    require(
        value["deadlineNs"] == value["startNs"] + wall_time,
        "Original frozen deadline",
    )


def authorization(value):
    object_keys(value, "operatorId authorizationRef authorizedAt")
    text(value["operatorId"])
    digest(value["authorizationRef"])
    utc(value["authorizedAt"])


def endpoint(value):
    text(value)
    parts = urlsplit(value)
    require(
        parts.scheme == "https"
        and not any(character.isspace() or ord(character) < 32 for character in value)
        and parts.hostname
        and parts.username is None
        and parts.password is None
        and not parts.query
        and not parts.fragment,
        "Public HTTPS endpoint without credentials/query/fragment",
    )
    require(parts.port is None or 1 <= parts.port <= 65535, "Endpoint port")


def plan_shape(plan):
    object_keys(
        plan,
        "schema experiment dataset strategy tactic pins arms tasks caps wallTimeNs "
        "contextPolicy retryPolicy clockPolicy",
    )
    require(plan["schema"] == PREFIX + "plan/v1", "Plan schema")
    for key in ("experiment", "dataset", "strategy", "tactic"):
        revision(plan[key])
    object_keys(plan["pins"], "definitions prompt outputSchema code dependencies")
    for key in ("code", "dependencies"):
        pins = plan["pins"][key]
        require(isinstance(pins, dict) and 0 < len(pins) <= MAX_ITEMS, "Revision pins")
        for name, pin in pins.items():
            text(name)
            digest(pin)
    require(plan["contextPolicy"] == CONTEXT, "Unsupported context policy")
    require(plan["retryPolicy"] == RETRY, "Unsupported retry policy")
    require(plan["clockPolicy"] == CLOCK, "Unsupported clock policy")
    caps(plan["caps"])
    integer(plan["wallTimeNs"])
    items(plan["arms"], 1)
    arms = {}
    for arm in plan["arms"]:
        object_keys(
            arm,
            "id provider protocol endpoint model acceptedModels settings adapter "
            "requestCaps timeoutNs",
        )
        for key in ("id", "provider", "protocol", "model"):
            text(arm[key])
        require(arm["protocol"] in PROTOCOL_FIELDS, "Unsupported public wire protocol")
        endpoint(arm["endpoint"])
        revision(arm["adapter"])
        items(arm["acceptedModels"], 1)
        for model in arm["acceptedModels"]:
            text(model)
        require(
            len(set(arm["acceptedModels"])) == len(arm["acceptedModels"]),
            "Unique model acceptance set",
        )
        object_keys(arm["settings"], "temperature reasoningEffort maxOutputTokens")
        temperature = arm["settings"]["temperature"]
        require(
            temperature is None
            or (type(temperature) in (int, float) and 0 <= temperature <= 2),
            "Temperature",
        )
        require(
            arm["settings"]["reasoningEffort"]
            in (None, "none", "low", "medium", "high"),
            "Reasoning setting",
        )
        integer(arm["settings"]["maxOutputTokens"], 1)
        caps(arm["requestCaps"])
        require(arm["requestCaps"]["dispatches"] == 1, "One dispatch per attempt")
        require(
            arm["requestCaps"]["outputTokens"] == arm["settings"]["maxOutputTokens"],
            "Output ceiling binding",
        )
        integer(arm["timeoutNs"], 1)
        require(arm["id"] not in arms, "Unique arm ID")
        arms[arm["id"]] = arm
    items(plan["tasks"], 1)
    keys, coordinates = set(), set()
    for task in plan["tasks"]:
        object_keys(
            task,
            "key caseId armId repeat stage source candidate request context questionIds",
        )
        for key in ("key", "caseId", "armId", "stage"):
            text(task[key])
        integer(task["repeat"])
        require(task["armId"] in arms, "Task arm binding")
        coordinate = (task["caseId"], task["armId"], task["repeat"], task["stage"])
        require(
            task["key"] not in keys and coordinate not in coordinates,
            "Unique semantic task/repetition",
        )
        keys.add(task["key"])
        coordinates.add(coordinate)
        items(task["questionIds"], 1)
        for question in task["questionIds"]:
            text(question)
        require(
            len(set(task["questionIds"])) == len(task["questionIds"])
            and len(task["questionIds"])
            <= arms[task["armId"]]["requestCaps"]["questions"],
            "Question order/ceiling",
        )
    return arms


def scope_digest(plan):
    return sha(canonical(plan["arms"]))


def identities(plan, identifier):
    """Derive run-bound task/turn IDs without allocating a run or reading artifacts."""
    result = []
    for task in plan["tasks"]:
        task_id = identity("task", [identifier, task])
        turn_id = identity("turn", [task_id, task["stage"], []])
        result.append({"key": task["key"], "taskId": task_id, "turnId": turn_id})
    return result


def attempt_id(turn_id, ordinal):
    return identity("attempt", [turn_id, ordinal])


def backoff_bounds(ordinal):
    integer(ordinal, 1)
    require(ordinal < MAX_ATTEMPTS, "No backoff after final attempt")
    low = 2 ** (ordinal - 1) * 1_000_000_000
    return low, low + 500_000_000


def wire_settings(arm):
    """The initial supported subset, exact public fields; not an SDK adapter."""
    settings = arm["settings"]
    expected = {"model": arm["model"]}
    if arm["protocol"] in {"typesafe-systemone/v1", "openai-decisions/v1"}:
        require(
            settings["temperature"] is None and settings["reasoningEffort"] is None,
            "Decision sampling settings unsupported",
        )
        return expected
    if settings["temperature"] is not None:
        expected["temperature"] = settings["temperature"]
    if arm["protocol"] == "openai-chat-completions/v1":
        expected["max_completion_tokens"] = settings["maxOutputTokens"]
        if settings["reasoningEffort"] is not None:
            expected["reasoning_effort"] = settings["reasoningEffort"]
    else:
        expected["max_output_tokens"] = settings["maxOutputTokens"]
        if settings["reasoningEffort"] is not None:
            expected["reasoning"] = {"effort": settings["reasoningEffort"]}
    return expected


def run_shape(run, plan):
    object_keys(
        run,
        "schema id initialInvocationId identityKind evidenceKind planDigest clock tasks permit predecessor "
        "journalHead lastClockNs state stopReason counts",
    )
    require(run["schema"] == PREFIX + "run/v1", "Run schema")
    run_id(run["id"])
    run_id(run["initialInvocationId"])
    require(run["initialInvocationId"] != run["id"], "Separate invocation identity")
    require(run["identityKind"] == "runtime-allocated", "Runtime identity kind")
    require(run["evidenceKind"] in ("mock", "live-capture"), "Evidence kind")
    require(run["planDigest"] == sha(canonical(plan)), "Run/plan binding")
    clock(run["clock"], plan["wallTimeNs"])
    require(run["tasks"] == identities(plan, run["id"]), "Task/turn identity binding")
    if run["predecessor"] is not None:
        object_keys(run["predecessor"], "runId unknownAttemptId captureDigest")
        run_id(run["predecessor"]["runId"])
        require(run["predecessor"]["runId"] != run["id"], "Separate predecessor run")
        text(run["predecessor"]["unknownAttemptId"])
        digest(run["predecessor"]["captureDigest"])
    if run["journalHead"] is not None:
        digest(run["journalHead"])
    integer(run["lastClockNs"])
    require(
        run["state"] in ("created", "running", "paused-unknown", "finished"),
        "Run state",
    )
    if run["stopReason"] is not None:
        text(run["stopReason"])
    object_keys(
        run["counts"],
        "reserved observedDispatches knownInputTokens knownOutputTokens unknownUsageAttempts",
    )
    caps(run["counts"]["reserved"])
    for key in ("observedDispatches", "knownInputTokens", "knownOutputTokens"):
        integer(run["counts"][key])
    integer(run["counts"]["unknownUsageAttempts"])
