# Runtime paired comparison v1

Task: [Issue 77](https://github.com/SoundBlaster/NormLab/issues/77).
Inputs: two verified [runtime archives](RUNTIME_ARCHIVE_V1.md) and corresponding
regenerated [score views](RUNTIME_SCORE_VIEW_V1.md). Neither saved metrics nor
recomputed IDs alone establish validity. Existing legacy comparator stays unchanged.

## Pair unit

One planned question. Logical key:
`(caseId, candidateDigest, armId, repeat, stage, questionId)`.
Different execution/task IDs are retained in side evidence; matching is never
based on row order. Duplicate keys reject as ambiguous. A changed candidate is
a different target and becomes unpaired; changed source with the same target
is incompatible. Both sides' entire planned key union remains visible.

## Compatibility

Dataset and experiment declarations, context/retry policies, pinned definitions,
prompt, output schema, code/dependencies, scorer policy/code, evidence kind and
reference schema/status/revision/scope must agree. Original reference IDs and
digests remain in bindings; per-question selection/expectation must agree.
Unsigned review declarations must agree except plan/source digest bindings,
which each side validates independently against its own reference source.

`--vary provider|strategy|tactic` declares metadata variation; it does not relax
source, prompt, question or request checks or establish causality. Provider
variation covers the planned arm metadata, including model/settings/adapter;
all raw conditions remain in the source binding. Different caps/deadlines are
disclosed and operational differences do not imply semantic improvements.

- Default `strict-wire`: exact request and context digests must agree.
- Explicit `same-protocol-body`: same protocol, identical request body except
  `model`, identical context except its independently verified `requestDigest`.
  Method/headers must still agree; endpoints remain in verified archives.
  This narrower context evidence
  is stated in the report; it is not exact-wire equality or provider attestation.
  Other body fields, including instructions, reasoning and output limits, stay
  significant. Different wire protocols are incompatible, never guessed equivalent.

Prompt, segmentation or question changes need a separate frozen intervention
protocol. Version 1 intentionally reports them as incompatible. Declaring a
variable alone does not authorize arbitrary normalization or weaken comparison.

## Planned result

Rows retain both statuses, attempts, source record/outcome references and
first/final predictions/agreements. Missing sides become baseline-only or
candidate-only. Incompatible and unevaluated pairs carry explicit reasons.
Compatible pairs with two selected scored outcomes share one denominator for
agreement delta, regressions and rescues. Failure-to-completed is operational
recovery and does not automatically become a semantic rescue. Empty quality
denominator produces null rates/delta. First-attempt agreement is separate.

Operational counts use unique planned tasks and verified runtime summaries;
attempts/tokens are not summed again per question. Unique cases and repeated
question rows are not independent observations. Confidence intervals and
critical-error-free rate remain null; mock quality/readiness/release flags false.

Comparison is deterministic and bounded to 2 MiB, source-bound and read-only.
It creates no execution, prediction seal, reference, MLflow entry or inference.
Later layers add comparator and fresh export/verify CLI with readable Markdown.
