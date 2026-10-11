# Vendored experimental ProxyAPI bridge

Source: [SoundBlaster/Jev4Mellea](https://github.com/SoundBlaster/Jev4Mellea), branch `proxyapi-adapter`, immutable commit `bb3f495988bd424a4ba462b2752f9f26a3193ff2`.

Original file: `src/mellea_jev/providers/proxyapi.py`; original SHA-256 `b03d51a422376247f509aa19fd0aac19535900e0dba261ecc9de4e4262a0527b`. No source checkout installation is required. The upstream repository is not modified.

Local modifications: package-relative imports replaced with installed `mellea_jev` imports, provenance header and NormLab formatter. Provider logic is copied without redesign. Shared contracts/results/TypeSafeProvider have no git diff between this commit and upstream v0.3.0.

## License/provenance

The source branch's full LICENSE is preserved verbatim as [LICENSE.proxyapi](LICENSE.proxyapi). It contains Apache-2.0, while upstream pyproject metadata and README say MIT. This discrepancy is recorded, not silently resolved or used to relabel the copied file as NormLab's license. Future publication should use clarified upstream attribution/license metadata. No NOTICE file was present in the inspected branch tree.

## Integration

Use Python 3.11+ in a dedicated environment with [requirements-providers.txt](../requirements-providers.txt). Exact top-level release pins are not a complete transitive dependency lock. Existing evaluation and historical 0.2.1 environment are not modified by copying this file.

```python
# With evaluation/ on sys.path (as for existing evaluation entry points):
from proxyapi_config import build_proxyapi_provider, provider_metadata

metadata = provider_metadata()  # no key read, no requests
# Explicit construction; requests only happen in .noul/.choice/.score/.system_one:
with build_proxyapi_provider() as provider:
    pass
```

Factory reads `PROXYAPI_API_KEY` only when explicitly called (or accepts explicit api_key). Credentials are never part of provider_metadata. Destination/model fixed: `https://api.proxyapi.ru/v1/decisions`, `openai/gpt-6-luna-decisions`. No retries, redirects or environment proxies; explicit close/context manager.

The proxy uses state + named questions + noul/choice/score. This is not native OpenAI Decisions SDK wire format: changing OpenAIProvider.base_url alone does not connect it. Existing JevVerifier/JevClassifier/JevScorer can consume its structural interfaces. Multiple questions can use one .system_one call; count questions and aggregate request usage separately.

The offline harness is unchanged and makes no API requests. This provider is prepared for the next live/multi-turn harness slice, not already selected by its CLI. Copying and import compilation do not establish live compatibility, semantic quality or full integration. Nothing is added to hosted services or Docker images.

## Offline compatibility evidence

[2026-10-09 report](../../docs/PROXYAPI_OFFLINE_CHECK_2026-10-09.md): 41 tests
passed with the installed released adapter 0.3.0 and Mellea 0.8.0, using
MockTransport only. The factory, primitive wrappers and real Requirement
callbacks were checked. Live interoperability and full sampling/repair remain
unverified. CI repeats these tests via Evaluation provider contracts.
