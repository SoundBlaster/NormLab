# Jev4Mellea 0.8.0: current SDK upgrade

Date: 2026-10-18. Task: [#147](https://github.com/SoundBlaster/NormLab/issues/147).
Previous implementation: [0.7.0 upgrade](JEV_ADAPTER_0_7_UPGRADE_2026-10-15.md).

## Scope

The [published upstream v0.8.0 release](https://github.com/SoundBlaster/Jev4Mellea/releases/tag/v0.8.0)
adds `CategoricalTask`, `CategoricalResult`, `CategoricalProvider` and
`ResponsesChoiceProvider`. A categorical result can contain one or several labels
without fabricated probability/confidence fields. Native probability-based
Noul/Choice/Score and Mellea requirements retain their existing contracts.

This delivery upgrades the **current SDK integration** in NormLab from 0.7.0 to
0.8.0. It is dependency maintenance after framework v1; it does not reopen
[#77](https://github.com/SoundBlaster/NormLab/issues/77).

| Path                                                                        | Version / behavior                                                                        |
| --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Current requirements and `provider_runtime.py`                              | Jev4Mellea 0.8.0, actual runtime metadata checked                                         |
| Copied ProxyAPI factory                                                     | Adds checked 0.8.0 support; keeps earlier supported versions and original 0.3.0 metadata  |
| Historical Stage 1 profile, `provider_config.py`, manifests and source pins | Remain 0.4.0 and byte-unchanged                                                           |
| SDK-free native execution/archive/scorer                                    | Unchanged; does not load this SDK                                                         |
| New categorical SDK exports                                                 | Available in the installed environment; no new NormLab factory/CLI integration in this PR |

The current smoke CLI still handles SystemOne and Decisions Noul/Choice/Score.
It does not automatically select Responses, synthesize native distributions from
labels or migrate the frozen Stage1 Responses implementation to the new provider.
That integration requires a separate explicit task/result mapping and protocol
revision. No new provider requests or model-quality experiment were performed.

## Dependency environment

Installed the current profile and existing provider-test requirements into a
fresh Python 3.13.15 environment on the verified TB5 volume. Package/build caches,
temporary test outputs and bytecode routing use that checkout's external build
root; old SDK environments were not updated or removed.

`uv pip check` passed for all 51 installed packages. Verified actual metadata:

| Package            | Version |
| ------------------ | ------- |
| mellea-jev-adapter | 0.8.0   |
| mellea             | 0.8.0   |
| typesafe-sdk       | 0.7.5   |
| openai             | 3.31.0  |
| httpx2             | 2.13.1  |
| pydantic           | 2.14.1  |
| pytest             | 8.4.2   |

The selected top-level pins are not a complete transitive lock. Pydantic is
reported as installed, not newly pinned by NormLab. Import checks confirmed all
four new categorical exports; they did not construct a live provider.

## Verification

Standing user requests to continue testing/checking this project are recorded in
[verification authorization](EVALUATION_VERIFICATION_AUTHORIZATION.md). Issue #147
recorded the bounded offline scope before execution. No live/billable inference,
credential retrieval, production storage writes or deployment is included.

The existing CI provider selection was run against the actual installed 0.8.0:

```bash
"$PROVIDER_ENV/bin/python" -B -m pytest \
  evaluation/test_provider_runtime.py evaluation/test_provider_smoke.py \
  evaluation/test_proxyapi_provider.py evaluation/test_verifier_capture.py \
  evaluation/test_harness_v2.py evaluation/test_adapter_compatibility.py -q
```

Result: **108 passed in 5.09 seconds**. These cover native SDK request/response
contracts with synthetic HTTP, custom/native endpoints, current runtime metadata,
copied ProxyAPI compatibility, verifier replay and real Mellea requirement hooks.
Provider credential variables were absent; fixtures use dummy credentials and
mock transports. Current SDK checks actively forbid real socket/HTTP transport.
No new test suite was added; existing current-version expectations were updated.

The separate frozen-retry compatibility diagnostic is described below. The full
SDK-free archive/MLflow suite is not rerun or claimed by this narrow upgrade.
GitHub CI/review on the upgrade PR remains separate from these local results.

## Historical compatibility boundary

The existing mock-only `CompatibilityProbe` still requires a frozen 0.4.0 plan.
It now permits exactly planned 0.4.0 / actually installed 0.8.0 in its two
diagnostic version equalities. Its installed-version guard and current provider
factory derive the current version from `provider_runtime.ADAPTER_VERSION`.

Version-gate checks explicitly reject a recorded 0.7.0 as the current probe's
runtime and reject a plan changed to 0.8.0. They continue to reject live execution
and live permits. Actual dependency metadata stays 0.8.0; it is never relabelled
as 0.4.0 to make a replay pass. Production historical version checks are unchanged.

The compatibility diagnostic cannot make historical permits valid under a new
runtime, prove hosted availability or establish semantic accuracy. Historical
0.7.0 reports remain evidence of their original runs.

The existing diagnostic completed with **7 passed in 26.25 seconds**, pytest exit
code 0, **332 mock attempt invocations and 0 network calls**. Its report records
actual adapter 0.8.0 and planned adapter 0.4.0, with 332 `Adapter version mismatch`
and 1,821 `Runtime metadata` equality bypasses. Source digests are recorded for
the diagnostic and its frozen inputs. The report explicitly keeps
`semanticQualityEvidence: false` and `historicalExecutionCompatibility: false`:
passing this diagnostic does not authorize an old live plan under the new SDK.

## Next step

Connect the released categorical Responses provider to one explicitly versioned
comparison path for ordinary Luna Low. Preserve the same source, candidate,
questions and criteria, keep native probability evidence separate, and validate
single/multi-question request mapping offline before a separately bounded live
experiment. Availability of an SDK export alone is not that integration.
