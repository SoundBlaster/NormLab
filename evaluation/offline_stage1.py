"""Normalize Stage 1 attempts after bounded, SDK-free native replay."""

import tempfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

from offline_bundle import (
    MAX_FILES,
    Builder,
    canonical,
    decode,
    identity,
    object_keys,
    require,
    sha,
)
from offline_stage1_source import (
    EVALUATION,
    NATIVE_FILES,
    READER_ASSETS,
    READER_FILES,
    SOURCE_SCHEMA,
    native,
    restore,
    safe_path,
    snapshot,
)


def attempt(
    builder, turn_id, ordinal, entry, native_turn, raw_turn, child_index, child_plan
):
    finished = entry["finished"]
    completed = native_turn is not None and native_turn["status"] == "completed"
    result = native_turn["result"] if completed else None
    status = (
        native_turn["status"] if finished and native_turn else "unknown-sent-outcome"
    )
    dispatches = native_turn["dispatches"] if native_turn else None
    return {
        "schema": "normlab.offline-attempt/v1",
        "id": identity("attempt", [turn_id, ordinal]),
        "turnId": turn_id,
        "ordinal": ordinal,
        "status": status,
        "originalStatus": native_turn["status"] if native_turn else None,
        "finished": finished,
        "dispatches": dispatches,
        "budgetDispatches": dispatches if dispatches is not None else 1,
        "rawTurnArtifact": raw_turn,
        "childCaptureArtifact": child_index,
        "childPlanArtifact": child_plan,
        "requestArtifact": builder.json(native_turn["request"])
        if native_turn and native_turn["request"] is not None
        else None,
        "error": native_turn["error"] if native_turn else None,
        "exceptionClasses": entry["exceptionClasses"],
        "scheduledBackoffSeconds": entry["backoffSeconds"],
        "returnedModel": result["returnedModel"] if result else None,
        "requestId": result["requestId"] if result else None,
        # A completed child not finalized by the outer checkpoint still has known usage.
        "usage": {
            "inputTokens": result["usage"]["input_tokens"],
            "outputTokens": result["usage"]["output_tokens"],
        }
        if result and result["usage"] is not None
        else None,
        "latencyMs": native_turn["latencySeconds"] * 1000
        if native_turn and native_turn["latencySeconds"] is not None
        else None,
        "cost": None,
        "observed": result["label"] if result and finished else None,
    }


