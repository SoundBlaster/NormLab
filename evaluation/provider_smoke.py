"""Provider-neutral Noul/Choice/Score smoke CLI. Dry-run unless --live is explicit."""

import argparse
import json
import os
import time
from dataclasses import asdict
from pathlib import Path

from provider_config import require
from provider_runtime import FORMATS, PRESETS, build_provider, configuration
from provider_task import payload as payload

MAX_BYTES = 2 * 1024 * 1024


def read_json(path):
    require(
        path.is_file() and path.stat().st_size <= MAX_BYTES,
        "Bounded JSON file required",
    )
    return json.loads(path.read_bytes())


def run(
    config,
    data,
    output,
    max_calls,
    *,
    key_file=None,
    transport=None,
    categorical=False,
    tactic="independent",
    policy=None,
):
    """Native primitives are independent; categorical batching is explicit."""
    payload(data)
    require(tactic in {"independent", "batch"}, "Explicit tactic")
    require(
        categorical or tactic == "independent",
        "Native smoke dispatches independent primitives",
    )
    groups = {name: {name: q} for name, q in data["questions"].items()}
    factory = build_provider
    if categorical:
        from responses_runtime import build_provider as responses_factory
        from responses_runtime import task_digest, validate_task

        validate_task(data)
        data = json.loads(json.dumps(data, ensure_ascii=False, allow_nan=False))
        groups = {name: {name: q} for name, q in data["questions"].items()}
        factory = responses_factory
        if tactic == "batch":
            groups = {"batch": data["questions"]}
    require(policy is None or categorical, "Policy requires categorical evaluation")
    if policy is not None:
        from categorical_runtime import build_provider as categorical_factory
        from categorical_runtime import validate_policy, validate_tactic

        validate_policy(data, policy)
        validate_tactic(config, data, tactic)
        policy = json.loads(json.dumps(policy, ensure_ascii=False, allow_nan=False))
        factory = categorical_factory
    require(
        type(max_calls) is int and len(groups) <= max_calls <= 3,
        "Explicit call cap must cover questions and be at most three",
    )
    import httpx2

    report = {
        "schema": "normlab.provider-smoke/v2",
        "provider": config.public(),
        "dependencies": {},
        "mode": "live" if transport is None else "mock-transport",
        "plannedCalls": len(groups),
        "maxCalls": max_calls,
        "calls": 0,
        "records": {
            name: {"status": "not-executed", "result": None, "error": None}
            for name in groups
        },
        "requests": [],
        "cost": None,
        "semanticQualityEvidence": False,
    }
    if categorical:
        report.update(
            schema="normlab.responses-choice-smoke/v1",
            tactic=tactic,
            semanticTaskDigest=task_digest(data),
            questionOrder=list(data["questions"]),
        )
    if policy is not None:
        report.update(
            schema="normlab.categorical-evaluation-smoke/v1",
            evaluationMethod="CategoricalRequirement.evaluate",
            policy=policy,
        )
    output.mkdir(mode=0o700, parents=True, exist_ok=False)

    def checkpoint():
        raw = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
        require(len(raw.encode()) <= MAX_BYTES, "Smoke capture bound")
        temporary = output / "report.tmp"
        temporary.write_text(raw + "\n")
        temporary.replace(output / "report.json")

    checkpoint()

    class RecordingTransport(httpx2.BaseTransport):
        def __init__(self):
            self.inner = (
                transport
                if transport is not None
                else httpx2.HTTPTransport(retries=0, trust_env=False)
            )
            self.closed = False

        def handle_request(self, request):
            require(report["calls"] < max_calls, "Request cap exhausted")
            require(
                request.method == "POST" and str(request.url) == config.endpoint_url,
                "SDK request differs from configured endpoint",
            )
            body = json.loads(request.read())
            require(
                body.get("model") == config.model,
                "SDK model differs from configuration",
            )
            report["calls"] += 1
            entry = {
                "method": "POST",
                "endpoint": config.endpoint_url,
                "body": body,
                "httpStatus": None,
            }
            report["requests"].append(entry)
            checkpoint()  # Reserve the slot before sending; never auto-resume.
            try:
                response = self.inner.handle_request(request)
            except Exception as exc:
                entry["transportError"] = type(exc).__name__
                raise
            entry["httpStatus"] = response.status_code
            chunks, size = [], 0
            try:
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    require(size <= MAX_BYTES // 2, "Provider response bound")
                    chunks.append(chunk)
            finally:
                response.close()
            # iter_bytes has decoded compression; do not ask the SDK to decode twice.
            headers = {
                k: v
                for k, v in response.headers.items()
                if k.lower()
                not in {"content-encoding", "content-length", "transfer-encoding"}
            }
            return httpx2.Response(
                response.status_code, headers=headers, content=b"".join(chunks)
            )

        def close(self):
            if not self.closed:
                self.closed = True
                self.inner.close()

    wrapped = RecordingTransport()
    try:
        import importlib.metadata

        report["dependencies"] = {
            name: importlib.metadata.version(name)
            for name in ("mellea-jev-adapter", "typesafe-sdk", "openai", "httpx2")
        }
        with factory(config, key_file=key_file, transport=wrapped) as provider:
            for name, questions in groups.items():
                record = report["records"][name]
                record["status"] = "sent"
                checkpoint()
                started = time.monotonic()
                try:
                    if categorical:
                        from responses_runtime import result_document, task

                        group = {"state": data["state"], "questions": questions}
                        record["semanticTaskDigest"] = task_digest(group)
                        if policy is None:
                            result = result_document(provider.classify(task(group)))
                        else:
                            from categorical_runtime import (
                                evaluate,
                                evaluation_document,
                            )

                            group_policy = {
                                "schema": policy["schema"],
                                "questions": {
                                    key: policy["questions"][key] for key in questions
                                },
                            }
                            result = evaluation_document(
                                evaluate(provider, group, group_policy), group_policy
                            )
                    else:
                        question = questions[name]
                        result = asdict(
                            getattr(provider, question["type"])(
                                state=data["state"],
                                question=question["instructions"],
                                criteria=question["criteria"],
                            )
                        )
                    record.update(
                        status="completed",
                        result=json.loads(json.dumps(result, allow_nan=False)),
                    )
                except Exception as exc:
                    record.update(
                        status="failed",
                        error={
                            "category": type(exc).__name__,
                            "httpStatus": getattr(exc, "status_code", None),
                        },
                    )
                record["latencySeconds"] = round(time.monotonic() - started, 6)
                checkpoint()
                if record["status"] == "failed":
                    break
    except Exception as exc:
        report["configurationError"] = type(
            exc
        ).__name__  # No exception text or error body.
    finally:
        wrapped.close()
        checkpoint()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input", type=Path, help="JSON state and up to three named questions"
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--provider", choices=PRESETS)
    source.add_argument(
        "--config", type=Path, help="Public provider configuration, never credentials"
    )
    parser.add_argument("--api-format", choices=FORMATS)
    parser.add_argument("--provider-id")
    parser.add_argument("--endpoint-url")
    parser.add_argument("--model")
    parser.add_argument("--key-env")
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--max-calls", type=int, default=1)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Permit potentially billable calls within the explicit cap",
    )
    args = parser.parse_args()
    try:
        config = configuration(
            args.provider or "typesafe",
            document=read_json(args.config) if args.config else None,
            id=args.provider_id,
            api_format=args.api_format,
            endpoint_url=args.endpoint_url,
            model=args.model,
            key_env=args.key_env,
            timeout=args.timeout,
        )
        data = payload(read_json(args.input))
        require(
            len(data["questions"]) <= args.max_calls <= 3,
            "--max-calls must cover the questions and be at most three",
        )
    except (ValueError, TypeError, KeyError, OSError):
        parser.error("Invalid public provider configuration, input or budget")
    if not args.live:
        print(
            json.dumps(
                {
                    "mode": "dry-run",
                    "provider": config.public(),
                    "calls": 0,
                    "plannedCalls": len(data["questions"]),
                    "questions": list(data["questions"]),
                }
            )
        )
        return 0
    if args.output is None:
        parser.error("Live smoke requires a new output directory")
    os.umask(0o077)
    report = run(config, data, args.output, args.max_calls, key_file=args.key_file)
    print(json.dumps(report, ensure_ascii=False))
    return (
        0 if all(r["status"] == "completed" for r in report["records"].values()) else 3
    )


if __name__ == "__main__":
    raise SystemExit(main())
