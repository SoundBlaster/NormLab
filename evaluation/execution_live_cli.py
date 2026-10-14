"""Native one-attempt boundary: requirements/inspect are offline; run-once is opt-in."""

import argparse
import json
import sys
from pathlib import Path

from execution_live_kernel import inspect_live, requirements, run_once


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("requirements")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("output", type=Path)
    execute = commands.add_parser("run-once")
    execute.add_argument("input", type=Path)
    execute.add_argument("output", type=Path)
    for name in ("run", "plan", "permit", "invocation"):
        execute.add_argument("--confirm-" + name, required=True)
    execute.add_argument("--confirm-external-ceiling-micros", type=int, required=True)
    execute.add_argument("--key-environment", required=True)
    args = parser.parse_args()
    try:
        if args.command == "requirements":
            report = requirements()
        elif args.command == "inspect":
            report = inspect_live(args.output)
        else:
            confirmation = {
                "runId": args.confirm_run,
                "planDigest": args.confirm_plan,
                "permitDigest": args.confirm_permit,
                "invocationId": args.confirm_invocation,
                "externalCeilingMicros": args.confirm_external_ceiling_micros,
            }
            report = run_once(
                args.input, args.output, confirmation, args.key_environment
            )
        print(json.dumps(report, ensure_ascii=False))
    except Exception as error:
        print("Native boundary failed: " + type(error).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