def project(builder, kind, files, scoring=None):
    require(kind in {"provider-v1", "retry-v2"}, "Stage 1 adapter kind")
    # Native replay reads only this bounded snapshot, with no access to its old paths.
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        restore(files, root)
        plan, parent, native_summary = native(kind, root)
        evaluated = None
        if scoring is not None:
            from offline_stage1_reference import evaluate

            evaluated = evaluate(builder, kind, plan, parent, root, scoring)
    refs = {name: builder.add(raw) for name, raw in sorted(files.items())}
    source_manifest = {
        "schema": SOURCE_SCHEMA,
        "experimentId": parent["experimentId"],
        "kind": kind,
        "files": [{"path": name, "artifact": ref} for name, ref in refs.items()],
    }
    manifest_ref = builder.json(source_manifest)
    capture_refs = [
        ref
        for name, ref in refs.items()
        if PurePosixPath(name).name == "capture.json"
        or PurePosixPath(name).name.startswith("J")
    ]
    binding = {
        "schema": SOURCE_SCHEMA,
        "manifest": manifest_ref["sha256"],
        "captures": capture_refs,
    }
    run_id = identity("run", binding)
    index = decode(files["capture.json"])
    jobs = parent["jobs"]
    groups = defaultdict(list)
    native_turns = {}
    if kind == "retry-v2":
        entries = index["attempts"]
    else:
        entries = []
        for job, ref in zip(jobs, index["turnArtifacts"]):
            turn = decode(files[ref["path"]])
            if turn["status"] != "not-executed":
                entries.append(
                    {
                        "jobId": job["jobId"],
                        "ordinal": 1,
                        "path": "",
                        "finished": turn["status"] != "sent",
                        "exceptionClasses": [],
                        "backoffSeconds": None,
                    }
                )
                native_turns[job["jobId"]] = (turn, refs[ref["path"]])
    for entry in entries:
        task_id = identity("task", [run_id, entry["jobId"]])
        turn_id = identity("turn", task_id)
        child_index = None
        child_plan = None
        if kind == "provider-v1":
            turn, raw_ref = native_turns[entry["jobId"]]
        else:
            child_path = entry["path"] + "/capture.json"
            child_plan = refs.get(entry["path"] + "/plan.json")
            child_index = refs.get(child_path)
            if child_index:
                child = decode(files[child_path])
                path = entry["path"] + "/" + child["turnArtifacts"][0]["path"]
                turn, raw_ref = decode(files[path]), refs[path]
            else:
                turn, raw_ref = None, None
        groups[entry["jobId"]].append(
            attempt(
                builder,
                turn_id,
                entry["ordinal"],
                entry,
                turn,
                raw_ref,
                child_index,
                child_plan,
            )
        )
    if index["stopReason"] == "returned-model-change" and entries:
        final = groups[entries[-1]["jobId"]][-1]
        final.update(status="model-rejected", observed=None)
    tasks, rows = [], []
    for job in jobs:
        history = groups[job["jobId"]]
        task_id = identity("task", [run_id, job["jobId"]])
        first, final = (history[0], history[-1]) if history else (None, None)
        phases = {
            phase: {
                "status": a["status"] if a else "not-executed",
                "observed": a["observed"] if a else None,
            }
            for phase, a in (("first", first), ("final", final))
        }
        row = {"jobId": job["jobId"], **phases, "selectedReferencePass": None}
        if evaluated:
            row["expected"] = evaluated["expected"][job["jobId"]]
            for phase in phases.values():
                phase["selectedReferencePass"] = (
                    phase["observed"] == row["expected"]
                    if phase["observed"] is not None
                    else None
                )
            row["selectedReferencePass"] = phases["final"]["selectedReferencePass"]
        rows.append(row)
        tasks.append(
            {
                "schema": "normlab.offline-task/v1",
                "id": task_id,
                "originalId": job["jobId"],
                "caseId": job["caseId"],
                "candidateId": job["recordId"],
                "familyId": job["familyId"],
                # Native plan omits language; do not infer it from text/case ID.
                "language": None,
                "armId": job["armId"],
                "repeat": job["repeat"],
                "sourceDigest": job["sourceDigest"],
                "taskDigest": job["taskDigest"],
                "context": {
                    "kind": "logical-payload",
                    "artifact": builder.json(job["task"]),
                    "policy": "stage1-independent-semantic-task/v1",
                },
                "turn": {
                    "id": identity("turn", task_id),
                    "stage": "selected-claim-verification",
                    "status": phases["final"]["status"],
                    "originalStatus": final["originalStatus"]
                    if final
                    else "not-executed",
                    "predictionArtifact": final["rawTurnArtifact"] if final else None,
                    "error": final["error"] if final else None,
                    "returnedModel": final["returnedModel"] if final else None,
                    "usage": final["usage"] if final else None,
                    "latencyMs": final["latencyMs"] if final else None,
                    "cost": None,
                    "questionIds": ["overall"],
                    "attempts": history,
                },
                "scoreArtifact": builder.json(row),
            }
        )
    histories = [a for history in groups.values() for a in history]
    counts = {
        "plannedTasks": len(tasks),
        "plannedQuestions": len(tasks),
        "recordedOutcomes": sum(
            t["turn"]["predictionArtifact"] is not None for t in tasks
        ),
        "statusCounts": dict(Counter(t["turn"]["status"] for t in tasks)),
        "firstStatusCounts": dict(Counter(row["first"]["status"] for row in rows)),
        "attemptStatusCounts": dict(Counter(a["status"] for a in histories)),
        "attemptsStarted": len(histories),
        "retryAttemptsStarted": sum(max(0, len(h) - 1) for h in groups.values()),
        "knownDispatches": sum(a["dispatches"] or 0 for a in histories),
        "reservedUnknownDispatches": sum(a["dispatches"] is None for a in histories),
        "unknownOutcomeAttempts": sum(
            a["status"] == "unknown-sent-outcome" for a in histories
        ),
        "unknownUsageAttempts": sum(
            bool(a["budgetDispatches"]) and a["usage"] is None for a in histories
        ),
        **{
            "known" + field[0].upper() + field[1:]: sum(
                a["usage"][field] for a in histories if a["usage"] is not None
            )
            for field in ("inputTokens", "outputTokens")
        },
    }
    require(
        counts["knownDispatches"] + counts["reservedUnknownDispatches"]
        == native_summary["networkCalls"] + native_summary["mockHttpCalls"],
        "Native dispatch denominator",
    )
    dataset_rows = sorted(
        {
            (
                j["caseId"],
                j["familyId"],
                j["recordId"],
                j["sourceDigest"],
                j["taskDigest"],
            )
            for j in jobs
        }
    )
    adapter = {
        "id": "offline-envelope",
        "version": "stage1-2",
        "code": {name: builder.file(EVALUATION / name) for name in READER_FILES},
        "assets": {
            name: builder.file(EVALUATION.parent / name) for name in READER_ASSETS
        },
    }
    report = {
        "schema": "normlab.offline-stage1-report/v1",
        "planDigest": sha(canonical(plan)),
        "nativeSummary": native_summary,
        "counts": counts,
        "rows": rows,
        "referenceStatus": "not-evaluated",
        "semanticQualityEvidence": False,
        "criticalErrorFreeRate": None,
        "inferenceCallsExecuted": 0,
    }
    reference = evaluated["reference"] if evaluated else None
    if evaluated:
        report.update(
            schema="normlab.offline-stage1-report/v2",
            referenceStatus=reference["status"],
            nativeScoreArtifact=evaluated["nativeReport"],
            nativeScoreSchema=evaluated["nativeSchema"],
            nativeSealArtifact=evaluated["seal"],
        )
    report_ref = builder.json(report)
    score = {
        "report": report_ref,
        "referenceId": reference["id"] if reference else None,
        "scorer": {
            "id": "stage1-selected-reference-projection/v1"
            if reference
            else "stage1-transport-projection/v1",
            "code": adapter["code"]["offline_stage1.py"],
            "dependencies": {
                name: adapter["code"][name]
                for name in (
                    *NATIVE_FILES,
                    *(
                        ("offline_stage1_reference.py", "offline_stage1_scoring.py")
                        if reference
                        else ()
                    ),
                )
            },
        },
        "scope": "stage1-selected-claim-candidate-first-final"
        if reference
        else "stage1-transport-first-final-no-reference",
        "criticalErrorFreeRate": None,
    }
    score["id"] = identity(
        "score", [run_id, report_ref["sha256"], score["referenceId"], adapter]
    )
    return {
        "schema": "normlab.offline-bundle/v1",
        "adapter": adapter,
        "source": {
            "schema": SOURCE_SCHEMA,
            "manifest": manifest_ref,
            "captures": capture_refs,
            "inputs": evaluated["inputs"] if evaluated else [],
        },
        "dataset": {
            "id": parent["datasetId"],
            "revision": None,
            "digest": sha(canonical(dataset_rows)),
        },
        "experiment": {
            "id": parent["experimentId"],
            "manifestDigest": manifest_ref["sha256"],
            "strategy": {"id": "stage1-selected-claim", "version": "1"},
            "tactic": {"id": kind, "version": "1"},
            "provider": parent["providers"],
            "policy": {
                "profile": parent["profile"],
                "budget": plan["budget"],
                "retryPolicy": plan.get("retryPolicy"),
                "ordering": parent["ordering"],
            },
        },
        "run": {
            "id": run_id,
            "identityKind": "legacy-bundle-derived",
            "evidenceKind": "saved-" + index["mode"],
            "captureDigest": sha(canonical(binding["captures"])),
            "predictionSealDigest": sha(canonical(binding)),
            "inferenceCallsExecuted": 0,
        },
        "reference": reference,
        "score": score,
        "records": [builder.json(t) for t in tasks],
        "counts": counts,
    }


