"""SDK-free registry import planning; never creates a registry or writes receipts."""

from execution_records import digest, items, text
from offline_bundle import (
    MAX_BYTES,
    MAX_FILES,
    canonical,
    identity,
    object_keys,
    require,
    sha,
)
from runtime_capture import capture_runtime
from runtime_export import RuntimeExportProjection, prepare_export

NODE_FIELDS = "key kind parentKey bindingDigest"
KINDS = {"execution", "capture", "projection", "prediction-seal"}


def execution_binding(projection):
    manifest, snapshot = projection.manifest, projection.snapshot
    execution = {
        "executionId": manifest["executionId"],
        "planDigest": manifest["planDigest"],
        "intentDigest": sha(snapshot.files["intent.json"]),
    }
    if manifest["evidenceKind"] == "mock":
        execution["scriptDigest"] = sha(snapshot.files["mock-script.json"])
    else:
        execution.update(
            evidenceKind="live-capture",
            codePins=snapshot.plan["pins"]["code"],
            dependencyPins=snapshot.plan["pins"]["dependencies"],
            adapterPins=[arm["adapter"] for arm in snapshot.plan["arms"]],
        )
    return execution


def registry_nodes(projection):
    manifest, snapshot = projection.manifest, projection.snapshot
    execution = execution_binding(projection)
    parent = {
        "key": identity("execution-import", manifest["executionId"]),
        "kind": "execution",
        "parentKey": None,
        "bindingDigest": sha(canonical(execution)),
    }
    capture = {
        "key": identity(
            "capture-import", [manifest["executionId"], manifest["captureRevisionId"]]
        ),
        "kind": "capture",
        "parentKey": parent["key"],
        "bindingDigest": sha(canonical(snapshot.manifest)),
    }
    view = {
        "key": identity("projection-import", manifest["projectionId"]),
        "kind": "projection",
        "parentKey": capture["key"],
        "bindingDigest": sha(canonical(manifest)),
    }
    nodes = [parent, capture, view]
    seal = manifest["predictionSeal"]
    if seal["status"] == "sealed":
        nodes.append(
            {
                "key": identity("seal-import", seal["id"]),
                "kind": "prediction-seal",
                "parentKey": capture["key"],
                "bindingDigest": seal["artifact"]["sha256"],
            }
        )
    return nodes


def reconcile(nodes, receipts):
    items(receipts, maximum=MAX_FILES)
    require(len(canonical(receipts)) <= MAX_BYTES, "Registry receipt byte cap")
    existing = {}
    for receipt in receipts:
        object_keys(receipt, NODE_FIELDS)
        text(receipt["key"])
        require(receipt["kind"] in KINDS, "Registry receipt kind")
        digest(receipt["bindingDigest"])
        if receipt["parentKey"] is not None:
            text(receipt["parentKey"])
        require(receipt["key"] not in existing, "Ambiguous duplicate registry receipt")
        existing[receipt["key"]] = receipt
    actions = []
    for node in nodes:
        found = existing.get(node["key"])
        require(
            found is None or canonical(found) == canonical(node),
            "Registry immutable key binding conflict",
        )
        actions.append(
            {"key": node["key"], "action": "reuse" if found is not None else "create"}
        )
    return actions


def registry_dry_run(projection, receipts=None):
    require(
        type(projection) is RuntimeExportProjection,
        "Verified runtime projection required",
    )
    receipts = [] if receipts is None else receipts
    nodes = registry_nodes(projection)
    manifest = projection.manifest
    plan = {
        "schema": "normlab.runtime-registry-plan/v1",
        "planId": None,
        "executionId": manifest["executionId"],
        "captureRevisionId": manifest["captureRevisionId"],
        "projectionId": manifest["projectionId"],
        "nodes": nodes,
        "actions": reconcile(nodes, receipts),
        "metrics": manifest["counts"],
        "navigation": {
            "captureManifest": manifest["captureManifest"],
            "taskRecords": manifest["records"],
            "predictionSeal": manifest["predictionSeal"],
            "sourceFiles": projection.snapshot.manifest["sourceFiles"],
        },
        "reference": None,
        "score": None,
        "actualCost": None,
        "registryWritesExecuted": 0,
        "inferenceCallsExecuted": 0,
        "releaseApproved": False,
        "executionReady": False,
        "semanticQualityEvidence": False,
    }
    if manifest["evidenceKind"] == "live-capture":
        plan["schema"] = "normlab.runtime-registry-plan/v2"
        plan["evidenceKind"] = "live-capture"
    plan["planId"] = identity(
        "registry-plan", {key: value for key, value in plan.items() if key != "planId"}
    )
    require(len(canonical(plan)) <= MAX_BYTES, "Registry plan byte cap")
    return plan


def verify_registry_plan(root, plan, receipts=None):
    kind = plan.get("evidenceKind", "mock")
    require(
        (plan.get("schema"), kind)
        in {
            ("normlab.runtime-registry-plan/v1", "mock"),
            ("normlab.runtime-registry-plan/v2", "live-capture"),
        },
        "Registry plan schema/evidence kind",
    )
    expected = registry_dry_run(
        prepare_export(capture_runtime(root, evidence_kind=kind)), receipts
    )
    require(canonical(plan) == canonical(expected), "Runtime registry plan binding")
    return expected
