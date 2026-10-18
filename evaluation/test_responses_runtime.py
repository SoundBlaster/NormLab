"""Actual released SDK over synthetic HTTP; no hosted inference or credentials."""

import copy
import json
import socket
import subprocess
import sys
from pathlib import Path

import httpx2
import pytest
from provider_config import configuration as historical_configuration
from provider_smoke import run
from responses_runtime import configuration, task, task_digest, validate_task

ROOT = Path(__file__).resolve().parents[1]
KEY = "offline-responses-placeholder"
SAMPLE = ROOT / "fixtures/providers/stage1-choice.json"


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Network forbidden in categorical integration checks")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", denied)
    monkeypatch.setenv("NORMLAB_OFFLINE_TEST_KEY", KEY)


def data(batch=False):
    value = json.loads(SAMPLE.read_text())
    if batch:
        value["questions"]["second"] = {
            "type": "choice",
            "instructions": "Is the vehicle identified in the source?",
            "criteria": {"yes": "Explicit identification", "unknown": "Not identified"},
        }
    return value


def answer(questions):
    return {
        "id": "body-response-id",
        "model": "fixture-luna",
        "status": "completed",
        "usage": {"input_tokens": 100, "output_tokens": 10},
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {
                                "answers": {
                                    name: list(q["criteria"])[-1]
                                    for name, q in questions.items()
                                }
                            }
                        ),
                    }
                ],
            }
        ],
    }


@pytest.mark.parametrize(
    "preset", ["openai-responses", "coreinfra-responses", "custom"]
)
@pytest.mark.parametrize(
    "tactic,batch,calls",
    [("independent", False, 1), ("independent", True, 2), ("batch", True, 1)],
)
def test_actual_sdk_task_mapping_and_label_only_capture(
    tmp_path, preset, tactic, batch, calls
):
    value = data(batch)
    before = copy.deepcopy(value)
    config = configuration(
        "coreinfra-responses" if preset == "custom" else preset,
        key_env="NORMLAB_OFFLINE_TEST_KEY",
        **(
            {
                "id": "custom",
                "endpoint_url": "https://gateway.example.com/inference/responses",
                "model": "custom/luna",
            }
            if preset == "custom"
            else {}
        ),
    )
    seen = []

    def handler(request):
        body = json.loads(request.read())
        seen.append(body)
        assert str(request.url) == config.endpoint_url
        assert request.headers["authorization"] == "Bearer " + KEY
        assert body["model"] == config.model
        assert body["store"] is False and body["stream"] is False
        assert body["reasoning"] == {"effort": "low"}
        assert body["max_output_tokens"] == 1024
        assert json.loads(body["input"]) == {"state": value["state"]}
        prompts = json.loads(body["instructions"].split("\n", 1)[1])
        selected = {name: value["questions"][name] for name in prompts}
        assert prompts == {
            name: {k: v for k, v in q.items() if k != "type"}
            for name, q in selected.items()
        }
        schema = body["text"]["format"]
        assert schema["strict"] is True
        assert schema["schema"]["properties"]["answers"]["required"] == list(selected)
        for name, q in selected.items():
            assert schema["schema"]["properties"]["answers"]["properties"][name][
                "enum"
            ] == list(q["criteria"])
        return httpx2.Response(
            200, json=answer(selected), headers={"x-request-id": "header-request-id"}
        )

    report = run(
        config,
        value,
        tmp_path / "capture",
        calls,
        transport=httpx2.MockTransport(handler),
        categorical=True,
        tactic=tactic,
    )
    assert value == before
    assert report["calls"] == report["plannedCalls"] == len(seen) == calls
    assert report["schema"] == "normlab.responses-choice-smoke/v1"
    assert report["semanticTaskDigest"] == task_digest(value)
    assert report["questionOrder"] == list(value["questions"])
    assert (
        report["mode"] == "mock-transport"
        and report["semanticQualityEvidence"] is False
    )
    assert report["provider"]["api_format"] == "openai-responses"
    assert report["provider"]["adapter_version"] == "0.8.0"
    assert report["dependencies"]["mellea-jev-adapter"] == "0.8.0"
    for record in report["records"].values():
        assert record["status"] == "completed"
        result = record["result"]
        assert result["request_id"] == "header-request-id"
        assert result["returned_model"] == "fixture-luna"
        assert result["requested_model"] == config.model
        assert result["usage"] == {
            "input_tokens": 100,
            "output_tokens": 10,
            "cost_usd": None,
        }
        assert result["adapter_revision"] == "responses-choice-v1"
        assert not {"confidence", "probabilities", "native_results", "evidence"} & set(
            result
        )
    assert KEY not in json.dumps(report)
    assert json.loads((tmp_path / "capture/report.json").read_text()) == report


