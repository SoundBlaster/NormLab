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
