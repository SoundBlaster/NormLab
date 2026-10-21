"""Current D1 Choice routing and captured-response replay; no provider requests."""

import json
import subprocess
import sys

import httpx2
import pytest
from provider_config import PRESETS as HISTORICAL_PRESETS
from provider_runtime import PRESETS, configuration
from provider_smoke import run
from test_categorical_runtime import KEY, ROOT, offline  # noqa: F401


def test_current_liquid_preset_does_not_modify_historical_configuration():
    assert "liquid-d1-ultra" not in HISTORICAL_PRESETS
    assert {k: PRESETS[k] for k in HISTORICAL_PRESETS} == HISTORICAL_PRESETS
    public = configuration("liquid-d1-ultra").public()
    document = json.loads(
        (ROOT / "fixtures/providers/liquid-d1-ultra-config.json").read_text()
    )
    assert configuration(document=document).public() == public
    assert public["adapter_version"] == "0.9.0"
    assert public["key_env"] == "LIQUID_API_KEY"


@pytest.mark.parametrize("job", ["U01", "U03"])
def test_captured_liquid_choice_replays_through_installed_sdk_and_bridge(tmp_path, job):
    capture = json.loads(
        (ROOT / "docs/evidence/claim-origin-probe-2026-10-21/report.json").read_text()
    )
    recorded = next(r for r in capture["attemptLog"] if r["job"] == job)
    request = recorded["request"]
    data = {k: request[k] for k in ("state", "questions")}
    question = data["questions"]["claim_origin"]
    policy = {
        "schema": "normlab.categorical-policy/v1",
        "questions": {
            "claim_origin": {
                k: "review" if k == "indeterminate" else "accept"
                for k in question["criteria"]
            }
        },
    }

    def handler(actual):
        assert str(actual.url) == "https://api.liquid.ai/decisions/v1/systemone"
        assert actual.headers["Authorization"] == "Bearer " + KEY
        assert json.loads(actual.read()) == request
        # Use the actual Liquid response body, not a fabricated Jev-shaped reply.
        return httpx2.Response(200, json=recorded["response"])

    result = run(
        configuration("liquid-d1-ultra", key_env="NORMLAB_OFFLINE_TEST_KEY"),
        data,
        tmp_path / "replay",
        1,
        transport=httpx2.MockTransport(handler),
        categorical=True,
        policy=policy,
    )
    assert result["calls"] == 1
    record = result["records"]["claim_origin"]
    assert record["status"] == "completed"
    response = record["result"]
    assert response["answers"] == {"claim_origin": recorded["label"]}
    assert response["returned_model"] == "d1-ultra"
    assert response["request_id"] is None
    native = response["native_results"]["claim_origin"]
    expected = recorded["response"]["answers"]["claim_origin"]
    assert native["confidence"] == expected["confidence"]
    assert native["probabilities"] == expected["probabilities"]
    assert response["usage"]["input_tokens"] == recorded["usage"]["input_tokens"]
    assert response["usage"]["output_tokens"] == 0
    assert KEY not in json.dumps(result)


def test_liquid_public_config_selects_same_default_without_sdk_or_keys():
    process = subprocess.run(
        [
            sys.executable,
            "-B",
            "-S",
            str(ROOT / "evaluation/categorical_smoke.py"),
            str(ROOT / "fixtures/providers/stage1-choice.json"),
            "--config",
            str(ROOT / "fixtures/providers/liquid-d1-ultra-config.json"),
            "--policy",
            str(ROOT / "fixtures/providers/choice-policy.json"),
        ],
        env={},
        capture_output=True,
        text=True,
        check=True,
    )
    plan = json.loads(process.stdout)
    assert plan["calls"] == 0
    assert plan["provider"] == configuration("liquid-d1-ultra").public()
