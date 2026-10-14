"""Explicit local MLflow import of verified runtime archives; dry-run is SDK-free."""

import argparse
import json
import sys
from pathlib import Path

from runtime_mlflow_projection import project, snapshot


def run(directory, storage, *, dry_run=False, score_path=None):
    with snapshot(directory) as (root, archive):
        records = project(archive)
        saved_score = None
        if score_path is not None:
            from offline_bundle import decode, read
            from runtime_score import verify_score
            from runtime_score_mlflow_projection import project_score

            saved_score = verify_score(archive, decode(read(score_path)))
            records.append(project_score(archive, saved_score))
        result = {
            "schema": "normlab.runtime-mlflow-import-result/v1",
            "archiveId": archive.index["archiveId"],
            "executionId": archive.index["executionId"],
            "captureRevisionId": archive.index["captureRevisionId"],
            "dryRun": dry_run,
            "inferenceCallsExecuted": 0,
            "semanticQualityEvidence": False,
            "executionReady": False,
        }
        if dry_run:
            return {**result, "records": records, "registryWritesExecuted": 0}
        from mlflow_registry import registry

        imported = {}
        with registry(storage) as store:
            for record in records:
                parent = imported.get(record["parentKey"])
                receipt = store.write(
                    record,
                    root,
                    parent["mlflowRunId"] if parent else None,
                    runtime_archive=archive,
                    runtime_score=saved_score
                    if record["kind"] == "runtime-score"
                    else None,
                )
                imported[record["key"]] = receipt
        return {**result, "imports": list(imported.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--storage", type=Path, default=Path(".data/mlflow-offline"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--score",
        type=Path,
        help="Verified runtime score view to import as capture child",
    )
    args = parser.parse_args()
    try:
        result = run(
            args.archive, args.storage, dry_run=args.dry_run, score_path=args.score
        )
        print(json.dumps(result, ensure_ascii=False))
    except Exception as error:
        print("Runtime MLflow import failed: " + type(error).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
