"""Versioned source/identity contract for unsigned offline bundles."""

from offline_bundle import (
    ADAPTER_FILES,
    MAX_FILES,
    MAX_TASKS,
    MAX_TOTAL_BYTES,
    SCHEMA,
    canonical,
    check_ref,
    decode,
    digest_value,
    identity,
    object_keys,
    require,
    sha,
)
from offline_task_contract import validate_counts, validate_tasks


def project_metadata(
    manifest, manifest_digest, inputs, json_artifact, plan_digest=None
):
    """Derive metadata from bound originals, shared by exporter and reader."""
    if manifest["schema"] == "normlab.s13-offline/v1":
        by_role = {entry["role"]: entry["artifact"] for entry in inputs}
        require(
            len(by_role) == len(inputs) and set(by_role) == set(manifest["artifacts"]),
            "S1.3 input roles",
        )
        require(
            all(
                by_role[key]["sha256"] == pin["sha256"]
                for key, pin in manifest["artifacts"].items()
            ),
            "S1.3 input binding",
        )
        dataset = {
            "id": json_artifact(by_role["sources"])["datasetId"],
            "revision": None,
            "digest": sha(
                canonical(
                    {
                        key: manifest["artifacts"][key]["sha256"]
                        for key in ("sources", "candidates")
                    }
                )
            ),
        }
        strategy = {"id": "s13-selected-claim-decomposition", "version": "1"}
        tactic = {"id": "independent-logical-jobs", "version": "1"}
        provider = manifest["providerBinding"]
        policy = {
            "planDigest": plan_digest,
            **{
                key: manifest[key]
                for key in ("caps", "noulDecision", "comparisonPolicy", "orderSeed")
            },
        }
    else:
        require(
            len(inputs) == 1 + 2 * len(manifest["cases"]),
            "Classification input coverage",
        )
        require(
            inputs[0]["role"] == "definitions"
            and inputs[0]["artifact"]["sha256"] == manifest["definitions"]["sha256"],
            "Definition binding",
        )
        rows = []
        for number, case in enumerate(manifest["cases"]):
            row = {"case": case}
            for offset, role in enumerate(("input", "parent")):
                entry = inputs[1 + 2 * number + offset]
                require(
                    entry["role"] == role
                    and entry["artifact"]["sha256"] == case[role]["sha256"],
                    "Case input binding",
                )
                row[role] = entry["artifact"]
            rows.append(row)
        dataset = {
            "id": manifest["dataset"]["id"],
            "revision": manifest["dataset"]["version"],
            "digest": sha(canonical(rows)),
        }
        strategy = {"id": manifest["strategy"], "version": None}
        tactic = {"id": manifest["tactic"], "version": None}
        provider = manifest["provider"]
        policy = {
            "mode": manifest["mode"],
            "budget": manifest["budget"],
            "definitions": inputs[0]["artifact"],
        }
    experiment = {
        "id": manifest["experimentId"],
        "manifestDigest": manifest_digest,
        "strategy": strategy,
        "tactic": tactic,
        "provider": provider,
        "policy": policy,
    }
    return dataset, experiment


def validate(envelope, fetch):
    object_keys(
        envelope,
        "schema adapter source dataset experiment run reference score records counts artifacts",
    )
    require(envelope["schema"] == SCHEMA, "Unsupported bundle schema")
    inventory = envelope["artifacts"]
    require(
        isinstance(inventory, list) and 0 < len(inventory) <= MAX_FILES, "Inventory cap"
    )
    blobs, total = {}, 0
    for ref in inventory:
        check_ref(ref)
        require(ref["path"] not in blobs, "Duplicate artifact path")
        raw = fetch(ref)
        require(
            len(raw) == ref["bytes"] and sha(raw) == ref["sha256"], "Artifact drift"
        )
        total += len(raw)
        require(total <= MAX_TOTAL_BYTES, "Bundle byte cap")
        blobs[ref["path"]] = (ref, raw)

    def artifact(ref):
        check_ref(ref)
        require(
            ref["path"] in blobs and blobs[ref["path"]][0] == ref, "Unindexed artifact"
        )
        return blobs[ref["path"]][1]

    def refs(value):
        if isinstance(value, dict):
            if set(value) == {"path", "sha256", "bytes"}:
                artifact(value)
            else:
                for child in value.values():
                    refs(child)
        elif isinstance(value, list):
            for child in value:
                refs(child)

    refs(envelope)
    run, is_s13, report = validate_metadata(envelope, artifact)
    tasks = validate_tasks(envelope, artifact, refs, run, is_s13, report)
    validate_counts(envelope["counts"], tasks)
    return envelope


