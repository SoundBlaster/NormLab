"""Released 0.7 SDK compatibility over synthetic HTTP; no provider inference."""

import asyncio
import json
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx2
import pytest
from mellea_jev import JevClassifier, JevScorer, JevVerifier
from provider_config import configuration as historical_configuration
from provider_runtime import ADAPTER_VERSION, PRESETS, build_provider, configuration
from provider_smoke import read_json, run

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "fixtures/providers/smoke.json"
KEY = "offline-placeholder-not-a-real-credential"


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Network forbidden in current SDK contracts")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", denied)


def response(request):
    body = json.loads(request.read())
    openai = isinstance(body["questions"], list)
    question = (
        body["questions"][0] if openai else next(iter(body["questions"].values()))
    )
    kind = question["type"]
    if kind in {"predicate", "noul"}:
        answer = {"type": kind, "probability" if openai else "noul": 0.9}
    else:
        if kind == "choice":
            labels = (
                [x["value"] for x in question["choices"]]
                if openai
                else list(question["criteria"])
            )
            answer = {"type": kind, "choice": labels[-1], "confidence": 1.0}
        else:
            labels = (
                [x["label"] for x in question["levels"]]
                if openai
                else question["criteria"]
            )
            answer = {"type": kind, "score": len(labels) - 1.0, "confidence": 1.0}
        probabilities = [float(i == len(labels) - 1) for i in range(len(labels))]
        if openai:
            answer["probabilities"] = [
                {
                    "value": label if kind == "choice" else i,
                    "probability": p,
                    **({"label": label} if kind == "score" else {}),
                }
                for i, (label, p) in enumerate(zip(labels, probabilities))
            ]
        else:
            answer["probabilities"] = {
                label if kind == "choice" else str(i): p
                for i, (label, p) in enumerate(zip(labels, probabilities))
            }
            if kind == "score":
                answer["legend"] = {str(i): label for i, label in enumerate(labels)}
    if openai:
        answers = [{**answer, "name": question["name"]}]
    else:
        answers = {next(iter(body["questions"])): answer}
    return httpx2.Response(
        200,
        json={
            "id": "fixture-id",
            "model": "fixture-model",
            "usage": {
                "input_tokens": 15,
                "output_tokens": 4,
                **(
                    {
                        "total_tokens": 19,
                        "input_tokens_details": {
                            "cached_tokens": 0,
                            "cache_write_tokens": 0,
                        },
                        "output_tokens_details": {"reasoning_tokens": 0},
                    }
                    if openai
                    else {}
                ),
            },
            "answers": answers,
        },
        headers={"x-request-id": "fixture-id", "x-typesafe-request-id": "fixture-id"},
    )


@pytest.mark.parametrize("preset", list(PRESETS) + ["custom"])
def test_all_primitives_capture_current_sdk_requests(tmp_path, monkeypatch, preset):
    config = (
        configuration(
            document={
                "schema": "normlab.provider-config/v1",
                "id": "custom",
                "api_format": "typesafe-systemone",
                "endpoint_url": "https://gateway.example.com/custom/systemone",
                "model": "custom/model",
                "key_env": "NORMLAB_OFFLINE_TEST_KEY",
            }
        )
        if preset == "custom"
        else configuration(preset, key_env="NORMLAB_OFFLINE_TEST_KEY")
    )
    monkeypatch.setenv(config.key_env, KEY)
    data = read_json(DATA)
    seen = []

    def handler(request):
        body = json.loads(request.read())
        assert str(request.url) == config.endpoint_url
        assert request.headers["authorization"] == "Bearer " + KEY
        assert request.headers["content-type"].startswith("application/json")
        assert set(body) == (
            {"model", "input", "questions"}
            if config.api_format == "openai-decisions"
            else {"model", "state", "questions"}
        )
        state = json.loads(body["input"]) if "input" in body else body["state"]
        assert state == data["state"]
        assert body["model"] == config.model
        seen.append(body)
        return response(request)

    report = run(
        config, data, tmp_path / "capture", 3, transport=httpx2.MockTransport(handler)
    )
    assert "configurationError" not in report
    assert report["calls"] == len(seen) == 3
    assert report["provider"]["adapter_version"] == ADAPTER_VERSION == "0.7.0"
    assert report["dependencies"]["mellea-jev-adapter"] == ADAPTER_VERSION
    assert report["mode"] == "mock-transport"
    assert report["schema"] == "normlab.provider-smoke/v2"
    assert report["semanticQualityEvidence"] is False
    assert report["cost"] is None
    for record in report["records"].values():
        assert record["status"] == "completed"
        assert record["result"]["request_id"] == "fixture-id"
        assert record["result"]["model"] == "fixture-model"
        assert record["result"]["usage"] == {
            "input_tokens": 15,
            "output_tokens": 4,
            "cost_usd": None,
        }
        assert record["latencySeconds"] >= 0
    assert report["records"]["payment_claim"]["result"]["p_yes"] == 0.9
    assert report["records"]["vehicle_match"]["result"]["choice"] == "unknown"
    assert report["records"]["certainty"]["result"]["score"] == 2.0
    assert KEY not in json.dumps(report)
    assert json.loads((tmp_path / "capture/report.json").read_text()) == report


