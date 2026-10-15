# Jev4Mellea 0.7.0: current runtime and backward compatibility

Date: 2026-10-15. Ledger: [#77](https://github.com/SoundBlaster/NormLab/issues/77).

## Scope and release

The [published upstream v0.7.0 release](https://github.com/SoundBlaster/Jev4Mellea/releases/tag/v0.7.0)
adds optional image support, a CoreInfra connection factory and evaluation timing.
NormLab adopts its released text SDK integration without enabling image inputs
or changing provider models, task wording, endpoints or native normalization.
This is offline compatibility evidence, not a live availability or quality result.

| Path                                  | Adapter/runtime                 | Installation / behavior                                                                              |
| ------------------------------------- | ------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Current `provider_smoke.py`           | Jev4Mellea 0.7.0, Mellea 0.8.0  | `requirements-providers-current.txt`; config/factory in `provider_runtime.py`                        |
| Copied ProxyAPI bridge                | Jev4Mellea 0.7.0                | Current environment; historical provider metadata retained, actual runtime recorded                  |
| Frozen Stage 1 exact execution        | Archived adapter 0.4.0 profile  | Optional `requirements-providers.txt` for exact historical re-execution; not installed by current CI |
| Native execution/archive/score/import | `normlab-native-wire`, SDK-free | Existing native code/runtime/source pins unchanged; SDK upgrade is not a native migration            |

Current checks use Python 3.13.15, TypeSafe SDK 0.7.5, OpenAI 3.31.0 and
httpx2 2.13.1. Those SDK/transport versions are explicitly pinned alongside the
adapter/Mellea versions. The requirements file is not a complete transitive lock.
Upstream requires Python 3.11+; this change checks the SDK integration on 3.13.

`provider_runtime.py` reuses the frozen public validation and credential selection,
while publishing/checking its own adapter version. A historical config cannot
silently acquire a current runtime label. Historical execution intentionally
rejects adapter 0.7.0. Exact archived re-execution can use its archived profile;
ordinary current use and CI need only 0.7.0. Existing plans, permits and
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

## Initial isolated verification (superseded by the follow-up below)

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

## Backward compatibility follow-up

The user asked to test the previous contracts on 0.7.0 before retaining an old
runtime. Direct execution of all 73 former tests gave **59 passed / 14 failed**.
The failures stopped at repository version gates before exercising SDK behavior.
A diagnostic process bypassing only version restrictions then gave **72 passed /
1 failed**. The remaining failure was our verifier replay reader rejecting the
new optional `usage.cost_usd` field, rather than a changed text request or answer.

Of the former 73 tests, 66 bridge/capture/harness checks now run directly on
0.7.0; the seven frozen retry checks need only the explicit diagnostic probe.

Corrections and simplification:

- Accept checked adapter 0.7.0 in the copied ProxyAPI factory. Preserve the original
  provider metadata and capture actual runtime versions independently.
- Extend verifier usage validation with optional `cost_usd`: null or nonnegative
  finite numeric value. Preserve it in replay output; reject booleans, negative,
  nonfinite, string, unknown fields and answer/aggregate metadata disagreement.
  Old captures without this optional field stay valid and byte-unchanged. No
  quality verdict or total cost is inferred from this field.
- CI now installs one current adapter 0.7.0 environment for direct SDK, bridge,
  capture/replay and Mellea checks. It no longer installs the 0.4.0 profile.
- Keep frozen Stage 1 production version/source/permit checks unchanged. The
  explicit `check_legacy_sdk_compatibility.py` test command substitutes the current
  provider factory and permits exactly planned 0.4.0 / recorded 0.7.0 in two version
  equalities. Other validation remains active, actual metadata is retained, and
  live execution/network are denied. It runs only the existing seven synthetic
  retry contracts and restores process patches afterward.

The probe writes a separate `normlab.legacy-sdk-compatibility/v1` diagnostic
receipt with actual dependency versions, source digests, bypass counts and
`historicalExecutionCompatibility=false`. Its
mock captures are not historical execution evidence; do not import them as a
real experiment or use them to authorize dispatch. An old plan/permit is not
silently upgraded. The six-job CI workflow contains the exact repeatable direct
and probe commands; callers choose separate report/temp/cache paths.

| Follow-up check                                                                | Result                                                                             |
| ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| Direct current SDK + former bridge/capture/harness + new metadata/probe guards | 108 passed (1.00 s); no version bypass in this suite                               |
| Frozen retry contracts on actual 0.7.0 through the mock-only probe             | 7 passed (28.64 s); exact version-pair guard enabled, 332 mock attempt invocations |
| Full SDK-free regression after the follow-up                                   | 288 passed (155.308 s), Python 3.14.8 without site packages                        |
| Current runtime dependencies                                                   | 0.7.0 / Mellea 0.8.0 / TypeSafe 0.7.5 / OpenAI 3.31.0 / httpx2 2.13.1              |

This supports compatibility on the checked synthetic text contracts. It does not
measure model accuracy or establish identical live supplier behavior. The optional
upstream image features were not activated.

## Next step

Review and merge this dependency/integration update, then return to native
resume/reconciliation with explicit treatment of unknown outcomes under #77.
