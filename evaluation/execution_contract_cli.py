"""Validate common execution records offline; no inference or resume command."""

import argparse
import sys
from pathlib import Path

from execution_decisions import resolution_preflight
from execution_plan import Store, dry_run, prepare
from execution_replay import replay
from offline_bundle import canonical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "dry-run", "replay", "resolution"))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        store = Store(args.directory)
        if args.command in {"plan", "dry-run"}:
            result = dry_run(prepare(store))
        else:
            result = replay(store)
            if args.command == "resolution":
                result["resolution"] = resolution_preflight(
                    store.json("resolution.json"), store.json("run.json"), result, store
                )
        print(canonical(result).decode())
        return 0
    except Exception as error:
        # Do not echo untrusted source text, paths, response bodies or credentials.
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
