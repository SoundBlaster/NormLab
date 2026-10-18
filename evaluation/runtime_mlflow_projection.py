"""SDK-free consumer projection of verified mock archives; no score is invented."""

import tempfile
from contextlib import contextmanager
from pathlib import Path

from offline_bundle import canonical, decode, identity, require, sha
from offline_mlflow_projection import numeric
from runtime_consumer_v4 import read_archive, verified_archive, version
from runtime_registry import execution_binding, registry_nodes

SCHEMA = "normlab.runtime-mlflow-projection/v1"


def archive_files(archive):
    require(verified_archive(archive), "Verified runtime archive required")
    return {
        **archive.files,
        "archive.json": canonical(archive.index),
        ".writer.lock": b"",
    }


@contextmanager
def snapshot(directory):
    """Upload a private copy of the verified bytes, never the mutable input tree."""
    archive = read_archive(directory)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for name, raw in archive_files(archive).items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        verified = read_archive(root)
        yield root, verified


def project(archive):
    require(verified_archive(archive), "Verified runtime archive required")
    projection = archive.projection
    manifest, capture = projection.manifest, projection.snapshot
    nodes = registry_nodes(projection)
    keys = {node["key"]: identity("runtime-mlflow", node["key"]) for node in nodes}
    execution = execution_binding(projection)
    evidence_kind = manifest["evidenceKind"]
    values = {
        "execution": execution,
        "capture": capture.manifest,
        "projection": {
            "manifest": manifest,
            "archiveIndex": archive.index,
            "navigation": {"archiveIndex": "archive/archive.json"},
        },
    }
    seal = manifest["predictionSeal"]
    if seal["status"] == "sealed":
        values["prediction-seal"] = decode(projection.files[seal["artifact"]["path"]])
    records = []
    for node in nodes:
        kind = node["kind"]
        payload = {
            # Execution parent stays byte-identical across v2/v3 capture revisions.
            "schema": "normlab.runtime-mlflow-projection/v"
            + str(
                min(version(archive), 2) if kind == "execution" else version(archive)
            ),
            "kind": "runtime-" + kind,
            "binding": node,
            "evidence": values[kind],
            "evidenceKind": evidence_kind,
            "reference": None,
            "score": None,
            "actualCost": None,
            "criticalErrorFreeRate": None,
            "sourceAuthenticated": False,
            "executionReady": False,
            "semanticQualityEvidence": False,
            "releaseApproved": False,
            "inferenceCallsExecuted": 0,
        }
        records.append(
            {
                "key": keys[node["key"]],
                "parentKey": keys.get(node["parentKey"]),
                "originalId": node["key"],
                "kind": payload["kind"],
                "digest": sha(canonical(payload)),
                "payload": payload,
                "metrics": {
                    **numeric(manifest["counts"], "runtime"),
                    **numeric(manifest.get("controlMetrics", {}), "control"),
                }
                if kind == "projection"
                else {},
                "params": {
                    "evidence_kind": evidence_kind,
                    "execution_ready": "false",
                    "semantic_quality_evidence": "false",
                    "execution_id": manifest["executionId"],
                },
            }
        )
    return records
