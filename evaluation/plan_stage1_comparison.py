"""Compile a frozen verifier comparison without SDKs, credentials or network."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from harness import digest, identifier, load_json, require

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "normlab.stage1-comparison/v1"
LABELS = ["compatible", "incompatible", "indeterminate"]
SAFE_CONVENTIONS = {
    "identityPolicy",
    "operatorPolicy",
    "scopeMeanings",
    "diagnosticPredicates",
}
SETTINGS = {
    "jev-coreinfra": {},
    "luna-low-coreinfra": {
        "reasoning": {"effort": "low"},
        "max_output_tokens": 1024,
        "store": False,
    },
    "luna-decisions-proxyapi": {},
}
PROVIDERS = {
    "jev-coreinfra": {
        "endpoint": "https://hub.coreinfra.ai/typesafe/api/v1/systemone",
        "requestedModel": "jev-1.13.0",
        "wireContract": "state-questions-choice",
        "credentialEnvironment": "COREINFRA_API_KEY",
    },
    "luna-low-coreinfra": {
        "endpoint": "https://hub.coreinfra.ai/codex/api/v1/responses",
        "requestedModel": "gpt-6-luna",
        "wireContract": "responses-json-schema",
        "credentialEnvironment": "COREINFRA_API_KEY",
    },
    "luna-decisions-proxyapi": {
        "endpoint": "https://api.proxyapi.ru/v1/decisions",
        "requestedModel": "openai/gpt-6-luna-decisions",
        "wireContract": "state-questions-choice",
        "credentialEnvironment": "PROXYAPI_API_KEY",
    },
}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def bound(entry):
    require(set(entry) == {"path", "sha256"}, "Pinned artifact reference")
    path = (ROOT / entry["path"]).resolve()
    require(
        not Path(entry["path"]).is_absolute() and path.is_relative_to(ROOT),
        "Repository artifact path",
    )
    value, raw = load_json(path)
    require(digest(raw) == entry["sha256"], "Artifact hash mismatch")
    return value


def request_body(provider, task):
    """Public wire request; adding auth and making calls belongs to a future runner."""
    if provider["wireContract"] == "state-questions-choice":
        return {"model": provider["requestedModel"], **task}
    return {
        "model": provider["requestedModel"],
        **provider["settings"],
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": canonical(task)}],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "selected_support",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"overall": {"type": "string", "enum": LABELS}},
                    "required": ["overall"],
                    "additionalProperties": False,
                },
            }
        },
    }


def prepare(path, profile):
    manifest, raw = load_json(path)
    require(
        set(manifest)
        == {
            "schema",
            "experimentId",
            "mode",
            "artifacts",
            "codePins",
            "question",
            "providers",
            "profiles",
            "policy",
        },
        "Comparison manifest fields",
    )
    require(
        manifest["schema"] == SCHEMA
        and identifier(manifest["experimentId"])
        and manifest["mode"] == "offline-plan",
        "Offline planning only",
    )
    require(
        set(manifest["codePins"])
        == {"evaluation/plan_stage1_comparison.py", "evaluation/harness.py"},
        "Planner pin coverage",
    )
    for name, expected in manifest["codePins"].items():
        require(digest((ROOT / name).read_bytes()) == expected, "Planner version drift")
    require(
        set(manifest["artifacts"])
        == {
            "datasetManifest",
            "reviewManifest",
            "sources",
            "candidates",
            "definitions",
            "conventions",
        },
        "Input artifact coverage",
    )
    data = {name: bound(entry) for name, entry in manifest["artifacts"].items()}
    dataset, review = data["datasetManifest"], data["reviewManifest"]
    require(dataset["schema"] == "normlab.stage1-audit/v2", "Reviewed dataset revision")
    require(
        review["datasetManifestDigest"]
        == manifest["artifacts"]["datasetManifest"]["sha256"]
        and review["disposition"]["annotationRegression"]
        == "resolved-under-declared-conventions",
        "Regression review binding",
    )
    require(
        review["disposition"]["labelsPromotedToExpert"] is False,
        "Candidate annotation boundary",
    )
    for name in ("sources", "candidates", "definitions", "conventions"):
        require(
            dataset["artifacts"][name]["sha256"]
            == manifest["artifacts"][name]["sha256"],
            "Dataset artifact binding",
        )
    sources, candidates = data["sources"], data["candidates"]
    require(
        candidates["sourcesDigest"] == manifest["artifacts"]["sources"]["sha256"]
        and candidates["datasetId"] == sources["datasetId"],
        "Candidate source binding",
    )
    require(
        sources["provenance"] == "authored-synthetic"
        and sources["splitPolicy"] == "diagnostic-development-only-no-holdout",
        "Diagnostic source scope",
    )
    question = manifest["question"]
    require(
        set(question) == {"type", "instructions", "criteria"}
        and question["type"] == "choice"
        and list(question["criteria"]) == LABELS,
        "Matched three-way choice",
    )
    require(
        isinstance(question["instructions"], str)
        and 0 < len(question["instructions"]) <= 4096
        and all(
            isinstance(v, str) and 0 < len(v) <= 2048
            for v in question["criteria"].values()
        ),
        "Bounded question text",
    )
    require(set(manifest["providers"]) == set(PROVIDERS), "Provider arm registry")
    for arm, expected in PROVIDERS.items():
        provider = manifest["providers"][arm]
        require(
            set(provider) == set(expected) | {"settings"}
            and all(
                provider[k] == expected[k] for k in expected if k != "requestedModel"
            )
            and canonical(provider["settings"]) == canonical(SETTINGS[arm]),
            "Declared provider route and settings",
        )
        require(
            isinstance(provider["requestedModel"], str)
            and re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}", provider["requestedModel"]
            ),
            "Explicit requested model",
        )
    policy = manifest["policy"]
    require(
        canonical(policy)
        == canonical(
            {
                "context": "fresh-single-candidate-single-turn",
                "ordering": "rotate-cases-alternate-record-and-arm-order/v1",
                "language": "ru",
                "questionOrder": ["overall"],
                "automaticRetries": 0,
                "repairCalls": 0,
                "parallelism": 1,
                "stopOn": [
                    "provider-error",
                    "invalid-output",
                    "returned-model-change",
                    "budget-exhaustion",
                    "label-leak",
                ],
                "unknownSentOutcome": "record-and-stop-no-automatic-resume",
                "criticalErrorFreeRate": None,
            }
        ),
        "Frozen execution policy",
    )
    require(profile in manifest["profiles"], "Known profile")
    selected = manifest["profiles"][profile]
    require(
        set(selected) == {"caseIds", "armIds", "repeats", "budget"}, "Profile fields"
    )
    case_ids, arms = selected["caseIds"], selected["armIds"]
    require(
        isinstance(case_ids, list)
        and len(case_ids) == len(set(case_ids))
        and 0 < len(case_ids) <= 16,
        "Distinct selected cases",
    )
    require(
        isinstance(arms, list)
        and len(arms) == len(set(arms))
        and arms
        and set(arms) <= set(PROVIDERS),
        "Distinct selected arms",
    )
    require(
        type(selected["repeats"]) is int and selected["repeats"] == 3,
        "Three fixed repeats",
    )
    budget = selected["budget"]
    require(
        set(budget)
        == {
            "maxCalls",
            "maxQuestions",
            "maxInputUtf8Bytes",
            "transportTimeoutSeconds",
            "wallDeadlineSeconds",
            "authorizedCalls",
            "monetaryCap",
            "pricingVerified",
        },
        "Declared budget fields",
    )
    require(
        all(
            type(budget[k]) is int and budget[k] > 0
            for k in (
                "maxCalls",
                "maxQuestions",
                "maxInputUtf8Bytes",
                "transportTimeoutSeconds",
                "wallDeadlineSeconds",
            )
        ),
        "Integer budget limits",
    )
    require(
        type(budget["authorizedCalls"]) is int
        and budget["authorizedCalls"] == 0
        and budget["monetaryCap"] is None
        and budget["pricingVerified"] is False,
        "Plan is not live/spend authorization",
    )
    require(
        budget["maxInputUtf8Bytes"] == 32768
        and budget["transportTimeoutSeconds"] == 30,
        "Shared request limits",
    )
    by_case = {c["id"]: c for c in sources["cases"]}
    require(set(case_ids) <= set(by_case), "Selected cases exist")
    by_record = {r["id"]: r for r in candidates["records"]}
    require(
        len(by_record) == len(candidates["records"]) == 32, "Distinct candidate records"
    )
    for cid in case_ids:
        require(
            len([r for r in by_record.values() if r["caseId"] == cid]) == 2,
            "Complete contrast pair",
        )
    conventions = {k: data["conventions"][k] for k in sorted(SAFE_CONVENTIONS)}
    jobs = []
    for repeat in range(selected["repeats"]):
        order = case_ids[repeat % len(case_ids) :] + case_ids[: repeat % len(case_ids)]
        for cid in order:
            case_index = case_ids.index(cid)
            case = by_case[cid]
            records = sorted(
                (r for r in by_record.values() if r["caseId"] == cid),
                key=lambda r: r["id"],
            )
            if (repeat + case_index) % 2:
                records.reverse()
            for record_index, record in enumerate(records):
                task = {
                    "state": {
                        "sourceText": case["sourceText"],
                        "candidateClaims": record["claims"],
                        "conventions": conventions,
                        "predicateDefinitions": data["definitions"],
                    },
                    "questions": {"overall": question},
                }
                require(
                    digest(case["sourceText"].encode()) == case["sourceDigest"],
                    "Original source digest",
                )
                require(
                    len(canonical(task).encode()) <= budget["maxInputUtf8Bytes"],
                    "Shared input byte budget",
                )
                arm_order = (
                    arms
                    if (repeat + case_index + record_index) % 2 == 0
                    else arms[::-1]
                )
                for arm in arm_order:
                    provider = manifest["providers"][arm]
                    jobs.append(
                        {
                            "jobId": f"J{len(jobs) + 1:04d}",
                            "caseId": cid,
                            "familyId": case["familyId"],
                            "recordId": record["id"],
                            "repeat": repeat + 1,
                            "armId": arm,
                            "contextId": f"context_{len(jobs) + 1:04d}",
                            "sourceDigest": case["sourceDigest"],
                            "taskDigest": digest(canonical(task).encode()),
                            "task": task,
                            "request": {
                                "method": "POST",
                                "endpoint": provider["endpoint"],
                                "body": request_body(provider, task),
                            },
                        }
                    )
    require(
        len(jobs) == budget["maxCalls"] == budget["maxQuestions"],
        "Exact calls/questions budget",
    )
    return {
        "schema": "normlab.stage1-comparison-plan/v1",
        "experimentId": manifest["experimentId"],
        "manifestDigest": digest(raw),
        "profile": profile,
        "datasetId": sources["datasetId"],
        "budget": budget,
        "jobs": jobs,
    }


def summary(plan):
    jobs = plan["jobs"]
    return {
        "schema": "normlab.stage1-comparison-plan-summary/v1",
        "experimentId": plan["experimentId"],
        "manifestDigest": plan["manifestDigest"],
        "planDigest": digest(canonical(plan).encode()),
        "profile": plan["profile"],
        "mode": "offline-plan",
        "callsExecuted": 0,
        "plannedCalls": len(jobs),
        "plannedQuestions": len(jobs),
        "cases": len({j["caseId"] for j in jobs}),
        "families": len({j["familyId"] for j in jobs}),
        "records": len({j["recordId"] for j in jobs}),
        "callsPerArm": dict(Counter(j["armId"] for j in jobs)),
        "repeats": len({j["repeat"] for j in jobs}),
        "criticalErrorFreeRate": None,
        "budget": plan["budget"],
    }


def export_plan(plan, folder):
    """Keep each JSON artifact below the common loader's 2 MiB bound."""
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    (folder / "jobs").mkdir()
    entries = []
    for job in plan["jobs"]:
        name = f"jobs/{job['jobId']}.json"
        raw = (json.dumps(job, ensure_ascii=False, indent=2) + "\n").encode()
        (folder / name).write_bytes(raw)
        entries.append({"path": name, "sha256": digest(raw)})
    raw = (json.dumps(summary(plan), ensure_ascii=False, indent=2) + "\n").encode()
    (folder / "summary.json").write_bytes(raw)
    index = {
        "schema": "normlab.stage1-comparison-export/v1",
        "plan": {k: v for k, v in plan.items() if k != "jobs"},
        "jobArtifacts": entries,
        "summaryArtifact": {"path": "summary.json", "sha256": digest(raw)},
    }
    (folder / "plan.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--profile", default="pilot")
    parser.add_argument(
        "--output",
        type=Path,
        help="New directory for inspectable planned requests; never sends them",
    )
    args = parser.parse_args()
    plan = prepare(args.manifest, args.profile)
    result = summary(plan)
    if args.output:
        export_plan(plan, args.output)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
