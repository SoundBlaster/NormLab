# Synthetic-v1 evaluation — 2026-10-05

## Scope

Dataset-aware runner/scorer was applied to all 40 synthetic-v1 cases in eight contrast families. The run used the existing two-stage LangExtract pipeline with LM Studio `openai/gpt-oss-20b`, local OpenAI-compatible endpoint, temperature 0 and seed 42. Discovery was attempted 40 times; no case reached the classification call. No retries, prompt changes, or model fallbacks were made during this baseline.

Raw run artifacts: [`2026-10-05-synthetic-v1-gpt-oss-20b`](../experiments/parking-baseline/2026-10-05-synthetic-v1-gpt-oss-20b/). Scored report and scorer snapshot: [`2026-10-05-synthetic-v1-final`](../experiments/parking-evaluation/2026-10-05-synthetic-v1-final/).

## Result

| Measure | Result |
|---|---:|
| Cases attempted | 40/40 |
| Structural pass | 0/40 |
| Candidate assertion-probe pass | 0/40 |
| Required probes matched | 0/46 |
| Forbidden-inference matches | 0 |
| Cases reaching classification stage | 0/40 |
| Empty discovery responses | 36/40 |
| Discovery responses copied from the prompt's demo example | 4/40 |
| Mean elapsed time per case | 3.49 s |

All 40 cases ended with `ValueError: No exactly anchored assertions; review source manually`. In 36 cases discovery returned an empty extraction array. In four cases it copied the three demo-example statements from the prompt; these quotes do not occur in the case narratives and were quarantined before classification. The classifier therefore received no fragments in any case.

The scoring denominator includes every case. A provider/extractor failure, missing output, malformed statement, required-probe miss, or forbidden inference cannot count as a pass. The scorer checks source digests, manifests, exact application offsets, candidate required predicate/stance/span probes, and forbidden predicate/stance pairs.

## Interpretation and limits

This run shows that this specific model, prompt, LangExtract adapter, and local server combination did not extract the current synthetic corpus. The demo-example copies suggest example leakage or failure to ground extraction in the input, but this run does not isolate whether the cause is model behavior, prompt/example interaction, or provider/library formatting. Since no case reached classification, this run provides no evidence about classifier accuracy, polarity handling after discovery, or downstream legal analysis.

The 0/40 assertion-probe result is diagnostic, not a population estimate and not the agreed 80% critical-error-free quality score. Expectations are candidate labels, not expert-approved gold. Eleven cases include candidate expected gaps, but the extraction output contract has no gap field, so gap detection is explicitly not evaluated. Legal sufficiency and truth of events are also outside the score.

## Next step

Inspect the captured discovery prompts and provider responses, then make a separately versioned pipeline change. Keep this run immutable as the baseline. After prompt/model compatibility review, rerun the same 40 inputs and compare structural pass, probe recall, and error categories; do not claim the 80% target until expert labels and expected-gap scoring are available.
