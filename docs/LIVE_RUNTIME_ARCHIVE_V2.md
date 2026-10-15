# Native live evidence consumers

Issue: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Source: [native boundary](NATIVE_LIVE_BOUNDARY_V1.md) and
[Stage1 schedule](STAGE1_NATIVE_SCHEDULE_V1.md).
Verification follows the [recorded user authorization](EVALUATION_VERIFICATION_AUTHORIZATION.md)
from the ongoing conversation.

## Read-only native capture

`capture_runtime(root, evidence_kind="live-capture")` explicitly selects the native
checkpoint reader. Default `mock` remains separate and rejects native evidence.
The native reader accepts fresh one-attempt/checkpoint v1 and bounded Stage1
schedule/checkpoint v2. It does not support native continuation.

The reader checks plan/intent/permit/journal bindings, installed execution code and
normalizer pins, all reservations/outcomes and re-derived normalized responses.
Stage1 lineage is regenerated without rewriting the source plan. Unknown outcome
reservations remain unknown; orphan response files are excluded from the snapshot
and cannot be adopted by export. A single lock covers source verification and the
immutable in-memory byte snapshot.

Native capture manifest v2 retains `evidenceKind=live-capture`, recorded dependency
pins and observed/unknown dispatch counts. All reader-side inference/authority
counters remain zero; recorded dispatches describe the source journal only.
The source is unsigned: response projections, saved clock declarations and runtime
pins are not proof that a provider, trusted clock or claimed runtime produced them.

Portable replay requires the same supported installed execution code/normalizer.
It allows a different reader Python runtime, retaining the captured dependency
digest verbatim. `readerRuntimePinsMatched` is a transient diagnostic in the replay
report, excluded from identity-bound manifests. `recordedRuntimeVerified=false`
remains explicit even when local runtime pins happen to match. Current dispatch
gates still require exact installed runtime pins; this read-only path grants no
execution permission, clock capability or credential access.

```bash
python3 -B -S evaluation/runtime_capture_cli.py snapshot /private/native-run \
  --evidence-kind live-capture
```

No clock factory, transport, persistent run authority or credentials are consulted
by snapshot/replay. Offline tests use fake-produced native checkpoints and do not
establish provider reachability or semantic quality.

## Archive v2

Explicit native export writes `normlab.runtime-archive/v2` with
`evidenceKind=live-capture`. Mock archive v1 remains a separate contract. A native
archive retains the original plan, intent, checkpoint, permit, source/candidate and
journal-backed response/result artifacts. No mock-script or mock continuation base
is inserted. Per-task records preserve first/final attempts, all planned tasks,
partial suffixes, unknown outcomes and usage gaps. Projection v2 adds recorded
observed dispatches and unknown-dispatch attempts to operational counts. Reader
side `inferenceCallsExecuted` stays zero.

```bash
python3 -B -S evaluation/runtime_archive_cli.py export /private/native-run \
  /private/native-archive --evidence-kind live-capture
python3 -B -S evaluation/runtime_archive_cli.py verify /private/native-archive
```

The existing fresh-directory/fsync/marker publication protocol is reused. The
reader verifies bounded complete inventories and regenerates capture/projection
bytes after the original source is removed. Live producer pins include the native
reader and execution modules. Trusted reader files are supplied by the caller;
archive files are data and are never imported as code. Producer code must match;
old code revisions require the corresponding trusted reader installation.

Stage1 lineage uses an independent pure reader, avoiding the frozen producer's
transitive extraction/`server` JSON imports. It checks revision, question,
provider/settings/caps, complete schedule, source/candidate and exact wire request
edges. As with the compiler, this establishes unsigned internal consistency,
not authenticity of the source manifest or human reference labels.

Only completed predictions receive a prediction seal. This seal does not certify
provider execution, billing completeness or semantic correctness; earlier transport
failures may still have unknown usage and dispatch status after a successful retry.
