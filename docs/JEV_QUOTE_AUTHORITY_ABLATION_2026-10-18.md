# Jev quote-authority ablation — 2026-10-18

Research: [#145](https://github.com/SoundBlaster/NormLab/issues/145).
[Protocol](../fixtures/providers/jev-quote-authority-v1/README.md),
[observations](evidence/jev-quote-authority-2026-10-18/observations.json),
[evidence ZIP](evidence/jev-quote-authority-2026-10-18/evidence.zip).

## Scope and actual execution

A is the unchanged baseline. B appends one generic paragraph: quote and offsets
anchor evidence; typed fields define the proposition being judged. State, source,
candidate values, criteria, policy, route and model are identical within pairs.
Both variants are fresh observations. This is a diagnostic prompt ablation, not
an extraction evaluation, a new pipeline default or a model ranking.

- Inputs, authorization and one-off supervisor frozen before dispatch:
  `265a1bb0592a9bd76b78270da24d2b90caceaf0f`.
- Plan SHA256: `649073d44d8fb2ab715e590ce9fd09c0ce53277dd4d65c425a9b21a67966dde5`.
- Executable evaluation source unchanged from merged
  `9f296a277512e00fe91b4c318bf9437c86fda4cf`.
- Runtime: Python3.13.15 / mellea-jev-adapter0.9.0 / Mellea0.8.0 /
  TypeSafe0.7.5 / OpenAI3.31.0 / httpx2 2.13.1.
- Route: `https://hub.coreinfra.ai/typesafe/api/v1/systemone`.
  Requested and successfully returned model: `jev-1.13.0`.
- Direct `CategoricalRequirement.evaluate()`, explicit caller label policy;
  compatible→accept, incompatible→reject, indeterminate→review.
- User authorized up to8 calls, no retries/repair/escalation; serial AB/BA/AB/BA,
  30s operation timeout,300s outer deadline, global stop on first error/unknown.
  User-confirmed external account ceiling$4 is not a verified balance or cost.

Execution **2026-10-18T20:43:09.930221+00:00–2026-10-18T20:43:18.193816+00:00**, **8.253551s**:
**4 actual requests /8 planned, all4 HTTP200;3 completed,1 protocol failure**.
**4 jobs not executed**, no retry or automatic continuation. No timeout or unknown
transport receipt; the failed request has an unknown semantic result and usage.
The stopped series is terminal. Unsent allowance is not automatically reused.

## Expected and observed

References are candidate annotations with prior guided nonblind user confirmation,
not independent whole-task human gold. Four controls have three distinct source
texts; one observation per variant/control was planned. No pooled prior baseline.

| Control and expected outcome                                                    | A: baseline                                       | B: added instruction  |
| ------------------------------------------------------------------------------- | ------------------------------------------------- | --------------------- |
| T01: source denies payment; typed candidate asserts actual payment. **Reject**. | **Accept — mismatch**                             | **Accept — mismatch** |
| T02: correct denial. **Accept**.                                                | **Protocol failure**, semantic answer unavailable | Accept                |
| T03: correctly represented explicit unknown. **Accept**.                        | Not executed                                      | Not executed          |
| T04: ambiguous parking placement under ПП. **Review**.                          | Not executed                                      | Not executed          |

T01 is the **only complete pair**. The added paragraph did not change its incorrect
acceptance in this observation. T02B retained the correct answer, but its baseline
failed; T03/T04 have no observations. Consequently full regression/ambiguity and
quality-improvement assessment is **incomplete/inconclusive**. The result does not
prove that quote masking is irrelevant, that the model cannot solve this task,
or that more observations would have the same outcome.

## Response characteristics

Native confidence and category probability are separate provider fields. Neither
is an accuracy guarantee or a calibrated probability of correctness. The bridge
uses the explicit label mapping and leaves decision score null; no confidence gate
was added after observing results.

| Job | Control/variant | Expected     | Native label | Confidence  | P(compatible / incompatible / indeterminate) | Policy              |
| --- | --------------- | ------------ | ------------ | ----------- | -------------------------------------------- | ------------------- |
| J01 | T01A            | incompatible | compatible   | 0.80        | 0.87 /0.12 /0.01                             | accept              |
| J02 | T01B            | incompatible | compatible   | 0.74        | 0.83 /0.15 /0.02                             | accept              |
| J03 | T02B            | compatible   | compatible   | 0.85        | 0.90 /0.08 /0.02                             | accept              |
| J04 | T02A            | compatible   | unavailable  | unavailable | unavailable                                  | operational failure |

Request IDs, native distributions, returned model, timing and known usage are in
observations.json and original reports. Completed calls report **5825 input /
129 output tokens**. J04 usage and total USD cost are unknown; completed-only
usage is not the whole-series bill. Raw HTTP response bodies and headers are not
retained by the existing runner. Its normalized native evidence is retained for
completed responses; actual request bodies and HTTP statuses are retained for all4.

J04 reports `JevProtocolError` with no normalized answer. HTTP200 only establishes
receipt of a response, not protocol validity. The saved runner report does not
retain the error message or response bytes, so it cannot distinguish malformed
provider content, gateway content or strict SDK validation. Do not call this a
network outage, provider root cause or semantic wrong answer. No live retry was
used to investigate it.

## Validation and next step

Preparation:8 SDK-free CLI dry runs with empty child environment and sockets denied;
byte-identical A copies, instruction-only B delta, unchanged state/criteria/policy,
all input hashes/digests and syntax checked. Static Ruff/format/Prettier checks.
The supervisor stopped globally on J04 exactly as planned. Offline archive binding
and credential checks are recorded in verification.json alongside the archive.
No new unit tests, full suite, framework extension, deployment or merge.

Next: review this partial evidence and the adapter's existing protocol-error
boundary offline, then choose one narrow follow-up factor or approve a separate
continuation. Do not broaden the live series or tune a confidence threshold from
these three responses. Issue145 remains open; incomplete controls and missing raw
response evidence prevent closing its broader causal-study acceptance.
