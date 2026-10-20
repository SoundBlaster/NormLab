# Fresh Jev quote-authority rerun with protocol retries — 2026-10-18

Research [#145](https://github.com/SoundBlaster/NormLab/issues/145), PR156.
[Protocol](evidence/jev-quote-authority-retry-2026-10-18/README.md),
[observations](evidence/jev-quote-authority-retry-2026-10-18/observations.json),
[evidence ZIP](evidence/jev-quote-authority-retry-2026-10-18/evidence.zip).
The [earlier partial series](JEV_QUOTE_AUTHORITY_ABLATION_2026-10-18.md) remains
unchanged and is not pooled into this fresh comparison.

## Frozen scope

User explicitly approved eight fresh planned jobs and at most four protocol-only
retries, **12 maximum attempts**, external account ceiling **$4**. At most one
retry per job, only on JevProtocolError with known HTTP200. Other failures/unknowns,
drift or a second failure of the same job stop globally. No semantic retries,
repair, escalation, threshold tuning or automatic resume.30s operation timeout,
300s series deadline. Balance/prices not independently verified.

A is unchanged baseline; B only appends the same generic quote-anchor versus typed
proposition instruction as before. No new prompt factor. All source/state/criteria,
policy, route, model, runtime and AB/BA/AB/BA order match the prior frozen plan.
Expected labels remain candidate, with guided nonblind user semantic confirmation;
not independent whole-task gold. Four controls contain three distinct source texts.

- Before-dispatch freeze: `46372297758ab766ec668b3ecc860e01af5551fe`.
- Plan SHA256: `e7898abbfb387e15e99474ffc9a0ec0a59f6bcba375a1c581f0d57b6152382bf`.
- Runtime evaluation code unchanged from merged
  `9f296a277512e00fe91b4c318bf9437c86fda4cf`.
- Python3.13.15, Jev4Mellea0.9.0, Mellea0.8.0, TypeSafe0.7.5,
  OpenAI3.31.0, httpx2 2.13.1.
- Endpoint `https://hub.coreinfra.ai/typesafe/api/v1/systemone`, requested and
  successfully returned model `jev-1.13.0`; direct categorical evaluate().

## Execution and paired result

**2026-10-18T20:55:07.764319+00:00–2026-10-18T20:55:25.075448+00:00, 17.310907s**.
**9 actual attempts, all HTTP200;8 valid responses,1 protocol failure**.
All8 planned jobs completed, using1 authorized retry. No timeout, unknown transport
receipt, final failed/unexecuted jobs or further inference.3 allowed attempts remain
unspent and are not automatically reused.

J04/T02A failed on attempt1 with JevProtocolError and no semantic result/usage.
Its immediate unchanged-input attempt2 returned compatible/accept. The failure
remains in observations and the original report, and is not treated as a semantic
answer. The earlier separate run also failed first on T02A; this repeated location
is descriptive evidence, not a diagnosis of the provider or SDK.

Final outcomes / native confidence:

| Control                             | Expected policy | A baseline   | B extra instruction |
| ----------------------------------- | --------------- | ------------ | ------------------- |
| T01: wrong actual-payment assertion | **reject**      | accept /0.80 | accept /0.69        |
| T02: correct denial                 | **accept**      | accept /0.89 | accept /0.86        |
| T03: correct explicit unknown       | **accept**      | accept /0.62 | accept /0.62        |
| T04: ambiguous parking placement    | **review**      | accept /0.52 | accept /0.28        |

compatible→accept, incompatible→reject, indeterminate→review. Accept concerns the
support of selected markup, not payment truth or legal liability. T01 should reject
because typed stance asserts actual payment despite source denial. T02's denial and
T03's unknown preserve source meaning. T04 should review the unresolved ПП meaning
for parking-specific placement while retaining the notice as claimant.

| Measure, fixed planned denominator per variant | A   | B   |
| ---------------------------------------------- | --- | --- |
| First-attempt valid replies                    | 3/4 | 4/4 |
| First-attempt candidate agreement              | 1/4 | 2/4 |
| Final valid replies                            | 4/4 | 4/4 |
| Final candidate agreement                      | 2/4 | 2/4 |
| Wrong acceptance on T01                        | 1/1 | 1/1 |
| False rejection on T02/T03                     | 0/2 | 0/2 |
| Determinate decision on ambiguous T04          | 1/1 | 1/1 |

The first-attempt difference includes the operational failure and is not semantic
superiority of B. **Final labels changed in0/4 pairs.** The instruction did not
rescue T01 or T04 in this run; T02/T03 retained correct labels. The proposed wording
is therefore not supported as a sufficient fix on these controls. This does not
exclude quote masking, prove universal inability, establish statistical significance,
measure extraction quality or rank models. One observed pair per control and the
retry-dependent T02A final observation limit inference.

## Native evidence and operational boundary

T01 native confidence A0.80/B0.69; Pcompatible A0.87/B0.79.
T04 native confidence A0.52/B0.28; Pcompatible A0.68/B0.52.
These shifts did not change labels. Native confidence is distinct from category
probability and is not a calibrated accuracy guarantee. The frozen caller policy
uses label mapping only, decision score remains null. No posthoc gate was added.

Known successful-response usage: **15750 input /344 output tokens**.
Failed-attempt usage and total USD cost remain unknown; these totals are not the
whole bill. All request IDs, native distributions, first/final outcomes and timing
are in observations.json and original reports.

The current CLI preserves actual request bodies and HTTP status, but not raw HTTP
response bytes or the protocol-error message. Adapter0.9.0 can raise JevProtocolError
on SDK response-schema validation or later answer-field validation. Without those
bytes, this saved failure cannot distinguish provider/gateway payload from SDK
validation. HTTP200 establishes a response, not protocol validity or root cause.

## Validation and next step

Eight SDK-free dry runs, original task/config/policy/runtime equality, all referenced
artifact hashes and syntax passed before dispatch. Static Ruff/format and Prettier
passed. Evidence includes every attempt and all original HTTP reports. Archive
hash/length, wire/task/config/policy, first/final score and retry-cap verification
are recorded in verification.json after fresh extraction with credentials absent
and sockets denied. Credential-value scan precedes publication.

No new unit tests/full local suite, framework feature, model defaults, deployment
or merge. Issue145 remains open. Next: review protocol-error observability offline
and then prepare a single simpler local polarity question as a separate frozen
factor, preserving this comparison as the baseline. Do not spend remaining allowance
on ad hoc retries or extend infrastructure work before choosing that experiment.
