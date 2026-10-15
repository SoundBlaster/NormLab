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
edges. Provider format/settings/variable names use a closed contract and bind to
the retained source manifest. As with the compiler, this establishes unsigned internal consistency,
not authenticity of the source manifest or human reference labels.

Only completed predictions receive a prediction seal. This seal does not certify
provider execution, billing completeness or semantic correctness; earlier transport
failures may still have unknown usage and dispatch status after a successful retry.

## Reference, score and MLflow

The existing reference source/review v1 contracts apply to verified native archives
as well as mock archives. References bind the exact captured plan/dataset and
selected task/question coordinates. Candidate references remain
`candidate-not-independent`; declared human review remains unsigned and explicitly
unauthenticated. Neither reference status establishes case-level correctness.

Native score views use `normlab.runtime-score-view/v2` and retain
`evidenceKind=live-capture`, first/final answers, all planned/selected denominators,
unevaluated reasons, observed usage and usage gaps. The scorer policy is unchanged:
selected-question agreement only, with no `criticalErrorFreeRate`. Repeated scoring
does not invoke inference or consume run authority.

```bash
python3 -B -S evaluation/runtime_score_cli.py score /private/native-archive \
  /private/reference.json --output /private/score.json
python3 -B -S evaluation/runtime_score_cli.py verify /private/native-archive \
  /private/score.json
python3 -B -S evaluation/import_runtime_mlflow.py /private/native-archive \
  --score /private/score.json --dry-run
```

MLflow live projection/score/import-result schemas use v2. Execution bindings retain
the original intent digest and execution code/dependency/adapter pins; they have no
mock script digest. The capture/projection/score parent structure and idempotent
local registry protocol are reused. Changed reference revisions add distinct score
children while reusing unchanged execution/capture records. Complete archives and
score bytes remain navigable from imported artifacts, including after deletion of
the original run/export directories.

`--dry-run` is SDK-free and creates no registry. Removing it explicitly writes to
the local registry selected by `--storage`; it still makes no provider calls.
Repeated import verifies existing immutable artifacts/metrics before reuse.
Recorded native usage/dispatch metrics are source evidence, while operation-side
`inferenceCallsExecuted=0` describes replay/import itself. Missing usage/cost is not
converted into a zero spend, and agreement is not semantic quality evidence.
Source verification of both export projections and registry plans selects its
reader only after validating the saved schema/evidence-kind pair; a v2 plan is
never silently passed to a mock reader. Partial receipt reuse is re-derived too.

Native live resume and separately authorized bounded live smoke remain outside
this consumer implementation. These readers cannot turn a saved permit into an
execution grant or adopt an orphan response.
