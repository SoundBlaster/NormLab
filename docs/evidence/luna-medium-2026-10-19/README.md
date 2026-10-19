# Authorized medium arm, 2026-10-19 MSK

User: «Ок, выполни» after the [paired comparison protocol](../../LUNA_EFFORT_COMPARISON_PLAN_2026-10-19.md)
and exact proposed caps. Ten original cases; maximum30 aggregate attempts, zero
retry/repair/judge,120/300/900s operation/case/series deadlines. Same earlier
user-reported external$4 account ceiling, not independently verified or reset.
Costs remain unknown without supplier monetary billing. No additional low run.

Production source, old low scripts and historical evidence stay unchanged.
`prepare.mjs` builds a separate runtime with exactly one source substitution:
`OPENAI_REQUEST_SETTINGS.reasoning.effort` low→medium. Both stages use that setting;
the hosted prompt digest recomputes from the actual medium configuration.
A regenerated low control bundle must byte-match the original low bundle.
Dependency/source closure and original source hashes are rechecked before build.

The bounded low supervisor is reused through five explicit, recorded unique
transformations: authority location, medium authority check, medium request check,
generated-driver self hash and prompt-digest check. Generated driver and effective
provider source are written only to a new private TB5 build directory; their
hashes/recipe are captured in authority and raw versions retained in evidence.
The same call/time accounting and first-error stopping rule remain in force.
`execution-plan.json` itself is hash-bound, alongside inputs/code/dependencies.

`prepare.mjs` arguments: repo, existing node_modules, **new** build directory.
After reviewing/copying the separate authority/plan here, run generated driver
with `dry-run|live`, repo, build directory, **new** private capture directory.
Live requires a clean committed tree and environment `COREINFRA_API_KEY`.
No credential arguments/files/header dumps are recorded. Existing directories
are never reused for live capture. Failure/unknown outcomes stop, not replay.

Before dispatch, `replay.mjs baseline-control` feeds the medium runtime the
archived low bytes using an injected offline transport, validates both-stage
request bodies differ only in effort and all result processing remains equivalent
apart from expected digest/request-effort and new UUID/latency differences.
After dispatch, `replay.mjs medium-replay` checks complete successful medium
results against their own captured bytes with real network forbidden.

This is one bounded experiment on ten related development-seen texts, not a new
framework or independent human gold. All outputs require whole-source/output
candidate review; higher effort cannot add missing contract fields. No UI,
human correction session, production default change, deployment or merge.
