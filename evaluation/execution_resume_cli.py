"""Apply one explicit mock continuation request, or inspect v1/v2 without writes."""

import argparse
import sys
from pathlib import Path

from execution_checkpoint import bounded_read
from execution_continuation import inspect_continuation
from execution_plan import Store
from execution_resume import continue_mock
from offline_bundle import MAX_BYTES, canonical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    apply = sub.add_parser("apply")
    apply.add_argument("directory", type=Path)
    apply.add_argument("request", type=Path)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        result = (
            inspect_continuation(args.directory)
            if args.command == "inspect"
            else continue_mock(
                args.directory, Store.decode_json(bounded_read(args.request, MAX_BYTES))
            )
        )
        print(canonical(result).decode())
        return 0
    except Exception as error:
        print(
            canonical(
                {
                    "status": "rejected",
                    "errorType": type(error).__name__,
                    "authorizedDispatches": 0,
                    "inferenceCallsExecuted": 0,
                }
            ).decode(),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
