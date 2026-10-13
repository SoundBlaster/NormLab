"""Import verified offline bundles into a local idempotent MLflow registry."""

import argparse
import sys
from pathlib import Path

from offline_bundle import canonical
from offline_mlflow_projection import project, snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument(
        "--storage",
        type=Path,
        default=Path(__file__).resolve().parents[1] / ".data/mlflow-offline",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        with snapshot(args.bundle) as (root, envelope, digest):
            parent, view = project(root, envelope, digest)
            result = {
                "schema": "normlab.mlflow-import-result/v1",
                "runId": envelope["run"]["id"],
                "scoreId": envelope["score"]["id"],
                "bundleDigest": digest,
                "inferenceCallsExecuted": 0,
                "dryRun": args.dry_run,
            }
            if args.dry_run:
                result["projection"] = [parent, view]
            else:
                from mlflow_registry import registry

                with registry(args.storage) as store:
                    result["capture"] = store.write(parent, root)
                    result["score"] = store.write(
                        view, root, result["capture"]["mlflowRunId"]
                    )
            print(canonical(result).decode())
        return 0
    except Exception as error:
        print("Offline MLflow import failed: " + type(error).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
