"""Public, SDK-free provider configuration; credentials are resolved only on opt-in."""

import importlib.metadata
import math
import os
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from urllib.parse import urlsplit

ADAPTER_VERSION = "0.4.0"
SCHEMA = "normlab.provider-config/v1"
FORMATS = ("typesafe-systemone", "openai-decisions")
PRESETS = {
    "typesafe": (
        "typesafe-systemone",
        "https://api.typesafe.ai/v1/systemone",
        "jev-1.13.0",
        "TYPESAFE_API_KEY",
    ),
    "openai": (
        "openai-decisions",
        "https://api.openai.com/v1/decisions",
        "gpt-6-luna",
        "OPENAI_API_KEY",
    ),
    "coreinfra-jev": (
        "typesafe-systemone",
        "https://hub.coreinfra.ai/typesafe/api/v1/systemone",
        "jev-1.13.0",
        "COREINFRA_API_KEY",
    ),
    "coreinfra-decisions": (
        "openai-decisions",
        "https://hub.coreinfra.ai/openai/api/v1/decisions",
        "gpt-6-luna",
        "COREINFRA_API_KEY",
    ),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def valid_endpoint(value):
    """Operator-only HTTPS destinations; diagnostics never include the input URL."""
    message = "Endpoint requires HTTPS, DNS host, port 443 and a plain path; credentials/query/fragment forbidden"
    require(isinstance(value, str) and value == value.strip(), message)
    require(
        not re.search(r"[\\%?#\s]", value) and not re.search(r"/\.\.?(?:/|$)", value),
        message,
    )
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError:
        raise ValueError(message) from None
    host = url.hostname or ""
    require(
        url.scheme == "https"
        and not url.username
        and not url.password
        and not url.query
        and not url.fragment
        and port in (None, 443)
        and len(host) <= 253
        and re.fullmatch(
            r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?",
            host,
        )
        and re.fullmatch(r"/[A-Za-z0-9._~/-]*", url.path)
        and "//" not in url.path,
        message,
    )
    # Match the SDK URL representation (lowercase DNS name, default port omitted).
    return url._replace(netloc=host).geturl()


@dataclass(frozen=True)
class ProviderConfig:
    id: str
    api_format: str
    endpoint_url: str
    model: str
    key_env: str
    timeout: float = 10.0

    def __post_init__(self):
        require(
            isinstance(self.id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", self.id),
            "Provider ID contract",
        )
        require(self.api_format in FORMATS, "Unknown provider API format")
        object.__setattr__(self, "endpoint_url", valid_endpoint(self.endpoint_url))
        require(
            isinstance(self.model, str)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:-]{0,255}", self.model),
            "Model metadata contract",
        )
        require(
            isinstance(self.key_env, str)
            and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", self.key_env),
            "Credential environment name contract",
        )
        require(
            type(self.timeout) in (float, int)
            and math.isfinite(self.timeout)
            and 0 < self.timeout <= 120,
            "Timeout must be finite, positive and at most 120 seconds",
        )

    def public(self):
        return {"schema": SCHEMA, "adapter_version": ADAPTER_VERSION, **asdict(self)}


def configuration(preset="typesafe", *, document=None, **overrides):
    """Resolve public metadata only. No SDK imports, credential reads or network."""
    if document is None:
        require(preset in PRESETS, "Unknown provider preset")
        api_format, endpoint_url, model, key_env = PRESETS[preset]
        config = ProviderConfig(preset, api_format, endpoint_url, model, key_env)
    else:
        require(
            isinstance(document, dict) and document.get("schema") == SCHEMA,
            "Provider configuration schema",
        )
        required = {"schema", "id", "api_format", "endpoint_url", "model", "key_env"}
        require(
            required <= set(document) <= required | {"timeout"},
            "Public configuration fields only; API keys are forbidden",
        )
        config = ProviderConfig(**{k: v for k, v in document.items() if k != "schema"})
    return replace(config, **{k: v for k, v in overrides.items() if v is not None})


def credential(config, key_file=None):
    if key_file is None:
        key = os.environ.get(config.key_env, "")
    else:
        path = Path(key_file)
        require(path.is_absolute(), "Credential file must be an absolute path")
        try:
            stat = path.stat()
            require(
                path.is_file() and stat.st_size <= 8192 and stat.st_mode & 0o077 == 0,
                "Credential file must be private and bounded",
            )
            key = path.read_text().removesuffix("\n").removesuffix("\r")
        except OSError:
            raise ValueError("Cannot read credential file") from None
    require(
        isinstance(key, str)
        and 0 < len(key) <= 8192
        and key.isascii()
        and all(33 <= ord(c) <= 126 for c in key),
        "Missing or invalid credential for selected provider",
    )
    return key


def build_provider(config, *, key_file=None, api_key=None, transport=None):
    """One exact endpoint, explicit key selection, and SDK retries disabled by adapter."""
    require(
        importlib.metadata.version("mellea-jev-adapter") == ADAPTER_VERSION,
        "Install evaluation/requirements-providers.txt in a dedicated environment",
    )
    key = credential(config, key_file) if api_key is None else api_key
    if config.api_format == "typesafe-systemone":
        from mellea_jev.providers.typesafe import TypeSafeProvider

        provider = TypeSafeProvider
    else:
        from mellea_jev.providers.openai import OpenAIProvider

        provider = OpenAIProvider
    return provider(
        api_key=key,
        model=config.model,
        endpoint_url=config.endpoint_url,
        timeout=config.timeout,
        transport=transport,
    )
