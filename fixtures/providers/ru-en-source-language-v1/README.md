# Jev RU/EN source-language diagnostic v1

Task: [Issue68](https://github.com/SoundBlaster/NormLab/issues/68).
Related polarity failure: [Issue145](https://github.com/SoundBlaster/NormLab/issues/145),
[latest Jev prompt ablation](../../../docs/JEV_QUOTE_AUTHORITY_RETRY_2026-10-18.md).

## Question and fixed controls

Does rendering the same narrative in English change selected-claim verification?
This tests one coherent surface-language factor, with no assumed English advantage.
It does not measure general Russian ability, extraction quality or intrinsic model
ranking. All six model inputs contain one candidate each, one overall Choice,
original baseline instruction and unchanged criteria. No neighbouring candidates,
reference labels, translation rationale or shared chat history enter model input.

| Control | RU source                      | EN source                                    | Candidate stance | Expected label/policy |
| ------- | ------------------------------ | -------------------------------------------- | ---------------- | --------------------- |
| T01     | Я не оплатил парковку.         | I did not pay for parking.                   | asserted         | incompatible/reject   |
| T02     | Я не оплатил парковку.         | I did not pay for parking.                   | denied           | compatible/accept     |
| T03     | Не помню, оплатил ли парковку. | I don't remember whether I paid for parking. | unknown          | compatible/accept     |

T01 intentionally retains its typed polarity defect after translation; it must not
be repaired. T03 expresses uncertainty, not nonpayment or payment. Acceptance is
support of selected markup, not confirmation of a real-world fact. T04/ПП is excluded:
translation could alter or resolve its ambiguity.

## Exact factor and fidelity

RU tasks are byte-identical copies of the earlier frozen T01–T03. EN changes only:
sourceText, matching quote, quote end offset and grammaticalSubject Я→I.
Start remains0; offsets use Python Unicode code points, exclusive end. The quote
excludes the final period, as in RU. No punctuation normalization beyond translation.

The added grammaticalSubject surface translation corrects the earlier proposal's
incomplete list of dependent text fields: leaving Я in an English narrative would
introduce a lexical mismatch unrelated to the desired language comparison. It changes
no actor identity. Predicate, stance, mode, subject/aboutEntity, actor, claimant,
episode and scope are identical. All conventions, definitions, instructions, criteria,
config and caller policy remain unchanged. Different token counts are expected.

**EN remains a mixed-context task:** predicate definitions stay Russian. Therefore
this experiment can diagnose sensitivity to narrative rendering, not isolate all
Russian exposure or establish a universal language cause. A fully English context,
local polarity question, alternative primitive or new model would be separate factors.

[Translation review](translation-review.json) records exact JSON-pointer diffs and
bilingual self-review of polarity, uncertainty, attribution, actor, modality and scope.
The translator and reviewer are the same agent: this is not independent fidelity
review, independent human gold or adjudication of the broader Issue68 corpus.
Candidate expected labels stay in reviewer-only.json and outside provider requests.

T01/T02 share source family F01; T03 is F02. Six tasks represent three controls and
**two authored source families**, not six independent cases. RU/EN pairs share family
IDs and must not be counted as new independent observations or eligible holdout.

## Proposed execution; no authorization yet

Six fresh jobs in RU/EN, EN/RU, RU/EN order; with three pairs the first language is
balanced only as closely as possible. No earlier results are pooled into the fresh
RU baseline. Jev only, current native Choice wrapper and direct evaluate(), exact
pinned config/policy/runtime in plan.json. No new framework or runtime implementation.

Propose maximum8 total attempts:6 scheduled and at most2 protocol-only retries,
at most1 per job. Retry only recorded JevProtocolError with known HTTP200 and exactly
unchanged input. Stop globally on any other error/unknown, repeated failure, drift
or cap.30s operation timeout,300s series deadline, serial calls, no semantic retries,
repair/escalation or automatic resume. Preserve failed attempts and first/final
metrics separately; failures cannot disappear from planned denominators.

**Authorized live calls:0.** User authorized preparation only. Existing$4 reported
account ceiling and prior completed-run grants do not authorize this experiment.
Balance/prices remain unverified. Existing CLI caps only each invocation at1 call;
a later separately authorized run requires explicit aggregate accounting and stop
supervision committed before dispatch. No executor is added in this preparation.

## Measures and interpretation

Record all first/final labels, projected policy, native confidence/distribution,
model/request IDs, operation errors/unknowns, timing and known/unknown usage.
Compare T01 wrong acceptance and T02/T03 regressions individually, plus fixed-denominator
coverage/reference agreement. Report raw paired changes, not a general accuracy score.

An EN rescue supports a follow-up about source-language/translation sensitivity on
these controls; it cannot distinguish language from every lexical/tokenization effect.
No change weakens only the narrow narrative-rendering rescue hypothesis; Russian
definitions and other prompt/representation explanations remain. Failed calls are
operationally missing, not semantic disagreement. One observation per variant/control
cannot establish statistical significance, robustness, calibration or a model ranking.

## Prepared result and remaining work

preparation.json records actual SDK-free dry-runs, hashes, source slices and exact
field-delta checks. No provider calls, SDK-generated translations, new unit tests or
new runtime features are included. Broader Issue68 gates, independent fidelity review,
live authorization, execution and results remain outstanding.
