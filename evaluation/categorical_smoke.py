"""Choice task + explicit policy; Liquid D1 Ultra, live execution opt-in."""

import argparse
import json
import os
from pathlib import Path

from categorical_runtime import validate_policy, validate_tactic
from provider_config import require
from provider_runtime import PRESETS as NATIVE_PRESETS
from provider_runtime import configuration as native_configuration
from provider_smoke import read_json, run
from responses_runtime import PRESETS as RESPONSES_PRESETS
from responses_runtime import configuration as responses_configuration
from responses_runtime import task_digest, validate_task


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--policy", type=Path, required=True)
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--provider",
        choices=(*NATIVE_PRESETS, *RESPONSES_PRESETS),
        help="Default: liquid-d1-ultra. Other native/Responses routes are explicit.",
    )
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
        document = read_json(args.config) if args.config else None
        require(
            args.config is None or isinstance(document, dict),
            "Public config object required",
        )
        preset = args.provider or "liquid-d1-ultra"
        responses = (
            (
                isinstance(document, dict)
                and document.get("api_format") == "openai-responses"
            )
            if document is not None
            else preset in RESPONSES_PRESETS
        )
        options = {
            "document": document,
            "endpoint_url": args.endpoint_url,
            "model": args.model,
            "key_env": args.key_env,
            "timeout": args.timeout,
        }
        if responses:
            config = responses_configuration(
                preset if preset in RESPONSES_PRESETS else "coreinfra-responses",
                **options,
                reasoning_effort=args.reasoning_effort,
                max_output_tokens=args.max_output_tokens,
            )
        else:
            require(
                args.reasoning_effort is None and args.max_output_tokens is None,
                "Generation settings require Responses",
            )
            config = native_configuration(
                preset if preset in NATIVE_PRESETS else "liquid-d1-ultra", **options
            )
        data = validate_task(read_json(args.input))
        policy = validate_policy(data, read_json(args.policy))
        validate_tactic(config, data, args.tactic)
        calls = 1 if args.tactic == "batch" else len(data["questions"])
        require(calls <= args.max_calls <= 3, "Call cap must cover the tactic")
    except (ValueError, TypeError, KeyError, OSError):
        parser.error(
            "Invalid public categorical configuration, Choice task, policy or budget"
        )
    if not args.live:
        print(
            json.dumps(
                {
                    "schema": "normlab.categorical-evaluation-plan/v1",
                    "mode": "dry-run",
                    "provider": config.public(),
                    "semanticTaskDigest": task_digest(data),
                    "questionOrder": list(data["questions"]),
                    "policy": policy,
                    "evaluationMethod": "CategoricalRequirement.evaluate",
                    "tactic": args.tactic,
                    "calls": 0,
                    "plannedCalls": calls,
                    "maxCalls": args.max_calls,
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.output is None:
        parser.error("Live evaluation requires a new output directory")
    os.umask(0o077)
    report = run(
        config,
        data,
        args.output,
        args.max_calls,
        key_file=args.key_file,
        categorical=True,
        tactic=args.tactic,
        policy=policy,
    )
    print(json.dumps(report, ensure_ascii=False))
    # Completion is operational; an explicit reject/review is still a completed evaluation.
    return (
        0 if all(r["status"] == "completed" for r in report["records"].values()) else 3
    )


if __name__ == "__main__":
    raise SystemExit(main())
