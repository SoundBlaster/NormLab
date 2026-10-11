# Stage 1: sealed candidate-label scoring

The scorer is separate from planning and provider execution. It imports no SDKs,
looks up no credentials and performs no network calls. It replays the complete
capture before creating a prediction seal. Scoring requires that seal, verifies
the capture binding again, then opens the dataset's pinned reviewer-only file.
Historical source manifests, labels and executor pins are unchanged.

```bash
python3 -B -S evaluation/score_stage1_providers.py \
  fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json \
  .artifacts/your-capture --seal-output .artifacts/your-seal.json

python3 -B -S evaluation/score_stage1_providers.py \
  fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json \
  .artifacts/your-capture --seal .artifacts/your-seal.json \
  --output .artifacts/your-score.json
```

Use `--profile corpus` in both commands for corpus captures. Output paths must be
new. The seal binds plan, capture index and ordered turn hashes. Reports bind
seal, capture, labels and scorer hashes. Replay checks the pinned executor code
and all actual requests/results. This is local integrity evidence, not a signature,
trusted timestamp or proof that the operator never saw labels earlier. Files are
checked again after scoring; bundles are expected to be locally trusted.

## Metrics and denominators

- Per arm: all planned turns, completed turns, statuses, candidate matches,
  agreement among completed answers, and matches divided by all planned turns.
  Failed, unknown-sent and unused turns remain visible in the denominator; they
  are not silently dropped or described as semantic misclassifications.
- Confusion matrix uses completed answers only, with expected labels as rows.
  `indeterminate` is an ordinary predicted class, not a transport failure.
- Per case: completion of every planned candidate/repeat and agreement of every
  planned verdict. These strict metrics penalize an unfinished run; they do not
  estimate extraction accuracy or the product's critical-error-free rate.
- Repeat variation counts records with two or more distinct completed labels.
  Incomplete repeat coverage is reported separately; zero variation does not
  establish stability when only one or no answer was observed.
- Pairwise tables compare the same case/record/repeat only when both arms
  completed. They also show the full planned pair denominator. No significance
  tests or confidence intervals treat repeats as independent observations.

The 16 authored synthetic cases are diagnostic development data, without a held-out
sample. Labels are **candidate-not-independent**, not expert ground truth. A report
can describe agreement with this annotation; it cannot establish general accuracy,
the 50% demo target, the original 80% target, or legal correctness. Population
accuracy, statistical significance and critical-error-free rate remain null.
Mock captures are explicitly marked `mock-http`; their comparisons only rehearse
the scorer and have no model-quality interpretation.

## Local execution evidence — 2026-10-11

SDK-free CLI rehearsals scored existing full pilot/corpus mock captures and partial
zero-cap/interrupted captures. A seal from a different capture was rejected. These
are local CLI checks, not an added automatic CI suite. No provider calls were made
by the scorer. A separate [live compatibility report](STAGE1_LIVE_PILOT_2026-10-11.md)
records the three authorized inference dispatches and their incomplete result.

Next: collect more matched live contexts after diagnosing the transport failure
and confirming spending capacity. Preserve this first attempt in reliability
accounting; a new attempt gets a new capture and seal.
