"""Verified immutable input and SDK-free MLflow projection; no registry writes."""

import tempfile
from contextlib import contextmanager
from pathlib import Path

from offline_bundle import (
    MAX_FILES,
    MAX_TOTAL_BYTES,
    canonical,
    check_ref,
    decode,
    identity,
    read,
    require,
    sha,
    verify,
)

SCHEMA = "normlab.mlflow-projection/v1"


@contextmanager
def snapshot(folder):
    """Verify the private bounded copy that will actually be uploaded."""
    source = folder.resolve()
    index = (source / "bundle.json").resolve()
    require(index.is_relative_to(source), "Bundle index containment")
    raw = read(index)
    envelope = decode(raw)
    inventory = envelope["artifacts"]
    require(
        isinstance(inventory, list) and 0 < len(inventory) <= MAX_FILES, "Inventory cap"
    )
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "artifacts").mkdir()
        total, seen = len(raw), set()
        for ref in inventory:
            check_ref(ref)
            require(ref["path"] not in seen, "Unique inventory")
            seen.add(ref["path"])
            path = (source / ref["path"]).resolve()
            require(path.is_relative_to(source), "Artifact containment")
            blob = read(path)
            require(
                sha(blob) == ref["sha256"] and len(blob) == ref["bytes"],
                "Artifact drift",
            )
            total += len(blob)
            require(total <= MAX_TOTAL_BYTES, "Snapshot byte cap")
            (root / ref["path"]).write_bytes(blob)
        (root / "bundle.json").write_bytes(raw)
        verified = verify(root)
        yield root, verified, sha(raw)


def numeric(value, prefix):
    """Only known numeric counts become metrics; null and booleans stay in evidence."""
    result = {}
    for key, item in value.items():
        name = prefix + "." + key
        if isinstance(item, dict):
            result.update(numeric(item, name))
        elif type(item) in (int, float):
            result[name] = item
    return result


def requested_models(value):
    models = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"model", "requestedModel"} and isinstance(item, str):
                models.add(item)
            else:
                models.update(requested_models(item))
    elif isinstance(value, list):
        for item in value:
            models.update(requested_models(item))
    return models


def project(root, envelope, bundle_digest):
    def value(ref):
        return decode(read(root / ref["path"]))

    source, run, score = envelope["source"], envelope["run"], envelope["score"]
    reference = envelope["reference"]
    parent = {
        "schema": SCHEMA,
        "kind": "capture",
        "run": run,
        "source": {key: source[key] for key in ("schema", "manifest", "captures")},
        "dataset": envelope["dataset"],
        "experiment": envelope["experiment"],
        "counts": envelope["counts"],
    }
    outcomes = []
    for ref in envelope["records"]:
        task = value(ref)
        row = value(task["scoreArtifact"])
        completed = task["turn"]["status"] == "completed"
        passed = None
        if completed and reference:
            if source["schema"] == "normlab.offline-stage1-source/v1":
                passed = row["selectedReferencePass"]
            elif source["schema"] == "normlab.s13-offline/v1":
                agreements = [q["agreement"] for q in row["questions"]]
                passed = all(agreements) if agreements else None
            else:
                passed = row["probePass"]
        require(passed is None or type(passed) is bool, "Selected-reference outcome")
        outcomes.append(passed)
    scored = sum(passed is not None for passed in outcomes)
    passed = sum(passed is True for passed in outcomes)
    summary = {
        "scope": "completed-selected-reference-scored-logical-tasks",
        "planned": len(outcomes),
        "scored": scored,
        "passed": passed,
        "notEvaluated": len(outcomes) - scored,
        "agreementAmongScored": passed / scored if scored else None,
        "criticalErrorFreeRate": None,
    }
    view = {
        "schema": SCHEMA,
        "kind": "score",
        "runId": run["id"],
        "score": score,
        "reference": reference,
        "bundleDigest": bundle_digest,
        "summary": summary,
        "navigation": {
            "bundleIndex": "bundle/bundle.json",
            "sourceManifest": "bundle/" + source["manifest"]["path"],
            "rawCaptures": ["bundle/" + ref["path"] for ref in source["captures"]],
            "nativeReport": "bundle/" + score["report"]["path"],
            "reference": "bundle/" + reference["artifact"]["path"]
            if reference
            else None,
        },
    }
    experiment = envelope["experiment"]
    params = {
        "dataset_id": envelope["dataset"]["id"],
        "dataset_digest": envelope["dataset"]["digest"],
        "dataset_revision": canonical(envelope["dataset"]["revision"]).decode(),
        "strategy_id": experiment["strategy"]["id"],
        "strategy_version": canonical(experiment["strategy"]["version"]).decode(),
        "tactic_id": experiment["tactic"]["id"],
        "tactic_version": canonical(experiment["tactic"]["version"]).decode(),
        "provider_config_digest": sha(canonical(experiment["provider"])),
        "requested_models": canonical(
            sorted(requested_models(experiment["provider"]))
        ).decode(),
        "policy_digest": sha(canonical(experiment["policy"])),
    }

    def record(kind, original_id, payload, metrics, extra_params):
        return {
            "key": identity("import", [kind, original_id]),
            "originalId": original_id,
            "kind": kind,
            "digest": sha(canonical(payload)),
            "payload": payload,
            "metrics": metrics,
            "params": {**params, **extra_params},
        }

    return (
        record(
            "capture", run["id"], parent, numeric(envelope["counts"], "capture"), {}
        ),
        record(
            "score",
            score["id"],
            view,
            numeric(summary, "selected_reference"),
            {
                "score_id": score["id"],
                "scorer_id": score["scorer"]["id"],
                "scorer_code_digest": score["scorer"]["code"]["sha256"],
                "scorer_dependencies_digest": sha(
                    canonical(score["scorer"]["dependencies"])
                ),
                "adapter_version": envelope["adapter"]["version"],
                "reference_status": reference["status"]
                if reference
                else "not-evaluated",
                "reference_id": reference["id"] if reference else "unavailable",
                "reference_revision": canonical(
                    reference["revision"] if reference else None
                ).decode(),
                "bundle_digest": bundle_digest,
            },
        ),
    )
