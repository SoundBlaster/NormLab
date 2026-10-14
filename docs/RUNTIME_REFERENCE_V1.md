# Runtime selected-question reference v1

Canonical task: [Issue 77](https://github.com/SoundBlaster/NormLab/issues/77).
Input: a [verified runtime archive](RUNTIME_ARCHIVE_V1.md), then explicitly
selected label and review bytes. No labels are read during runtime execution.

## Label source

`normlab.runtime-reference-source/v1` has exactly `schema`, `revision`, `status`,
`planDigest`, `dataset` and `expected`. `dataset` matches the plan's pinned
`id/revision/sha256` declaration; `planDigest` matches its exact canonical plan.
The same reference can be reused for continued capture revisions of that plan.
It cannot silently follow changes to tasks, providers, contexts or dataset.

Each `expected` entry contains `taskKey`, `questionId` and `label`. Select at
least one and at most 4096 unique planned task/question pairs. A subset is valid:
unselected questions remain explicitly unevaluated. Noul labels are `yes`, `no`
or `uncertain`; choice labels must occur in the pinned answer schema; score
labels are integer scale indices. Boolean values are not integers here.

## Provenance and review

- `candidate-not-independent`: no adjudication artifacts may be attached.
- `human-adjudicated`: at least one review artifact is required. Each uses
  `normlab.runtime-reference-review/v1` with `reviewer`, `method`, `sourceDigest`,
  `planDigest`, `dataset`, `scope: selected-questions-only`, `approved: true`.
  The source digest binds exact original label bytes, including whitespace.
  Duplicate review artifacts, wrong scope and mismatched bindings are rejected.

The generated `normlab.runtime-reference/v1` retains source/review SHA-256 and
byte lengths, selected expectations and a content-derived `referenceId`.
Human review is a saved declaration, **not authenticated evidence of reviewer
identity or independence**. A hash proves consistency of supplied bytes, not
their correctness. Synthetic review fixtures must not be reported as real human
adjudication. Candidate agreement is not human gold or case-level accuracy.

Source plus reviews are bounded by 2 MiB; there are at most 16 reviews. The
generated reference also fits 2 MiB. Raw inputs are retained exactly for portable
revalidation. Unknown properties, out-of-plan selections and label types reject.
The API uses stdlib only and creates no registry or inference requests.

## Score boundary

The next layer creates an immutable score view for one capture revision. It
will not modify archive bytes, invent a prediction seal for partial captures,
claim full-case completeness or produce a critical-error-free rate. Mock
reference/score evidence retains false semantic quality and readiness flags.
