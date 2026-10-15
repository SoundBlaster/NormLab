"""Export or verify a mock runtime archive; no SDK or registry writes."""

import argparse
import sys
from pathlib import Path

from offline_bundle import canonical
from runtime_archive_export import export_runtime_archive
from runtime_archive_reader import read_archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("source", type=Path)
    export.add_argument("output", type=Path)
    export.add_argument(
        "--evidence-kind", choices=("mock", "live-capture"), default="mock"
    )
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        receipt = (
            export_runtime_archive(
                args.source, args.output, evidence_kind=args.evidence_kind
            )
            if args.command == "export"
            else None
        )
        result = read_archive(
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
