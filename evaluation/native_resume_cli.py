"""SDK-free explicit native resume commands; errors never expose credential text."""

import argparse
import json
import sys
from pathlib import Path

from execution_checkpoint import bounded_read
from execution_plan import Store
from native_resume_capture import inspect_resume, prepare_resume
from native_resume_execution import resume_native
from offline_bundle import MAX_BYTES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("directory")
    prepare.add_argument("--authorization", required=True)
    prepare.add_argument("--expires-at", required=True)
    prepare.add_argument("--key-environments", required=True)
    prepare.add_argument("--caps")
    apply = sub.add_parser("apply")
    apply.add_argument("directory")
    apply.add_argument("request")
    apply.add_argument("--confirm-request-digest", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("directory")
    options = parser.parse_args()

    def read(path):
        return Store.decode_json(bounded_read(Path(path), MAX_BYTES))

    try:
        if options.operation == "prepare":
            result = prepare_resume(
                options.directory,
                authorization_record=read(options.authorization),
                expires_at=options.expires_at,
                key_environments=read(options.key_environments),
                limits=read(options.caps) if options.caps else None,
            )
        elif options.operation == "apply":
            result = resume_native(
                options.directory,
                read(options.request),
                confirm_request_digest=options.confirm_request_digest,
            )
        else:
            result = inspect_resume(options.directory)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OSError, RuntimeError, StopIteration):
        # Dispatch may already have happened. Do not claim zero calls on apply errors.
        print(
            json.dumps(
                {
                    "error": "native-resume-rejected",
                    "dispatchAttemptsInvoked": None
                    if options.operation == "apply"
                    else 0,
                    "inferenceCallsExecuted": None
                    if options.operation == "apply"
                    else 0,
                }
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
