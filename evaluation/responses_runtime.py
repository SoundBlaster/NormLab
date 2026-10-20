"""Current label-only Responses integration; no frozen/native runtime migration."""

import importlib.metadata
import json
from dataclasses import asdict, dataclass
from hashlib import sha256

from provider_config import require
from provider_runtime import ADAPTER_VERSION, RuntimeProviderConfig
from provider_runtime import configuration as native_configuration
from provider_task import payload

SCHEMA = "normlab.responses-config/v1"
MAX_TASK_BYTES = 32768
PRESETS = {
    "openai-responses": "https://api.openai.com/v1/responses",
    "coreinfra-responses": "https://hub.coreinfra.ai/openai/api/v1/responses",
}


@dataclass(frozen=True)
class ResponsesConfig:
    # Reuse existing validation for common public fields, not its wire protocol.
    provider: RuntimeProviderConfig
    reasoning_effort: str | None = "low"
    max_output_tokens: int = 1024

    def __post_init__(self):
        require(
            isinstance(self.provider, RuntimeProviderConfig)
            and self.provider.api_format == "openai-decisions",
            "Validated current common provider fields required",
        )
        require(
            self.reasoning_effort
            in (None, "none", "minimal", "low", "medium", "high", "xhigh"),
            "Explicit reasoning effort",
        )
        require(
            type(self.max_output_tokens) is int
            and 16 <= self.max_output_tokens <= 16384,
            "Output token bound",
        )

    @property
    def endpoint_url(self):
        return self.provider.endpoint_url

    @property
    def model(self):
        return self.provider.model

    def public(self):
        return {
            **self.provider.public(),
            "schema": SCHEMA,
            "api_format": "openai-responses",
            "reasoning_effort": self.reasoning_effort,
            "max_output_tokens": self.max_output_tokens,
        }


def configuration(preset="coreinfra-responses", *, document=None, **overrides):
    if document is None:
        require(preset in PRESETS, "Unknown Responses preset")
        fields = {
            "id": preset,
            "endpoint_url": PRESETS[preset],
            "model": "gpt-6-luna",
            "key_env": "COREINFRA_API_KEY"
            if preset == "coreinfra-responses"
            else "OPENAI_API_KEY",
        }
    else:
        required = {"schema", "id", "api_format", "endpoint_url", "model", "key_env"}
        require(
            isinstance(document, dict)
            and required
            <= set(document)
            <= required | {"timeout", "reasoning_effort", "max_output_tokens"}
            and document["schema"] == SCHEMA
            and document["api_format"] == "openai-responses",
            "Public Responses configuration fields only",
        )
        fields = {
            k: v for k, v in document.items() if k not in {"schema", "api_format"}
        }
    fields.update({k: v for k, v in overrides.items() if v is not None})
    effort = fields.pop("reasoning_effort", "low")
    tokens = fields.pop("max_output_tokens", 1024)
    provider = native_configuration(
        document={
            "schema": "normlab.provider-config/v1",
            "api_format": "openai-decisions",
            **fields,
        }
    )
    return ResponsesConfig(provider, effort, tokens)


def validate_task(data):
    payload(data)
    require(
        all(q["type"] == "choice" for q in data["questions"].values()),
        "Responses accepts Choice questions only",
    )
    # Bound the complete task, including criteria. Escaped Responses instructions
    # and repeated request captures can be larger than the source JSON file.
    require(
        len(json.dumps(data, ensure_ascii=False, allow_nan=False).encode())
        <= MAX_TASK_BYTES,
        "Complete Choice task exceeds 32768 UTF-8 bytes",
    )
    return data


def task_digest(data):
    """Provider-independent digest of the exact semantic input, without answers."""
    validate_task(data)
    return sha256(
        json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def task(data):
    validate_task(data)
    from mellea_jev import CategoricalTask
    from mellea_jev.providers.typesafe import ChoiceQuestion

    return CategoricalTask(
        state=data["state"],
        questions={
            name: ChoiceQuestion(q["instructions"], q["criteria"])
            for name, q in data["questions"].items()
        },
    )


def build_provider(config, *, key_file=None, transport=None):
    from provider_config import credential

    require(isinstance(config, ResponsesConfig), "Responses configuration required")
    require(
        importlib.metadata.version("mellea-jev-adapter") == ADAPTER_VERSION,
        "Install evaluation/requirements-providers-current.txt",
    )
    key = credential(config.provider, key_file)
    from mellea_jev import ResponsesChoiceProvider

    return ResponsesChoiceProvider(
        api_key=key,
        model=config.model,
        endpoint_url=config.endpoint_url,
        timeout=config.provider.timeout,
        reasoning_effort=config.reasoning_effort,
        max_output_tokens=config.max_output_tokens,
        transport=transport,
    )


def result_document(result):
    # CategoricalResult contains MappingProxyType and sensitive optional evidence;
    # never serialize it wholesale or convert its labels to native probabilities.
    return {
        "answers": dict(result.answers),
        "requested_model": result.requested_model,
        "returned_model": result.returned_model,
        "request_id": result.request_id,
        "usage": asdict(result.usage) if result.usage else None,
        "adapter_revision": result.adapter_revision,
        "settings": dict(result.settings) if result.settings else None,
    }
