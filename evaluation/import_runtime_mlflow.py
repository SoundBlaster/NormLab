"""Explicit local MLflow import of verified runtime archives; dry-run is SDK-free."""

import argparse
import json
import sys
from pathlib import Path

from runtime_mlflow_projection import project, snapshot


def run(directory, storage, *, dry_run=False):
    with snapshot(directory) as (root, archive):
        records = project(archive)
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
                )
                imported[record["key"]] = receipt
        return {**result, "imports": list(imported.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--storage", type=Path, default=Path(".data/mlflow-offline"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = run(args.archive, args.storage, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        print("Runtime MLflow import failed: " + type(error).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
