"""Export validated legacy fixtures as offline bundles; never constructs a provider."""

import argparse
import sys
from collections import Counter
from pathlib import Path

from offline_bundle import (
    ADAPTER_FILES,
    Builder,
    canonical,
    decode,
    identity,
    read,
    require,
    sha,
    validate,
    verify,
)
from offline_contract import project_metadata

ROOT = Path(__file__).resolve().parents[1]
EVALUATION = Path(__file__).resolve().parent
S13_FIXTURE = ROOT / "fixtures/parking-pilot/s13-offline-v1"


def base(builder, schema, manifest, captures, inputs, dataset, experiment, evidence):
    binding = {"schema": schema, "manifest": manifest["sha256"], "captures": captures}
    return {
        "schema": "normlab.offline-bundle/v1",
        "adapter": {
            "id": "offline-envelope",
            "version": "1",
            "code": {name: builder.file(EVALUATION / name) for name in ADAPTER_FILES},
        },
        "source": {
            "schema": schema,
            "manifest": manifest,
            "captures": captures,
            "inputs": inputs,
        },
        "dataset": dataset,
        "experiment": experiment,
        "run": {
            "id": identity("run", binding),
            "identityKind": "legacy-bundle-derived",
            "evidenceKind": evidence,
            "captureDigest": sha(canonical(captures)),
            "predictionSealDigest": sha(canonical(binding)),
            "inferenceCallsExecuted": 0,
        },
    }


def reference(builder, path, status, revision, expected):
    artifact = builder.file(path, expected)
    return {
        "id": identity("reference", artifact["sha256"]),
        "revision": revision,
        "status": status,
        "artifact": artifact,
    }


def task(
    builder,
    envelope,
    original_id,
    case_id,
    family,
    language,
    arm,
    repetition,
    source_digest,
    task_digest,
    context,
    turn,
    score,
    candidate_id=None,
):
    task_id = identity("task", [envelope["run"]["id"], original_id])
    return {
        "schema": "normlab.offline-task/v1",
        "id": task_id,
        "originalId": original_id,
        "caseId": case_id,
        "candidateId": candidate_id,
        "familyId": family,
        "language": language,
        "armId": arm,
        "repeat": repetition,
        "sourceDigest": source_digest,
        "taskDigest": task_digest,
        "context": context,
        "turn": {"id": identity("turn", task_id), **turn, "attempts": None},
        "scoreArtifact": builder.json(score),
    }


def finish(builder, envelope, tasks, report, ref, scorer, scope):
    report_ref = builder.json(report)
    score = {
        "report": report_ref,
        "referenceId": ref["id"] if ref else None,
        "scorer": scorer,
        "scope": scope,
        "criticalErrorFreeRate": None,
    }
    score["id"] = identity(
        "score",
        [
            envelope["run"]["id"],
            report_ref["sha256"],
            score["referenceId"],
            envelope["adapter"],
        ],
    )
    turns = [row["turn"] for row in tasks]
    questions = [row["questionIds"] for row in turns]
    return {
        **envelope,
        "reference": ref,
        "score": score,
        "records": [builder.json(row) for row in tasks],
        "counts": {
            "plannedTasks": len(tasks),
            "plannedQuestions": None
            if any(q is None for q in questions)
            else sum(len(q) for q in questions),
            "recordedOutcomes": sum(
                row["predictionArtifact"] is not None for row in turns
            ),
            "statusCounts": dict(Counter(row["status"] for row in turns)),
            "knownInputTokens": sum(
                (row["usage"] or {}).get("inputTokens") or 0 for row in turns
            ),
            "knownOutputTokens": sum(
                (row["usage"] or {}).get("outputTokens") or 0 for row in turns
            ),
            "unknownUsageOutcomes": sum(
                row["predictionArtifact"] is not None
                and (
                    row["usage"] is None
                    or any(v is None for v in row["usage"].values())
                )
                for row in turns
            ),
        },
    }


