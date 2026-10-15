"""Offline Stage1 compiler; retain exact requests and chunk source-plan provenance."""

import json
from pathlib import Path

from execution_checkpoint import DurableWriter
from execution_live_kernel import requirements
from execution_plan import Store, dry_run, prepare
from execution_records import CLOCK, CONTEXT, RETRY, integer, text
from offline_bundle import canonical, object_keys, require, sha
from stage1_provider_plan import ARMS, request_body
from stage1_provider_plan import prepare as stage1_prepare

PROTOCOLS = (
    "typesafe-systemone/v1",
    "openai-decisions-input/v1",
    "openai-responses-stage1/v1",
)


def ordered(value):
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode()


class Artifacts:
    def __init__(self):
        self.files = {}

    def put(self, value, *, raw=False):
        data = value if raw else ordered(value)
        ref = {
            "path": f"artifacts/{sha(data)}.blob",
            "sha256": sha(data),
            "bytes": len(data),
        }
        self.files[ref["path"]] = data
        return ref


def build(source, options, manifest_raw):
    """Deterministic projection; source must originate from the pinned producer."""
    object_keys(options, "acceptedModels inputTokenCap decisionOutputTokenCap")
    object_keys(options["acceptedModels"], " ".join(ARMS))
    integer(options["inputTokenCap"], 1)
    integer(options["decisionOutputTokenCap"], 1)
    require(source["schema"] == "normlab.stage1-provider-plan/v1", "Stage1 source plan")
    require(
        source["manifestDigest"] == sha(manifest_raw), "Stage1 source manifest digest"
    )
    budget = source["budget"]
    require(
        len(source["jobs"]) == budget["maxCalls"] == budget["maxQuestions"],
        "Complete source denominator",
    )
    artifacts = Artifacts()
    pins = requirements()
    source_digest = sha(canonical(source))
    definition = {
        "schema": "normlab.stage1-native-lineage/v1",
        "sourcePlanDigest": source_digest,
        "manifest": artifacts.put(manifest_raw, raw=True),
        "metadata": {k: v for k, v in source.items() if k != "jobs"},
        "jobs": [artifacts.put(job) for job in source["jobs"]],
        "options": options,
    }
    question = source["jobs"][0]["task"]["questions"]["overall"]
    labels = list(question["criteria"])
    answer_schema = {
        "schema": "normlab.execution-answer-schema/v1",
        "questions": [{"id": "classification", "type": "choice", "labels": labels}],
    }
    arms = []
    for identifier, protocol in zip(ARMS, PROTOCOLS):
        provider = source["providers"][identifier]
        models = options["acceptedModels"][identifier]
        require(
            isinstance(models, list)
            and 0 < len(models) <= 32
            and len(set(models)) == len(models),
            "Explicit model acceptance set",
        )
        for model in models:
            text(model)
        output_cap = (
            1024 if identifier == ARMS[2] else options["decisionOutputTokenCap"]
        )
        arms.append(
            {
                "id": identifier,
                "provider": identifier,
                "protocol": protocol,
                "endpoint": provider["endpoint"],
                "model": provider["model"],
                "acceptedModels": models,
                "settings": {
                    "temperature": None,
                    "reasoningEffort": "low" if identifier == ARMS[2] else None,
                    "maxOutputTokens": output_cap,
                },
                "adapter": pins["adapter"],
                "requestCaps": {
                    "dispatches": 1,
                    "questions": 1,
                    "inputTokens": options["inputTokenCap"],
                    "outputTokens": output_cap,
                },
                "timeoutNs": budget["transportTimeoutSeconds"] * 1_000_000_000,
            }
        )
    tasks = []
    for job in source["jobs"]:
        require(
            job["task"]["questions"]["overall"] == question, "Frozen shared question"
        )
        require(sha(canonical(job["task"])) == job["taskDigest"], "Source task digest")
        state = job["task"]["state"]
        require(
            sha(state["sourceText"].encode()) == job["sourceDigest"],
            "Source text digest",
        )
        original = job["request"]
        provider = source["providers"][job["armId"]]
        require(
            original["method"] == "POST"
            and original["endpoint"] == provider["endpoint"]
            and ordered(original["body"])
            == ordered(request_body(provider, job["task"])),
            "Exact source task/provider request binding",
        )
        request = artifacts.put(
            {
                "method": original["method"],
                "url": original["endpoint"],
                "headers": {"Content-Type": "application/json"},
                "body": original["body"],
            }
        )
        source_ref = artifacts.put(state["sourceText"].encode(), raw=True)
        candidate = artifacts.put(state["candidateClaims"])
        context = artifacts.put(
            {
                "policy": CONTEXT,
                "sourceDigest": source_ref["sha256"],
                "candidateDigest": candidate["sha256"],
                "requestDigest": request["sha256"],
                "questionIds": ["classification"],
                "parentTurnIds": [],
                "history": [],
            }
        )
        tasks.append(
            {
                "key": job["jobId"],
                "caseId": job["caseId"] + "/" + job["recordId"],
                "armId": job["armId"],
                "repeat": job["repeat"],
                "stage": "selected-support",
                "source": source_ref,
                "candidate": candidate,
                "request": request,
                "context": context,
                "questionIds": ["classification"],
            }
        )

    def revision(identifier, digest):
        return {"id": identifier, "revision": "stage1-native/v1", "sha256": digest}

    max_output = max(a["requestCaps"]["outputTokens"] for a in arms)
    plan = {
        "schema": "normlab.execution-plan/v1",
        "experiment": revision(source["experimentId"], source["manifestDigest"]),
        "dataset": revision(source["datasetId"], source["parentManifestDigest"]),
        "strategy": revision("stage1-selected-support", sha(canonical(question))),
        "tactic": revision(source["ordering"], source_digest),
        "pins": {
            "definitions": artifacts.put(definition),
            "prompt": artifacts.put(question),
            "outputSchema": artifacts.put(answer_schema),
            "code": pins["code"],
            "dependencies": pins["dependencies"],
        },
        "arms": arms,
        "tasks": tasks,
        "caps": {
            "dispatches": budget["maxCalls"],
            "questions": budget["maxQuestions"],
            "inputTokens": budget["maxCalls"] * options["inputTokenCap"],
            "outputTokens": budget["maxCalls"] * max_output,
        },
        "wallTimeNs": budget["wallDeadlineSeconds"] * 1_000_000_000,
        "contextPolicy": CONTEXT,
        "retryPolicy": RETRY,
        "clockPolicy": CLOCK,
    }
    return plan, artifacts.files