@pytest.mark.parametrize(
    "failure",
    [
        "401",
        "429",
        "500",
        "redirect",
        "transport",
        "refusal",
        "incomplete",
        "missing",
        "extra",
        "unknown",
        "duplicate",
    ],
)
@pytest.mark.parametrize("tactic", ["independent", "batch"])
def test_failures_stop_without_retry_or_answer_salvage(tmp_path, failure, tactic):
    value = data(True)
    calls = []

    def handler(request):
        calls.append(request)
        if failure == "transport":
            raise httpx2.ConnectError("private " + KEY, request=request)
        if failure.isdecimal() or failure == "redirect":
            return httpx2.Response(
                int(failure) if failure.isdecimal() else 302,
                text="private " + KEY,
                headers={"location": "https://elsewhere.invalid/"},
            )
        body = answer({"overall": value["questions"]["overall"]})
        if failure == "refusal":
            body["output"][0]["content"] = [
                {"type": "refusal", "refusal": "private " + KEY}
            ]
        elif failure == "incomplete":
            body["status"] = "incomplete"
        else:
            labels = {"overall": "indeterminate"}
            if failure == "missing":
                labels = {}
            elif failure == "extra":
                labels["extra"] = "indeterminate"
            elif failure == "unknown":
                labels["overall"] = "made-up"
            body["output"][0]["content"][0]["text"] = (
                json.dumps({"answers": labels})
                if failure != "duplicate"
                else '{"answers":{"overall":"compatible","overall":"incompatible"}}'
            )
        return httpx2.Response(200, json=body)

    report = run(
        configuration(key_env="NORMLAB_OFFLINE_TEST_KEY"),
        value,
        tmp_path / "capture",
        2,
        transport=httpx2.MockTransport(handler),
        categorical=True,
        tactic=tactic,
    )
    assert len(calls) == report["calls"] == 1
    failed = "batch" if tactic == "batch" else "overall"
    assert report["records"][failed]["status"] == "failed"
    assert report["records"][failed]["result"] is None
    if tactic == "independent":
        assert report["records"]["second"]["status"] == "not-executed"
    assert "private" not in json.dumps(report) and KEY not in json.dumps(report)


def test_task_snapshots_and_historical_semantic_identity():
    from plan_stage1_comparison import prepare

    historical = prepare(
        ROOT / "fixtures/parking-pilot/stage1-comparison-v1/experiment.json", "pilot"
    )
    value = data()
    original = historical["jobs"][0]
    assert value == original["task"]
    assert task_digest(value) == original["taskDigest"]
    captured = task(value)
    value["state"]["sourceText"] = "changed"
    assert captured.state["sourceText"] == original["task"]["state"]["sourceText"]


def test_unavailable_metadata_stays_null_for_batch(tmp_path):
    value = data(True)

    def handler(request):
        body = answer(value["questions"])
        for name in ("model", "usage"):
            body.pop(name)
        return httpx2.Response(200, json=body)

    report = run(
        configuration(key_env="NORMLAB_OFFLINE_TEST_KEY"),
        value,
        tmp_path / "capture",
        1,
        transport=httpx2.MockTransport(handler),
        categorical=True,
        tactic="batch",
    )
    result = report["records"]["batch"]["result"]
    assert set(result["answers"]) == set(value["questions"])
    assert result["returned_model"] is None
    assert result["request_id"] is None
    assert result["usage"] is None
    assert report["cost"] is None


@pytest.mark.parametrize("kind", ["noul", "score"])
def test_no_implicit_primitive_conversion(kind):
    value = data()
    value["questions"]["overall"] = {
        "type": kind,
        "instructions": "Question",
        "criteria": {"true": "Yes", "false": "No"}
        if kind == "noul"
        else ["Low", "High"],
    }
    with pytest.raises(ValueError, match="Choice"):
        validate_task(value)


def test_custom_public_config_and_sdk_free_cli():
    config = configuration(
        document={
            "schema": "normlab.responses-config/v1",
            "id": "custom",
            "api_format": "openai-responses",
            "endpoint_url": "https://gateway.example.com/exact",
            "model": "vendor/luna",
            "key_env": "CUSTOM_TEST_KEY",
            "reasoning_effort": None,
            "max_output_tokens": 512,
        }
    )
    assert config.endpoint_url == "https://gateway.example.com/exact"
    assert config.reasoning_effort is None
    with pytest.raises(ValueError):
        configuration(endpoint_url="http://wrong.example.com/responses")
    with pytest.raises(ValueError):
        configuration(max_output_tokens=True)
    with pytest.raises(ValueError):
        configuration(document={**config.public(), "api_key": KEY})
    process = subprocess.run(
        [
            sys.executable,
            "-B",
            "-S",
            str(ROOT / "evaluation/responses_smoke.py"),
            str(SAMPLE),
        ],
        env={},
        capture_output=True,
        text=True,
        check=True,
    )
    plan = json.loads(process.stdout)
    assert plan["calls"] == 0 and plan["mode"] == "dry-run"
    assert plan["semanticTaskDigest"] == task_digest(data())
    assert historical_configuration().public()["adapter_version"] == "0.4.0"


@pytest.mark.parametrize("field", ["id", "endpoint_url", "model", "key_env", "timeout"])
def test_null_public_fields_never_fall_back_to_native_defaults(field):
    document = {
        "schema": "normlab.responses-config/v1",
        "id": "custom",
        "api_format": "openai-responses",
        "endpoint_url": "https://gateway.example.com/custom",
        "model": "custom/luna",
        "key_env": "CUSTOM_KEY",
        "timeout": 10,
    }
    document[field] = None
    with pytest.raises(ValueError):
        configuration(document=document)
