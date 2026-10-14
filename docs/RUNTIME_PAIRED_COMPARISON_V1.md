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
all raw conditions remain in the source binding. Different caps/deadlines,
including arm `timeoutNs` and `requestCaps`, are disclosed and suppress
operational completion delta. Complete task batch membership must agree;
row compatibility checks request/context bindings for every paired question.

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

## Result

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
The comparator and fresh export/verify CLI include readable Markdown.

## Offline CLI

From the repository root, with two archives and their saved score views:

```bash
python3 -B -S evaluation/runtime_compare_cli.py compare \
  baseline-archive baseline-score.json candidate-archive candidate-score.json \
  --output comparison-report
python3 -B -S evaluation/runtime_compare_cli.py verify \
  baseline-archive baseline-score.json candidate-archive candidate-score.json \
  comparison-report
```

For an explicitly declared provider variation within one protocol, add
`--context same-protocol-body --vary provider` to `compare`. This does not relax
other compatibility requirements. `verify` regenerates using the saved policy.

The output directory must be fresh and outside both input archives. It contains
exactly `report.json`, `report.md` and an empty `.writer.lock`. Both artifacts
are bounded to 2 MiB. Markdown previews the first 50 changed/excluded rows;
JSON retains the full union. Source archives and score files remain unchanged.

Export uses exclusive creation, file/directory fsync and a non-overwriting JSON
commit marker under a writer lock. Readers use a non-blocking shared lock and
reject active or incomplete publication, including the initial directory/lock
creation window; they do not wait or retry. Reading succeeds after publication
and lock release. Inventory scanning stops after at most four entries.
Failed partial
exports remain visible and cannot be resumed or overwritten. This is a POSIX
local publication protocol, not a power-loss durability guarantee.

Verification revalidates both archives and scores, regenerates the comparison
and Markdown, and rejects extra files, symlinks, altered counters/statuses and
rehashed derived artifacts. Incompatible or unevaluated pairs are valid report
data (exit 0); malformed inputs or invalid exports fail (exit 1). No provider
SDK or registry is loaded; errors print only their exception type.