def compile_stage1(manifest, output, options, *, profile="pilot"):
    manifest = Path(manifest)
    source = stage1_prepare(manifest, profile)
    raw = manifest.read_bytes()
    plan, files = build(source, options, raw)
    with DurableWriter(output) as writer:
        for data in files.values():
            writer.put(data, phase="compiler-artifact")
        # Retain dictionary/choice order in artifacts; canonical plan contains only refs.
        writer.publish("plan.json", canonical(plan), phase="compiler-plan")
        verify_stage1(Store(writer.root))
    return dry_run(plan)


def verify_stage1(store):
    """Unsigned internal lineage consistency; no provider calls or current authority."""
    plan = prepare(store)
    lineage = store.value(plan["pins"]["definitions"])
    object_keys(lineage, "schema sourcePlanDigest manifest metadata jobs options")
    require(lineage["schema"] == "normlab.stage1-native-lineage/v1", "Stage1 lineage")
    source = {
        **lineage["metadata"],
        "jobs": [store.value(ref) for ref in lineage["jobs"]],
    }
    require(
        sha(canonical(source)) == lineage["sourcePlanDigest"],
        "Source plan lineage digest",
    )
    expected, files = build(
        source, lineage["options"], store.artifact(lineage["manifest"])
    )
    require(canonical(plan) == canonical(expected), "Regenerated Stage1 native plan")
    for name, data in files.items():
        require(store.read(name) == data, "Exact source projection artifact")
    return plan, source
