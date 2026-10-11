"""Opt-in one-batch verifier capture; dry-run by default, no hidden retries."""

import argparse
import importlib.metadata
import json
import os
import time
from dataclasses import asdict
from pathlib import Path

from harness import digest, load_json, require
from proxyapi_config import build_proxyapi_provider
from verifier_capture import CAPTURE_SCHEMA, replay_verifier, validate_manifest


def write_json(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def run_capture(
    manifest, raw, output, *, provider_factory=build_proxyapi_provider, transport=None
):
    validate_manifest(manifest)
    import httpx2
    from mellea_jev import (
        ChoiceQuestion,
        JevError,
        JevHTTPError,
        JevProtocolError,
        NoulQuestion,
        ScoreQuestion,
    )

    questions = {}
    for name, question in manifest["questions"].items():
        cls = {"noul": NoulQuestion, "choice": ChoiceQuestion, "score": ScoreQuestion}[
            question["type"]
        ]
        questions[name] = cls(question["instructions"], question["criteria"])
    turn = {
        "id": "turn_1",
        "stage": "verification",
        "status": "prepared",
        "request": None,
        "response": None,
        "error": None,
        "httpStatus": None,
        "calls": 0,
        "questions": len(questions),
        "latencyMs": None,
        "cost": None,
    }
    capture = {
        "schema": CAPTURE_SCHEMA,
        "manifestDigest": digest(raw),
        "sourceDigest": digest(manifest["state"]["sourceText"].encode()),
        "provider": manifest["provider"],
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("mellea-jev-adapter", "typesafe-sdk", "httpx2")
        },
        "turn": turn,
    }
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    (output / "experiment.json").write_bytes(raw)
    write_json(output / "capture.json", capture)

    class RecordingTransport(httpx2.BaseTransport):
        def __init__(self, inner):
            self.inner = inner
            self.closed = False

        def handle_request(self, request):
            require(
                turn["calls"] == 0, "Request budget exhausted; no retries permitted"
            )
            body = json.loads(request.content)
            expected = {
                "model": manifest["provider"]["model"],
                "state": manifest["state"],
                "questions": manifest["questions"],
            }
            require(
                request.method == "POST"
                and str(request.url) == manifest["provider"]["endpoint"]
                and body == expected,
                "Actual request differs from manifest",
            )
            turn.update(
                status="sent",
                calls=1,
                request={
                    "method": request.method,
                    "endpoint": str(request.url),
                    "body": body,
                },
            )
            write_json(output / "capture.json", capture)
            response = self.inner.handle_request(request)
            turn["httpStatus"] = response.status_code
            return response

        def close(self):
            if not self.closed:
                self.closed = True
                self.inner.close()

    wrapped = RecordingTransport(
        transport if transport is not None else httpx2.HTTPTransport(retries=0)
    )
    started = time.monotonic()
    try:
        with provider_factory(transport=wrapped) as provider:
            result = provider.system_one(state=manifest["state"], questions=questions)
        turn.update(status="completed", response=json.loads(json.dumps(asdict(result))))
    except JevHTTPError:
        turn.update(status="failed", error="http")
    except JevProtocolError:
        turn.update(status="failed", error="protocol")
    except JevError:
        turn.update(status="failed", error="transport")
    except ValueError:
        turn.update(status="failed", error="configuration")
    except Exception:
        turn.update(status="failed", error="unknown")
    finally:
        wrapped.close()
        turn["latencyMs"] = round((time.monotonic() - started) * 1000, 3)
        write_json(output / "capture.json", capture)
    report = replay_verifier(manifest, raw, capture)
    write_json(output / "report.json", report)
    for name in (
        "run_verifier.py",
        "verifier_capture.py",
        "proxyapi_config.py",
        "harness.py",
        "mellea_candidate.py",
        "classification_v3.py",
        "anchor.py",
    ):
        (output / name).write_bytes(Path(__file__).with_name(name).read_bytes())
    folder = output / "providers"
    folder.mkdir()
    for name in ("proxyapi.py", "LICENSE.proxyapi", "README.md"):
        (folder / name).write_bytes(
            Path(__file__).with_name("providers").joinpath(name).read_bytes()
        )
    files = [
        {"path": str(p.relative_to(output)), "sha256": digest(p.read_bytes())}
        for p in sorted(output.rglob("*"))
        if p.is_file()
    ]
    write_json(
        output / "artifact-manifest.json",
        {
            "schema": "normlab.evaluation-artifacts/v1",
            "entries": files,
            "signed": False,
        },
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Permit exactly one potentially billable batch request",
    )
    args = parser.parse_args()
    manifest, raw = load_json(args.manifest)
    validate_manifest(manifest)
    if not args.live:
        print(
            json.dumps(
                {
                    "experimentId": manifest["experimentId"],
                    "calls": 0,
                    "plannedCalls": 1,
                    "questions": len(manifest["questions"]),
                    "mode": "dry-run",
                }
            )
        )
        return 0
    require(args.output is not None, "Live capture requires a new output directory")
    os.umask(0o077)
    report = run_capture(manifest, raw, args.output)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "completed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
