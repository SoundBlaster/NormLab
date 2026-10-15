"""Independent read-only Stage1 lineage checks, without legacy producer imports."""

import json
import re

from execution_records import integer
from offline_bundle import canonical, object_keys, require, sha

ARMS = ("jev-coreinfra", "luna-decisions-coreinfra", "luna-low-coreinfra")
PROTOCOLS = (
    "typesafe-systemone/v1",
    "openai-decisions-input/v1",
    "openai-responses-stage1/v1",
)


def ordered(value):
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode()


def verify(store, plan):
    lineage = store.value(plan["pins"]["definitions"])
    object_keys(lineage, "schema sourcePlanDigest manifest metadata jobs options")
    require(
        lineage["schema"] == "normlab.stage1-native-lineage/v1", "Stage1 native lineage"
    )
    source = {
        **lineage["metadata"],
        "jobs": [store.value(ref) for ref in lineage["jobs"]],
    }
    require(
        source["schema"] == "normlab.stage1-provider-plan/v1"
        and sha(canonical(source)) == lineage["sourcePlanDigest"]
        and sha(store.artifact(lineage["manifest"])) == source["manifestDigest"],
        "Source plan/manifest lineage",
    )
    options, budget, jobs = lineage["options"], source["budget"], source["jobs"]
    object_keys(options, "acceptedModels inputTokenCap decisionOutputTokenCap")
    object_keys(options["acceptedModels"], " ".join(ARMS))
    integer(options["inputTokenCap"], 1)
    integer(options["decisionOutputTokenCap"], 1)
    require(
        len(jobs) == len(plan["tasks"]) == budget["maxCalls"] == budget["maxQuestions"],
        "Stage1 complete denominator",
    )
    question = jobs[0]["task"]["questions"]["overall"]
    labels = list(question["criteria"])

    def exact(ref, value, *, raw=False):
        require(
            store.artifact(ref) == (value if raw else ordered(value)),
            "Exact Stage1 source projection",
        )

    def revision(identifier, digest):
        return {"id": identifier, "revision": "stage1-native/v1", "sha256": digest}

    expected = {
        "experiment": revision(source["experimentId"], source["manifestDigest"]),
        "dataset": revision(source["datasetId"], source["parentManifestDigest"]),
        "strategy": revision("stage1-selected-support", sha(canonical(question))),
        "tactic": revision(source["ordering"], lineage["sourcePlanDigest"]),
    }
    require(all(plan[k] == v for k, v in expected.items()), "Stage1 revision lineage")
    exact(plan["pins"]["prompt"], question)
    exact(
        plan["pins"]["outputSchema"],
        {
            "schema": "normlab.execution-answer-schema/v1",
            "questions": [{"id": "classification", "type": "choice", "labels": labels}],
        },
    )
    require([a["id"] for a in plan["arms"]] == list(ARMS), "Stage1 arm order")
    object_keys(source["providers"], " ".join(ARMS))
    for arm, identifier, protocol in zip(plan["arms"], ARMS, PROTOCOLS):
        provider = source["providers"][identifier]
        object_keys(provider, "apiFormat endpoint model keyEnvironment settings")
        expected_format = {
            PROTOCOLS[0]: "typesafe-systemone",
            PROTOCOLS[1]: "openai-decisions",
            PROTOCOLS[2]: "openai-responses",
        }[protocol]
        expected_settings = (
            {"reasoning": {"effort": "low"}, "max_output_tokens": 1024, "store": False}
            if expected_format == "openai-responses"
            else {}
        )
        require(
            provider["apiFormat"] == expected_format
            and canonical(provider["settings"]) == canonical(expected_settings)
            and isinstance(provider["model"], str)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:-]{0,199}", provider["model"])
            and isinstance(provider["keyEnvironment"], str)
            and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", provider["keyEnvironment"]),
            "Stage1 complete provider format/settings/configuration",
        )
        output_cap = (
            1024 if identifier == ARMS[2] else options["decisionOutputTokenCap"]
        )
        require(
            arm["provider"] == identifier
            and arm["protocol"] == protocol
            and arm["model"] == provider["model"]
            and arm["endpoint"] == provider["endpoint"]
            and arm["acceptedModels"] == options["acceptedModels"][identifier]
            and arm["settings"]
            == {
                "temperature": None,
                "reasoningEffort": "low" if identifier == ARMS[2] else None,
                "maxOutputTokens": output_cap,
            }
            and arm["requestCaps"]
            == {
                "dispatches": 1,
                "questions": 1,
                "inputTokens": options["inputTokenCap"],
                "outputTokens": output_cap,
            }
            and arm["timeoutNs"] == budget["transportTimeoutSeconds"] * 1_000_000_000,
            "Stage1 provider/settings/cap lineage",
        )
    require(
        plan["wallTimeNs"] == budget["wallDeadlineSeconds"] * 1_000_000_000
        and plan["caps"]
        == {
            "dispatches": budget["maxCalls"],
            "questions": budget["maxQuestions"],
            "inputTokens": budget["maxCalls"] * options["inputTokenCap"],
            "outputTokens": budget["maxCalls"]
            * max(a["requestCaps"]["outputTokens"] for a in plan["arms"]),
        },
        "Stage1 aggregate caps/deadline lineage",
    )
    for task, job in zip(plan["tasks"], jobs):
        semantic = job["task"]
        require(
            semantic["questions"]["overall"] == question
            and sha(canonical(semantic)) == job["taskDigest"]
            and sha(semantic["state"]["sourceText"].encode()) == job["sourceDigest"],
            "Source task/context digests",
        )
        require(
            task["key"] == job["jobId"]
            and task["caseId"] == job["caseId"] + "/" + job["recordId"]
            and task["repeat"] == job["repeat"]
            and task["armId"] == job["armId"]
            and task["stage"] == "selected-support"
            and task["questionIds"] == ["classification"],
            "Stage1 schedule coordinates",
        )
        exact(task["source"], semantic["state"]["sourceText"].encode(), raw=True)
        exact(task["candidate"], semantic["state"]["candidateClaims"])
        original, provider = job["request"], source["providers"][job["armId"]]
        require(
            original["method"] == "POST"
            and original["endpoint"] == provider["endpoint"],
            "Source request route",
        )
        body = original["body"]
        if provider["apiFormat"] == "typesafe-systemone":
            require(
                ordered(body)
                == ordered(
                    {
                        "model": provider["model"],
                        "state": semantic["state"],
                        "questions": {"classification": question},
                    }
                ),
                "Stage1 TypeSafe body",
            )
        elif provider["apiFormat"] == "openai-decisions":
            require(
                ordered(body)
                == ordered(
                    {
                        "model": provider["model"],
                        "input": json.dumps(
                            semantic["state"], ensure_ascii=False, allow_nan=False
                        ),
                        "questions": [
                            {
                                "type": "choice",
                                "name": "classification",
                                "instructions": question["instructions"],
                                "choices": [
                                    {"value": k, "description": v}
                                    for k, v in question["criteria"].items()
                                ],
                            }
                        ],
                    }
                ),
                "Stage1 Decisions body",
            )
        else:
            require(
                body["input"]
                == [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": canonical(semantic).decode()}
                        ],
                    }
                ],
                "Stage1 Responses input",
            )
        exact(
            task["request"],
            {
                "method": original["method"],
                "url": original["endpoint"],
                "headers": {"Content-Type": "application/json"},
                "body": body,
            },
        )
