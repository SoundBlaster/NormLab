# Native live evidence consumers

Issue: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Source: [native boundary](NATIVE_LIVE_BOUNDARY_V1.md) and
[Stage1 schedule](STAGE1_NATIVE_SCHEDULE_V1.md).

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
