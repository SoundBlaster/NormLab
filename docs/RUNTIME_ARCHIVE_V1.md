# Durable mock runtime archive: versioned format

Date: 2026-10-14. Related task: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Builds on [capture revisions](RUNTIME_CAPTURE_PREPARATION_V1.md) and
[export projections](RUNTIME_EXPORT_PREPARATION_V1.md).

## Layer 1: closed publication plan

`prepare_archive(RuntimeExportProjection)` generates immutable bytes and a closed
`normlab.runtime-archive/v1` index. It performs no filesystem export or inference.
Original bytes are copied without rewriting filenames inside source evidence:

```text
archive.json                 # final commit marker, written last
.writer.lock                 # fresh archive writer / read-only inspection lock
capture.json                 # generated normlab.runtime-capture/v1 manifest
projection.json              # generated normlab.runtime-export-plan/v1 index
source/                      # exact validated original runtime inventory
  plan.json, intent.json, mock-script.json, checkpoint.json
  checkpoint-v1.json          # exact original snapshot when current is v2
  artifacts/<sha256>.blob
projection/artifacts/<sha256>.blob
```

The archive index contains schema/ID, execution/capture/projection IDs, capture
and projection refs, sorted exact file inventory, derived totals, producer-module
pins, mock evidence kind and false readiness/semantic flags with zero inference.
`archiveId` hashes the complete index except its own ID. It changes when captured
bytes or producer pins change; `executionId` and `captureRevisionId` retain their
separate original meanings. Source and projection namespaces cannot collide.

Closed path rules allow only metadata names and content-addressed artifact paths.
Ordinary files/index are at most 2 MiB; source checkpoints retain their 16 MiB
limit. Planned tree entries, including directories, index and lock, are at most 4096. Total content plus final index is at most 64 MiB; lock bytes are zero.
The index records content byte totals separately to avoid a self-size cycle.
Unknown/partial captures can be planned without a fabricated prediction seal.

The thirteen `producerPins` refer to the exact trusted format/validation/projection
Python modules. They are metadata, not executable code embedded in the archive.
A later reader must match its trusted installed producer modules to these pins
and reject unsupported versions. This is version compatibility, not writer/source
authentication or attestation of runtime code. Archives remain unsigned mock
evidence; no live clock/provider/semantic readiness is inferred.

## Checks and dependent layers

Four format regression methods cover deterministic identity, immutable copies,
original/continued checkpoint retention, rehashed invalid paths/shape/types and
bounds including metadata/directories/marker/lock. Python 3.10/3.14 results and
final combined evidence will be recorded with the completed stack.

Layer 2 adds fresh-directory durable export and a final atomic commit marker.
Layer 3 adds read-only portable replay, exact inventory/projection validation,
corruption/process-fault coverage and original-source deletion round trips.
Until those dependent layers land, this format module does not publish or read
archives. Existing offline-envelope/native/MLflow schemas remain unchanged.

## Layer 2: fresh durable export

`export_archive(plan, output)` and `export_runtime_archive(source, output)` publish
into a fresh private local directory. Plan shape, all hashes/bytes and current
trusted producer pins are checked before directory creation. Existing or partial
output directories reject; no overwrite, cleanup or export recovery occurs.

The writer flushes the new parent entry, creates/flocks/fsyncs the archive lock,
creates and flushes the fixed directories, then writes every content file with
exclusive creation, full-write check, file fsync and containing-directory fsync.
The final index is fully written/flushed to a root temporary name, atomically
renamed to `archive.json`, then the root directory is flushed. No further writes
follow the committed marker. A healthy writer acknowledges durability only after
the final directory barrier; any failure poisons the writer and aborts publication.

Before the final rename, no commit marker exists and the later reader must reject
the partial tree. After rename the complete index can be visible even if the
writer did not receive durability acknowledgement. This layer tests barrier
ordering under simulated in-process faults, not abrupt process termination,
physical power-loss/controller safety, remote
filesystem guarantees or protection from hostile local rewriting.

Four export methods cover exact saved bytes/barrier order, reader lock contention,
no overwrite/second publication, ten interruption points and real fsync OSError.
The combined format/export suite passes eight methods on Python 3.10/3.14. A
dependent portable reader will validate exact tree inventory and regenerate the
capture/projection rather than trusting the index alone. No archive reader,
registry write, provider call or deployment is implemented by this second layer.

## Layer 3: portable read-only replay

```bash
python -B -S evaluation/runtime_archive_cli.py export /path/to/mock-execution /path/to/fresh-archive
python -B -S evaluation/runtime_archive_cli.py verify /path/to/archive
```

`read_archive(root)` holds the archive's shared reader lock, requires the commit
marker, validates its closed schema/pins/limits and checks the **exact complete
tree**, including regular empty lock and expected directories. Missing/extra
entries, symlinks, FIFO, temporary tails, wrong sizes/hashes and unsupported pins
reject. Source checkpoints retain their 16 MiB limit rather than the ordinary
2 MiB limit. The reader never repairs, resumes or dispatches anything.

The reader runs unchanged strict checkpoint/continuation replay against archived
`source/`, reconstructs `RuntimeSnapshot` and export projection, then regenerates
the whole archive plan. Index and content must exactly match that regenerated
plan. Coordinately rehashed capture/projection summaries and source counters
cannot bypass replay. Replacing a whole unsigned source consistently is not
detected as an authorship forgery; `sourceAuthenticated` stays false.

Verification needs no original runtime directory, repository fixtures, registry,
provider SDK or credentials. The archive does not contain executable reader code.
For a standalone trusted reader distribution, copy the thirteen `PIN_MODULES`
listed in `runtime_archive_format.py` plus `runtime_archive_export.py`,
`runtime_archive_reader.py` and `runtime_archive_cli.py` into a separate tools
directory. Invoke its CLI with Python 3.10+. Their exact bytes must match the
saved producer pins; use the known Git revision for older archives rather than
silently updating modules or executing untrusted code from an archive.

`VerifiedArchive` exposes original snapshot, generated projection and immutable
archive bytes for future consumers. CLI output is a verification summary without
raw source/response prose: IDs, state, denominators, unknown attempts and mock seal
status; zero inference/registry writes and false semantic/live-readiness flags.
Successful export additionally reports final durability acknowledgement. The
original projection's `exportWritten: false` remains unchanged: this archive is
not an offline-envelope export, and that historical plan is not rewritten.

Original and continued archives share execution lineage but retain distinct
capture/archive IDs and both historical byte sets. Tests delete the original
runtime source and replay both archives, including unknown → adopted and retry
history, from separate trusted tools under write/network/SDK denial.

See [archive verification](RUNTIME_ARCHIVE_VERIFICATION_2026-10-14.md). Existing
native/envelope/MLflow consumers remain unchanged; integrating these runtime
schemas and validating real registry round trips is the next result. No live
clock/code/provider attestation, semantic quality, inference or deployment is
established by this archive implementation.
