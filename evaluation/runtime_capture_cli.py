"""SDK-free mock capture preparation; prints metadata, never exports raw source text."""

import argparse
import sys
from pathlib import Path

from execution_checkpoint import bounded_read
from execution_plan import Store
from offline_bundle import MAX_BYTES, canonical
from runtime_capture import capture_runtime, verify_capture_manifest
from runtime_export import prepare_export
from runtime_registry import registry_dry_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("directory", type=Path)
    project = commands.add_parser("project")
    project.add_argument("directory", type=Path)
    registry = commands.add_parser("registry-plan")
    registry.add_argument("directory", type=Path)
    registry.add_argument("--receipts", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    verify.add_argument("manifest", type=Path)
    for command in (snapshot, project, registry, verify):
        command.add_argument("--native-continuation", action="store_true")
        command.add_argument(
            "--evidence-kind", choices=("mock", "live-capture"), default="mock"
        )
    args = parser.parse_args()
    try:
        if args.native_continuation:
            from offline_bundle import require
            from runtime_resume_capture import ResumeExportProjection, capture_resume

            require(
                args.evidence_kind == "live-capture",
                "Explicit live continuation evidence",
            )
            snapshot = capture_resume(args.directory)
            if args.command == "verify":
                require(
                    canonical(snapshot.manifest)
                    == canonical(
                        Store.decode_json(bounded_read(args.manifest, MAX_BYTES))
                    ),
                    "Continuation capture manifest binding",
                )
        elif args.command == "verify":
            snapshot = verify_capture_manifest(
                args.directory,
                Store.decode_json(bounded_read(args.manifest, MAX_BYTES)),
                evidence_kind=args.evidence_kind,
            )
        else:
            snapshot = capture_runtime(args.directory, evidence_kind=args.evidence_kind)
        if args.command == "registry-plan":
            receipts = (
                Store.decode_json(bounded_read(args.receipts, MAX_BYTES))
                if args.receipts
                else None
            )
            result = registry_dry_run(
                ResumeExportProjection(snapshot)
                if args.native_continuation
                else prepare_export(snapshot),
                receipts,
            )
            print(canonical(result).decode())
        else:
            result = (
                (
                    ResumeExportProjection(snapshot)
                    if args.native_continuation
                    else prepare_export(snapshot)
                )
                if args.command == "project"
                else snapshot
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
