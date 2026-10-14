"""SDK-free mock capture preparation; prints metadata, never exports raw source text."""

import argparse
import sys
from pathlib import Path

from execution_checkpoint import bounded_read
from execution_plan import Store
from offline_bundle import MAX_BYTES, canonical
from runtime_capture import capture_runtime, verify_capture_manifest
from runtime_export import prepare_export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("directory", type=Path)
    project = commands.add_parser("project")
    project.add_argument("directory", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    verify.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        result = (
            prepare_export(capture_runtime(args.directory))
            if args.command == "project"
            else capture_runtime(args.directory)
            if args.command == "snapshot"
            else verify_capture_manifest(
                args.directory,
                Store.decode_json(bounded_read(args.manifest, MAX_BYTES)),
            )
        )
        print(canonical(result.manifest).decode())
        return 0
    except Exception as error:
        print(
            canonical(
                {
                    "status": "rejected",
                    "errorType": type(error).__name__,
                    "inferenceCallsExecuted": 0,
                }
            ).decode(),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
