"""Current SDK integration, separate from the source-pinned Stage 1 provider."""

import importlib.metadata
from dataclasses import asdict, dataclass

from provider_config import FORMATS as FORMATS
from provider_config import PRESETS as HISTORICAL_PRESETS
from provider_config import SCHEMA, ProviderConfig, credential, require
from provider_config import configuration as historical_configuration

ADAPTER_VERSION = "0.9.0"
PRESETS = {
    **HISTORICAL_PRESETS,
    "liquid-d1-ultra": (
        "typesafe-systemone",
        "https://api.liquid.ai/decisions/v1/systemone",
        "d1-ultra",
        "LIQUID_API_KEY",
    ),
}


@dataclass(frozen=True)
class RuntimeProviderConfig(ProviderConfig):
    def public(self):
        return {"schema": SCHEMA, "adapter_version": ADAPTER_VERSION, **asdict(self)}


def configuration(preset="typesafe", *, document=None, **overrides):
    """Reuse public validation without altering historical metadata or source pins."""
    if document is None:
        require(preset in PRESETS, "Unknown provider preset")
        api_format, endpoint_url, model, key_env = PRESETS[preset]
        document = {
            "schema": SCHEMA,
            "id": preset,
            "api_format": api_format,
            "endpoint_url": endpoint_url,
            "model": model,
            "key_env": key_env,
        }
    value = historical_configuration(preset, document=document, **overrides)
    return RuntimeProviderConfig(**asdict(value))


def build_provider(config, *, key_file=None, api_key=None, transport=None):
    """Construct the released text provider; never select images or call the API."""
    require(
        isinstance(config, RuntimeProviderConfig),
        "Current runtime requires provider_runtime.configuration",
    )
    require(
        importlib.metadata.version("mellea-jev-adapter") == ADAPTER_VERSION,
        "Install evaluation/requirements-providers-current.txt in a dedicated environment",
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
