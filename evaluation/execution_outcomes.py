"""Strict normalized outcome shapes; saved declarations are not provider attestation."""

from execution_records import (
    ERROR_CLASSES,
    MAX_ATTEMPTS,
    PREFIX,
    TRANSIENT,
    integer,
    items,
    revision,
    text,
)
from offline_bundle import object_keys, require

TERMINAL = {
    "completed",
    "transport-failed",
    "http-failed",
    "invalid-output",
    "refused",
    "model-rejected",
}


def answer_schema(value):
    object_keys(value, "schema questions")
    require(value["schema"] == PREFIX + "answer-schema/v1", "Answer schema revision")
    items(value["questions"], 1)
    questions = {}
    for question in value["questions"]:
        object_keys(question, "id type labels")
        text(question["id"])
        require(question["type"] in ("noul", "choice", "score"), "Answer type")
        items(question["labels"])
        for label in question["labels"]:
            text(label)
        require(
            len(set(question["labels"])) == len(question["labels"])
            and (
                not question["labels"]
                if question["type"] == "noul"
                else len(question["labels"]) >= 2
            ),
            "Answer label set/scale",
        )
        require(question["id"] not in questions, "Unique question definition")
        questions[question["id"]] = question
    return questions


def answers(value, task, arm, questions):
    object_keys(value, "schema normalizer answers")
    require(value["schema"] == PREFIX + "answers/v1", "Normalized answers schema")
    revision(value["normalizer"])
    require(value["normalizer"] == arm["adapter"], "Normalizer revision binding")
    items(value["answers"], 1)
    require(len(value["answers"]) == len(task["questionIds"]), "Answer denominator")
    for answer, identifier in zip(value["answers"], task["questionIds"]):
        object_keys(answer, "questionId type value")
        definition = questions[identifier]
        require(
            answer["questionId"] == identifier and answer["type"] == definition["type"],
            "Answer/question order binding",
        )
        result = answer["value"]
        if definition["type"] == "choice":
            require(
                isinstance(result, str) and result in definition["labels"], "Choice"
            )
        else:
            upper = 1 if definition["type"] == "noul" else len(definition["labels"]) - 1
            require(
                type(result) in (int, float) and 0 <= result <= upper, "Answer range"
            )


def outcome(value, task, arm, questions, store, *, observation, mock):
    object_keys(
        value,
        "schema status requestDigest contextDigest model providerRequestId dispatchObserved "
        "usage response result errorClasses backoffNs statusCode",
    )
    require(value["schema"] == PREFIX + "outcome/v1", "Outcome schema")
    require(
        value["status"] in ({"unknown-outcome"} if observation else TERMINAL),
        "Outcome event category",
    )
    require(
        value["requestDigest"] == task["request"]["sha256"]
        and value["contextDigest"] == task["context"]["sha256"],
        "Outcome request/context binding",
    )
    for key in ("model", "providerRequestId"):
        if value[key] is not None:
            text(value[key])
    require(
        value["dispatchObserved"] is None or type(value["dispatchObserved"]) is bool,
        "Nullable observed dispatch",
    )
    object_keys(value["usage"], "inputTokens outputTokens")
    for key, count in value["usage"].items():
        if count is not None:
            integer(count)
    if value["dispatchObserved"] is False:
        require(
            value["usage"] == {"inputTokens": 0, "outputTokens": 0},
            "Definitively unsent attempt requires explicit zero provider usage",
        )
    if mock:
        require(
            value["dispatchObserved"] is False
            and value["usage"] == {"inputTokens": 0, "outputTokens": 0},
            "Mock evidence cannot claim provider dispatch/usage",
        )
    items(value["errorClasses"], maximum=8)
    require(
        all(
            isinstance(name, str) and name in ERROR_CLASSES
            for name in value["errorClasses"]
        ),
        "Sanitized transport classes",
    )
    if value["response"] is not None:
        store.artifact(value["response"])
    if value["status"] == "completed":
        require(
            value["model"] in arm["acceptedModels"] and value["response"] is not None,
            "Completed response/model evidence",
        )
        require(
            mock or value["dispatchObserved"] is True,
            "Completed live response requires observed dispatch",
        )
        require(value["result"] is not None, "Normalized result evidence")
        answers(store.value(value["result"]), task, arm, questions)
    else:
        require(value["result"] is None, "No completed answers for failure/unknown")
    if value["status"] in {
        "http-failed",
        "invalid-output",
        "refused",
        "model-rejected",
    }:
        require(
            value["response"] is not None
            and (mock or value["dispatchObserved"] is True),
            "Response-backed failure/observed live dispatch",
        )
    if value["status"] == "model-rejected":
        require(value["model"] is not None, "Rejected model identity")
    if value["status"] == "http-failed":
        integer(value["statusCode"], 400)
        require(value["statusCode"] <= 599, "HTTP failure code")
    else:
        require(value["statusCode"] is None, "No failure HTTP status for this outcome")
    if value["status"] == "transport-failed":
        require(
            value["errorClasses"] and value["response"] is None, "Transport evidence"
        )
        if value["backoffNs"] is not None:
            integer(value["backoffNs"], 1)
    else:
        require(
            not value["errorClasses"] and value["backoffNs"] is None,
            "Only transport failures have retry metadata",
        )
    return value


def retryable(value, ordinal):
    classes = set(value["errorClasses"])
    return (
        value["status"] == "transport-failed"
        and ordinal < MAX_ATTEMPTS
        and bool(classes & TRANSIENT)
        and not classes & {"SSLCertVerificationError", "CertificateError"}
    )


def preserve_observation(previous, current):
    if previous is None:
        return
    if previous["dispatchObserved"] is not None:
        require(
            current["dispatchObserved"] is previous["dispatchObserved"],
            "Observed dispatch cannot be forgotten/reversed",
        )
    for key in ("model", "providerRequestId", "response"):
        if previous[key] is not None:
            require(current[key] == previous[key], "Observed response identity drift")
    for key, count in previous["usage"].items():
        if count is not None:
            require(
                current["usage"][key] is not None and current["usage"][key] >= count,
                "Known usage cannot be forgotten/decreased",
            )
