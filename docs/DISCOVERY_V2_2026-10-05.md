# Direct discovery v2 — 2026-10-05

## Changes

`evaluation/two_stage_v2.py` selects the separately versioned
`literal-discovery-then-classification/v2` candidate. Discovery now uses a direct
local OpenAI-compatible call, Russian instructions, no demonstration example,
and a JSON Schema with bounded non-empty fields and neutral subject/episode ID
patterns. Source text is passed unchanged in a separate user message.

The prompt distinguishes the narrator from letters, notifications and notes,
including indirect quotations. Exact unique source anchoring remains mandatory;
quotes are not translated, case-normalized or rewritten to rescue a response.
All discovery requests and complete SDK responses are captured. Classification
prompt/schema/model settings are unchanged; its complete response is also saved
for this candidate.

V2 statements retain `speaker`. The review contract accepts this optional field
for compatibility with older revisions. UI permits editing the source; a source
edit resets confirmation through the existing content-edit workflow. V1 output
does not gain a guessed/default speaker. The HTTP worker still selects v1;
v2 is an evaluation candidate, not a promoted default or a passed readiness gate.

## Development checks

The first candidate passed two of three discovery/attribution checks. Payment
was correctly quoted but quarantined because `aboutEpisode` was empty.
The final candidate clarifies the single-episode default and constrains IDs.

[Final three probes](../experiments/parking-discovery/2026-10-05-v2-probes-final/summary.json)
all pass exact quote coverage and expected speaker checks. Payment is classified
as asserted, non-payment as denied, and both opposing payment claims survive
with `narrator` and `letter_1`. The letter introduction is preserved in the quote.
These probes were used to tune the prompt and are not holdout evidence.

The [initial candidate evidence](../experiments/parking-discovery/2026-10-05-v2-probes/summary.json)
is preserved too. Both runs snapshot worker dependencies and their probe runner.

## Full synthetic-v1 comparison

40 unchanged inputs in eight development families. Local LM Studio
`openai/gpt-oss-20b`, temperature 0, seed 42, 8192 output tokens, no retries or
fallback. Classification settings and candidate labels were not tuned during
the run. Model IDs do not pin weights, quantization or server versions.

| Measure | V1 baseline | V2 candidate |
| --- | ---: | ---: |
| Cases attempted | 40 | 40 |
| Cases reaching classification | 0 | 40 |
| Empty discovery responses | 36 | 0 |
| Demo copies without source anchoring | 4 | 0 |
| Structural passes | 0 | 39 |
| All selected assertion probes pass | 0 | 11 |
| Required probes matched in retained statements | 0/46 | 17/46 |
| Selected forbidden-inference matches | 0 | 0 |
| Mean elapsed time per case | 3.49 s | 10.14 s |

All v2 subprocesses completed successfully. SYN021 fails the structural gate:
four classification records have empty `valueText` and are quarantined; no
statement survives. Successful process exit is not a structural/semantic pass.

Artifacts:

- [Raw v2 run](../experiments/parking-baseline/2026-10-05-synthetic-v2-gpt-oss-20b/run-manifest.json).
- [Comparison and scorer snapshot](../experiments/parking-evaluation/2026-10-05-discovery-v2-comparison/report.json).
- [Offline stage analysis](../experiments/parking-evaluation/2026-10-05-discovery-v2-stage-analysis/report.json).

The comparison scorer verified dataset snapshots and artifact digests for both
runs. Its diagnostic outcome now distinguishes successfully anchored discovery
from unanchored-only outputs; a quote matching the demo is counted as leakage
only if absent from the source. Assertion/structural pass rules were not relaxed.

## Where the probes are lost

Offline analysis uses exact fragment spans covering the unchanged candidate
probe offsets. It does not infer facts from related words or repair quotes.

- 44/46 candidate probe spans are covered by accepted discovery fragments.
- Two spans are absent: SYN019 payment-status information and SYN033 unnamed city.
- Of the 44 covered spans, 22 receive no classification record for any covering
  fragment; four receive classifications without the expected predicate/stance.
- 18 probes have raw predicate/stance matches. One is quarantined for
  empty `valueText`, leaving 17 retained probe matches.

For example, SYN001 discovers both the Moscow parking sentence and
`Парковку оплатил через приложение.`, but the classifier outputs records only
for the first fragment. This is not an anchoring failure.

## Attribution evidence and remaining problems

Selected manual inspection found:

- SYN026: narrator versus note separated; both payment polarities retained.
- SYN028: narrator versus notice separated on the same episode.
- SYN027: morning payment and evening non-payment assigned distinct episodes.
- SYN030: the claim about payment for another vehicle remains assigned to
  `vehicle_1`. Vehicle attribution is still imperfect.

These observations are not a scored attribution benchmark or a complete semantic
review. Candidate probes cover selected facts only; 44/46 quote coverage is not
full discovery recall. The 11/40 probe rate is not the agreed critical-error-free
target. Labels are not expert-approved gold; gaps and legal sufficiency remain
unscored. Zero selected forbidden matches does not prove no invented inference.

## Next step

Create a separately versioned classification candidate requiring an explicit
result for every `fragmentId`: supported classifications, explicit unknown when
the text expresses uncertainty, or a justified no-supported-predicate result.
Reject silent omissions and empty `valueText`; preserve the original fragments
and attribution. Measure coverage, polarity and extra unsupported predicates
separately. Address the two discovery omissions and vehicle attribution as
separate categories. Then repeat the same corpus without changing its labels.

## Reproduction and checks

```sh
.tools/parking-evaluation/bin/python evaluation/run_synthetic.py \
  experiments/parking-baseline/local-v2 --pipeline v2
npm run parking:evaluate:synthetic -- \
  experiments/parking-evaluation/local-v2 \
  experiments/parking-baseline/2026-10-05-synthetic-v1-gpt-oss-20b \
  experiments/parking-baseline/local-v2
.tools/parking-evaluation/bin/python evaluation/analyze_stages.py \
  experiments/parking-baseline/local-v2 \
  experiments/parking-evaluation/local-v2-stages
```

Destinations must be new directories. Executed validation: six development probe
cases (initial and final candidates), 40 corpus cases, comparison scorer and
offline stage analysis. TypeScript check, Oxlint, Ruff and formatter checks
passed. Browser interaction and the broader test suite were not run.
