"""SDK-free consumer projection of verified mock archives; no score is invented."""

import tempfile
from contextlib import contextmanager
from pathlib import Path

from offline_bundle import canonical, decode, identity, require, sha
from offline_mlflow_projection import numeric
from runtime_archive_reader import VerifiedArchive, read_archive
from runtime_registry import registry_nodes

SCHEMA = "normlab.runtime-mlflow-projection/v1"


def archive_files(archive):
    require(type(archive) is VerifiedArchive, "Verified runtime archive required")
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
    require(type(archive) is VerifiedArchive, "Verified runtime archive required")
    require(archive.index["evidenceKind"] == "mock", "Mock-only MLflow consumer")
    projection = archive.projection
    manifest, capture = projection.manifest, projection.snapshot
    nodes = registry_nodes(projection)
    keys = {node["key"]: identity("runtime-mlflow", node["key"]) for node in nodes}
    execution = {
        "executionId": manifest["executionId"],
        "planDigest": manifest["planDigest"],
        "intentDigest": sha(capture.files["intent.json"]),
        "scriptDigest": sha(capture.files["mock-script.json"]),
    }
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
            "schema": SCHEMA,
            "kind": "runtime-" + kind,
            "binding": node,
            "evidence": values[kind],
            "evidenceKind": "mock",
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
                "metrics": numeric(manifest["counts"], "runtime")
                if kind == "projection"
                else {},
                "params": {
                    "evidence_kind": "mock",
                    "execution_ready": "false",
                    "semantic_quality_evidence": "false",
                    "execution_id": manifest["executionId"],
                },
            }
        )
    return records
