"""Explicit opt-in ProxyAPI construction for future evaluation runs."""

import importlib.metadata
import os

ADAPTER_VERSION = "0.3.0"
KEY_VARIABLE = "PROXYAPI_API_KEY"
ENDPOINT = "https://api.proxyapi.ru/v1/decisions"
MODEL = "openai/gpt-6-luna-decisions"


def provider_metadata():
    """Public configuration only; never reads or serializes a credential."""
    return {
        "id": "proxyapi-luna-decisions",
        "endpoint": ENDPOINT,
        "model": MODEL,
        "wireContract": "proxyapi-state-questions/v1",
        "adapterVersion": ADAPTER_VERSION,
    }


def build_proxyapi_provider(*, api_key=None, transport=None):
    """Construct a provider without a request; callers own close/deadline/budget."""
    # Historical v1 metadata remains frozen; actual runtime is recorded separately
    # in capture.dependencies. Current SDK compatibility is checked separately.
    if importlib.metadata.version("mellea-jev-adapter") not in {
        ADAPTER_VERSION,
        "0.4.0",
        "0.7.0",
        "0.8.0",
        "0.9.0",
    }:
        raise ValueError(
            "Install evaluation/requirements-providers-current.txt in a dedicated environment"
        )
    key = os.environ.get(KEY_VARIABLE, "") if api_key is None else api_key
    if (
        not isinstance(key, str)
        or not key
        or not key.isascii()
        or any(c.isspace() for c in key)
    ):
        raise ValueError(
            "Supply PROXYAPI_API_KEY or an explicit nonempty ASCII credential"
        )
    from providers.proxyapi import ProxyAPIProvider

    return ProxyAPIProvider(api_key=key, model=MODEL, timeout=10.0, transport=transport)
