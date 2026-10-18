# Jev RU/EN source-language comparison — 2026-10-19 MSK

Research [#68](https://github.com/SoundBlaster/NormLab/issues/68), related
[#145](https://github.com/SoundBlaster/NormLab/issues/145), PR157.
[Prepared protocol](../fixtures/providers/ru-en-source-language-v1/README.md),
[observations](evidence/ru-en-source-language-2026-10-19/observations.json),
[evidence ZIP](evidence/ru-en-source-language-2026-10-19/evidence.zip).

## Frozen scope and authorization

User confirmed both displayed translations and explicitly authorized6 main calls
plus at most2 protocol-only retries, maximum8 attempts; external account ceiling$4
still applies. One retry maximum per job, only knownHTTP200 JevProtocolError;
stop any other error/unknown, repeated failure or drift.30s operation/300s series,
serial fresh RU/EN, EN/RU, RU/EN order. No semantic retries, repair, escalation,
confidence tuning or automatic reuse of unused allowance. Balance/prices not verified.

- Packet prepared at `a35978038cccd2c0977e4f330350a702c5031fa8`.
- Input/authorization/one-off supervisor frozen before dispatch at
  `65ea6d34e7e3a730cb032efa7e4678252e745bea`.
- Execution plan SHA256: `4cd992c3677f4ad8c17e6a71feef0cc181a1b87b756aa5dbdc16134cc2c4593a`.
- Evaluation runtime unchanged from merged
  `9f296a277512e00fe91b4c318bf9437c86fda4cf`.
- Python3.13.15 / Jev4Mellea0.9.0 / Mellea0.8.0 / TypeSafe0.7.5 /
  OpenAI3.31.0 / httpx2 2.13.1.
- Route `https://hub.coreinfra.ai/typesafe/api/v1/systemone`; requested and
  returned model `jev-1.13.0`; direct categorical evaluate(), frozen label policy.

RU tasks exactly copy prior T01/T02/T03. EN changes only sourceText, matching quote,
quote end offset and grammaticalSubject Я→I. Typed candidate semantics, all remaining
state/conventions/definitions, instruction, criteria, model/config/policy unchanged.
No reviewer labels or translation rationale were sent. Each request has one candidate
and no shared conversation history. Prior RU observations are not pooled as baseline.

Human confirmation covers displayed translation equivalence in a nonblind project
conversation; it is not independent whole-task gold or corpus adjudication. References
remain candidate. Three controls share two authored source families, not six independent
cases. T04/ПП excluded because translation could alter ambiguity. English tasks still
contain Russian predicate definitions; the factor is source-language rendering.

## Actual execution

**2026-10-19 00:21:27–00:21:39 MSK**, corresponding to
2026-10-18T21:21:27.824654+00:00–2026-10-18T21:21:39.885721+00:00 UTC; **12.060772s**.
All **6/6 jobs completed on first attempt,6 HTTP200 responses**. No failures,
unknown outcomes, unexecuted jobs or retries.6 of8 maximum attempts used;
2 remain unspent, with no further calls or automatic reuse.

## Expected and observed

compatible→accept, incompatible→reject, indeterminate→review. This policy concerns
support of selected markup, not payment truth or legal liability.

| Control                                        | RU source                      | EN source                                    | Expected   | RU actual             | EN actual             |
| ---------------------------------------------- | ------------------------------ | -------------------------------------------- | ---------- | --------------------- | --------------------- |
| T01, typed asserted payment contradicts source | Я не оплатил парковку.         | I did not pay for parking.                   | **reject** | **accept — mismatch** | **accept — mismatch** |
| T02, typed denied payment matches source       | Я не оплатил парковку.         | I did not pay for parking.                   | accept     | accept                | accept                |
| T03, explicit unknown correctly represented    | Не помню, оплатил ли парковку. | I don't remember whether I paid for parking. | accept     | accept                | accept                |

| Descriptive measure                                  | RU  | EN  |
| ---------------------------------------------------- | --- | --- |
| First/final valid replies, fixed planned denominator | 3/3 | 3/3 |
| First/final candidate-reference agreement            | 2/3 | 2/3 |
| Wrong acceptance on T01                              | 1/1 | 1/1 |
| False rejection on T02/T03                           | 0/2 | 0/2 |
| Unnecessary review on T02/T03                        | 0/2 | 0/2 |

Final labels differ in **0/3 pairs**. A switch to these English narratives was
**not sufficient to correct T01 in this run**. T02/T03 labels were preserved. This
weakens the narrow source-translation rescue hypothesis for this context; it does
not prove that Russian has no effect, that Jev understands every denial, or that
language is irrelevant across tasks. Russian definitions remain, translation changes
lexical/tokenization details, order is not perfectly balanced with three pairs and
there is one observation per variant/control. No significance, robustness, general
accuracy, calibration, extraction-quality or model-ranking claim follows.

## Response characteristics

| Control                    | RU native confidence | EN native confidence | RU Pcompatible | EN Pcompatible |
| -------------------------- | -------------------- | -------------------- | -------------- | -------------- |
| T01, expected incompatible | 0.80                 | 0.85                 | 0.87           | 0.90           |
| T02, expected compatible   | 0.91                 | 0.91                 | 0.94           | 0.94           |
| T03, expected compatible   | 0.62                 | 0.64                 | 0.75           | 0.76           |

EN T01 was still incorrectly accepted with higher reported native confidence in
this observation. Native confidence and category probability are distinct fields,
not calibrated probabilities of correctness. The caller policy maps labels only,
with null decision score; no gate was tuned after seeing results. All distributions,
model/request IDs, timing and report hashes are preserved in observations.json.

All6 valid responses report usage: **11178 input /258 output tokens**.
USD cost is not reported. The$4 account ceiling is not the experiment cost. Existing
CLI records request bodies/status and normalized native evidence, not raw HTTP
response bytes/headers. No error happened here to investigate or retry.

## Validation and next step

Before dispatch:6 SDK-free dry-runs; unchanged prepared tasks/config/policy/runtime,
all referenced artifact/authority hashes and syntax checked. Supervisor reserved
before dispatch and checked exact wire requests, task/policy binding, stable returned
model and retry/attempt caps. Evidence archive includes every attempt and report.
Fresh offline archive extraction, hashes/lengths, native/result/policy/reference joins,
paired scores, first/final and usage verification are recorded in verification.json.
Credential scan precedes publication. Static Ruff/format/Prettier/whitespace checks.
No new unit tests/full local suite, framework/runtime default changes, deployment or merge.

Next proposed factor: one local payment-polarity question, separating source stance
recognition from the overall typed-candidate verification task; coordinate with #67
and #145. Freeze its changed semantics and controls before any separately authorized
inference. This experiment completes the narrow prepared comparison, not broader
Issue68 reference review, full-English context or Noul/boolean/cross-provider study.
