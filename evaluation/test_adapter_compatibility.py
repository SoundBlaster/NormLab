"""Compatibility is additive metadata support, never live/version authority."""

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import stage1_provider_executor as executor
from check_legacy_sdk_compatibility import CompatibilityProbe, compatible_gate
from verifier_capture import replay_verifier

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/parking-pilot/evaluation-harness/verifier-smoke.json"


def capture_with_cost(cost):
    capture = json.loads(FIXTURE.with_name("verifier-live-capture.json").read_bytes())
    response = capture["turn"]["response"]
    for result in [response, *response["answers"].values()]:
        result["usage"]["cost_usd"] = copy.deepcopy(cost)
    return capture


@pytest.mark.parametrize("cost", [None, 0, 0.000002, 1])
def test_optional_reported_cost_is_preserved_without_an_inferred_total(cost):
    raw = FIXTURE.read_bytes()
    capture = capture_with_cost(cost)
    before = copy.deepcopy(capture)
    report = replay_verifier(json.loads(raw), raw, capture)
    assert capture == before
    assert report["usage"]["cost_usd"] == cost
    assert report["cost"] is None
    assert report["quality"] == "not_evaluated"


@pytest.mark.parametrize(
    "cost", [True, -1, -0.1, float("nan"), float("inf"), "0.01", {}, []]
)
def test_malformed_cost_is_rejected(cost):
    raw = FIXTURE.read_bytes()
    with pytest.raises(ValueError, match="Usage contract"):
        replay_verifier(json.loads(raw), raw, capture_with_cost(cost))


def test_unknown_usage_fields_and_inconsistent_answer_cost_are_rejected():
    raw = FIXTURE.read_bytes()
    capture = capture_with_cost(None)
    capture["turn"]["response"]["usage"]["unknown"] = 0
    with pytest.raises(ValueError, match="Usage contract"):
        replay_verifier(json.loads(raw), raw, capture)
    capture = capture_with_cost(0.1)
    answer = next(iter(capture["turn"]["response"]["answers"].values()))
    answer["usage"]["cost_usd"] = 0.2
    with pytest.raises(ValueError, match="metadata consistency"):
        replay_verifier(json.loads(raw), raw, capture)


def test_probe_cannot_enable_live_and_restores_version_guards(tmp_path):
    original_require, original_run, original_factory = (
        executor.require,
        executor.run,
        executor.build_provider,
    )
    with CompatibilityProbe() as probe:
        with pytest.raises(ValueError, match="forbids live"):
            executor.run({}, tmp_path / "forbidden", mock=False)
        with pytest.raises(ValueError, match="forbids live"):
            executor.run({}, tmp_path / "forbidden", mock=True, permit={})
        with pytest.raises(ValueError, match="frozen 0.4.0"):
            executor.run({"adapterVersion": "0.7.0"}, tmp_path / "forbidden", mock=True)
        with pytest.raises(ValueError, match="Adapter version mismatch"):
            executor.require(False, "Adapter version mismatch")
        assert probe.gates == {}
        with pytest.raises(ValueError, match="Payload contract"):
            executor.require(False, "Payload contract")
    assert not (tmp_path / "forbidden").exists()
    assert executor.require is original_require
    assert executor.run is original_run
    assert executor.build_provider is original_factory
    with pytest.raises(ValueError, match="Adapter version mismatch"):
        executor.require(False, "Adapter version mismatch")


def test_probe_rejects_an_unchecked_adapter_version():
    with (
        patch("importlib.metadata.version", return_value="0.4.0"),
        pytest.raises(ValueError, match="requirements-providers-current"),
    ):
        with CompatibilityProbe():
            pytest.fail("No legacy environment should be selected")


@pytest.mark.parametrize("message", ["Adapter version mismatch", "Runtime metadata"])
def test_probe_only_accepts_exact_planned_and_recorded_adapter_versions(message):
    for value, accepted in (
        (None, False),
        ([], False),
        ({}, False),
        ({"mellea-jev-adapter": "0.4.0"}, False),
        ({"mellea-jev-adapter": "0.7.0"}, False),
        ({"mellea-jev-adapter": "0.8.0"}, True),
    ):
        values = {
            "plan": {"adapterVersion": "0.4.0"},
            "versions": value,
            "index": {"dependencies": value},
        }
        assert compatible_gate(message, values) is accepted
        values["plan"]["adapterVersion"] = "0.8.0"
        assert compatible_gate(message, values) is False
