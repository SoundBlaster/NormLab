"""Bounded local execution input reader and SDK-free plan/dry-run projection."""

import json
import os
import stat
from pathlib import Path
from uuid import uuid4

from execution_outcomes import answer_schema
from execution_records import (
    CAP_FIELDS,
    CONTEXT,
    MAX_ATTEMPTS,
    PREFIX,
    PROTOCOL_FIELDS,
    caps,
    identities,
    items,
    plan_shape,
    run_shape,
    text,
    wire_settings,
)
from offline_bundle import (
    MAX_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    canonical,
    check_ref,
    object_keys,
    require,
    sha,
)

MISSING_CAPABILITIES = [
    "durable-writer/v1",
    "single-worker-dispatch/v1",
    "runtime-clock-attestation/v1",
    "provider-wire-normalization/v1",
    "resume-resolution-application/v1",
]
MAX_JOURNAL_BYTES = 16 * 1024 * 1024


class Store:
    """Read each bounded regular local file once; never resolve network references."""

    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        require(self.root.is_dir(), "Execution input directory")
        self.files = {}
        self.total = 0

    def read(self, name):
        require(
            name in {"plan.json", "run.json", "journal.json", "resolution.json"}
            or (
                isinstance(name, str)
                and name.startswith("artifacts/")
                and len(Path(name).parts) == 2
            ),
            "Execution input path",
        )
        if name not in self.files:
            path = self.root / name
            limit = MAX_JOURNAL_BYTES if name == "journal.json" else MAX_BYTES
            require(
                not path.parent.is_symlink()
                and path.resolve().is_relative_to(self.root),
                "Input escapes execution root",
            )
            with os.fdopen(
                os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb"
            ) as handle:
                metadata = os.fstat(handle.fileno())
                require(
                    stat.S_ISREG(metadata.st_mode) and metadata.st_size <= limit,
                    "Bounded regular execution file",
                )
                raw = handle.read(limit + 1)
            require(len(raw) <= limit, "Input grew beyond cap")
            require(len(self.files) < MAX_FILES, "Execution file count cap")
            self.total += len(raw)
            require(self.total <= MAX_TOTAL_BYTES, "Execution byte cap")
            self.files[name] = raw
        return self.files[name]

    def json(self, name):
        return self.decode_json(self.read(name))

    @staticmethod
    def decode_json(raw):
        def pairs(entries):
            result = {}
            for key, child in entries:
                require(key not in result, "Duplicate JSON key")
                result[key] = child
            return result

        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
        canonical(
            value
        )  # Reject exponent overflow/nonfinite values and invalid Unicode.
        return value

    def artifact(self, ref):
        check_ref(ref)
        raw = self.read(ref["path"])
        require(
            len(raw) == ref["bytes"] and sha(raw) == ref["sha256"], "Artifact drift"
        )
        return raw

    def value(self, ref):
        return self.decode_json(self.artifact(ref))


