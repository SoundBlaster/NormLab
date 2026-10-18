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

Pending. This section was committed before dispatch; results will be appended
without rewriting the frozen protocol.
