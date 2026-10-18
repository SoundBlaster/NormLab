# Current SDK: matched three-arm probe, 2026-10-18

Task: [#145](https://github.com/SoundBlaster/NormLab/issues/145).

## Frozen pre-dispatch protocol

User authorized preparation and execution after the SDK/integration stack merged.
This is one bounded compatibility/diagnostic probe, not a population accuracy
estimate, model ranking or causal ablation. The broader Jev investigation remains
open. No framework implementation changes are required.

- Executable source: `32d4a4eb418adb36131d156618742a003a4209fa`; adapter 0.8.0, Mellea 0.8.0,
  TypeSafe SDK 0.7.5, OpenAI 3.31.0, httpx2 2.13.1, Python 3.13.15.
- Exact input: `fixtures/providers/stage1-choice.json`, C002/R003; semantic task
  digest `dedfab0c194443cb8523dfb05e614918981f15e45c03cbd0cf8c8f3eb76373e8`.
  Every arm receives the same state, candidate, one overall Choice question and
  criteria. Expected answer is not included in that task.
- Source «Я не оплатил парковку.» denies payment; candidate stance=asserted,
  mode=actual, scope=actor-payment conflicts with it. Existing candidate
  reference is `incompatible`; this is not new independent human gold.
- Fixed order: Jev → Luna Decisions → ordinary Luna Responses Low. One fresh
  independent request per arm, no conversation state, repeats, retries or repair.
- Jev: `https://hub.coreinfra.ai/typesafe/api/v1/systemone`, requested
  `jev-1.13.0`; current native smoke runner.
- Decisions: `https://hub.coreinfra.ai/openai/api/v1/decisions`, requested
  `gpt-6-luna`; same current native smoke runner.
- Responses: `https://hub.coreinfra.ai/openai/api/v1/responses`, requested
  `gpt-6-luna`, reasoning low, max_output_tokens=1024, store=false, stream=false,
  truncation=disabled; released ResponsesChoiceProvider and categorical runner.
  Its wrapper differs from native/historical requests; semantic equality does
  not make serialization or provider behavior equivalent.
- Caps: at most **3 actual requests / 3 questions**, at most one per arm;
  per-arm timeout 30 seconds, outer process deadline 120 seconds. Stop the whole
  probe at the first failure, incomplete/protocol error or unknown outcome.
  Preserve the unexecuted suffix; do not restart automatically.
- The latest user-reported external key ceiling is $4. It is not independently
  checked or a predicted spend. Prices are not verified; native APIs expose no
  equal output-token cap here. Unknown USD cost/usage remains unknown. The
  monetary ceiling does not itself authorize more calls.
- Credential: existing COREINFRA_API_KEY in process environment, never written
  to protocol, command arguments or evidence. No credential lookup requests.
- Primary observations: completion/failure by arm, selected label and whether
  it equals the predeclared candidate reference. Preserve native distributions
  separately; Responses remains label-only. No invented probabilities/confidence.
- Operational evidence: actual request bodies, returned/requested models, request
  IDs, usage, HTTP status, errors and measured per-request latency. No latency
  ranking from one observation per arm in a fixed order. Report bodies are
  private during execution and published only after credential-value scanning.
- No full extraction/case-completeness score or critical-error-free rate follows.
  Agreement/disagreement can motivate a later controlled experiment with positive,
  negative and unknown controls; those are not silently added to this probe.

## Results

Protocol committed before inference at `2a89c8e4c091cdd800fa591401eb77d83cf65298`.
Execution completed on 2026-10-18: **3/3 requests, HTTP 200, no retries/failures**,
11.907 seconds wall time. Independent offline inspection matched each actual
wire request back to the same source/state, question and criterion descriptions;
provider-specific question IDs/serialization are different, as declared above.

| Arm / returned model                     | Selected label | Matches candidate reference | Request latency | Input / output tokens |
| ---------------------------------------- | -------------- | --------------------------- | --------------- | --------------------- |
| Jev / jev-1.13.0                         | compatible     | No                          | 2.031 s         | 1,872 / 43            |
| Luna Decisions / gpt-6-luna              | incompatible   | Yes                         | 3.556 s         | 1,089 / 0             |
| Ordinary Luna Responses Low / gpt-6-luna | incompatible   | Yes                         | 4.622 s         | 1,089 / 68            |

All usage values are provider-reported. Decisions' output count of zero is kept
as reported, not substituted with an estimate. Total known usage: **4,050 input /
111 output tokens**. Actual USD cost was not supplied; it remains unknown.
Individual latency excludes the driver's process startup overhead; these fixed-
order single observations do not establish relative model speed.

Native evidence is preserved without interpreting confidence as the selected
label's probability:

- Jev: confidence `0.82`; distribution compatible `0.88`, incompatible `0.11`,
  indeterminate `0.01`.
- Luna Decisions: confidence `0.34`; distribution compatible `0.43`, incompatible
  `0.56`, indeterminate `0.01`. A matching selected label is not a high-confidence
  automatic acceptance decision.
- Ordinary Responses: only `overall=incompatible`; no native probability or
  confidence fields exist. No calibration/threshold equivalence is claimed.

Request IDs:

- Jev: `req_01a14fbb533872b6ade5eeb7916d5da7`.
- Decisions: `req_286cdf674520454486b7bf2dbcc083d0`.
- Responses: `req_a75249aef8754cbdb62215978c4b433e`.

### Interpretation

This confirms live compatibility of the checked current SDK paths through
CoreInfra for this task. Jev's previous C002/R003 false acceptance was reproduced;
both Luna configurations selected the predeclared incompatible label on this
occasion. The failure is not explained by a different semantic task: actual
requests preserve the same source, typed candidate and definitions. This does
not isolate a cause or eliminate provider/prompt serialization effects.

The source quotation matches the source text while the typed candidate polarity
conflicts. Quote support masking the typed-polarity defect remains a hypothesis.
One selected label per model cannot distinguish understanding from a label bias;
there are no positive/unknown controls, repeats, blind human gold or complete
extraction outputs here. No population accuracy, critical-error-free rate or
ranking is calculated. #145's broader controls/causal acceptance remain open.

Next bounded scientific step: prepare compatible and indeterminate controls,
retaining the same task conventions, and freeze a small follow-up protocol.
Do not change prompts, add repetitions, or run those controls under this
already-exhausted three-call authorization.

### Evidence and verification

[Evidence ZIP](evidence/current-sdk-matched-2026-10-18.zip) contains the frozen
protocol, exact task, one-off execution driver, execution index, three current
runner reports, derived observations and a payload hash manifest. ZIP SHA256:
`c96dbce67638380807e61e8413ebcdb43d9c21d0c9b6459d26c41bb881f6450b`.
The manifest binds eight payload files; the manifest itself is protected by the
ZIP digest. Original report hashes are also bound by the execution index.
Reports preserve source-bearing actual requests and normalized SDK results;
raw HTTP response bodies/headers were not retained by this smoke runner.

Credential values were scanned out before publication. Frozen protocol/driver
hashes and all three semantic inputs were checked offline; a fresh archive
read with provider variables removed verifies file lengths/digests and report
bindings without inference. This is evidence for this probe, not a native
archive/scorer/MLflow run; those formats were not changed or exercised.
No new framework code, new unit tests, application build or deployment was run.
Repository CI/review for this documentation/evidence PR is separate.