def public(value, depth=0):
    """Reject credential-bearing structured fields; never scan or rewrite source prose."""
    require(depth <= 32, "Public request nesting cap")
    if isinstance(value, dict):
        for key, child in value.items():
            require(isinstance(key, str), "JSON object key")
            name = "".join(
                character for character in key.lower() if character.isalnum()
            )
            require(
                name
                not in {
                    "authorization",
                    "apikey",
                    "xapikey",
                    "accesstoken",
                    "refreshtoken",
                    "password",
                    "secret",
                },
                "Credentials forbidden in public request",
            )
            public(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            public(child, depth + 1)


def prepare(store):
    plan = store.json("plan.json")
    arms = plan_shape(plan)
    for key in ("definitions", "prompt", "outputSchema"):
        store.artifact(plan["pins"][key])
    questions = answer_schema(store.value(plan["pins"]["outputSchema"]))
    for task in plan["tasks"]:
        require(
            all(key in questions for key in task["questionIds"]),
            "Question schema coverage",
        )
        for key in ("source", "candidate"):
            store.artifact(task[key])
        context = store.value(task["context"])
        require(
            context
            == {
                "policy": CONTEXT,
                "sourceDigest": task["source"]["sha256"],
                "candidateDigest": task["candidate"]["sha256"],
                "requestDigest": task["request"]["sha256"],
                "questionIds": task["questionIds"],
                "parentTurnIds": [],
                "history": [],
            },
            "Exact independent public context binding",
        )
        request = store.value(task["request"])
        object_keys(request, "method url headers body")
        arm = arms[task["armId"]]
        require(
            request["method"] == "POST"
            and request["url"] == arm["endpoint"]
            and request["headers"] == {"Content-Type": "application/json"}
            and isinstance(request["body"], dict)
            and request["body"].get("model") == arm["model"],
            "Public wire route/model binding",
        )
        public(request["body"])
        body = request["body"]
        settings = wire_settings(arm)
        require(
            set(body) <= set(settings) | PROTOCOL_FIELDS[arm["protocol"]]
            and all(
                key in body and canonical(body[key]) == canonical(value)
                for key, value in settings.items()
            ),
            "Exact public wire settings; unplanned fields forbidden",
        )
        if arm["protocol"] in {
            "openai-decisions-input/v1",
            "openai-responses-stage1/v1",
        }:
            from execution_stage1_protocol import validate

            validate(
                body,
                task,
                questions,
                store.decode_json,
                store.value(plan["pins"]["prompt"]),
            )
        elif arm["protocol"] in {"typesafe-systemone/v1", "openai-decisions/v1"}:
            require(
                isinstance(body.get("state"), (str, dict))
                and body["state"]
                and isinstance(body.get("questions"), dict),
                "Decision public state/questions",
            )
            require(
                list(body["questions"]) == task["questionIds"], "Wire question order"
            )
            for key, question in body["questions"].items():
                require(
                    isinstance(question, dict)
                    and {"type", "instructions"}
                    <= set(question)
                    <= {"type", "instructions", "criteria"}
                    and question.get("type") == questions[key]["type"],
                    "Wire question type",
                )
                text(question["instructions"])
                definition, criteria = questions[key], question.get("criteria")
                if definition["type"] == "choice":
                    require(
                        isinstance(criteria, dict)
                        and list(criteria) == definition["labels"],
                        "Wire choice labels/order",
                    )
                    for instructions in criteria.values():
                        text(instructions)
                elif definition["type"] == "score":
                    require(criteria == definition["labels"], "Wire score scale/order")
                elif "criteria" in question:
                    object_keys(criteria, "true false")
                    for instructions in criteria.values():
                        text(instructions)
        elif arm["protocol"] == "openai-chat-completions/v1":
            items(body.get("messages"), 1)
            for message in body["messages"]:
                object_keys(message, "role content")
                require(
                    message["role"] in ("system", "developer", "user", "assistant")
                    and isinstance(message["content"], str),
                    "Text-only public messages",
                )
        else:
            require(
                isinstance(body.get("input"), (str, list)) and body["input"],
                "Exact public Responses input",
            )
    return plan


def charge(plan, task):
    arm = next(arm for arm in plan["arms"] if arm["id"] == task["armId"])
    return {
        **arm["requestCaps"],
        "questions": len(task["questionIds"]),
    }


def dry_run(plan):
    """Report ceilings, never permission; the plan must already pass prepare()."""
    maximum = {key: 0 for key in CAP_FIELDS.split()}
    for task in plan["tasks"]:
        for key, count in charge(plan, task).items():
            maximum[key] += MAX_ATTEMPTS * count
    return {
        "schema": PREFIX + "dry-run/v1",
        "planDigest": sha(canonical(plan)),
        "tasks": len(plan["tasks"]),
        "turns": len(plan["tasks"]),
        "questions": sum(len(task["questionIds"]) for task in plan["tasks"]),
        "maximumAttemptsBeforeCaps": MAX_ATTEMPTS * len(plan["tasks"]),
        "ceilings": {
            key: min(count, plan["caps"][key]) for key, count in maximum.items()
        },
        "wallTimeNs": plan["wallTimeNs"],
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


def new_run(plan, clock, *, evidence_kind, permit=None, predecessor=None):
    """Allocate an intent; bind its live permit after UUID allocation, before replay."""
    plan_shape(plan)
    identifier = str(uuid4())
    zero = {key: 0 for key in CAP_FIELDS.split()}
    caps(zero)
    from execution_records import clock as validate_clock

    validate_clock(clock, plan["wallTimeNs"])
    run = {
        "schema": PREFIX + "run/v1",
        "id": identifier,
        "initialInvocationId": str(uuid4()),
        "identityKind": "runtime-allocated",
        "evidenceKind": evidence_kind,
        "planDigest": sha(canonical(plan)),
        "clock": clock,
        "tasks": identities(plan, identifier),
        "permit": permit,
        "predecessor": predecessor,
        "journalHead": None,
        "lastClockNs": clock["startNs"],
        "state": "created",
        "stopReason": None,
        "counts": {
            "reserved": zero,
            "observedDispatches": 0,
            "knownInputTokens": 0,
            "knownOutputTokens": 0,
            "unknownUsageAttempts": 0,
        },
    }
    run_shape(run, plan)
    if evidence_kind == "mock":
        require(permit is None, "Mocks cannot consume a live permit")
    if permit is not None:
        check_ref(permit)
    # No state is persisted and this declaration cannot establish clock support.
    return run