def validate_metadata(envelope, artifact):
    source, run = envelope["source"], envelope["run"]
    object_keys(source, "schema manifest captures inputs")
    require(
        isinstance(source["captures"], list)
        and 0 < len(source["captures"]) <= MAX_TASKS,
        "Capture inventory",
    )
    for ref in source["captures"]:
        decode(artifact(ref))
    require(
        isinstance(source["inputs"], list) and len(source["inputs"]) <= MAX_FILES,
        "Input inventory",
    )
    for entry in source["inputs"]:
        object_keys(entry, "role artifact")
        require(isinstance(entry["role"], str), "Input role")
        decode(artifact(entry["artifact"]))
    original_manifest = decode(artifact(source["manifest"]))
    require(original_manifest["schema"] == source["schema"], "Source manifest schema")
    require(
        source["schema"]
        in {
            "normlab.evaluation-experiment/v1",
            "normlab.evaluation-experiment/v2",
            "normlab.s13-offline/v1",
        },
        "Unsupported source schema",
    )
    object_keys(
        run,
        "id identityKind evidenceKind captureDigest predictionSealDigest inferenceCallsExecuted",
    )
    require(run["identityKind"] == "legacy-bundle-derived", "Run identity provenance")
    binding = {
        "schema": source["schema"],
        "manifest": source["manifest"]["sha256"],
        "captures": source["captures"],
    }
    require(run["id"] == identity("run", binding), "Run binding")
    require(
        run["captureDigest"] == sha(canonical(source["captures"])),
        "Capture set binding",
    )
    require(run["predictionSealDigest"] == sha(canonical(binding)), "Prediction seal")
    require(
        type(run["inferenceCallsExecuted"]) is int
        and run["inferenceCallsExecuted"] == 0,
        "Offline boundary",
    )
    require(
        run["evidenceKind"]
        == (
            "offline-fixture"
            if source["schema"] == "normlab.s13-offline/v1"
            else "offline-fixed-captures"
        ),
        "Evidence kind binding",
    )
    object_keys(envelope["adapter"], "id version code")
    require(
        isinstance(envelope["adapter"]["code"], dict)
        and set(envelope["adapter"]["code"]) == set(ADAPTER_FILES),
        "Adapter code provenance",
    )
    for ref in envelope["adapter"]["code"].values():
        artifact(ref)
    require(
        envelope["adapter"]["id"] == "offline-envelope"
        and envelope["adapter"]["version"] == "1",
        "Adapter revision",
    )
    object_keys(envelope["dataset"], "id revision digest")
    require(
        isinstance(envelope["dataset"]["id"], str)
        and (
            envelope["dataset"]["revision"] is None
            or isinstance(envelope["dataset"]["revision"], str)
        ),
        "Dataset revision metadata",
    )
    require(digest_value(envelope["dataset"]["digest"]), "Dataset digest")
    object_keys(
        envelope["experiment"], "id manifestDigest strategy tactic provider policy"
    )
    require(
        envelope["experiment"]["id"] == original_manifest["experimentId"],
        "Experiment identity",
    )
    for name in ("strategy", "tactic"):
        value = envelope["experiment"][name]
        object_keys(value, "id version")
        require(
            isinstance(value["id"], str)
            and (value["version"] is None or isinstance(value["version"], str)),
            "Strategy/tactic revision",
        )
    require(
        envelope["experiment"]["manifestDigest"] == source["manifest"]["sha256"],
        "Experiment binding",
    )
    reference = envelope["reference"]
    if reference is not None:
        object_keys(reference, "id revision status artifact")
        original_reference = decode(artifact(reference["artifact"]))
        require(
            original_reference["status"] == reference["status"]
            and original_reference.get("revision") == reference["revision"],
            "Reference metadata binding",
        )
        require(
            reference["id"] == identity("reference", reference["artifact"]["sha256"]),
            "Reference identity",
        )
        require(
            reference["status"]
            in {"candidate", "candidate-not-independent", "human-adjudicated"},
            "Reference status",
        )
    score = envelope["score"]
    object_keys(score, "id report referenceId scorer scope criticalErrorFreeRate")
    object_keys(score["scorer"], "id code dependencies")
    original_report = decode(artifact(score["report"]))
    is_s13 = source["schema"] == "normlab.s13-offline/v1"
    dataset, experiment = project_metadata(
        original_manifest,
        source["manifest"]["sha256"],
        source["inputs"],
        lambda ref: decode(artifact(ref)),
        original_report.get("planDigest"),
    )
    require(
        envelope["dataset"] == dataset and envelope["experiment"] == experiment,
        "Projected dataset/experiment binding",
    )
    require(
        len(source["captures"]) == (1 if is_s13 else len(original_manifest["records"])),
        "Original capture denominator",
    )
    require(
        original_report["schema"]
        == (
            "normlab.s13-replay-report/v1" if is_s13 else "normlab.evaluation-replay/v2"
        ),
        "Scored report schema",
    )
    if is_s13:
        original_capture = decode(artifact(source["captures"][0]))
        require(
            original_manifest["mode"] == "offline-only"
            and original_manifest["authorizedLiveCalls"] == 0
            and original_manifest["providerBinding"]
            == {"supplier": None, "model": None, "modelVersion": None},
            "Frozen offline provider boundary",
        )
        require(
            original_capture["schema"] == "normlab.s13-offline-capture/v1"
            and original_capture["evidenceKind"] == "offline-fixture",
            "Original fixture provenance",
        )
        require(
            original_capture["manifestDigest"] == source["manifest"]["sha256"]
            and original_capture["planDigest"] == original_report["planDigest"],
            "Original S1.3 capture binding",
        )
        require(
            score["scope"] == "s13-selected-claims-not-whole-source-completeness"
            and score["scorer"]["id"] == "s13-selected-claim/v1",
            "S1.3 score scope",
        )
        require(
            score["scorer"]["code"]["sha256"]
            == original_manifest["codePins"]["evaluation/s13_offline.py"]
            and score["scorer"]["dependencies"] == {},
            "S1.3 scorer binding",
        )
        require(
            original_report["captureDigest"]
            == sha(canonical(decode(artifact(source["captures"][0])))),
            "Scored capture binding",
        )
        require(
            reference is not None
            and reference["artifact"]["sha256"] == original_report["referenceDigest"]
            and reference["status"] == original_report["referenceStatus"]
            and reference["revision"] == original_report["referenceRevision"],
            "Scored reference revision",
        )
    else:
        require(
            original_manifest["mode"] == "offline-replay"
            and original_manifest["budget"]["liveCalls"] == 0,
            "Classification offline boundary",
        )
        require(
            all(
                decode(artifact(ref))["schema"] == "normlab.evaluation-capture/v1"
                for ref in source["captures"]
            ),
            "Original classification capture schema",
        )
        require(
            [ref["sha256"] for ref in source["captures"]]
            == [record["capture"]["sha256"] for record in original_manifest["records"]],
            "Manifest capture pins",
        )
        require(
            score["scope"] == "classification-selected-payment-probes"
            and score["scorer"]["id"] == original_report["scorer"],
            "Classification score scope",
        )
        require(
            score["scorer"]["code"]["sha256"] == original_report["scorerDigest"]
            and {
                key: ref["sha256"]
                for key, ref in score["scorer"]["dependencies"].items()
            }
            == original_report["dependencyDigests"],
            "Classification scorer binding",
        )
        require(
            original_report["manifestDigest"] == source["manifest"]["sha256"],
            "Scored manifest binding",
        )
        require(
            original_report["labelsDigest"]
            == (reference["artifact"]["sha256"] if reference else None),
            "Scored labels binding",
        )
    require(
        score["referenceId"] == (reference["id"] if reference else None),
        "Score reference binding",
    )
    require(score["criticalErrorFreeRate"] is None, "No case-level quality claim")
    require(
        score["id"]
        == identity(
            "score",
            [
                run["id"],
                score["report"]["sha256"],
                score["referenceId"],
                envelope["adapter"],
            ],
        ),
        "Score identity",
    )
    return run, is_s13, original_report
