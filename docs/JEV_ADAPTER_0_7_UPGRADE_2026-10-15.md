# Jev4Mellea 0.7.0: isolated current integration

Date: 2026-10-15. Ledger: [#77](https://github.com/SoundBlaster/NormLab/issues/77).

## Scope and release

The [published upstream v0.7.0 release](https://github.com/SoundBlaster/Jev4Mellea/releases/tag/v0.7.0)
adds optional image support, a CoreInfra connection factory and evaluation timing.
NormLab adopts its released text SDK integration without enabling image inputs
or changing provider models, task wording, endpoints or native normalization.
This is offline compatibility evidence, not a live availability or quality result.

| Path                                          | Adapter/runtime                 | Installation / behavior                                                                   |
| --------------------------------------------- | ------------------------------- | ----------------------------------------------------------------------------------------- |
| Current `provider_smoke.py`                   | Jev4Mellea 0.7.0, Mellea 0.8.0  | `requirements-providers-current.txt`; config/factory in `provider_runtime.py`             |
| Historical Stage 1 and copied ProxyAPI bridge | Jev4Mellea 0.4.0                | Existing `requirements-providers.txt`; source-pinned planners/executors unchanged         |
| Native execution/archive/score/import         | `normlab-native-wire`, SDK-free | Existing native code/runtime/source pins unchanged; SDK upgrade is not a native migration |

Current checks use Python 3.13.15, TypeSafe SDK 0.7.5, OpenAI 3.31.0 and
httpx2 2.13.1. Those SDK/transport versions are explicitly pinned alongside the
adapter/Mellea versions. The requirements file is not a complete transitive lock.
Upstream requires Python 3.11+; this change checks the SDK integration on 3.13.

`provider_runtime.py` reuses the frozen public validation and credential selection,
while publishing/checking its own adapter version. A historical config cannot
silently acquire a current runtime label. Historical execution intentionally
rejects adapter 0.7.0; use its separate environment. Existing plans, permits and
captures do not authorize a new-version experiment.

The current CLI retains explicit exact HTTPS endpoint, model and key selection.
It uses the generic TypeSafe/OpenAI providers so custom/native endpoints obey the
same path contract. The upstream CoreInfra convenience factory is not needed to
select a protocol by hostname. No provider fallback is introduced.

## Smoke report revision

Current output is `normlab.provider-smoke/v2`. It keeps actual request bodies,
HTTP status, model/request ID, usage, dependency versions and measured latency.
The adapter's usage now includes `cost_usd`; absent provider cost remains null.
The top-level `cost` remains null rather than estimating an aggregate.

SDK Score result dictionaries use integer keys. The current CLI converts the
result to its JSON representation before retaining/returning it, so the returned
report matches `report.json` exactly. Historical v1 reports stay unchanged.
This standalone smoke report does not replace a Stage 1/native capture or quality
score and has no automatic resume.

## Verification

| Check                                                                                | Result                                                              |
| ------------------------------------------------------------------------------------ | ------------------------------------------------------------------- |
| Fresh isolated 0.7.0 dependency environment                                          | Installed; `uv pip check` passed, 51 packages compatible            |
| Current SDK + smoke contracts                                                        | 25 passed (1.54 s), synthetic MockTransport only                    |
| Historical provider/ProxyAPI/capture/retry contracts in a separate 0.4.0 environment | 73 passed (35.11 s)                                                 |
| SDK-free archive/export/replay/comparison contracts                                  | 288 passed (157.735 s), Python 3.14.8 without site packages         |
| Ruff lint / format                                                                   | Passed; 159 Python files formatted                                  |
| Frozen native producer modules and tracked fixtures                                  | All 22 modules and fixtures byte-identical to merged base `a25a7ec` |
| GitHub CI                                                                            | Added separate current-adapter job; PR CI tracked separately        |

The 25 current checks cover all three primitives through native TypeSafe/OpenAI,
CoreInfra Jev/Decisions and one custom exact endpoint; real Mellea Requirement
validation for both protocols; version/config mismatch rejection; SDK-free dry-run;
HTTP 302/401/429/500 and transport failure without hidden retries or redirects;
stop-on-first-failure and sanitized checkpointed reports. The SDK tests deny
socket connections/default HTTP transport. Successful fixtures include the
complete usage structure required by the current OpenAI SDK; validation was not
weakened to accommodate incomplete mock responses.

Initial fixture assertions exposed the additional `cost_usd` metadata and required
OpenAI usage detail fields; the fixtures were corrected. A subsequent successful
Score capture exposed the JSON integer-key mismatch described above, which was
fixed in the current CLI. Final outcomes above are the subsequent checks.

After the user's TB5 routing instruction arrived, subsequent pytest caches,
bytecode and temporary results were routed to the verified TB5 volume under this
checkout's identity. Existing local environments and the already-running SDK-free
suite were retained in their original locations; no bulk migration/deletion was
performed. Machine-specific paths are not configured in tracked scripts or CI.

No provider requests, paid inference, credential lookup, production registry
writes or deployment were performed. Reaching the supplier and judging text
quality require separately authorized bounded experiments.

## Next step

Review and merge this dependency/integration update, then return to native
resume/reconciliation with explicit treatment of unknown outcomes under #77.
