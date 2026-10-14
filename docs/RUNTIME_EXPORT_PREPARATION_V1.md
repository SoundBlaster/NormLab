# Runtime export projection preparation: 5d.2

Date: 2026-10-14. Related task: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Depends on [capture revision snapshots](RUNTIME_CAPTURE_PREPARATION_V1.md).
Implementation: [projection](../evaluation/runtime_export.py).

## Read-only projection

`prepare_export(RuntimeSnapshot)` constructs a bounded in-memory export plan from
validated mock evidence. It does not write an archive or an offline-envelope v1
bundle, change source bytes or acquire dispatch/resume authority. CLI preview:

```bash
python -B -S evaluation/runtime_capture_cli.py project /path/to/mock-execution
```

The generated `normlab.runtime-export-plan/v1` index retains execution/revision,
plan digest, capture manifest, full public arm/context-policy metadata, counts
and references to separate task artifacts. The task schema is
`normlab.runtime-export-task/v1`; records include original task/turn/case IDs,
arm/repeat/stage, exact source/candidate/request/context references, question IDs,
status, first/final outcome references and all ordered reservations/outcome
observations. Raw event/invocation IDs retain adoption/retry lineage.

Every planned task is present, including the unstarted suffix. A reserved attempt
without an outcome remains unknown; orphan bytes do not establish completion.
Retry retains both charges and distinct first/final outcomes. Adoption keeps the
original reservation and adds its committed outcome history, not a fabricated
new dispatch. The journal is indexed once before task projection.

Counts retain planned tasks/questions, status denominators, attempt count,
reserved budget and known/unknown usage. Unknown usage is not charged as known
zero. Synthetic mock usage is explicitly mock evidence, not billed API usage.
Reference/score/actual cost/critical-error-free rate stay null; export-written,
readiness and semantic-quality flags stay false. Raw captures remain reachable
through the snapshot inventory and content-addressed references.

## Mock seal and validation

A `normlab.runtime-prediction-seal/v1` projection is generated only for a finished,
complete checkpoint with all task outcomes completed and no unknown attempt.
It binds execution ID, capture revision and the full ordered task/result set.
Partial, failed, unknown or merely unfinalized captures remain unsealed. It is an
unsigned mock completion binding; it does not establish live authenticity or
human gold, and existing native scorers/importers do not consume it.

Generated task/seal/capture-manifest artifacts are separate files in a read-only
byte map; ordinary artifacts/index are limited to 2 MiB, source plus generated
inventory to 4096 files/64 MiB. Source checkpoints keep their 16 MiB input limit.
A 288-task/864-question unstarted matrix verifies the split artifact layout.

`verify_export_projection(root, index, artifacts)` recomputes the expected plan
from the saved root and requires exact canonical index and artifact equality.
Edited/rehashed summaries, promoted references, fabricated scores or altered
records reject. This is source-bound consistency, not a standalone portable
reader. An advanced source checkpoint requires its new capture revision.

## Checks and remaining work

Seven dedicated tests cover complete seals/exact context, unknown suffixes,
retry first/final, adoption without a new attempt, edited metadata/records,
write/network/SDK-denied preview and the large matrix. Python 3.10/3.14 and final
combined-suite evidence are recorded in the stack handoff.

Next: **5d.3 registry import planning** keyed by execution and capture revision.
Actual durable portable export, native offline-envelope adapter, reference/score
consumer integration and MLflow writes remain outside preparation. No provider
requests, credentials, network or deployment are used.
