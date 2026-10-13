"""Run or inspect a local deterministic mock; never inference, resume or adoption."""

import argparse
import sys
from pathlib import Path

from execution_checkpoint import bounded_read, inspect_checkpoint
from execution_mock import run_mock
from execution_plan import Store
from offline_bundle import MAX_BYTES, canonical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("input", type=Path)
    run.add_argument("output", type=Path)
    run.add_argument("script", type=Path)
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "run":
            result = run_mock(
                args.input,
                args.output,
                Store.decode_json(bounded_read(args.script, MAX_BYTES)),
            )
        else:
            result = inspect_checkpoint(args.directory)
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
