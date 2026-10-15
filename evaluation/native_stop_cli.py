"""Prepare, apply or inspect an explicit native stop; never dispatch inference."""

import argparse
import sys
from pathlib import Path

from execution_checkpoint import bounded_read
from execution_plan import Store
from native_stop_resolution import apply_stop, inspect_stop, prepare_stop
from offline_bundle import MAX_BYTES, canonical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("directory", type=Path)
    prepare.add_argument("--attempt-id", required=True)
    prepare.add_argument("--authorization", type=Path, required=True)
    prepare.add_argument("--expires-at", required=True)
    apply = commands.add_parser("apply")
    apply.add_argument("directory", type=Path)
    apply.add_argument("request", type=Path)
    apply.add_argument("--confirm-request-digest", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            report = prepare_stop(
                args.directory,
                attempt_id=args.attempt_id,
                authorization_record=Store.decode_json(
                    bounded_read(args.authorization, MAX_BYTES)
                ),
                expires_at=args.expires_at,
            )
        elif args.command == "apply":
            report = apply_stop(
                args.directory,
                Store.decode_json(bounded_read(args.request, MAX_BYTES)),
                confirm_request_digest=args.confirm_request_digest,
            )
        else:
            report = inspect_stop(args.directory)
        print(canonical(report).decode())
        return 0
    except Exception as error:
        print(
            canonical(
                {
                    "status": "rejected",
                    "errorType": type(error).__name__,
                    "dispatchAttemptsInvoked": 0,
                    "inferenceCallsExecuted": 0,
                }
            ).decode(),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
