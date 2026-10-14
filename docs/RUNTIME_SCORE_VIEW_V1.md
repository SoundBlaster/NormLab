# Runtime score view v1

The stdlib-only scorer combines one [verified archive](RUNTIME_ARCHIVE_V1.md)
with one [source-bound reference](RUNTIME_REFERENCE_V1.md). It regenerates and
validates the reference before scoring. The archive and reference bytes are
never changed; the output is a separate `normlab.runtime-score-view/v1`.

## Fixed policy

`runtime-selected-question-agreement/v1` uses Noul `yes` at probability >= 0.8,
`no` at <= 0.2, and `uncertain` otherwise. Choice compares exact labels. Score
compares the returned numeric value to the reference's integer scale index
exactly: 1.5 does not match 2. No rounding/tolerance is implied. A new policy
requires a new version; saved output cannot select arbitrary scorer code.

## Rows and denominators

Every planned task and question remains in the view, including unselected,
not-dispatched, failure and unknown outcomes. Each question retains its selected
flag, expected label, first/final prediction, first/final agreement and explicit
not-evaluated reason. A failure has no fabricated prediction. Retries keep their
attempt counts and source outcome references; first and final scores are separate.

Global and per-arm summaries show planned/selected/scored questions, unselected
and selected-unevaluated counts, disagreements, first-pass counts and statuses.
`agreementAmongScored` divides final agreements by selected completed questions;
with no scored questions it is null. This conditional agreement is not a
completion rate, case-level accuracy or critical-error-free rate. Arm/repeat
rows are not assumed statistically independent.

## Binding and verification

The content-derived score ID binds archive/execution/capture IDs, original task
record/outcome references, complete reference inputs and provenance, fixed policy,
trusted scorer code pins, rows and regenerated summaries. Different capture or
reference revisions produce distinct views. The reference ID stays stable for
continuation of the same plan. Source/review UTF-8 bytes are embedded losslessly,
so original label files are unnecessary for verification.

`verify_score` revalidates embedded provenance and recomputes the entire view
using the trusted installed scorer. Rehashing edited counters, status, policy,
reference status or code pins cannot make altered output valid. The view is
bounded by 2 MiB; oversized output is rejected, never truncated. The matching
portable archive must still be available for raw prediction replay.

Partial captures can be scored without acquiring a fabricated prediction seal.
The view preserves the existing sealed/unsealed state. All current captures are
unsigned mock evidence: cost and critical-error-free rate remain null;
readiness, semantic quality and release approval remain false even with a
declared human reference. [Local score-child import](RUNTIME_SCORE_MLFLOW_V1.md)
is a separate explicit command; scoring itself never opens registry storage.

Canonical task: [Issue 77](https://github.com/SoundBlaster/NormLab/issues/77).
