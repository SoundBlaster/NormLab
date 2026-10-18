# Final native stop-control consumers: v4

Date: 2026-10-18 (Europe/Moscow). Ledger:
[#77](https://github.com/SoundBlaster/NormLab/issues/77).

This additive adapter connects both [native unknown-stop](NATIVE_UNKNOWN_STOP_V1.md)
and [resumed unknown-stop](RESUMED_UNKNOWN_STOP_V1.md) to portable archives,
selected-question scoring and local MLflow. All 59 frozen native/resume/stop/v3
producer modules stay byte-identical to `d28c08c`. There are no provider calls,
current clock/claim/key lookups or execution grants in these consumers.

## Closed versions and identities

| Artifact                                     | New version                                                                   |
| -------------------------------------------- | ----------------------------------------------------------------------------- |
| Capture / export projection                  | `normlab.runtime-capture/v4`, `normlab.runtime-export-plan/v4`                |
| Portable archive / verification              | `normlab.runtime-archive/v4`, `normlab.runtime-archive-verification/v4`       |
| Selected-question score                      | `normlab.runtime-score-view/v4`                                               |
| Registry plan / import result                | `normlab.runtime-registry-plan/v4`, `normlab.runtime-mlflow-import-result/v4` |
| MLflow capture/projection and score payloads | `normlab.runtime-mlflow-projection/v4`, `normlab.runtime-mlflow-score/v4`     |

The source format is `native-stop-control/v1`; its exact control checkpoint is
either `normlab.native-stop-checkpoint/v1` or `normlab.resumed-stop-checkpoint/v1`.
Fresh native, mock and ordinary continuation inputs reject under this adapter.
Frozen v1/v2/v3 readers remain closed. `runtime_consumer_v4.py` is a separate schema
dispatcher; common score/import CLIs use it without changing the pinned previous
dispatcher. The historical minimal copied archive reader still handles its
original formats without loading the new optional modules.

The original UUID/plan/intent define one execution parent. A final control creates
a distinct exact capture revision, projection and score. The capture ID binds
every retained source byte plus the three new consumer pins. Archive producer
pins contain the frozen 59 plus these three modules: 62 files covering the local
reader import closure. Existing execution MLflow payloads remain native v2, so
the parent is byte-identical across pre-stop and final-control revisions.

## Source bytes, control and unknown evidence

A shared source lock covers control validation and the immutable byte snapshot.
The adapter verifies the existing control through its frozen reader, original
source bytes and immutable pre-stop archive. It retains the exact final request
and control checkpoint, original and resumed journals/checkpoints, original base
archives, and the full resumed pre-stop evidence package when present.

Unreferenced content-addressed root blobs are retained separately and explicitly
labelled `unattributed-uncommitted-artifacts`, `adopted=false`. Resumed controls
retain their previously committed orphan inventory and evidence ID. The older
native stop format did not bind orphan blobs: v4 binds the bytes observed during
capture, without claiming that its older control authenticated their history or
associated them with an attempt. Unpublished `.pending-*` writer temporaries do
not become outcomes. Hashes/pins demonstrate consistency, not producer, provider,
clock or operator authenticity.

Task records, first/final outcomes and all existing counts are reused from the
verified immutable pre-stop projection. A stop cannot change semantic results,
clear reservations/charges, establish unknown usage or seal predictions.
`state=paused-unknown` remains the source semantic state;
`controlState=stopped-with-unknown` explicitly describes the final operator
decision. The prediction seal remains `unsealed`.

Supplemental `controlMetrics` count operator-stopped unknown attempts, retained
orphan blobs/bytes and zero adopted outcomes. They are not provider token usage
or billed cost. Existing runtime unknown usage/counts remain unchanged and
`actualCost` remains null. Selected references score only completed selected
questions; unknown/not-attempted questions retain their unevaluated reasons. No
case-level correctness or critical-error-free rate is inferred.

Score IDs bind the exact v4 archive, capture, reference, policy, control metadata
and current scorer pins. The common scorer's code pins change with this additive
integration; saved older score views require their original trusted scorer code.
Regenerating a view with current code creates a distinct score ID rather than
silently blessing an old view.

## Portable publication and local MLflow

The v4 archive uses fresh-only durable publication with bounded regular files,
closed fixed-depth namespaces and content-addressed blobs. Existing limits stay
unchanged: 2 MiB per bounded metadata/blob, 64 MiB aggregate and 4096 entries,
with the existing separate journal bound. Existing/partial directories reject;
there is no overwrite, repair or orphan adoption. Readers verify the full tree,
installed pins, lengths/hashes, nested archives and regenerated capture/projection.
Verification survives original source deletion and copied trusted readers.

Local MLflow imports retain one execution parent and distinct immutable
capture/projection/score children. Re-import verifies/reuses matching records;
interrupted local import reuses its run/metric history without duplicates. Both
the archive and score remain navigable from stored artifacts after source deletion,
including the exact stop control and orphan bytes. `--dry-run` remains SDK-free
and creates no registry, using only a temporary verified byte copy. Actual import
writes only explicitly selected local storage. No registry import grants resume,
adoption, inference or release authority.

## Commands

```bash
python3 -B -S evaluation/runtime_capture_cli.py snapshot /path/to/stopped-run \
  --native-stop --evidence-kind live-capture
python3 -B -S evaluation/runtime_capture_cli.py registry-plan /path/to/stopped-run \
  --native-stop --evidence-kind live-capture

python3 -B -S evaluation/runtime_archive_cli.py export /path/to/stopped-run \
  /path/to/fresh-v4-archive --native-stop --evidence-kind live-capture
python3 -B -S evaluation/runtime_archive_cli.py verify /path/to/fresh-v4-archive

python3 -B -S evaluation/runtime_score_cli.py score /path/to/fresh-v4-archive \
  /path/to/reference.json --output /path/to/fresh-score.json
python3 -B -S evaluation/runtime_score_cli.py verify /path/to/fresh-v4-archive \
  /path/to/fresh-score.json
python3 -B -S evaluation/import_runtime_mlflow.py /path/to/fresh-v4-archive \
  --score /path/to/fresh-score.json --dry-run --storage /path/to/local-registry

# With the pinned local MLflow runtime, removing --dry-run writes local storage.
```

`--native-stop` and `--native-continuation` are mutually exclusive. Native stop
capture/export requires explicit `--evidence-kind live-capture`. Archive verify,
score and import dispatch only on supported closed archive schemas.

## Verification and remaining work

Verification uses synthetic native/resumed captures, fake HTTP/clocks, SDK/network/
write guards, source deletion and copied trusted readers, coordinated rehashed
mutations, active locks, publication faults/process exits and the 288-task corpus.
Actual pinned MLflow uses temporary local SQLite/artifacts with network denied.
See [standing authorization](EVALUATION_VERIFICATION_AUTHORIZATION.md). Exact local
results are recorded below after execution; CI/review are separate evidence.

Local results on 2026-10-18:

| Check                                                               | Result                                                         |
| ------------------------------------------------------------------- | -------------------------------------------------------------- |
| Full SDK-free regression, Python 3.14.8                             | 368/368; 249.040 s                                             |
| Focused v4 consumers, Python 3.10.19                                | 10/10; 37.494 s                                                |
| Full local MLflow import regression, Python 3.13.15 / MLflow 3.16.1 | 45/45; 64.205 s                                                |
| Ruff lint/format                                                    | 182 Python files pass                                          |
| Frozen producer equality / reader closure                           | 59 files unchanged from `d28c08c`; 62 pins cover local imports |
| Prettier / relative documentation links / whitespace                | Pass; 162 relative links                                       |

The checks cover both control formats, raw request/checkpoint/orphan bytes,
read-only and SDK guards, source deletion, a copied 62-file trusted reader,
rehashed mutations, publication faults and two actual process exits. Corpus
coverage retains all 288 selected questions: one scored, 287 unevaluated in the
synthetic partial-run fixture. Actual local MLflow verifies shared execution
parents, distinct capture children, source deletion, idempotence and interrupted
metric publication recovery. Dependency deprecation/resource warnings remain;
all assertions pass. Builds/tests/temp/logs use verified per-checkout TB5 paths.
No provider requests or real credentials were used.

Correlated adoption requires independent attempt-bound producer receipts and
remains unsupported. Separately authorized bounded live smoke, transport/provider
reachability and semantic quality remain unproven. Broad #77 acceptance is not
automatically completed by this consumer slice.
