"""Export or verify a mock runtime archive; no SDK or registry writes."""

import argparse
import sys
from pathlib import Path

from offline_bundle import canonical
from runtime_archive_export import export_runtime_archive
from runtime_archive_reader import read_archive


def read_supported_archive(root):
    # Keep the historical minimal copied-reader installation self-contained.
    from execution_checkpoint import bounded_read
    from execution_plan import Store
    from offline_bundle import MAX_BYTES

    index = Store.decode_json(bounded_read(root / "archive.json", MAX_BYTES))
    if index.get("schema") == "normlab.runtime-archive/v4":
        from runtime_stop_archive import read_archive as read

        return read(root)
    if index.get("schema") == "normlab.runtime-archive/v3":
        from runtime_resume_archive import read_archive as read

        return read(root)
    return read_archive(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("source", type=Path)
    export.add_argument("output", type=Path)
    modes = export.add_mutually_exclusive_group()
    modes.add_argument("--native-continuation", action="store_true")
    modes.add_argument("--native-stop", action="store_true")
    export.add_argument(
        "--evidence-kind", choices=("mock", "live-capture"), default="mock"
    )
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "export" and (args.native_continuation or args.native_stop):
            from offline_bundle import require

            if args.native_stop:
                from runtime_stop_archive import export_archive
            else:
                from runtime_resume_archive import export_archive

            require(
                args.evidence_kind == "live-capture",
                "Explicit live versioned native export",
            )
            receipt = export_archive(args.source, args.output)
            result = read_supported_archive(args.output).summary()
            result["durabilityAcknowledged"] = receipt["durabilityAcknowledged"]
            print(canonical(result).decode())
            return 0
        receipt = (
            export_runtime_archive(
                args.source, args.output, evidence_kind=args.evidence_kind
            )
            if args.command == "export"
            else None
        )
        result = read_supported_archive(
            args.output if receipt is not None else args.directory
        ).summary()
        if receipt is not None:
            result["durabilityAcknowledged"] = receipt["durabilityAcknowledged"]
        print(canonical(result).decode())
        return 0
    except Exception as error:
        print(
            canonical(
                {
                    "status": "rejected",
                    "errorType": type(error).__name__,
                    "inferenceCallsExecuted": 0,
                    "registryWritesExecuted": 0,
                }
            ).decode(),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
