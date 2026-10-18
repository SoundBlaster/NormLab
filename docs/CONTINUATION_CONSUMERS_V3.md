# Native continuation evidence consumers: v3

Date: 2026-10-18 (Europe/Moscow). Ledger:
[#77](https://github.com/SoundBlaster/NormLab/issues/77).
Source: [native safe resume](NATIVE_SAFE_RESUME_V1.md).

## Scope and compatibility

The additive reader supports `normlab.native-resume-checkpoint/v1` as
`sourceFormat=native-continuation/v1`, `evidenceKind=live-capture`. It never resumes
execution, samples time, reads credentials/local claims, adopts orphan outcomes or
constructs transport. Original fresh native captures remain v2; mock evidence stays
v1. The frozen 54 native/resume dependency modules are unchanged. Old source and
archive readers continue to reject the unsupported continuation format.

The new consumer layer is separate from the pinned execution layer:

| Area                                   | Schema                                    |
| -------------------------------------- | ----------------------------------------- |
| Snapshot                               | `normlab.runtime-capture/v3`              |
| Export projection                      | `normlab.runtime-export-plan/v3`          |
| Portable archive                       | `normlab.runtime-archive/v3`              |
| Verification report                    | `normlab.runtime-archive-verification/v3` |
| Registry plan                          | `normlab.runtime-registry-plan/v3`        |
| Selected-question score                | `normlab.runtime-score-view/v3`           |
| MLflow capture/projection/score/result | corresponding `v3` schemas                |

Task records and selected-reference source/review contracts retain their existing
v1 shapes. The MLflow **execution parent** deliberately retains its native v2
payload, even when its capture children use v3. This preserves the immutable key
and bytes for one original execution across original/continued revisions.

## Exact snapshot and portable archive

A source shared lock covers `ResumeCapture` validation and collection of immutable
bytes. The snapshot retains the exact plan, intent and current checkpoint; all raw
invocation/reservation/terminal events; control requests; and every referenced
request/outcome/response/result artifact. It also retains the complete verified
`native-resume-base/` archive, including its marker/empty lock and byte-identical
original checkpoint. Orphan responses remain excluded and cannot become verdicts.

The manifest records original base archive/capture/checkpoint identities, invocation
IDs, effective caps, original deadline, recorded dependencies and cumulative
observed/unknown dispatches. Its `captureRevisionId` binds execution UUID, exact
source inventory and consumer pins. Consumer changes therefore create a different
revision without changing the original execution UUID. New consumer pins cover
the three new reader/dispatch modules; archive producer pins additionally include
all 54 frozen resume dependencies. Existing archives require matching trusted
reader files; archive contents never supply executable code.

Archive v3 contains `source/`, `projection/`, `capture.json` and `projection.json`.
The source namespace permits exactly the original flat source files/artifacts plus
the embedded legacy base archive under `source/native-resume-base/`. Inventory,
path, regular-file, symlink, digest/length, sorted uniqueness, per-file, total-byte
and total-entry checks precede replay. Verification regenerates snapshot,
projection and archive index from the retained source, including after the original
run/export directories have been deleted. Recomputed outer hashes alone cannot
make changed source counters or projections valid.

Publication uses a fresh owner-private directory, exclusive writer lock, fsync and
an atomically replaced final archive marker. Partial archives are rejected; existing
destinations are never overwritten or repaired. A committed marker can be inspected
after missing acknowledgement. Actual process-exit checks establish tested local
crash boundaries, not arbitrary power-loss durability.

## Counts, selected references and scoring

The projection retains all planned tasks/questions, every original and resumed
attempt/invocation, reservation charges, known usage and unknown billing, and
first/final outcomes. An interrupted reservation remains unknown/unscored; the
unused suffix remains `not-dispatched` and stays in the denominator. A successful
retry can seal completed predictions while earlier dispatch/billing remains
unknown. A seal certifies neither provider authenticity nor semantic correctness.

The existing scorer policy remains selected-question agreement. Candidate labels
remain `candidate-not-independent`; declared human adjudication is still unsigned.
Score views bind the exact archive/capture/reference revision, keep unevaluated
reasons and first/final comparisons, and never report `criticalErrorFreeRate` or
case-level quality. Repeated scoring dispatches nothing.

## Local MLflow and recovery

Original intent/plan/code/dependency/adapter bindings define one stable execution
parent. Distinct exact capture revisions create distinct capture/projection/score
children. Importing an older revision again verifies/reuses its immutable records;
it cannot overwrite a later capture or reset the original reservations. A new
reference revision creates a distinct score child without reimporting the capture.

The existing local SQLite/MLflow protocol verifies payloads, metrics, completed
parents and uploaded source artifacts before reuse. The full v3 archive and score
remain navigable from stored artifacts after source deletion. Recovery from a
local post-metric interruption reuses the original MLflow run and does not append
duplicate metric history. This recovery is registry reconciliation, not inference
resume. Unknown usage/cost is never converted into zero spend.

`--dry-run` is SDK-free and creates no registry, although it uses a temporary
verified byte copy. Actual import writes only the explicit local `--storage` and
makes no provider calls. Production registry writes/deployment are outside this
delivery.

## Commands

```bash
python3 -B -S evaluation/runtime_capture_cli.py snapshot /path/to/continued-run \
  --evidence-kind live-capture --native-continuation
python3 -B -S evaluation/runtime_capture_cli.py registry-plan /path/to/continued-run \
  --evidence-kind live-capture --native-continuation

python3 -B -S evaluation/runtime_archive_cli.py export /path/to/continued-run \
  /path/to/fresh-v3-archive --evidence-kind live-capture --native-continuation
python3 -B -S evaluation/runtime_archive_cli.py verify /path/to/fresh-v3-archive

python3 -B -S evaluation/runtime_score_cli.py score /path/to/fresh-v3-archive \
  /path/to/reference.json --output /path/to/fresh-score.json
python3 -B -S evaluation/runtime_score_cli.py verify /path/to/fresh-v3-archive \
  /path/to/fresh-score.json
python3 -B -S evaluation/import_runtime_mlflow.py /path/to/fresh-v3-archive \
  --score /path/to/fresh-score.json --dry-run --storage /path/to/local-registry

# In the pinned MLflow environment, removing --dry-run writes to local storage.
```

Default capture/export paths retain their previous closed formats. Archive
verification dispatches on the closed saved schema; the old minimal copied-reader
installation still handles its original schemas without the new optional modules.
Stop-only native controls remain unsupported by this v3 source adapter; it cannot
skip unknown work or turn saved authorization into current execution permission.

## Verification and remaining work

Offline tests use synthetic original/resumed native captures, fake clocks/HTTP,
SDK/network/write guards, copied trusted reader files, controlled process exits and
the full 288-task corpus denominator. Local integration uses pinned MLflow 3.16.1
with network denied and temporary SQLite storage. These checks do not establish
provider reachability, trusted producer/clock identity, model quality or deployment.
The [standing verification authorization](EVALUATION_VERIFICATION_AUTHORIZATION.md)
covers this consumer slice and local registry checks.

Local results on 2026-10-18:

| Check                                                               | Result                                                  |
| ------------------------------------------------------------------- | ------------------------------------------------------- |
| Full SDK-free regression, Python 3.14.8                             | 343/343; 191.803 s                                      |
| Focused continuation consumers, Python 3.10.19                      | 14/14; 20.578 s                                         |
| Full local MLflow import regression, Python 3.13.15 / MLflow 3.16.1 | 42/42; 54.049 s                                         |
| Ruff lint and format                                                | 174 Python files pass                                   |
| Frozen execution/resume producers                                   | All 54 files byte-identical to base `d6173b7`           |
| v3 producer closure                                                 | 57 pinned files cover the local consumer import closure |

The regression caught an optional-module import breaking the old minimal copied
reader installation; lazy schema dispatch preserves that installation. MLflow
integration emits dependency deprecation/resource warnings; all assertions pass.
No provider requests were made.

### CI follow-up — 2026-10-18

Codex review completed without findings at `f1692d1`. Five jobs passed in
[CI run 39102182314](https://github.com/SoundBlaster/NormLab/actions/runs/39102182314).
`Stage 1 dataset audit` was cancelled: its annotation explicitly reports that the
job exceeded the five-minute timeout. The SDK-free suite was still progressing
through passing tests. Increase that job's timeout to ten minutes, retaining the
same commands and network guards; the new-head CI result is separate evidence.

Unknown-stop application to resumed captures, portable stop-control consumers,
attempt-correlated adoption and separately authorized live smoke remain open.
Completion of this slice alone does not close broad #77 acceptance.
