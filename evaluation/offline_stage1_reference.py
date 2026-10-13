"""Bounded Stage 1 candidate references, prediction seals and native score views."""

from offline_bundle import canonical, decode, identity, object_keys, read, require, sha
from offline_stage1_scoring import provider_report, retry_report
from offline_stage1_source import EVALUATION, safe_path
from plan_stage1_comparison import LABELS

ROLES = ("manifest", "parent", "dataset", "sources", "labels", "seal", "score")
REFERENCE_SCHEMA = "normlab.offline-stage1-reference/v1"


def snapshot(manifest_path, seal_path, score_path, kind, validated_binding):
    """Read only explicitly selected files and pinned provenance dependencies."""
    # Reject an unbound capture/seal before opening reviewer-only labels.
    seal_raw = read(seal_path)
    validate_seal(kind, validated_binding, seal_raw)
    root = EVALUATION.parent
    files = {"manifest": read(manifest_path)}

    def pinned(role, base, entry):
        object_keys(entry, "path sha256")
        path = (base / safe_path(entry["path"])).resolve()
        require(path.is_relative_to(base.resolve()), "Reference path containment")
        files[role] = read(path)
        require(sha(files[role]) == entry["sha256"], "Pinned reference input")
        return decode(files[role]), path

    manifest = decode(files["manifest"])
    parent, _ = pinned("parent", root, manifest["parent"])
    dataset, dataset_path = pinned(
        "dataset", root, parent["artifacts"]["datasetManifest"]
    )
    pinned("sources", root, parent["artifacts"]["sources"])
    pinned("labels", dataset_path.parent, dataset["artifacts"]["reviewer-only"])
    files["seal"], files["score"] = seal_raw, read(score_path)
    return files


def reference(files, parent):
    require(set(files) == set(ROLES), "Scoring input coverage")
    manifest, ancestor, dataset, sources, labels = (
        decode(files[role]) for role in ROLES[:5]
    )
    require(
        manifest["schema"] == "normlab.stage1-provider-experiment/v1"
        and manifest["experimentId"] == parent["experimentId"]
        and manifest["providers"] == parent["providers"]
        and sha(files["manifest"]) == parent["manifestDigest"]
        and sha(files["parent"]) == manifest["parent"]["sha256"]
        and sha(files["parent"]) == parent["parentManifestDigest"]
        and ancestor["schema"] == "normlab.stage1-comparison/v1"
        and sha(files["dataset"]) == ancestor["artifacts"]["datasetManifest"]["sha256"]
        and dataset["schema"] == "normlab.stage1-audit/v2"
        and sha(files["sources"]) == ancestor["artifacts"]["sources"]["sha256"]
        and sha(files["sources"]) == dataset["artifacts"]["sources"]["sha256"]
        and sha(files["labels"]) == dataset["artifacts"]["reviewer-only"]["sha256"],
        "Reference provenance chain",
    )
    require(
        labels["schema"] == "normlab.stage1-review/v2"
        and labels["datasetId"] == parent["datasetId"] == sources["datasetId"]
        and labels["sourcesDigest"] == sha(files["sources"])
        and labels["labelStatus"] == "candidate-not-independent"
        and labels["evaluationPolicy"] == "selected-claim-support",
        "Candidate reference status",
    )
    cases = {row["caseId"]: row for row in labels["cases"]}
    rows = {(row["caseId"], row["recordId"]): row for row in labels["records"]}
    source_cases = {row["id"]: row for row in sources["cases"]}
    require(len(cases) == len(labels["cases"]), "Unique reference cases")
    require(len(rows) == len(labels["records"]), "Unique reference records")
    require(len(source_cases) == len(sources["cases"]), "Unique source cases")
    expected = {}
    for job in parent["jobs"]:
        key = (job["caseId"], job["recordId"])
        require(rows[key]["expectation"] in LABELS, "Candidate expectation")
        require(
            cases[job["caseId"]]["sourceDigest"]
            == job["sourceDigest"]
            == source_cases[job["caseId"]]["sourceDigest"]
            and source_cases[job["caseId"]]["sourceText"]
            == job["task"]["state"]["sourceText"]
            and sha(job["task"]["state"]["sourceText"].encode()) == job["sourceDigest"]
            and source_cases[job["caseId"]]["familyId"] == job["familyId"],
            "Reference source binding",
        )
        expected[job["jobId"]] = rows[key]["expectation"]
    return rows, expected


def native_binding(kind, plan, files):
    """Derive native seal fields from the immutable snapshot after native replay."""
    index = decode(files["capture.json"])
    result = {
        "planDigest": sha(canonical(plan)),
        "captureDigest": sha(files["capture.json"]),
    }
    if kind == "provider-v1":
        return {**result, "turnArtifacts": index["turnArtifacts"]}
    children = []
    for entry in index["attempts"]:
        prefix = entry["path"] + "/"
        capture = files.get(prefix + "capture.json")
        child_plan = files.get(prefix + "plan.json")
        children.append(
            {
                "path": entry["path"],
                "captureDigest": sha(capture) if capture is not None else None,
                "planDigest": sha(child_plan) if child_plan is not None else None,
                "turnArtifacts": decode(capture)["turnArtifacts"]
                if capture is not None
                else None,
            }
        )
    return {
        **result,
        "exportedPlanDigest": sha(files["plan.json"]),
        "attemptArtifacts": children,
        "scorerCodePins": {
            name: sha(read(EVALUATION / name))
            for name in ("score_stage1_retries_v2.py", "score_stage1_providers.py")
        },
    }


def validate_seal(kind, validated_binding, raw):
    saved = decode(raw)
    object_keys(saved, "schema createdAt " + " ".join(validated_binding))
    require(
        saved["schema"]
        == (
            "normlab.stage1-prediction-seal/v1"
            if kind == "provider-v1"
            else "normlab.stage1-retry-prediction-seal/v2"
        )
        and isinstance(saved["createdAt"], str)
        and {key: saved[key] for key in validated_binding} == validated_binding,
        "Native prediction seal binding",
    )


def evaluate(builder, kind, plan, parent, root, files, validated_binding, summary):
    """Validate seal first, then labels, then regenerate every native score field."""
    validate_seal(kind, validated_binding, files["seal"])
    labels, expected = reference(files, parent)
    regenerate = provider_report if kind == "provider-v1" else retry_report
    report = regenerate(
        plan,
        root,
        files["seal"],
        labels,
        sha(files["labels"]),
        validated_binding,
        summary,
    )
    require(
        canonical(decode(files["score"])) == canonical(report), "Native score drift"
    )
    inputs = [{"role": role, "artifact": builder.add(files[role])} for role in ROLES]
    projected = {
        "schema": REFERENCE_SCHEMA,
        "status": "candidate-not-independent",
        "revision": "stage1-review/v2",
        "expected": expected,
        "labelsDigest": sha(files["labels"]),
        "provenance": {entry["role"]: entry["artifact"] for entry in inputs[:5]},
    }
    artifact = builder.json(projected)
    ref = {
        "id": identity("reference", artifact["sha256"]),
        "revision": projected["revision"],
        "status": projected["status"],
        "artifact": artifact,
    }
    return {
        "reference": ref,
        "expected": expected,
        "inputs": inputs,
        "nativeReport": builder.add(files["score"]),
        "seal": builder.add(files["seal"]),
        "nativeSchema": report["schema"],
    }
