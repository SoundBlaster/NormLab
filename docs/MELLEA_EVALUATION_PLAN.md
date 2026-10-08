# Mellea validation/repair experiment

Approved by the user on 2026-10-07. This is an evaluation candidate, separate
from hosted inference, the UI review contract and Lean verification.

## Question and boundaries

Does a bounded validation/repair loop reduce critical extraction errors enough
to justify additional latency, provider calls and a Python worker?

The demo target remains 50% of cases without critical errors before human edits.
Passing a validator is a diagnostic, not this quality metric. Synthetic labels
are candidate expectations, not independent expert labels. No previous 50%/80%
claim or selected-probe score transfers to this candidate.

The source narrative is immutable. Repair changes the proposed annotation only.
Never require a desired factual outcome, such as asserted payment. Require
fidelity to the text, including negation, explicit uncertainty, opposing
speakers and unsupported predicates. Human confirmation remains mandatory.

## Phase 1 — controlled classification comparison

Freeze exactly the same discovery fragments, source digest, definitions,
classification prompt, generator/model and sampling settings for three arms:

| Arm | Validation | Maximum generation attempts |
| --- | --- | --- |
| `baseline` | Current deterministic classification contract, no repair | 1 |
| `deterministic` | Same contract, one repair with failure feedback | 2 |
| `jev` | Same contract plus Jev semantic fidelity check, one repair | 2 |

Use Mellea's same generation entry point in all three arms; check-only
requirements keep validation descriptions out of the initial prompt. This is a
new matched baseline, not an exact reproduction of historical v3 transport.
Run the existing v3 baseline separately as a reference. Replayed discovery
isolates classification and cannot measure full-pipeline discovery improvements.

Programmatic checks: exact source binding and unique quotes, fragment/attribute
contracts, complete classification decisions, known predicates and stances,
status/reason consistency and no duplicate predicate/stance. Attribution and
offsets come from frozen fragments; the model cannot edit them.

Jev checks whether the candidate annotations faithfully represent the supplied
fragments and definitions, preserving negation/unknown values and conflicts.
Include source evidence in the reference, but no expected labels. Verification
scores are not independent ground truth. Uncertainty, refusal and transport
failure never become acceptance; do not automatically retry provider errors.

## Phase 2 — full pipeline

After the classification comparison, evaluate discovery plus classification
with the same three arms. Add exact anchoring and semantic completeness
requirements. All failures remain in the denominator; an exhausted loop routes
to human review and never exposes an unvalidated fallback as an accepted result.

## Phase 3 — decision about hosted integration

Compare paired case outcomes and retain both successful and failed captures:

- Independent critical-error review: invented facts, lost negation/uncertainty,
  wrong speaker/subject/episode, lost contradictions and required omissions.
- Validator acceptance separately from selected semantic probes and independent
  case-level quality; report coverage and unreviewed labels explicitly.
- Repair rescue rate, regressions among first-pass successes, all error counts.
- Generation/verification attempts, end-to-end latency, measured token usage
  and cost where available; missing usage/cost must stay null, not zero.
- Paired differences and uncertainty intervals; choose sample size from a
  meaningful effect and independent labels before claiming significance.

Run all selected cases in all arms. Preserve source/parent/prompt digests,
dependency versions, raw candidates, per-attempt checks, repair feedback and
final acceptance. Use a new artifact directory per run. Never capture keys.

## Execution budget and ownership

- One initial generation plus at most one repair, concurrency one.
- At most one semantic verification per structurally valid candidate.
- A shared per-case deadline; no hidden SDK retries or provider fallback.
- The candidate's sampling deadline cancels asynchronous work; a synchronous
  verifier request already running in a thread can finish at its transport
  timeout. Use an outer process timeout for a strict wall-clock budget in corpus
  execution. No new attempt starts after cancellation.
- Start with offline Mellea/DummyBackend control-flow tests; real generator and
  real semantic verification remain distinct evidence levels.
- Existing 40 synthetic cases support diagnostics; independent labels/holdout
  are needed for the target quality conclusion.
- The user owns CoreInfra URL and Mellea-version updates in Jev4Mellea. NormLab
  does not edit that repository or reuse a mutable checkout as a release pin.
- No deployment or Python service in the hosted Compose image at this stage.

References: [Mellea requirements](https://docs.mellea.ai/concepts/requirements-system),
[Jev4Mellea](https://github.com/SoundBlaster/Jev4Mellea),
[existing evaluation plan](EVALUATION_PLAN.md).

## Research extension — 2026-10-09

The [extraction experiment roadmap](EXTRACTION_EXPERIMENT_ROADMAP.md) defines
controlled verifier/language comparisons, atomic requirements, segmentation and
statement representation experiments before selecting a pipeline. These are
hypotheses, not a commitment to LangExtract, syntax parsing or a provider.
The original matched Mellea arms and evidence boundaries remain applicable.
