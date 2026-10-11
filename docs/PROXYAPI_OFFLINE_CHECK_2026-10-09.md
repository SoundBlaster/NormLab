# ProxyAPI bridge: offline compatibility — 2026-10-09

## Result and scope

**41/41 provider tests passed** against the released `mellea-jev-adapter==0.3.0` in a newly created Python 3.13 environment, `.tools/provider-evaluation`. `pip check` passed. Combined provider and existing Mellea fixed-sampling suite: **49/49 passed** (41 provider tests + 8 existing tests). Historical `.tools/mellea-evaluation` was not upgraded.

All inference requests used `httpx2.MockTransport` and a synthetic `mock-key`; actual CoreInfra/ProxyAPI credentials were not needed. This proves copied bridge compatibility with the installed SDK and Mellea callback contract on these fixtures, not live endpoint availability, extraction quality or a full sampling/repair pipeline.

## Covered behavior

- Mixed Noul/Choice/Score request reaches the fixed ProxyAPI `/v1/decisions` route with the configured model/state/questions; one intercepted request.
- Noul value, Choice labels/distribution/confidence and Score scale/weighted value/legend are validated through the real TypeSafe SDK.
- ProxyAPI response `id` becomes request ID; usage/model propagate into answer results. Missing, empty, non-ASCII/control-character IDs fail.
- Existing JevVerifier/JevClassifier/JevScorer consume the bridge. Real Mellea 0.8 Requirement.validate callbacks accept mock pass outcomes; a mock uncertain Noul triggers ReviewRequired. The context is a fixture, not a live generator.
- Broken JSON, wrong primitive values/labels/score keys/legends/usage fail without returning accepted answers.
- HTTP 302/401/429/500 and connection errors are surfaced safely, with no body/credential echo and no retries or redirects. Environment proxies are disabled.
- Explicit key overrides the selected environment variable; missing PROXYAPI_API_KEY does not fall back to OpenAI/TypeSafe credentials. Factory rejects adapter versions other than 0.3.0. Construction sends no request.
- Closing the provider closes the inner transport, including failed initialization; unexpected routes are rejected before forwarding.

Tests were adapted from the pinned upstream branch with imports changed to NormLab's copied bridge. NormLab factory and Mellea callback checks were added. License/provenance: [provider README](../evaluation/providers/README.md).

## Reproduce

```bash
python3.13 -m venv .tools/provider-evaluation
.tools/provider-evaluation/bin/python -m pip install -r evaluation/requirements-provider-tests.txt
.tools/provider-evaluation/bin/python -m pip check
.tools/provider-evaluation/bin/python -m pytest evaluation/test_proxyapi_provider.py -q
```

New CI job `Evaluation provider contracts` runs this test file with Python 3.13 and the released dependency. A local pass is not a CI pass until the job finishes on the pushed head. Direct release pins do not lock all transitive packages; the local installed-version snapshot is retained separately.

## Remaining work

Connect provider results to bounded harness turn/case capture, preserving raw probability versus routing policy. Then perform a separately budgeted live smoke before quality experiments. No live request or change to hosted configuration was made in this verification.
