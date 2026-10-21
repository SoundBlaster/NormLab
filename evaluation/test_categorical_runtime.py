"""Released 0.9 bridge with real SDK serialization and synthetic HTTP only."""

import copy
import json
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx2
import pytest
from categorical_runtime import evaluate, evaluation_document, validate_policy
from mellea_jev import CategoricalResult, JevHTTPError
from provider_runtime import configuration as native_configuration
from provider_smoke import run
from responses_runtime import configuration as responses_configuration
from test_provider_runtime import response as native_response
from test_responses_runtime import answer as responses_answer
from test_responses_runtime import data

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "fixtures/providers/choice-policy.json"
KEY = "offline-categorical-placeholder"


def policy(value):
    mapping = json.loads(POLICY.read_text())
    if "second" in value["questions"]:
        mapping["questions"]["second"] = {"yes": "accept", "unknown": "review"}
    return mapping


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Network forbidden in categorical evaluate checks")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", denied)
    monkeypatch.setenv("NORMLAB_OFFLINE_TEST_KEY", KEY)


@pytest.mark.parametrize(
    "preset",
    [
        "typesafe",
        "openai",
        "coreinfra-jev",
        "coreinfra-decisions",
        "liquid-d1-ultra",
        "openai-responses",
        "coreinfra-responses",
    ],
)
@pytest.mark.parametrize(
    "label,outcome",
    [("compatible", "accept"), ("incompatible", "reject"), ("indeterminate", "review")],
)
def test_installed_bridge_preserves_tasks_evidence_and_policy(
    tmp_path, preset, label, outcome
):
    value = data()
    before = copy.deepcopy(value)
    responses = preset.endswith("responses")
    config = (responses_configuration if responses else native_configuration)(
        preset, key_env="NORMLAB_OFFLINE_TEST_KEY"
    )
    requests = []

    def handler(request):
        body = json.loads(request.read())
        requests.append(body)
        assert str(request.url) == config.endpoint_url
        assert body["model"] == config.model
        if responses:
            assert json.loads(body["input"]) == {"state": value["state"]}
            reply = responses_answer(value["questions"])
            reply["output"][0]["content"][0]["text"] = json.dumps(
                {"answers": {"overall": label}}
            )
        else:
            assert (
                json.loads(body["input"]) if "input" in body else body["state"]
            ) == value["state"]
            reply = json.loads(native_response(request).content)
            native = (
                reply["answers"][0]
                if isinstance(reply["answers"], list)
                else reply["answers"]["overall"]
            )
            assert (native.get("name", "overall")) == "overall"
            native["choice"] = label
            native["confidence"] = 0.82
            probabilities = {
                key: 0.88 if key == label else 0.06
                for key in value["questions"]["overall"]["criteria"]
            }
            native["probabilities"] = (
                [{"value": k, "probability": v} for k, v in probabilities.items()]
                if isinstance(reply["answers"], list)
                else probabilities
            )
        return httpx2.Response(
            200,
            json=reply,
            headers={
                "x-request-id": "fixture-id",
                "x-typesafe-request-id": "fixture-id",
            },
        )

    report = run(
        config,
        value,
        tmp_path / "capture",
        1,
        transport=httpx2.MockTransport(handler),
        categorical=True,
        policy=policy(value),
    )
    assert value == before
    assert report["schema"] == "normlab.categorical-evaluation-smoke/v1"
    assert report["evaluationMethod"] == "CategoricalRequirement.evaluate"
    assert report["calls"] == len(requests) == 1
    record = report["records"]["overall"]
    assert record["status"] == "completed"
    result = record["result"]
    assert result["answers"] == {"overall": label}
    assert result["decision"]["outcome"] == outcome
    assert result["decision"]["score"] is None
    assert result["questionDecisions"] == {"overall": outcome}
    assert result["request_id"] == "fixture-id"
    assert result["requested_model"] == config.model
    assert report["dependencies"]["mellea-jev-adapter"] == "0.9.0"
    if responses:
        assert result["native_results"] is None
    else:
        native = result["native_results"]["overall"]
        assert native["choice"] == label and native["confidence"] == 0.82
        assert native["probabilities"][label] == 0.88
    assert not {"confidence", "probabilities", "evidence"} & set(result)
    assert KEY not in json.dumps(report)
    assert json.loads((tmp_path / "capture/report.json").read_text()) == report


@pytest.mark.parametrize(
    "batch,tactic,calls", [(True, "batch", 1), (True, "independent", 2)]
)
def test_responses_batch_and_independent_are_explicit(tmp_path, batch, tactic, calls):
    value = data(batch)

    def handler(request):
        prompts = json.loads(
            json.loads(request.read())["instructions"].split("\n", 1)[1]
        )
        return httpx2.Response(
            200, json=responses_answer({k: value["questions"][k] for k in prompts})
        )

    report = run(
        responses_configuration(key_env="NORMLAB_OFFLINE_TEST_KEY"),
        value,
        tmp_path / "capture",
        calls,
        transport=httpx2.MockTransport(handler),
        categorical=True,
        tactic=tactic,
        policy=policy(value),
    )
    assert report["calls"] == calls
    assert all(r["status"] == "completed" for r in report["records"].values())
    assert all(
        r["result"]["decision"]["outcome"] == "review"
        for r in report["records"].values()
    )


