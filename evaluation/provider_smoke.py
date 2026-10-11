"""Provider-neutral Noul/Choice/Score smoke CLI. Dry-run unless --live is explicit."""

import argparse
import json
import os
import time
from dataclasses import asdict
from pathlib import Path

from provider_config import FORMATS, PRESETS, build_provider, configuration, require

MAX_BYTES = 2 * 1024 * 1024


def read_json(path):
    require(
        path.is_file() and path.stat().st_size <= MAX_BYTES,
        "Bounded JSON file required",
    )
    return json.loads(path.read_bytes())


def payload(value):
    require(
        isinstance(value, dict) and set(value) == {"state", "questions"},
        "Smoke input requires state and questions",
    )
    require(
        isinstance(value["state"], dict)
        and len(
            json.dumps(value["state"], ensure_ascii=False, allow_nan=False).encode()
        )
        <= 32768,
        "Bounded dictionary state required",
    )
    questions = value["questions"]
    require(
        isinstance(questions, dict) and 0 < len(questions) <= 3,
        "One to three questions required",
    )
    for name, question in questions.items():
        require(
            isinstance(name, str)
            and name.isascii()
            and name.isidentifier()
            and len(name) <= 80,
            "Question ID contract",
        )
        require(
            isinstance(question, dict)
            and set(question) == {"type", "instructions", "criteria"},
            "Question fields",
        )
        kind = question["type"]
        require(kind in ("noul", "choice", "score"), "Question primitive")
        require(
            isinstance(question["instructions"], str)
            and 0 < len(question["instructions"].strip()) <= 4096,
            "Question instruction limits",
        )
        criteria = question["criteria"]
        if kind == "score":
            require(
                isinstance(criteria, list)
                and 2 <= len(criteria) <= 10
                and len(set(criteria)) == len(criteria),
                "Score rubric",
            )
            descriptions = criteria
        else:
            require(
                isinstance(criteria, dict)
                and (
                    set(criteria) == {"true", "false"}
                    if kind == "noul"
                    else 2 <= len(criteria) <= 255
                ),
                "Named criteria",
            )
            require(
                all(isinstance(k, str) and 0 < len(k) <= 128 for k in criteria),
                "Criterion label limits",
            )
            descriptions = criteria.values()
        require(
            all(
                isinstance(x, str) and 0 < len(x.strip()) <= 2048 for x in descriptions
            ),
            "Criterion description limits",
        )
    return value


def run(config, data, output, max_calls, *, key_file=None, transport=None):
    """Each primitive is a separate request in both APIs, never an implicit batch."""
    payload(data)
    require(
        type(max_calls) is int and len(data["questions"]) <= max_calls <= 3,
        "Explicit call cap must cover questions and be at most three",
    )
    import httpx2

    report = {
        "schema": "normlab.provider-smoke/v1",
        "provider": config.public(),
        "dependencies": {},
        "mode": "live" if transport is None else "mock-transport",
        "plannedCalls": len(data["questions"]),
        "maxCalls": max_calls,
        "calls": 0,
        "records": {
            name: {"status": "not-executed", "result": None, "error": None}
            for name in data["questions"]
        },
        "requests": [],
        "cost": None,
        "semanticQualityEvidence": False,
    }
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
            response = self.inner.handle_request(request)
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
        with build_provider(config, key_file=key_file, transport=wrapped) as provider:
            for name, question in data["questions"].items():
                record = report["records"][name]
                record["status"] = "sent"
                checkpoint()
                started = time.monotonic()
                try:
                    result = getattr(provider, question["type"])(
                        state=data["state"],
                        question=question["instructions"],
                        criteria=question["criteria"],
                    )
                    record.update(status="completed", result=asdict(result))
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