def export(builder, folder, manifest=None, seal=None, score=None):
    paths = (manifest, seal, score)
    require(all(paths) or not any(paths), "Complete scoring inputs required")
    kind, files = snapshot(folder)
    scoring = None
    if all(paths):
        from offline_stage1_reference import snapshot as scoring_snapshot

        scoring = scoring_snapshot(manifest, seal, score, kind, files)
    return project(builder, kind, files, scoring)


def validate(envelope, artifact):
    manifest = decode(artifact(envelope["source"]["manifest"]))
    object_keys(manifest, "schema experimentId kind files")
    require(manifest["schema"] == SOURCE_SCHEMA, "Stage 1 source schema")
    require(
        isinstance(manifest["files"], list) and 0 < len(manifest["files"]) <= MAX_FILES,
        "Snapshot inventory",
    )
    files = {}
    for entry in manifest["files"]:
        object_keys(entry, "path artifact")
        name = entry["path"]
        safe_path(name)
        require(name not in files, "Duplicate snapshot path")
        files[name] = artifact(entry["artifact"])
    builder = Builder()
    inputs = envelope["source"]["inputs"]
    require(isinstance(inputs, list), "Scoring inputs")
    scoring = {}
    for entry in inputs:
        object_keys(entry, "role artifact")
        require(entry["role"] not in scoring, "Duplicate scoring input")
        scoring[entry["role"]] = artifact(entry["artifact"])
    expected = project(builder, manifest["kind"], files, scoring or None)
    expected["artifacts"] = [
        {"path": path, "sha256": sha(raw), "bytes": len(raw)}
        for path, raw in sorted(builder.files.items())
    ]
    require(canonical(envelope) == canonical(expected), "Stage 1 projection drift")
    return envelope
