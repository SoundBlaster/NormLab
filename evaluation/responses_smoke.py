"""Choice-only ordinary-model comparison entry point. Dry-run unless --live."""

import argparse
import json
import os
from pathlib import Path

from provider_config import require
from provider_smoke import read_json, run
from responses_runtime import PRESETS, configuration, task_digest, validate_task


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--provider", choices=PRESETS)
    source.add_argument("--config", type=Path)
    parser.add_argument("--endpoint-url")
    parser.add_argument("--model")
    parser.add_argument("--key-env")
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--timeout", type=float)
    parser.add_argument(
        "--reasoning-effort",
        choices=("none", "minimal", "low", "medium", "high", "xhigh"),
    )
    parser.add_argument("--max-output-tokens", type=int)
    parser.add_argument(
        "--tactic", choices=("independent", "batch"), default="independent"
    )
    parser.add_argument("--max-calls", type=int, default=1)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    try:
        config = configuration(
            args.provider or "coreinfra-responses",
            document=read_json(args.config) if args.config else None,
            endpoint_url=args.endpoint_url,
            model=args.model,
            key_env=args.key_env,
            timeout=args.timeout,
            reasoning_effort=args.reasoning_effort,
            max_output_tokens=args.max_output_tokens,
        )
        data = validate_task(read_json(args.input))
        calls = 1 if args.tactic == "batch" else len(data["questions"])
        require(calls <= args.max_calls <= 3, "Call cap must cover the tactic")
    except (ValueError, TypeError, KeyError, OSError):
        parser.error("Invalid public Responses configuration, Choice task or budget")
    if not args.live:
        print(
            json.dumps(
                {
                    "schema": "normlab.responses-choice-plan/v1",
                    "mode": "dry-run",
                    "provider": config.public(),
                    "semanticTaskDigest": task_digest(data),
                    "tactic": args.tactic,
                    "questionOrder": list(data["questions"]),
                    "calls": 0,
                    "plannedCalls": calls,
                    "maxCalls": args.max_calls,
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.output is None:
        parser.error("Live smoke requires a new output directory")
    os.umask(0o077)
    report = run(
        config,
        data,
        args.output,
        args.max_calls,
        key_file=args.key_file,
        categorical=True,
        tactic=args.tactic,
    )
    print(json.dumps(report, ensure_ascii=False))
    return (
        0 if all(r["status"] == "completed" for r in report["records"].values()) else 3
    )


if __name__ == "__main__":
    raise SystemExit(main())
