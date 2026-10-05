# Complete classification v3 — 2026-10-05

## Contract and implementation

`evaluation/two_stage_v3.py` selects discovery v2 plus the new classification
candidate `literal-discovery-then-classification/v3`. HTTP/UI still selects v1.

The classification JSON Schema requires a result property for every incoming
`fragmentId`, with no additional IDs. Each decision has one of two statuses:

- `classified`: non-empty classifications, non-empty bounded `valueText`, empty
  `reason`; allowed predicate and stance only.
- `no-supported-predicate`: empty classifications and a non-empty reason.

The application independently checks the complete ID set, status/field
consistency, limits, predicate/stance vocabulary and duplicate predicate/stance
pairs. Invalid responses fail without retry or silent repair. Source quotes,
subjects, episodes and speakers are retained from discovery; the classifier
cannot supply replacements. Raw requests/responses and accepted decisions are
saved separately. An explicit refusal to classify is not automatically correct.

Russian instructions distinguish explicit uncertainty (`unknown`) from denial
and from an unrelated fragment. Silence does not justify adding `unknown`.

## Development checks

The initial five-case probe restored payment/permit classification but still
treated explicit payment uncertainty as unrelated. The prompt was refined to
choose the predicate first, then its stance. Initial and final evidence are
preserved in the [initial probe run](../experiments/parking-baseline/2026-10-05-classification-v3-probes/)
and [final probe run](../experiments/parking-baseline/2026-10-05-classification-v3-probes-final/).

The final five probes preserve payment, payment uncertainty, permit and both
payment polarities from narrator versus note/notice. These were prompt tuning
cases, not holdout evidence.

[Nine offline contract checks](../experiments/parking-classification/2026-10-05-contract-checks/report.json)
passed: valid unknown and explicit unrelated decisions accepted; missing/extra
IDs, blank values, duplicate predicate/stance, inconsistent status/items,
missing reason and unknown predicate rejected. CI runs these checks with the
standard library; no model or local server is required.

## Controlled comparison

The 40-case comparison reuses all **82 accepted fragments** from the saved v2
run. Their quotes, IDs and attributes are unchanged. Each parent output is copied
into the new run, hashed in the artifact manifest and bound by source digest and
parent output digest. Copied discovery calls are marked `replayed=true`.
This isolates classification changes from new discovery variation.
The [replay integrity check](../experiments/parking-classification/2026-10-05-replay-integrity/report.json)
passed all 40 cases and confirmed 82 unchanged fragments, parent digests and
explicit replay/latency metadata.

Each case makes one new classification call to local LM Studio
`openai/gpt-oss-20b`: temperature 0, seed 42, max tokens 8192, timeout 180 seconds,
no retries or fallback. `latencyScope=classification-with-replayed-discovery`
excludes new discovery inference; it cannot be compared directly with v2's
full-pipeline elapsed time. Model IDs do not pin weights/server versions.

The unchanged dataset-aware scorer verifies source/dataset snapshots and artifact
digests. Labels remain candidate expectations; no labels were sent to the model.

| Measure | V2 | V3 with fixed v2 discovery |
| --- | ---: | ---: |
| Cases attempted | 40 | 40 |
| Structural passes | 39 | 38 |
| All selected assertion probes pass | 11 | 28 |
| Required probes retained | 17/46 | 34/46 |
| Input fragments represented in raw classification output | 57/82 | 82/82 |
| Fragments absent from raw classification output | 25 | 0 |
| Accepted explicit per-fragment decisions | Not part of v2 contract | 79/82 |
| Selected forbidden-inference matches | 0 | 0 |

Raw ID coverage is not contract acceptance: SYN018 and SYN033 contain all their
IDs but have non-empty `reason` under `classified`, violating the declared
contract. Their three decisions are rejected as whole responses; 38 cases remain
accepted. SYN018 also incorrectly treats bank debit as proof of parking payment.
The validator catches inconsistent fields; the payment error is a separate
semantic observation, not a semantic guarantee provided by validation.

## Where errors remain

The fixed discovery covers 44/46 selected probe spans. Coverage was not improved
by classification replay; SYN019 and SYN033 discovery omissions remain.

