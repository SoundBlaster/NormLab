# Idempotent local MLflow import v1

Slice of [#77](https://github.com/SoundBlaster/NormLab/issues/77), after
[offline envelope](OFFLINE_ENVELOPE_V1.md), [comparison](OFFLINE_PAIRED_COMPARISON_V1.md)
and [Stage 1 score views](OFFLINE_STAGE1_REFERENCE_V1.md).

## Commands

```bash
# SDK-free validation and projection, no registry writes:
python3 -B -S evaluation/import_offline_mlflow.py saved-bundle --dry-run

# Use the existing evaluation environment with mlflow==3.16.1:
.tools/parking-evaluation/bin/python -B evaluation/import_offline_mlflow.py \
  saved-bundle --storage .data/mlflow-offline
```

The default storage is `.data/mlflow-offline` under the repository containing
the importer. `--storage` selects a local directory, not a tracking URI.
`MLFLOW_TRACKING_URI` does not redirect this path. Tracking uses explicit local
SQLite; artifact locations must resolve under the selected storage directory.
Telemetry and OTLP export are disabled before importing MLflow. No provider,
LLM judge, tracing, inference or server is started.

The existing `evaluation/import_mlflow.py` remains the separate legacy parking
report importer. It has not been made idempotent; this new entry point accepts
only verified `normlab.offline-bundle/v1` bundles for classification, S1.3 and
Stage 1. Unsupported/invalid input returns exit 1 with a sanitized error type.

## Verified snapshot and identity

Before opening registry storage, the importer copies only the declared bundle
index and content-addressed inventory into a private temporary directory, checks
containment, bytes, hashes and bounds, then runs the trusted offline verifier on
that copy. The same immutable copy is uploaded. Adjacent files are excluded.
Bounds: 2 MiB per file, 64 MiB total including index, 4096 artifacts.

One **capture parent run** is keyed by the original NormLab run ID and a digest
of its capture/dataset/experiment/count projection. Reference and score views
are excluded from that parent binding. Each **score child run** is keyed by its
NormLab score ID and bound to the exact bundle byte digest and projection.
New score views reuse the parent and create separate children; they do not
overwrite prior views. A changed digest for an existing key is a conflict.
Even whitespace changes in the bundle index change its exact byte digest.

MLflow run UUIDs are registry identities, distinct from NormLab run/score IDs.
Tags record the import key, original ID, projection digest, kind, parent link,
import state, `release_approved=false` and zero new inference calls. Params
record dataset/revision, strategy/tactic versions, requested models, provider
and policy digests, and score/scorer/dependency/adapter/reference bindings.
Full provider settings and context policy remain in the capture projection and
portable evidence. Unknown version values stay JSON `null` in params.

## Registry and recovery

```text
storage/
  import.lock        # OS advisory lock, released if the process dies
  imports.sqlite     # durable unique import intents and progress
  tracking.sqlite    # MLflow local tracking store
  artifacts/         # MLflow run artifacts
```

Writers using the same resolved storage root serialize with `flock` on macOS/Linux.
This is a local single-host contract, not distributed locking. It does not
protect against another tool bypassing the importer and modifying its registry.

1. Commit a unique intent with original ID/digest and `pending` state.
2. Find the uniquely tagged MLflow run or create it, then bind its UUID in the
   ledger. A crash between creation and binding is recovered by that tag.
3. Write missing params/metrics/artifacts. Metrics use fixed step/timestamp zero;
   existing history must contain exactly the same one value, so a retry after
   a committed metric does not append another history item.
4. Mark MLflow completed/finished, then commit ledger completion. A crash before
   that final commit resumes the same UUID and reconciles existing writes.

Ordinary failures retain `failed` state and an error class; interruptions may
leave `pending`. Reimporting the same input resumes either state. Partial artifact
copies can be overwritten during recovery. Completed imports are audited and
returned as `alreadyImported: true`; completed artifact/metric/parameter drift,
deleted runs, mismatched tags or ambiguous duplicate runs are rejected for manual
investigation. The importer does not delete or silently repair completed evidence.
Guarantees require retaining both SQLite stores, artifacts and the lock path.

## Metrics and raw navigation

Capture metrics contain only known numeric counts, status counts and usage from
the validated envelope. Score metrics are explicitly scoped to **completed,
selected-reference-scored logical tasks**: planned/scored/passed/not-evaluated,
and agreement among scored tasks when the denominator is nonzero.

Unknown usage/cost and case-level `criticalErrorFreeRate` are not logged as zero.
Booleans and nonnumeric metadata are not flattened into numeric metrics. Native
arm/family/first-final metrics remain available in original report artifacts;
they are not silently merged into a differently scoped aggregate.

Each child contains `normlab/projection.json` and a complete portable bundle at
`normlab/bundle/`. Its navigation fields point to the bundle index, source
manifest, raw capture artifacts, score report and reference. Native Stage 1
seals/scores remain reachable through their archived report/input references.
The archived bundle can be copied out and independently verified with its exact
trusted reader revision; the MLflow UI is not the sole copy of evidence.

Candidate labels stay candidate labels. Import success and metric agreement do
not establish independent human review, model quality, statistical significance
or deployment readiness. No evaluation predictions are recomputed by this path.

## Validation and next step

[Executed local checks](OFFLINE_MLFLOW_IMPORT_2026-10-13.md).
CI separates stdlib-only projection checks from real pinned MLflow/SQLite tests.
Next: review the importer, then define the remaining execution/resume contract;
resuming an import never authorizes resuming inference.
