"""Portable projection of saved Stage 1 provider v1 / retry v2 transport evidence."""

from pathlib import Path, PurePosixPath

from offline_bundle import (
    ADAPTER_FILES,
    MAX_FILES,
    MAX_TASKS,
    MAX_TOTAL_BYTES,
    canonical,
    decode,
    object_keys,
    read,
    require,
    sha,
)

SOURCE_SCHEMA = "normlab.offline-stage1-source/v1"
NATIVE_FILES = (
    "harness.py",
    "mellea_candidate.py",
    "classification_v3.py",
    "anchor.py",
    "plan_stage1_comparison.py",
    "provider_config.py",
    "stage1_provider_plan.py",
    "stage1_provider_executor.py",
    "stage1_provider_wire.py",
    "stage1_wire_v2.py",
    "stage1_retry_executor_v2.py",
    "score_stage1_providers.py",
    "score_stage1_retries_v2.py",
)
READER_FILES = (
    *ADAPTER_FILES,
    "offline_stage1.py",
    "offline_stage1_source.py",
    "offline_stage1_reference.py",
    "offline_stage1_scoring.py",
    *NATIVE_FILES,
)
EVALUATION = Path(__file__).resolve().parent
READER_ASSETS = ("server/inference-prompts.json",)


def safe_path(name):
    path = PurePosixPath(name)
    require(
        isinstance(name, str)
        and name == str(path)
        and not path.is_absolute()
        and all(p not in {".", ".."} for p in path.parts)
        and "\\" not in name,
        "Snapshot relative path",
    )
    return path


def snapshot(folder):
    """Copy only indexed JSON; never include adjacent credentials or execute code."""
    root = folder.resolve()
    files, total = {}, 0

    def add(name):
        nonlocal total
        safe_path(name)
        path = (root / name).resolve()
        require(path.is_relative_to(root), "Snapshot escapes capture")
        if name not in files:
            require(len(files) < MAX_FILES, "Snapshot file cap")
            files[name] = read(path)
            total += len(files[name])
            require(total <= MAX_TOTAL_BYTES, "Snapshot byte cap")
        return decode(files[name])

    def provider(prefix):
        plan = add(prefix + "plan.json")
        for ref in plan["jobs"]:
            add(prefix + ref["path"])
        if (root / (prefix + "capture.json")).exists():
            capture = add(prefix + "capture.json")
            for ref in capture["turnArtifacts"]:
                add(prefix + ref["path"])

    index = add("capture.json")
    retry = index["schema"] == "normlab.stage1-retry-capture/v2"
    require(
        retry or index["schema"] == "normlab.stage1-provider-capture/v1",
        "Unsupported Stage 1 capture",
    )
    if retry:
        header = add("plan.json")
        for ref in header["jobs"]:
            add(ref["path"])
        for entry in index["attempts"]:
            prefix = entry["path"] + "/"
            safe_path(prefix + "capture.json")
            if (root / (prefix + "plan.json")).exists():
                provider(prefix)
            else:
                require(
                    not (root / (prefix + "capture.json")).exists(),
                    "Child capture requires a plan",
                )
    else:
        provider("")
    return "retry-v2" if retry else "provider-v1", files


def restore(files, root):
    for name, raw in files.items():
        path = root / safe_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def validate_plan(plan):
    """Validate saved logical/wire bindings; does not regenerate a source corpus."""
    from provider_config import ADAPTER_VERSION, valid_endpoint
    from stage1_provider_plan import ARMS, FORMATS, request_body

    object_keys(
        plan,
        "schema experimentId manifestDigest parentManifestDigest parentPlanDigest profile datasetId adapterVersion providers budget ordering jobs",
    )
    require(plan["schema"] == "normlab.stage1-provider-plan/v1", "Provider plan")
    require(set(plan["providers"]) == set(ARMS), "Provider arms")
    require(plan["adapterVersion"] == ADAPTER_VERSION, "Supported adapter version")
    for arm in ARMS:
        provider = plan["providers"][arm]
        object_keys(provider, "apiFormat endpoint model keyEnvironment settings")
        require(
            valid_endpoint(provider["endpoint"]) == provider["endpoint"],
            "Public endpoint",
        )
    jobs = plan["jobs"]
    require(0 < len(jobs) <= MAX_TASKS, "Stage 1 task cap")
    require(
        plan["profile"] in {"pilot", "corpus"}
        and len(jobs) == (36 if plan["profile"] == "pilot" else 288),
        "Matched profile denominator",
    )
    seen, cases, contexts = set(), {}, {}
    for number, job in enumerate(jobs, 1):
        require(
            job["jobId"] == f"J{number:04d}"
            and job["contextId"] == f"context_{number:04d}"
            and job["armId"] in plan["providers"],
            "Saved job order/arm",
        )
        key = (job["caseId"], job["recordId"], job["armId"], job["repeat"])
        require(key not in seen, "Duplicate semantic task")
        seen.add(key)
        semantic_key = (job["caseId"], job["recordId"], job["repeat"])
        context = (job["familyId"], job["sourceDigest"], job["taskDigest"])
        require(
            contexts.setdefault(semantic_key, context) == context,
            "Matched task bindings",
        )
        require(type(job["repeat"]) is int and job["repeat"] > 0, "Repetition")
        source_text = job["task"]["state"]["sourceText"]
        require(isinstance(source_text, str), "Source text string")
        require(
            job["taskDigest"] == sha(canonical(job["task"]))
            and job["sourceDigest"] == sha(source_text.encode()),
            "Logical source/task digest",
        )
        provider = plan["providers"][job["armId"]]
        require(
            provider["apiFormat"] == FORMATS[ARMS.index(job["armId"])]
            and job["request"]
            == {
                "method": "POST",
                "endpoint": provider["endpoint"],
                "body": request_body(provider, job["task"]),
            },
            "Planned wire request binding",
        )
        metadata = (job["familyId"], job["sourceDigest"])
        require(cases.setdefault(job["caseId"], metadata) == metadata, "Case lineage")
    require(len(seen) == len(contexts) * len(ARMS), "All arms per semantic task")


def native(kind, folder):
    from harness import artifact, load_json
    from stage1_provider_executor import code_pins
    from stage1_provider_executor import replay as provider_replay
    from stage1_retry_executor_v2 import POLICY, read_plan, replay

    if kind == "retry-v2":
        plan = read_plan(folder)
        parent = plan["parent"]
    else:
        saved, _ = load_json(folder / "plan.json")
        plan = {
            **saved["plan"],
            "jobs": [artifact(folder.resolve(), ref) for ref in saved["jobs"]],
        }
        parent = plan
    validate_plan(parent)
    if kind == "retry-v2":
        require(
            plan["parentDigest"] == sha(canonical(parent))
            and plan["retryPolicy"] == POLICY
            and plan["codePins"]
            == {
                **code_pins(),
                "stage1_retry_executor_v2.py": sha(
                    read(EVALUATION / "stage1_retry_executor_v2.py")
                ),
            }
            and plan["budget"]
            == {
                **parent["budget"],
                "maxCalls": len(parent["jobs"]) * POLICY["maxAttemptsPerJob"],
                "maxQuestions": len(parent["jobs"]) * POLICY["maxAttemptsPerJob"],
            },
            "Frozen retry plan policy/code binding",
        )
    summary = (
        replay(plan, folder) if kind == "retry-v2" else provider_replay(plan, folder)
    )
    return plan, parent, summary