| Covered candidate spans | V2 | V3 |
| --- | ---: | ---: |
| No classification records | 22 | 2 |
| Classified with other predicate/stance | 4 | 8 |
| Raw predicate/stance matches | 18 | 34 |

The two v3 spans without classifications split into one rejected response
(SYN018) and one explicit but incorrect unrelated decision (SYN038). Therefore
zero missing raw fragment IDs does not mean zero semantic omissions.

The twelve cases missing the all-probes gate are SYN004, SYN008, SYN010, SYN017,
SYN018, SYN019, SYN029, SYN030, SYN032, SYN033, SYN038 and SYN039. Categories
include interval-specific payment, payment failure versus uncertainty,
registration/zone ambiguity, payment for another vehicle and jurisdiction.

## Fresh end-to-end probes

[Three additional cases](../experiments/parking-baseline/2026-10-05-classification-v3-fresh/)
(SYN001, SYN003, SYN026) execute new discovery plus classification without replay.
All complete successfully and preserve target payment/unknown/opposing-source
claims. SYN026 additionally repeats location/parking predicates on payment
quotations whose place evidence is in another fragment. This needs review of
evidence bindings; successful execution and target-probe preservation do not
establish that every generated statement is supported by its own quote.

## Evidence

- [Raw controlled run](../experiments/parking-baseline/2026-10-05-classification-v3-replay/run-manifest.json).
- [Unchanged semantic scorer comparison](../experiments/parking-evaluation/2026-10-05-classification-v3-comparison/report.json).
- [V2 stage analysis](../experiments/parking-evaluation/2026-10-05-classification-v2-stages-final/report.json).
- [V3 stage analysis](../experiments/parking-evaluation/2026-10-05-classification-v3-stages-final/report.json).

Stage analysis distinguishes submitted IDs, accepted explicit decisions, actual
classifications and explicit unrelated results. Its raw coverage parsing is
diagnostic, not acceptance of the submitted decision semantics. Source snapshots
and raw outputs remain immutable; all manifests are unsigned local records.

## Limits and next step

28/40 is **70% selected candidate-probe pass**, not the agreed 80% of cases
without critical errors. Selected probes do not cover all statements or all
unsupported inferences. Gap detection, legal sufficiency and final outcomes are
unscored; data is synthetic development material, not independent holdout.
Broader coverage exposed more wrong predicate/stance choices (four to eight).
Full contract validity decreased by one case. These costs remain in the score.

Next: review the twelve failures by category and add per-classification evidence
support checks. Treat explicit unknown, interval-specific claims and other-vehicle
payment separately; do not transfer a fact from another fragment without a
recorded evidence binding. Resolve the status/reason grammar inconsistency and
two unchanged discovery omissions in separately versioned candidates. Keep
independent semantic review before promotion to HTTP/UI.

## Reproduction

```sh
.tools/parking-evaluation/bin/python evaluation/check_classification_v3.py \
  experiments/parking-classification/local-contract
.tools/parking-evaluation/bin/python evaluation/run_synthetic.py \
  experiments/parking-baseline/local-v3 --pipeline v3 \
  --replay-discovery experiments/parking-baseline/2026-10-05-synthetic-v2-gpt-oss-20b
npm run parking:evaluate:synthetic -- \
  experiments/parking-evaluation/local-v3 \
  experiments/parking-baseline/2026-10-05-synthetic-v2-gpt-oss-20b \
  experiments/parking-baseline/local-v3
.tools/parking-evaluation/bin/python evaluation/analyze_stages.py \
  experiments/parking-baseline/local-v3 \
  experiments/parking-evaluation/local-v3-stages
```

All destinations must be new. Omit `--replay-discovery` for new discovery inference.
Executed checks: nine contract checks, ten development classification cases,
40 controlled classification cases and three fresh end-to-end cases; scorer and
stage analyses; TypeScript, Oxlint, Ruff and formatter checks. Browser walkthrough
and the broader test suite were not run. CI contract step is added; workflow
triggers remain limited to PRs/pushes targeting main.
