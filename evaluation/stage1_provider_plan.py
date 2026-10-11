"""Three-arm provider plan layered over the unchanged historical Stage 1 inputs."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from harness import MAX_BYTES, digest, load_json, require
from plan_stage1_comparison import ROOT, bound, canonical
from plan_stage1_comparison import prepare as historical_prepare
from provider_config import ADAPTER_VERSION, valid_endpoint

SCHEMA = "normlab.stage1-provider-experiment/v1"
ARMS = ("jev-coreinfra", "luna-decisions-coreinfra", "luna-low-coreinfra")
FORMATS = ("typesafe-systemone", "openai-decisions", "openai-responses")


def sha(value):
    return digest(canonical(value).encode())


def request_body(provider, task):
    model = provider["model"]
    question = task["questions"]["overall"]
    if provider["apiFormat"] == "typesafe-systemone":
        return {
            "model": model,
            "state": task["state"],
            "questions": {"classification": question},
        }
    if provider["apiFormat"] == "openai-decisions":
        return {
            "model": model,
            "input": json.dumps(task["state"], ensure_ascii=False, allow_nan=False),
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
    from plan_stage1_comparison import request_body as historical_body

    return {
        **historical_body(
            {
                "requestedModel": model,
                "wireContract": "responses-json-schema",
                "settings": provider["settings"],
            },
            task,
        ),
        "stream": False,
    }


def prepare(path, profile="pilot"):
    manifest, raw = load_json(path)
    require(
        set(manifest) == {"schema", "experimentId", "parent", "codePins", "providers"},
        "Provider manifest fields",
    )
    require(
        manifest["schema"] == SCHEMA
        and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", manifest["experimentId"]),
        "Provider manifest identity",
    )
    parent = bound(manifest["parent"])
    require(
        parent["schema"] == "normlab.stage1-comparison/v1", "Historical parent required"
    )
    pins = {
        "evaluation/stage1_provider_plan.py",
        "evaluation/plan_stage1_comparison.py",
        "evaluation/harness.py",
        "evaluation/provider_config.py",
    }
    require(set(manifest["codePins"]) == pins, "Provider planner pin coverage")
    for name, expected in manifest["codePins"].items():
        require(
            digest((ROOT / name).read_bytes()) == expected,
            "Provider planner version drift",
        )
    require(profile in ("pilot", "corpus"), "Known matched profile")
    historical = historical_prepare(ROOT / manifest["parent"]["path"], profile)
    providers = manifest["providers"]
    require(set(providers) == set(ARMS), "Three matched arms required")
    for arm, api_format in zip(ARMS, FORMATS):
        p = providers[arm]
        require(
            set(p) == {"apiFormat", "endpoint", "model", "keyEnvironment", "settings"},
            "Public provider fields",
        )
        require(
            p["apiFormat"] == api_format
            and valid_endpoint(p["endpoint"]) == p["endpoint"],
            "Exact provider format/URL",
        )
        require(
            isinstance(p["model"], str)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:-]{0,199}", p["model"]),
            "Provider model",
        )
        require(
            isinstance(p["keyEnvironment"], str)
            and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", p["keyEnvironment"]),
            "Key source name",
        )
        expected = (
            {"reasoning": {"effort": "low"}, "max_output_tokens": 1024, "store": False}
            if api_format == "openai-responses"
            else {}
        )
        require(p["settings"] == expected, "Frozen sampling settings")
    # One semantic task per historical context; the two old arms have identical tasks.
    contexts = []
    for job in historical["jobs"]:
        if contexts and all(
            contexts[-1][k] == job[k] for k in ("caseId", "recordId", "repeat")
        ):
            continue
        contexts.append(job)
    jobs = []
    for number, old in enumerate(contexts):
        shift = number % len(ARMS)
        order = ARMS[shift:] + ARMS[:shift]
        for arm in order:
            provider = providers[arm]
            identity = {
                k: old[k]
                for k in (
                    "caseId",
                    "familyId",
                    "recordId",
                    "repeat",
                    "sourceDigest",
                    "taskDigest",
                    "task",
                )
            }
            jobs.append(
                {
                    **identity,
                    "jobId": f"J{len(jobs) + 1:04d}",
                    "contextId": f"context_{len(jobs) + 1:04d}",
                    "armId": arm,
                    "request": {
                        "method": "POST",
                        "endpoint": provider["endpoint"],
                        "body": request_body(provider, old["task"]),
                    },
                }
            )
    budget = {
        **historical["budget"],
        "maxCalls": len(jobs),
        "maxQuestions": len(jobs),
        "wallDeadlineSeconds": historical["budget"]["wallDeadlineSeconds"] * 3 // 2,
    }
    require(
        len(jobs) == (36 if profile == "pilot" else 288), "Complete matched denominator"
    )
    return {
        "schema": "normlab.stage1-provider-plan/v1",
        "experimentId": manifest["experimentId"],
        "manifestDigest": digest(raw),
        "parentManifestDigest": manifest["parent"]["sha256"],
        "parentPlanDigest": sha(historical),
        "profile": profile,
        "datasetId": historical["datasetId"],
        "adapterVersion": ADAPTER_VERSION,
        "providers": providers,
        "budget": budget,
        "ordering": "rotate-three-arms-per-context/v1",
        "jobs": jobs,
    }


def summary(plan):
    return {
        "schema": "normlab.stage1-provider-plan-summary/v1",
        "planDigest": sha(plan),
        "profile": plan["profile"],
        "plannedCalls": len(plan["jobs"]),
        "callsPerArm": dict(Counter(j["armId"] for j in plan["jobs"])),
        "authorizedCalls": 0,
        "budget": plan["budget"],
        "semanticQualityEvidence": False,
    }


def write_json(path, value):
    raw = (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    require(len(raw) <= MAX_BYTES, "Artifact bound")
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(raw)
    temporary.replace(path)
    return {"path": path.name, "sha256": digest(raw)}


def export(plan, folder):
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    entries = [
        write_json(folder / f"planned-{j['jobId']}.json", j) for j in plan["jobs"]
    ]
    write_json(
        folder / "plan.json",
        {"plan": {k: v for k, v in plan.items() if k != "jobs"}, "jobs": entries},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--profile", choices=("pilot", "corpus"), default="pilot")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    plan = prepare(args.manifest, args.profile)
    if args.output:
        export(plan, args.output)
    print(json.dumps(summary(plan), ensure_ascii=False))


if __name__ == "__main__":
    main()
