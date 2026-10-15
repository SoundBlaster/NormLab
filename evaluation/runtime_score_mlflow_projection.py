"""SDK-free MLflow score-child projection, regenerated from exact archive/view bytes."""

from offline_bundle import MAX_BYTES, canonical, identity, require, sha
from offline_mlflow_projection import numeric
from runtime_mlflow_projection import project
from runtime_score import verify_score


def project_score(archive, saved):
    view = verify_score(archive, saved)
    capture = project(archive)[1]
    reference = view["reference"]
    arm_keys = {arm: "a-" + sha(arm.encode("utf-8")) for arm in view["arms"]}
    payload = {
        "schema": "normlab.runtime-mlflow-score/v1"
        if view["evidenceKind"] == "mock"
        else "normlab.runtime-mlflow-score/v2",
        "kind": "runtime-score",
        "scoreId": view["scoreId"],
        "archiveId": view["archiveId"],
        "executionId": view["executionId"],
        "captureRevisionId": view["captureRevisionId"],
        "referenceId": reference["referenceId"],
        "referenceStatus": reference["status"],
        "policy": view["policy"],
        "scorerCodePins": view["scorerCodePins"],
        "scoreArtifact": {
            "sha256": sha(canonical(view)),
            "bytes": len(canonical(view)),
        },
        "summary": view["summary"],
        "arms": view["arms"],
        "armMetricKeys": arm_keys,
        "navigation": {"score": "score.json", "archiveIndex": "archive/archive.json"},
        "evidenceKind": view["evidenceKind"],
        "actualCost": None,
        "criticalErrorFreeRate": None,
        "semanticQualityEvidence": False,
        "executionReady": False,
        "releaseApproved": False,
        "inferenceCallsExecuted": 0,
    }
    require(len(canonical(payload)) <= MAX_BYTES, "MLflow score projection cap")
    return {
        "key": identity("runtime-score-import", view["scoreId"]),
        "parentKey": capture["key"],
        "originalId": view["scoreId"],
        "kind": "runtime-score",
        "digest": sha(canonical(payload)),
        "payload": payload,
        "metrics": {
            **numeric(view["summary"], "selected"),
            **numeric(
                {arm_keys[arm]: values for arm, values in view["arms"].items()}, "arms"
            ),
        },
        "params": {
            "evidence_kind": view["evidenceKind"],
            "execution_ready": "false",
            "semantic_quality_evidence": "false",
            "execution_id": view["executionId"],
            "capture_revision_id": view["captureRevisionId"],
            "reference_id": reference["referenceId"],
            "reference_status": reference["status"],
            "policy_id": view["policy"]["id"],
            "scorer_pins_digest": sha(canonical(view["scorerCodePins"])),
        },
    }