def classification(builder, path, labels_path):
    import harness_v2

    prepared = harness_v2.prepare(path, labels_path)
    manifest, manifest_digest, bound, labels, labels_digest = prepared
    report = harness_v2.replay(prepared)
    manifest_ref = builder.file(path, manifest_digest)
    directory = path.resolve().parent

    def pinned(entry):
        target = (directory / entry["path"]).resolve()
        require(target.is_relative_to(directory), "Artifact escapes experiment")
        return builder.file(target, entry["sha256"])

    inputs = [{"role": "definitions", "artifact": pinned(manifest["definitions"])}]
    case_inputs = {}
    for case in manifest["cases"]:
        row = {
            "case": case,
            "input": pinned(case["input"]),
            "parent": pinned(case["parent"]),
        }
        case_inputs[case["id"]] = builder.value(row["input"])
        inputs.extend(
            {"role": role, "artifact": row[role]} for role in ("input", "parent")
        )
    captures = [pinned(row["capture"]) for row in manifest["records"]]
    dataset, experiment = project_metadata(
        manifest, manifest_digest, inputs, builder.value
    )
    envelope = base(
        builder,
        manifest["schema"],
        manifest_ref,
        captures,
        inputs,
        dataset,
        experiment,
        "offline-fixed-captures",
    )
    ref = (
        reference(builder, labels_path, labels["status"], None, labels_digest)
        if labels is not None
        else None
    )
    scorer = {
        "id": report["scorer"],
        "code": builder.file(EVALUATION / "harness_v2.py", report["scorerDigest"]),
        "dependencies": {
            name: builder.file(EVALUATION / name, digest)
            for name, digest in report["dependencyDigests"].items()
        },
    }
    tasks = []
    for (record, case, parent, turn, returned_model), score in zip(
        bound, report["records"]
    ):
        # Preserve the complete original turn/capture. Exact HTTP context is absent.
        capture_ref = pinned(record["capture"])
        source = case_inputs[case["id"]]
        tasks.append(
            task(
                builder,
                envelope,
                record["id"],
                case["id"],
                case["family"],
                case["language"],
                "classification",
                None,
                source["sourceDigest"],
                sha(
                    canonical(
                        {
                            "input": case["input"]["sha256"],
                            "parent": case["parent"]["sha256"],
                            "definitions": manifest["definitions"]["sha256"],
                        }
                    )
                ),
                {"kind": "unavailable", "artifact": None, "policy": None},
                {
                    "stage": "classification",
                    "originalStatus": turn["status"],
                    "status": score["status"],
                    "predictionArtifact": capture_ref,
                    "error": turn["error"],
                    "returnedModel": returned_model,
                    "usage": None,
                    "latencyMs": None,
                    "cost": None,
                    "questionIds": None,
                },
                score,
            )
        )
    return finish(
        builder,
        envelope,
        tasks,
        report,
        ref,
        scorer,
        "classification-selected-payment-probes",
    )


