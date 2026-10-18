# Ten-case ordinary Luna hosted development run

User authorization (2026-10-19 MSK): «Платный прогон разрешаю» for the prepared
[ten-case plan](../../../fixtures/parking-pilot/luna-development-pilot-v1/plan.json).
The preparation plan remains an immutable historical proposal; `authority.json`
records the separate execution grant and runtime freeze.

## Boundaries fixed before dispatch

- Existing `runHostedExtraction`, ordinary CoreInfra Responses `gpt-6-luna`, low
  reasoning, unchanged discovery/classification prompts and schemas.
- Maximum 30 aggregate provider attempts across ten cases; zero retries, repair
  or judge calls. 120 seconds per provider operation, 300 seconds per extraction,
  900 seconds for the series. Stop at first operational/protocol/unknown outcome,
  authority drift or cap; semantic errors do not start a retry or stop the series.
- Existing user-reported external account ceiling $4; not independently verified.
  The supervisor enforces attempts/time, cannot enforce dollar spend without
  pricing, and does not claim a known request cost or remaining account balance.
- Only source DTOs enter inference. Candidate readings, rubric, selection reasons,
  previous outputs and human-correction worksheets do not enter model context.
- No application changes, deployment, human correction session or independent
  human gold. Active human correction time remains unobserved, never zero.

## Actual preparation

TB5 identity preflight passed. Built only the current source entry point and its
dependencies to the verified external build directory: Node v26.5.0, esbuild
0.28.2, 128 source/input/config/driver bindings; only `node:crypto` and `node:net`
remain external runtime imports. No install, application test suite or provider
request during preparation. Source checkouts and existing dependencies stay put.

Dry-run loaded the actual bundled runtime, verified hashes and strict input
bindings: ten cases, zero provider calls. Hosted prompt digest:
`46c9b4089ba8a93e71272c817dd3bab1aefabc74924b0b360199ec42666627a2`.

The one-off scripts are experiment instrumentation, not a new framework or
deployment entry point. `build.mjs` accepts repo, existing node_modules and build
directory arguments. It emits the bundle and an authority proposal; the reviewed
authority is committed here before live execution. `driver.mjs` accepts
`dry-run|live`, repo, build directory and **new** private output directory. Live
mode requires a clean committed tree and `COREINFRA_API_KEY` from the environment.
Reusing a previous output directory is rejected; this is not a resume mechanism.

The transport reserves/checkpoints every attempt before dispatch, captures exact
request JSON and bounded response bytes (including unsuccessful HTTP responses),
and waits for all in-flight transport operations after failure. A transport/body
capture failure is unknown, not retried. Response buffering preserves existing
provider parsing; raw evidence is separate from accepted pipeline results. The
driver refuses to write an artifact containing the credential value. Request
headers and environment dumps are never persisted.

After execution, inspect every source claim and every generated output claim,
including discarded fragments, before reporting candidate extraction results.
Track clarification/scope contract limitations separately; a claim extraction
pass cannot imply full assisted-task completion. Human correction and its timing
require a later observed session.
