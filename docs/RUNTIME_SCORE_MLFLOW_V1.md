# MLflow runtime score children v1

Canonical task: [Issue 77](https://github.com/SoundBlaster/NormLab/issues/77).
Input: exact [runtime archive](RUNTIME_ARCHIVE_V1.md) and regenerated
[score view](RUNTIME_SCORE_VIEW_V1.md). No score is trusted from its ID alone.

## Identity

The SDK-free `runtime_score_mlflow_projection.project_score` regenerates the
entire view, then creates a `runtime-score` record in the shared local registry.
Its key derives from `scoreId`, which already binds capture, reference, policy
and scorer-code revisions. Its parent is the exact runtime capture import key.

A new reference revision creates a sibling score child, not a replacement.
A continued capture creates another capture parent and its own score child.
Changed policy/code must pass the installed versioned scorer; arbitrary edited
policies or recomputed IDs are rejected. Different supported policy versions
would naturally produce different score IDs; v1 supports only its fixed policy.

The projection retains reference status, exact score artifact digest/length,
summary, arm summaries and navigation. Metrics are explicitly prefixed
`selected.*` / `arms.*`; null quality values are never converted to zero.
Arm components use `a-` plus SHA-256 of the UTF-8 arm ID, keeping metric names
bounded and backend-safe even for punctuation, Unicode or long IDs. The exact
original IDs remain in `arms`, with the explicit `armMetricKeys` mapping.
Params pin execution/capture/reference/policy/scorer identities. Candidate or
unsigned human declarations do not become authenticated gold through import.

## Delivery

1. SDK-free score-child projection and extraction roadmap note.
2. Additive explicit local import, preserving archive and score bytes.
3. Pinned real MLflow checks for reuse, sibling/reference/capture revisions,
   interruption recovery, artifact/metric drift and standalone saved replay.

Artifacts will include the complete portable archive plus `score.json`; the
registry projection is separate `projection.json`. All import bounds include
these files. Near-limit views/archives may be rejected rather than truncated.
No live inference, quality promotion or deployment follows from import.

## Local CLI

```bash
python evaluation/import_runtime_mlflow.py ARCHIVE --score score.json --dry-run
python evaluation/import_runtime_mlflow.py ARCHIVE --score score.json --storage .data/mlflow-offline
```

The archive is privately snapshotted and both score and projection regenerated
before opening registry storage. The writer rechecks canonical record binding
and the completed capture parent before creating an intent. Score children save
the verified archive, exact canonical `score.json` and registry projection.
These files fit the existing 64 MiB / 4096-entry whole-payload caps; score and
projection individually fit 2 MiB. Archive checkpoints retain their 16 MiB cap.

Legacy import and score-free runtime import stay supported. Repeated import
reuses IDs, validates metric histories and exact artifacts, and rejects completed
drift. Multiple records are resumable, not an atomic registry transaction.