@pytest.mark.parametrize("preset", ["coreinfra-jev", "coreinfra-decisions"])
@pytest.mark.parametrize("primitive", ["noul", "choice", "score"])
def test_current_provider_with_real_mellea_requirements(preset, primitive):
    calls = []

    def handler(request):
        calls.append(request)
        return response(request)

    with build_provider(
        configuration(preset), api_key=KEY, transport=httpx2.MockTransport(handler)
    ) as provider:
        if primitive == "noul":
            requirement = JevVerifier(provider, "Claim present?").as_requirement(
                check_only=True
            )
        elif primitive == "choice":
            requirement = JevClassifier(
                provider,
                "Status?",
                criteria={"asserted": "Claimed", "unknown": "Unknown"},
            ).as_requirement("unknown", minimum_confidence=0.7)
        else:
            requirement = JevScorer(
                provider, "Certainty?", criteria=["Low", "High"]
            ).as_requirement(maximum_score=1.0, minimum_confidence=0.7)
        context = SimpleNamespace(
            last_output=lambda: SimpleNamespace(value="Synthetic candidate.")
        )
        assert bool(asyncio.run(requirement.validate(None, context)))
    assert len(calls) == 1


def test_current_factory_does_not_relabel_historical_configuration():
    with pytest.raises(ValueError, match="Current runtime"):
        build_provider(historical_configuration(), api_key=KEY)
    assert historical_configuration().public()["adapter_version"] == "0.4.0"


def test_version_drift_fails_before_reading_credentials():
    with (
        patch("importlib.metadata.version", return_value="0.4.0"),
        patch(
            "provider_runtime.credential", side_effect=AssertionError("No key reads")
        ),
        pytest.raises(ValueError, match="requirements-providers-current"),
    ):
        build_provider(configuration())


def test_smoke_dry_run_without_sdk_or_credentials():
    process = subprocess.run(
        [
            sys.executable,
            "-B",
            "-S",
            str(ROOT / "evaluation/provider_smoke.py"),
            str(DATA),
            "--provider",
            "coreinfra-jev",
            "--max-calls",
            "3",
        ],
        check=True,
        capture_output=True,
        text=True,
        env={},
    )
    report = json.loads(process.stdout)
    assert report["calls"] == 0
    assert report["mode"] == "dry-run"
    assert report["provider"]["adapter_version"] == ADAPTER_VERSION


@pytest.mark.parametrize("preset", ["coreinfra-jev", "coreinfra-decisions"])
@pytest.mark.parametrize("status", [302, 401, 429, 500])
def test_http_failures_never_redirect_retry_or_expose_error_body(
    tmp_path, monkeypatch, preset, status
):
    config = configuration(preset, key_env="NORMLAB_OFFLINE_TEST_KEY")
    monkeypatch.setenv(config.key_env, KEY)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(
            status,
            text="private body " + KEY,
            headers={"location": "https://wrong.invalid/"},
        )

    report = run(
        config,
        read_json(DATA),
        tmp_path / "capture",
        3,
        transport=httpx2.MockTransport(handler),
    )
    assert len(calls) == report["calls"] == 1
    assert report["requests"][0]["httpStatus"] == status
    assert report["records"]["payment_claim"]["status"] == "failed"
    assert report["records"]["vehicle_match"]["status"] == "not-executed"
    assert "private body" not in json.dumps(report)
    assert KEY not in json.dumps(report)
