# Local MLflow import: executed checks

Date: 2026-10-13 (Europe/Moscow). Task:
[#77](https://github.com/SoundBlaster/NormLab/issues/77).
Base: `ba3f92af57e3625bf5f5cda6512c895342ee1b70` (#88).
[Contract and commands](OFFLINE_MLFLOW_IMPORT_V1.md).

## Delivered

Added an SDK-free projection/private snapshot module, a local locked
SQLite/MLflow registry writer and CLI. The original legacy importer, offline
readers, frozen native sources and fixtures remain unchanged.

The registry uses one capture parent and one child per score view. Imports are
bound to original NormLab IDs, projection digests and exact bundle bytes. A
durable intent plus OS lock prevents concurrent importer duplicates in one
storage root; unique tagged-run lookup recovers the create/bind crash window.
Metric-history reconciliation prevents duplicate points after partial writes.
Completed records are audited; identity/digest/metric/artifact conflicts fail
without silently overwriting completed evidence.

## Local test evidence

- Python **3.14.8**, stdlib-only complete offline suite: **61/61 tests**,
  **122.953 seconds**, including six new MLflow projection/dry-run tests.
- Existing evaluation environment, Python **3.10.19**, actual **MLflow 3.16.1**:
  **13/13 integration tests**, **11.531 seconds**. These use real SDK calls,
  temporary SQLite stores and file artifacts, not a mocked MLflow client.

```bash
python3 -B -S -m unittest discover -s evaluation -p 'test_offline_*.py' -v
.tools/parking-evaluation/bin/python -B -m unittest discover \
  -s evaluation -p 'test_mlflow_import.py' -v
```

Projection coverage: classification with/without labels, S1.3 and Stage 1 with
and without a scored view; nullable conditional metrics, raw navigation,
capture-parent reuse, SDK-free dry-run, invalid-input rejection before storage
and isolation from a subsequent source mutation.

Real SDK coverage:

- Repeat imports reuse UUIDs, preserve exactly one metric history item and
  retain a portable archived bundle that passes the independent verifier.
- Five bundle variants create **eight** runs: three capture parents and five
  distinct score views; labels/scoring changes reuse their existing capture.
- Recovery after metric commit, partially corrupted artifact copy, creation
  before ledger binding, and MLflow completion before ledger completion uses
  the same run UUID. Fault injection wraps real SDK writes.
- Two independent CLI processes concurrently importing one bundle create only
  one parent/view pair; one process returns `alreadyImported: true`.
- Changed bundle bytes with the same score ID, completed artifact drift,
  conflicting metric history and ambiguous duplicate tagged runs are rejected.
- A remote `MLFLOW_TRACKING_URI` environment value cannot redirect the explicitly
  local SQLite destination. Network-guard positive control also passes.

Integration tests deny DNS/connection/bind socket audit events throughout local
SDK activity, including the concurrent child processes. SDK-free CLI tests use
the existing stronger network/process/provider-import guards. No provider
clients, judge calls, inference or remote tracking were used.

## Historical capture smoke

Both saved scored bundles from `stage1-coreinfra-live-20261011-1408` and
`stage1-retry-v2-live-20261011-1904` were imported twice through the final CLI
and actual MLflow SDK with network transport denied. The second call for each
returned the same capture/score UUIDs with `alreadyImported: true`.

The registry has exactly **four** runs: two capture parents and two score views.
Both archived portable bundles passed independent verification, and all logged
metric histories contain exactly one value. Historical attempts, status/usage
gaps and candidate-label scope are retained; no new inference occurred.
Local registry and smoke summary: `.artifacts/mlflow-import-final-20261013/`
(not committed).

## Static validation and remaining scope

Ruff lint/format for all 81 Python files, changed-module syntax,
documentation/YAML formatting, relative links, frozen-source byte comparisons
and whitespace passed. New **Local MLflow import contracts** CI job installs the existing
pin `mlflow==3.16.1` and runs real local SDK integration under network guards.
The existing Stage 1 CI step discovers the six SDK-free tests. Fresh CI/review
are separate from local evidence and remain pending at publication.

No legacy importer migration, remote registry, distributed locking, inference,
model quality claim, deployment or execution/resume implementation is included.
The archived unsigned evidence proves consistency within its stated contracts,
not source authenticity or independent human gold. #77 remains open for its
remaining acceptance. Next: review this slice, then execution/resume contract.

## Review fix: audit the complete artifact inventory

The P2 finding on PR #89 identified that completed imports checked expected file
contents but ignored extra files under `normlab/`. Added full destination file-set
validation, including the archived bundle. Unexpected files, symlinks and
nonregular entries now reject; completed runs require the exact expected file set.
Partial recovery still permits missing or partially written expected files.

Two new real-SDK tests reproduced five pre-fix failures: extra files in capture
parent/score roots, bundle root and nested artifact directory, plus a dangling
symlink. After the fix all are rejected without deleting the extra evidence or
changing completed ledger state. Removing the extra file restores a successful
idempotent reimport. Existing partial-write/concurrent-import tests still pass.

After-fix evidence: **15/15** actual MLflow 3.16.1 integration tests on Python
3.10.19, **11.780 seconds**, with network transport guards. Ruff lint/format for
81 Python files, changed-module syntax, documentation formatting and whitespace
passed. The SDK-free projection/reader code is unchanged; the earlier 61-test
offline result above is historical and was not rerun for this registry-only fix.
No inference or deployment. Previous head c3ad107 had all six CI checks successful;
CI for this review fix must be checked separately after publication.
