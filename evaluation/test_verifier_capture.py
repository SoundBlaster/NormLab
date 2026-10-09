"""Actual provider execution through mock HTTP, plus offline replay boundaries."""

import copy
import json
from pathlib import Path

import httpx2
import pytest
from harness import digest
from proxyapi_config import build_proxyapi_provider
from run_verifier import run_capture
from verifier_capture import replay_verifier, validate_manifest

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures/parking-pilot/evaluation-harness/verifier-smoke.json"
)


def factory(**kwargs):
    return build_proxyapi_provider(api_key="fixture-secret", **kwargs)


def payload(manifest):
    return {
        "id": "fixture-request",
        "model": "fixture-returned-model",
        "usage": {"input_tokens": 15, "output_tokens": 4},
        "answers": {
            "Q001": {"type": "noul", "noul": 0.5},
            "Q002": {
                "type": "choice",
                "choice": "denied",
                "confidence": 1.0,
                "probabilities": {
                    "asserted": 0.0,
                    "denied": 1.0,
                    "unknown": 0.0,
                    "unsupported": 0.0,
                },
            },
            "Q003": {
                "type": "score",
                "score": 2.0,
                "confidence": 1.0,
                "probabilities": {"0": 0.0, "1": 0.0, "2": 1.0},
                "legend": {
                    str(i): v
                    for i, v in enumerate(manifest["questions"]["Q003"]["criteria"])
                },
            },
        },
    }


def test_capture_and_replay(tmp_path):
    raw = FIXTURE.read_bytes()
    manifest = json.loads(raw)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(200, json=payload(manifest))

    output = tmp_path / "capture"
    report = run_capture(
        manifest,
        raw,
        output,
        provider_factory=factory,
        transport=httpx2.MockTransport(handler),
    )
    assert len(calls) == report["calls"] == 1
    assert report["status"] == "completed"
    assert report["verdicts"]["Q001"]["outcome"] == "uncertain"
    assert report["verdicts"]["Q002"]["choice"] == "denied"
    assert report["verdicts"]["Q003"]["score"] == 2
    assert report["quality"] == "not_evaluated"
    capture = json.loads((output / "capture.json").read_text())
    assert replay_verifier(manifest, raw, capture) == report
    assert "fixture-secret" not in "".join(
        p.read_text() for p in output.rglob("*") if p.is_file()
    )
    entries = json.loads((output / "artifact-manifest.json").read_text())["entries"]
    assert all(
        digest((output / e["path"]).read_bytes()) == e["sha256"] for e in entries
    )
    changed = copy.deepcopy(capture)
    changed["sourceDigest"] = "invalid"
    with pytest.raises(ValueError):
        replay_verifier(manifest, raw, changed)
    changed = copy.deepcopy(capture)
    changed["turn"]["response"]["answers"]["Q001"]["p_yes"] = True
    with pytest.raises(ValueError):
        replay_verifier(manifest, raw, changed)


@pytest.mark.parametrize("failure", ["http", "transport", "protocol"])
def test_failure_no_retry(tmp_path, failure):
    raw = FIXTURE.read_bytes()
    manifest = json.loads(raw)
    calls = []

    def handler(request):
        calls.append(request)
        if failure == "transport":
            raise httpx2.ConnectError("fixture-secret must not leak")
        return httpx2.Response(
            401 if failure == "http" else 200, json={"secret": "fixture-secret"}
        )

    report = run_capture(
        manifest,
        raw,
        tmp_path / "capture",
        provider_factory=factory,
        transport=httpx2.MockTransport(handler),
    )
    assert len(calls) == 1
    assert report["status"] == "failed"
    assert report["error"] == failure
    assert "fixture-secret" not in (tmp_path / "capture/capture.json").read_text()


@pytest.mark.parametrize("mutation", ["budget", "score", "provider"])
def test_manifest_rejected(mutation):
    manifest = json.loads(FIXTURE.read_bytes())
    if mutation == "budget":
        manifest["budget"]["maxCalls"] = 2
    elif mutation == "score":
        manifest["questions"]["Q003"]["criteria"][0] = {}
    else:
        manifest["provider"]["endpoint"] = "https://other.example/"
    with pytest.raises(ValueError):
        validate_manifest(manifest)


def test_archived_live_capture():
    raw = FIXTURE.read_bytes()
    capture = json.loads(FIXTURE.with_name("verifier-live-capture.json").read_bytes())
    report = replay_verifier(json.loads(raw), raw, capture)
    assert report["status"] == "completed"
    assert report["calls"] == 1
    assert report["usage"]["input_tokens"] == 521
    assert report["quality"] == "not_evaluated"


def test_offline_cli_without_sdk(tmp_path):
    import os
    import subprocess
    import sys

    output = tmp_path / "replay"
    env = dict(os.environ)
    env.pop("PROXYAPI_API_KEY", None)
    result = subprocess.run(
        [
            sys.executable,
            "-S",
            str(FIXTURE.parents[3] / "evaluation/harness.py"),
            str(FIXTURE),
            "--verifier-capture",
            str(FIXTURE.with_name("verifier-live-capture.json")),
            "--output",
            str(output),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(result.stdout)
    assert report == json.loads((output / "report.json").read_text())
    assert report["status"] == "completed"
