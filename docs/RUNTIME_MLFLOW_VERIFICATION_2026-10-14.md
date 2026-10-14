# Runtime consumer and local MLflow verification

Date: 2026-10-14. Canonical task:
[Issue 77](https://github.com/SoundBlaster/NormLab/issues/77).
Contract: [runtime consumer v1](RUNTIME_MLFLOW_CONSUMER_V1.md).

## Scope and local evidence

| Check                                                                | Result                                           |
| -------------------------------------------------------------------- | ------------------------------------------------ |
| Complete SDK-free offline suite, Python 3.14.8                       | 182/182, 144.725 s                               |
| Dedicated consumer/dry-run suite, Python 3.14.8                      | 7/7; repeated after CLI backend-error correction |
| Dedicated consumer/dry-run suite, Python 3.10.19                     | 7/7; repeated after CLI backend-error correction |
| Real MLflow 3.16.1 / SQLite suite, Python 3.10.19                    | 27/27, 19.578 s; final reviewed importer bytes   |
| Runtime integration portion of that suite                            | 12/12                                            |
| Legacy MLflow integration portion                                    | 15/15                                            |
| Ruff including CI import rule `I`, format, AST, Prettier, whitespace | Passed locally                                   |

The complete offline suite preceded the final import-order correction and SDK
directory-drift guard. Its affected consumer checks and the new backend-error regression were repeated; the final
27-test SDK suite exercises the directory guard. New runtime checks are wired
into the pinned MLflow CI job; offline consumer checks use the existing
`test_offline_*.py` discovery. GitHub CI and independent review remain separate
from these local results.

## Independently checked outcomes

- Repeated imports reuse the same MLflow UUIDs and one metric history item per
  known count. The saved archive remains readable after both original runtime
  source and input archive are deleted; it can itself be re-imported.
- Original and continued capture revisions share one execution parent, retain
  distinct capture/projection children, and preserve both exact archives. A
  prediction-seal child is created only for the already-sealed complete capture.
- Unknown and adopted revisions preserve one attempt and null actual cost;
  adoption does not turn mock evidence into semantic quality evidence.
- In-process fault injections after run creation, metric commit, projection
  upload and MLflow finish recover through durable intents without duplicate
  runs/history. These are exception/interruption checks, not independent process
  crash or physical power-loss attestations. CLI success/reuse is additionally
  checked in separate subprocesses.
- Completed artifact bytes, parent tags and extra empty directories drift are
  rejected. Modified runtime records and wrong parent bindings are rejected
  before creating an import intent. Checkpoints above the ordinary 2 MiB limit
  import and re-import under their archive-specific 16 MiB bound.
- Dry-run runs with network and SDK imports forbidden and creates no registry
  storage. Real SDK checks forbid network transport; storage is temporary local
  SQLite and file artifacts. No persistent production registry is changed.

The #106 P2 review identified SQLite/MLflow backend exceptions escaping the CLI
error handler. The importer now sanitizes ordinary `Exception` failures while
letting `BaseException` interruptions through. A regression check injects SQLite
and custom backend exceptions and verifies the one-line, content-free message,
plus propagation of `KeyboardInterrupt`.

## Changes and limits

The three delivery layers add SDK-free consumer/snapshot, explicit local import,
and runtime round-trip/recovery CI coverage. Of 122 base evaluation files, 121
remain byte-identical; only the existing registry is extended. Producer-pinned
archive modules remain unchanged, preserving existing archive compatibility.
Legacy score bundles remain supported; runtime archives are a separate versioned
consumer contract, not a fabricated legacy score envelope.

An initial CI run found unsorted fixture imports because the first local Ruff
command omitted CI's explicit `I` selection. Corrected in the bottom layer and
propagated to descendants; final local lint uses the exact CI selection. Only
fresh CI on rewritten heads can establish remote pass status.

No provider calls, paid inference, new dependencies, credentials or deployment.
All runtime inputs are synthetic mock captures. Reference, score, actual cost
and critical-error-free rate remain null; source authentication, execution
readiness, semantic quality and release approval remain false. Registry import
is resumable across records, not an atomic multi-run transaction. Full Issue 77
acceptance remains incomplete.

Next after review: define runtime reference/score attachment to these immutable
capture revisions, before adding native live transport and capability gates.
