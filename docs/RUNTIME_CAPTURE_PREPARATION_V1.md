# Runtime capture revision preparation: 5d.1

Date: 2026-10-14. Related task: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
First of three dependent preparation layers above [5c](MOCK_RESUME_V1.md).
Implementation: [snapshot](../evaluation/runtime_capture.py) and
[CLI](../evaluation/runtime_capture_cli.py).

## Implemented boundary

`capture_runtime(root)` obtains the shared reader lock, validates the original
5b/v2 checkpoint through `Capture`, and collects the exact journal-backed source
bytes into an immutable in-memory inventory. Plan, intent, script, current
checkpoint, v1 base when present, public inputs, requests, controls, committed
outcomes and their response/results are retained. `.writer.lock`, unrelated files
and unreferenced crash/orphan artifacts are excluded. No directory is modified.

`RuntimeSnapshot.files` is a read-only map of bytes. Plan, intent, events, report
and manifest properties return independent copies. This protects ordinary callers
from accidental mutation; it is not a sandbox against hostile Python code.

The closed generated `normlab.runtime-capture/v1` manifest records execution ID,
plan digest, checkpoint schema/digest/head/state/stop reason, mock evidence kind,
source file inventory and explicit false readiness/semantic-quality flags with
zero new inference. `captureRevisionId` hashes the execution ID and sorted exact
source inventory. It does not incorporate labels, scores, registry IDs or local
directory paths. Repeating identical saved input gives the same revision; a new
checkpoint gives a new revision of the same execution. Already captured bytes
remain available in memory after a later authorized continuation.

Bounds are inherited from the validated input: ordinary files 2 MiB, checkpoints
16 MiB, 4096 captured files, total captured bytes plus manifest at most 64 MiB.
The manifest itself is capped at 2 MiB. Input hashes, bytes and strict replay are
checked before constructing a snapshot. These remain unsigned consistency
checks, not source/writer authentication or proof of a provider call.

## CLI and verification

```bash
python -B -S evaluation/runtime_capture_cli.py snapshot /path/to/mock-execution
python -B -S evaluation/runtime_capture_cli.py verify /path/to/mock-execution /path/to/capture-manifest.json
```

The CLI prints only the manifest, not raw narrative/response bodies. Exit 0 means
validated metadata; exit 2 reports only a sanitized error type. Both commands are
read-only, SDK-free and acquire no inference/continuation authority.

`verify_capture_manifest(root, manifest)` derives metadata anew and requires exact
canonical equality, including field types. An old manifest rejects against a root
whose checkpoint has since advanced. This layer does **not** archive a filesystem
snapshot or add a portable capture reader; retaining historical captures on disk
is a later adapter responsibility. It also does not accept live captures, score
labels, an offline-envelope v1 bundle or any MLflow input.

## Checks and remaining layers

Five regression methods cover repeat identity and original source bytes,
defensive copies, immutable inventory, continuation lineage, preserved old bytes,
orphan exclusion, edited metadata and write/network/SDK-denied CLI inspection.
Python 3.14 dedicated suite: 5/5. The existing Stage 1 offline CI discovers it.
Python 3.10, style and final combined suite evidence are recorded in the stack
handoff after the remaining preparation layers.

[5d.2 export projection preparation](RUNTIME_EXPORT_PREPARATION_V1.md) retains all planned tasks and
first/final/attempt evidence without claiming an actual envelope export.
Then **5d.3 registry import plan**, binding execution/revision identities without
registry writes. Actual portable runtime export, prediction/reference scoring,
existing MLflow importer integration and live capability verification remain
outside this three-layer preparation stack; #77 remains incomplete.
