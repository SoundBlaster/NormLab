# Stage 1 CoreInfra provider experiment v1

Separate provider revision over the immutable comparison-v1 source/candidate/task
contracts. [Transport and permit documentation](../../../docs/STAGE1_PROVIDER_TRANSPORT.md).

- Pilot digest: `ac5458e62eca6be1a5d447d1098a7f93cb96f6554dc70a20d2edb554987ba6f2`.
- Corpus digest: `eaf1b7d7f36ca31a975ae6b260ef4c230bcd455b017321c35cc37ebb600a30c5`.
- Arms: Jev, Luna Decisions and ordinary Luna Low; application OpenAI endpoints.
- Authorized live calls: **0**. `permit.example.json` is deliberately invalid.
- Labels remain candidate annotations and are not opened by planning/execution.

## Recorded implementation evidence

`mock-summaries.json` binds executor/parser code hashes and both plan digests.
Actual SDK 0.4.0 control flow uses `httpx2.MockTransport`; no provider credential
lookup or external HTTP. `COREINFRA_API_KEY` was removed from subprocess environments.
Every capture was replayed with `python3 -B -S`, without SDK imports. Returned
choices/confidences/usage are synthetic, not predictions or model-quality evidence.

| Capture | Reserved mock HTTP slots | Stop |
| --- | ---: | --- |
| pilot | 36 | complete |
| corpus | 288 | complete |
| http | 1 | provider-error |
| transport | 2 | transport-error |
| malformed | 3 | invalid-output |
| model-drift | 4 | returned-model-change |
| request-mismatch | 0 | request-mismatch |
| interrupt | 2 | unknown-sent-outcome |
| cap-two | 2 | budget-exhaustion |
| cap-zero | 0 | budget-exhaustion |

A fault slot is zero-based: HTTP at 0, timeout at 1, malformed JSON at 2, returned
model drift at 3, request mismatch at 0, interruption at 1. Interruption raises
KeyboardInterrupt after the sent checkpoint; replay reports unknown outcome.
No automatic resume or retry occurs. Request mismatch consumes **zero** dispatches.
All summaries keep every planned job, including failed and unused suffixes.
The unfilled permit was rejected without creating a live output directory.

Ignored local captures: `.artifacts/stage1-coreinfra-evidence-v1/`.
Public summaries are evidence of these runs, not an automatically executed CI
suite. Existing CI checks style and the historical/provider regression suites;
the new CLI rehearsals were invoked locally.

## Reproduce

```bash
python3 -B -S evaluation/stage1_provider_executor.py \
  fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json
.tools/provider-evaluation-0.4/bin/python -B evaluation/stage1_provider_executor.py \
  fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json \
  --mock-output .artifacts/new-provider-pilot
python3 -B -S evaluation/stage1_provider_executor.py \
  fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json \
  --replay .artifacts/new-provider-pilot
```

Use `--profile corpus` for the larger schedule. Always use a new output directory.
For future model/provider changes, create a new manifest revision and new code
pins if relevant; never edit this manifest or historical evidence to reuse a score.
