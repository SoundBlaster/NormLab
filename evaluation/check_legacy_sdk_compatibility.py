"""Mock-only SDK compatibility probe; never a historical/live execution command."""

import argparse
import hashlib
import importlib.metadata
import json
import socket
import sys
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from provider_runtime import ADAPTER_VERSION, RuntimeProviderConfig, build_provider

EVALUATION = Path(__file__).resolve().parent


def compatible_gate(message, values):
    plan = values.get("plan")
    if not isinstance(plan, dict) or plan.get("adapterVersion") != "0.4.0":
        return False
    if message == "Adapter version mismatch":
        versions = values.get("versions")
    elif message == "Runtime metadata":
        index = values.get("index")
        versions = index.get("dependencies") if isinstance(index, dict) else None
    else:
        return False
    return (
        isinstance(versions, dict)
        and versions.get("mellea-jev-adapter") == ADAPTER_VERSION
    )


class CompatibilityProbe:
    """Keep frozen source and actual metadata; bypass two version equalities only."""

    def __init__(self):
        self.gates = {}
        self.attempts = 0
        self.stack = ExitStack()

    def __enter__(self):
        import httpx2
        import stage1_provider_executor as executor

        if importlib.metadata.version("mellea-jev-adapter") != ADAPTER_VERSION:
            raise ValueError("Install requirements-providers-current.txt")
        original_require, original_run = executor.require, executor.run

        def require(ok, message):
            if (
                not ok
                and message in {"Adapter version mismatch", "Runtime metadata"}
                and compatible_gate(message, sys._getframe(1).f_locals)
            ):
                self.gates[message] = self.gates.get(message, 0) + 1
                return
            return original_require(ok, message)

        def mock_only(plan, folder, **kwargs):
            if kwargs.get("mock") is not True or kwargs.get("permit") is not None:
                raise ValueError("Compatibility probe forbids live execution")
            if plan["adapterVersion"] != "0.4.0":
                raise ValueError("Compatibility probe requires the frozen 0.4.0 plan")
            self.attempts += 1
            return original_run(plan, folder, **kwargs)

        def current_provider(config, **kwargs):
            return build_provider(RuntimeProviderConfig(**asdict(config)), **kwargs)

        def denied(*args, **kwargs):
            raise AssertionError("Network forbidden in legacy SDK compatibility probe")

        for item in (
            patch.object(socket.socket, "connect", denied),
            patch.object(httpx2.HTTPTransport, "handle_request", denied),
            patch.object(executor, "run", mock_only),
            patch.object(executor, "require", require),
            patch.object(executor, "build_provider", current_provider),
        ):
            self.stack.enter_context(item)
        return self

    def __exit__(self, *error):
        return self.stack.__exit__(*error)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--temp-dir", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.report.exists():
        parser.error("Use a new report path")
    import pytest

    with CompatibilityProbe() as probe:
        outcome = pytest.main(
            [
                str(EVALUATION / "test_retry_contracts_v2.py"),
                "-q",
                "-o",
                f"cache_dir={args.cache_dir}",
                f"--basetemp={args.temp_dir}",
            ]
        )
    report = {
        "schema": "normlab.legacy-sdk-compatibility/v1",
        "diagnosticOnly": True,
        "plannedAdapterVersion": "0.4.0",
        "actualAdapterVersion": importlib.metadata.version("mellea-jev-adapter"),
        "dependencies": {
            **{
                name: importlib.metadata.version(name)
                for name in (
                    "mellea-jev-adapter",
                    "typesafe-sdk",
                    "openai",
                    "httpx2",
                    "mellea",
                )
            },
            "python": sys.version,
        },
        "sourceDigests": {
            name: hashlib.sha256((EVALUATION / name).read_bytes()).hexdigest()
            for name in (
                "check_legacy_sdk_compatibility.py",
                "provider_runtime.py",
                "provider_config.py",
                "stage1_provider_executor.py",
                "stage1_provider_plan.py",
                "stage1_provider_wire.py",
                "stage1_retry_executor_v2.py",
                "test_retry_contracts_v2.py",
            )
        },
        "versionEqualityBypasses": probe.gates,
        "mockAttemptInvocations": probe.attempts,
        "networkCalls": 0,
        "semanticQualityEvidence": False,
        "historicalExecutionCompatibility": False,
        "pytestExitCode": int(outcome),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return int(outcome)


if __name__ == "__main__":
    sys.exit(main())