def s13(builder, capture_path, reference_path):
    import s13_offline

    # S1.3 v1 intentionally supports the repo-pinned fixture manifest only.
    manifest, jobs, summary = s13_offline.compile_plan()
    capture_raw = read(capture_path)
    capture = decode(capture_raw)
    read(
        reference_path
    )  # Apply the envelope's bound before the legacy reader opens it.
    report = s13_offline.replay(capture, reference_path)
    require(report["planDigest"] == summary["planDigest"], "Plan changed during replay")
    manifest_ref = builder.file(
        s13_offline.FIXTURE / "experiment.json", summary["manifestDigest"]
    )
    capture_ref = builder.add(capture_raw)
    inputs = []
    for role, entry in manifest["artifacts"].items():
        inputs.append(
            {
                "role": role,
                "artifact": builder.file(ROOT / entry["path"], entry["sha256"]),
            }
        )
    sources = builder.value(
        next(entry["artifact"] for entry in inputs if entry["role"] == "sources")
    )
    require(sha(canonical(capture)) == report["captureDigest"], "Capture seal changed")
    source_cases = {row["id"]: row for row in sources["cases"]}
    dataset, experiment = project_metadata(
        manifest,
        summary["manifestDigest"],
        inputs,
        builder.value,
        summary["planDigest"],
    )
    envelope = base(
        builder,
        manifest["schema"],
        manifest_ref,
        [capture_ref],
        inputs,
        dataset,
        experiment,
        "offline-fixture",
    )
    ref = reference(
        builder,
        reference_path,
        report["referenceStatus"],
        report["referenceRevision"],
        report["referenceDigest"],
    )
    scorer = {
        "id": "s13-selected-claim/v1",
        "code": builder.file(
            EVALUATION / "s13_offline.py",
            manifest["codePins"]["evaluation/s13_offline.py"],
        ),
        "dependencies": {},
    }
    predictions = {row["jobId"]: row for row in capture["records"]}
    scores = {row["jobId"]: row for row in report["results"]}
    tasks = []
    for job in jobs:
        source = source_cases[job["caseId"]]
        prediction = predictions.get(job["jobId"])
        payload = builder.json(job["payload"])
        require(payload["sha256"] == job["requestDigest"], "Logical payload binding")
        tasks.append(
            task(
                builder,
                envelope,
                job["jobId"],
                job["caseId"],
                source["familyId"],
                source["language"],
                job["arm"],
                job["repetition"],
                source["sourceDigest"],
                job["requestDigest"],
                {
                    "kind": "logical-payload",
                    "artifact": payload,
                    "policy": "provider-neutral-independent/v1",
                },
                {
                    "stage": "selected-claim-verification",
                    "originalStatus": prediction["status"]
                    if prediction
                    else "not-recorded",
                    "status": scores[job["jobId"]]["status"],
                    "predictionArtifact": builder.json(prediction)
                    if prediction
                    else None,
                    "error": None,
                    "returnedModel": None,
                    "usage": {k: prediction[k] for k in ("inputTokens", "outputTokens")}
                    if prediction
                    else None,
                    "latencyMs": None,
                    "cost": None,
                    "questionIds": list(job["payload"]["questions"]),
                },
                scores[job["jobId"]],
                candidate_id=job["recordId"],
            )
        )
    return finish(
        builder,
        envelope,
        tasks,
        report,
        ref,
        scorer,
        "s13-selected-claims-not-whole-source-completeness",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    classification_parser = sub.add_parser("classification")
    classification_parser.add_argument("manifest", type=Path)
    classification_parser.add_argument("--labels", type=Path)
    s13_parser = sub.add_parser("s13")
    s13_parser.add_argument(
        "--capture", type=Path, default=S13_FIXTURE / "mock-capture.json"
    )
    s13_parser.add_argument(
        "--reference", type=Path, default=S13_FIXTURE / "reviewer-only.json"
    )
    stage1_parser = sub.add_parser("stage1")
    stage1_parser.add_argument("capture", type=Path)
    stage1_parser.add_argument("--manifest", type=Path)
    stage1_parser.add_argument("--seal", type=Path)
    stage1_parser.add_argument("--native-score", type=Path)
    for command in (classification_parser, s13_parser, stage1_parser):
        command.add_argument("--output", type=Path)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "verify":
            envelope = verify(args.bundle)
        else:
            builder = Builder()
            if args.command == "classification":
                envelope = classification(builder, args.manifest, args.labels)
            elif args.command == "s13":
                envelope = s13(builder, args.capture, args.reference)
            else:
                from offline_stage1 import export as export_stage1

                envelope = export_stage1(
                    builder, args.capture, args.manifest, args.seal, args.native_score
                )
            if args.output:
                envelope = builder.export(envelope, args.output)
            else:
                # Validate the complete in-memory bundle without writing artifacts.
                envelope["artifacts"] = [
                    {"path": path, "sha256": sha(raw), "bytes": len(raw)}
                    for path, raw in sorted(builder.files.items())
                ]
                validate(envelope, lambda ref: builder.files[ref["path"]])
        print(
            canonical(
                {
                    "schema": envelope["schema"],
                    "runId": envelope["run"]["id"],
                    "scoreId": envelope["score"]["id"],
                    "counts": envelope["counts"],
                    "inferenceCallsExecuted": 0,
                }
            ).decode()
        )
    except (ValueError, OSError, TypeError, KeyError, RecursionError):
        # No arbitrary source text, provider body or exception message in logs.
        print("Offline bundle contract validation/export failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
