"""Native planning/inspection and explicit opt-in one-attempt/Stage1 execution."""

import argparse
import json
import sys
from pathlib import Path

from execution_checkpoint import bounded_read
from execution_live_kernel import inspect_live, requirements, run_once
from execution_plan import Store, dry_run
from offline_bundle import MAX_BYTES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("requirements")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("output", type=Path)
    compile_command = commands.add_parser("compile-stage1")
    compile_command.add_argument("manifest", type=Path)
    compile_command.add_argument("output", type=Path)
    compile_command.add_argument("--options", type=Path, required=True)
    compile_command.add_argument(
        "--profile", choices=("pilot", "corpus"), default="pilot"
    )
    verify = commands.add_parser("verify-stage1")
    verify.add_argument("input", type=Path)
    bind = commands.add_parser("bind-stage1")
    bind.add_argument("input", type=Path)
    bind.add_argument("output", type=Path)
    bind.add_argument("--authorization", type=Path, required=True)
    for command in ("run-once", "run-schedule"):
        execute = commands.add_parser(command)
        execute.add_argument("input", type=Path)
        execute.add_argument("output", type=Path)
        for name in ("run", "plan", "permit", "invocation"):
            execute.add_argument("--confirm-" + name, required=True)
        execute.add_argument(
            "--confirm-external-ceiling-micros", type=int, required=True
        )
        if command == "run-once":
            execute.add_argument("--key-environment", required=True)
    args = parser.parse_args()
    try:
        if args.command == "requirements":
            report = requirements()
        elif args.command == "inspect":
            report = inspect_live(args.output)
        elif args.command == "compile-stage1":
            from execution_stage1_plan import compile_stage1

            report = compile_stage1(
                args.manifest,
                args.output,
                Store.decode_json(bounded_read(args.options, MAX_BYTES)),
                profile=args.profile,
            )
        elif args.command == "verify-stage1":
            from execution_stage1_plan import verify_stage1

            report = dry_run(verify_stage1(Store(args.input))[0])
        elif args.command == "bind-stage1":
            from execution_stage1_bind import bind_stage1

            report = bind_stage1(
                args.input,
                args.output,
                Store.decode_json(bounded_read(args.authorization, MAX_BYTES)),
            )
        else:
            confirmation = {
                "runId": args.confirm_run,
                "planDigest": args.confirm_plan,
                "permitDigest": args.confirm_permit,
                "invocationId": args.confirm_invocation,
                "externalCeilingMicros": args.confirm_external_ceiling_micros,
            }
            if args.command == "run-schedule":
                from execution_live_scheduler import run_schedule

                report = run_schedule(args.input, args.output, confirmation)
            else:
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
