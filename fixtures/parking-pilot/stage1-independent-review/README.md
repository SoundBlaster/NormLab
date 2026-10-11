# Independent Stage 1 LLM review — 2026-10-09

Fresh reviewer with no conversation history. Phase 1 read only source-only.json,
saved blind.json, then phase 2 compared all 16 sources and 32 authored candidate
expectations. This is independent model review, not human/expert ground truth.
The reviewer used no provider API, credentials, network or production access.

- `blind.json`: frozen source-only readings, 25 literal evidence spans.
- `review.json`, `report.md`: raw comparison verdicts and five issues.
- `blind-integrity.json`: integration owner's source/span check.
- `provenance.json`, `integration-policy.json`: input hashes, protocol and the
  treatment policy declared before the owner read final comparison artifacts.
- `adjudication-counterexamples.json`: owner's proposed examples for the next
  revision; these are not independent reviewer labels or additional scored cases.
- `manifest.json`: portable file hashes, original dataset binding and hold decision.

Raw reviewer artifacts retain the paths originally used under `.artifacts/`.
Their portable copies are siblings here and retain identical bytes/hashes. Hashes
bind the saved evidence; they do not prove reviewer identity or absence of bias.

The historical `review.json` stays byte-identical. Its C001→IR-003 association
was inconsistent with IR-003's case and record scope; `erratum-2026-10-10.json`
records the correction, and `review-v2.json` is the consistent projection for
new readers.

30/32 authored expectations agreed; R028 needs revision and R015 is unresolved.
These are review judgments, not an accuracy measurement. Historical v1 corpus and
bookkeeping counts remain intact; this review does not certify their semantics.
Candidate/expert status is not automatically promoted.

The comparison gate decision is `hold`: resolve IR-001/IR-002 and scope/ambiguity
policy before constructing a new version. This is a documented research decision,
not an access control or an API-runner enforcement mechanism.

Report: [integration summary](../../../docs/STAGE1_INDEPENDENT_REVIEW_2026-10-09.md).