@pytest.mark.parametrize("failure", ["batch", "policy"])
def test_invalid_capability_or_policy_fails_before_output_credentials_or_dispatch(
    tmp_path, monkeypatch, failure
):
    value = data(True)
    mapping = policy(value)
    if failure == "policy":
        mapping["questions"]["overall"].pop("indeterminate")
    monkeypatch.setattr(
        "provider_config.credential", Mock(side_effect=AssertionError("No key reads"))
    )
    output = tmp_path / "forbidden"
    with pytest.raises(ValueError):
        run(
            native_configuration(),
            value,
            output,
            2,
            categorical=True,
            tactic="batch" if failure == "batch" else "independent",
            policy=mapping,
        )
    assert not output.exists()


@pytest.mark.parametrize(
    "preset",
    ["coreinfra-jev", "coreinfra-decisions", "coreinfra-responses", "liquid-d1-ultra"],
)
@pytest.mark.parametrize("failure", [401, 429, "transport", "protocol"])
def test_errors_remain_operational_without_retry_or_fallback(tmp_path, preset, failure):
    requests = []

    def handler(request):
        requests.append(request)
        if failure == "transport":
            raise httpx2.ConnectError("private " + KEY, request=request)
        return httpx2.Response(
            failure if isinstance(failure, int) else 200, json={"private": KEY}
        )

    config = (
        responses_configuration
        if preset.endswith("responses")
        else native_configuration
    )(preset, key_env="NORMLAB_OFFLINE_TEST_KEY")
    report = run(
        config,
        data(True),
        tmp_path / "capture",
        2,
        transport=httpx2.MockTransport(handler),
        categorical=True,
        policy=policy(data(True)),
    )
    assert report["calls"] == len(requests) == 1
    assert report["records"]["overall"]["status"] == "failed"
    assert report["records"]["overall"]["result"] is None
    assert report["records"]["second"]["status"] == "not-executed"
    assert KEY not in json.dumps(report)


def test_direct_evaluate_retains_bound_task_and_raises_operational_error():
    value = data()
    provider = SimpleNamespace(
        classify=Mock(return_value=CategoricalResult({"overall": "indeterminate"}))
    )
    evaluation = evaluate(provider, value, policy(value))
    assert evaluation.decision.outcome == "review"
    assert evaluation.task.state == value["state"]
    assert evaluation_document(evaluation, policy(value))["native_results"] is None
    provider.classify.assert_called_once_with(evaluation.task)
    error = JevHTTPError(401)
    provider.classify.side_effect = error
    with pytest.raises(JevHTTPError) as caught:
        evaluate(provider, value, policy(value))
    assert caught.value is error


@pytest.mark.parametrize(
    "preset",
    [
        None,
        "coreinfra-jev",
        "coreinfra-decisions",
        "coreinfra-responses",
        "liquid-d1-ultra",
    ],
)
def test_cli_dry_run_needs_no_sdk_or_credentials(preset):
    process = subprocess.run(
        [
            sys.executable,
            "-B",
            "-S",
            str(ROOT / "evaluation/categorical_smoke.py"),
            str(ROOT / "fixtures/providers/stage1-choice.json"),
            *(["--provider", preset] if preset else []),
            "--policy",
            str(POLICY),
        ],
        env={},
        check=True,
        capture_output=True,
        text=True,
    )
    plan = json.loads(process.stdout)
    assert plan["calls"] == 0 and plan["plannedCalls"] == 1
    assert plan["provider"]["adapter_version"] == "0.9.0"
    assert plan["evaluationMethod"] == "CategoricalRequirement.evaluate"
    if preset is None:
        config = plan["provider"]
        assert config["id"] == "liquid-d1-ultra"
        assert config["api_format"] == "typesafe-systemone"
        assert config["model"] == "d1-ultra"
        assert "reasoning_effort" not in config
        assert "max_output_tokens" not in config
        assert config["key_env"] == "LIQUID_API_KEY"
        assert config["endpoint_url"] == "https://api.liquid.ai/decisions/v1/systemone"


@pytest.mark.parametrize(
    "name,api_format",
    [
        ("coreinfra-jev", "typesafe-systemone"),
        ("coreinfra-decisions", "openai-decisions"),
        ("coreinfra-responses", "openai-responses"),
    ],
)
def test_explicit_config_preserves_route_after_default_switch(name, api_format):
    process = subprocess.run(
        [
            sys.executable,
            "-B",
            "-S",
            str(ROOT / "evaluation/categorical_smoke.py"),
            str(ROOT / "fixtures/providers/stage1-choice.json"),
            "--config",
            str(
                ROOT
                / f"fixtures/providers/bridge-semantic-probe-v1/configs/{name}.json"
            ),
            "--policy",
            str(POLICY),
        ],
        env={},
        check=True,
        capture_output=True,
        text=True,
    )
    plan = json.loads(process.stdout)
    assert plan["calls"] == 0
    assert plan["provider"]["id"] == name
    assert plan["provider"]["api_format"] == api_format


def test_policy_does_not_assume_label_meaning():
    value = data()
    mapping = policy(value)
    mapping["questions"]["overall"]["compatible"] = "review"
    validate_policy(value, mapping)
    provider = SimpleNamespace(
        classify=lambda _: CategoricalResult({"overall": "compatible"})
    )
    assert evaluate(provider, value, mapping).decision.outcome == "review"


def test_explicit_null_config_is_not_replaced_with_a_default(tmp_path):
    config = tmp_path / "null.json"
    config.write_text("null")
    process = subprocess.run(
        [
            sys.executable,
            "-B",
            "-S",
            str(ROOT / "evaluation/categorical_smoke.py"),
            str(ROOT / "fixtures/providers/stage1-choice.json"),
            "--config",
            str(config),
            "--policy",
            str(POLICY),
        ],
        env={},
        capture_output=True,
        text=True,
    )
    assert process.returncode == 2
    assert "Invalid public categorical" in process.stderr
    assert "Traceback" not in process.stderr
