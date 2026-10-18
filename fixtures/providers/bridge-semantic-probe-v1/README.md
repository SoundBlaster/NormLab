# Direct-evaluate semantic controls v1

Prepared protocol for [research #145](https://github.com/SoundBlaster/NormLab/issues/145).
**No live requests authorized or executed.** Uses the merged Jev4Mellea 0.9.0
integration at `9f296a277512e00fe91b4c318bf9437c86fda4cf`.
The reviewed packet commit supplies the new data; its executable runtime must
still match that base. Later runtime/dependency changes require a new protocol
revision, not an implicit switch to the newest main.

## Question

Can the current three provider paths distinguish a known typed-polarity defect,
a supported denial, a correctly represented explicit unknown, and ambiguity
inside a selected claim, while preserving the direct bridge's result/policy/error
boundaries? This is a small development diagnostic, not a model ranking,
population accuracy estimate, calibration study or proof of the earlier failure's cause.

The earlier one-case probe is [PR #152](https://github.com/SoundBlaster/NormLab/pull/152)
at `8f849cfb43e21baef75a2b003f12ace5a7ac7b86`. It used adapter 0.8.0. Its observations
are historical and will not be pooled with these fresh calls or treated as a
paired causal test of an SDK change. Its three-call grant is exhausted.

## Inputs and expected interpretation

All labels below are **candidate references, not independent human gold**.
The four tasks contain **three distinct source texts**, not four independent cases.
All are previously exposed diagnostic development materials; holdout eligibility is zero.

| Task | Source and selected candidate meaning                                                                                                              | Expected label | Policy outcome |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- | -------------- |
| T01  | «Я не оплатил парковку.»; candidate says actual payment **asserted**                                                                               | incompatible   | reject         |
| T02  | Same source/quote; candidate says actual payment **denied**                                                                                        | compatible     | accept         |
| T03  | «Не помню, оплатил ли парковку.»; candidate stance is **unknown**                                                                                  | compatible     | accept         |
| T04  | «В постановлении: “ТС стояло в зоне ПП; оплаты нет”.»; candidate claims parking-specific **placement**, plus the notice's supported payment denial | indeterminate  | review         |

- **T01** is a byte-for-byte copy of `fixtures/providers/stage1-choice.json`,
  C002/R003. Its semantic digest remains
  `dedfab0c194443cb8523dfb05e614918981f15e45c03cbd0cf8c8f3eb76373e8`.
- **T02** uses existing C002/R004. Relative to T01, only A01.stance changes
  from asserted to denied; source, quote, offsets, question and conventions stay identical.
- **T03** uses existing C003/R005. Accepting a correct description of uncertainty
  does not assert payment or nonpayment. Returning indeterminate here would
  confuse uncertainty in the source with uncertainty about candidate support.
- **T04** derives from v2 C016/R032 by changing only A01.predicate from raw
  `standing` to parking-specific `placement`. The original **v2 R032 is compatible**
  and is not relabelled. “ПП” remains unresolved inside the selected location claim:
  a parking reading supports placement; another zone reading does not. Payment's
  denied stance, notice claimant and episode scope remain unchanged and supported.
  Historical [IR-004](../../parking-pilot/stage1-independent-review/report.md)
  supports this ambiguity rationale, but reviewed a different v1 task. T04 is a
  new derived candidate, not an exact replay or newly independently reviewed label.

### User semantic confirmation — 2026-10-18

In a guided discussion with the expected interpretations visible, the user confirmed:

- T03: correctly representing explicit uncertainty is compatible/accept; payment
  itself stays unknown and still needs human confirmation.
- T04: the candidate expansion is paid parking, but the abbreviation might mean
  **pedestrian crossing**. Ask: «Что означает “ПП” в этом постановлении: платную
  парковку или пешеходный переход?» Parking-specific placement remains
  indeterminate/review until clarified. The source abbreviation is still unresolved.
- «В постановлении: оплаты нет» is an **attributed statement** by the notice.
  Preserve `claimant=notice_1`; confirming markup does not establish nonpayment.

These confirmations are recorded in `reviewer-only.json`; they do not change the
four model inputs, category references, policy or budget. The extra abbreviation
explanations and clarification question are not added to model prompts. This is
nonblind semantic-policy review, not independent whole-task human gold or
authorization to run inference. T01/T02 received no new whole-task human review.
The earlier packet is preserved at commit `2c8e438`; updated reference/plan hashes
and their previous binding are explicit in `preparation.json`.

If an interpretation is subsequently disputed, record adjudication and publish
a new protocol revision or omit it under a newly declared schedule **before**
observing model outputs. Do not change labels afterwards to fit answers. No silent
substitution with C003/R006: that existing wrong-stance candidate is labelled
incompatible, not indeterminate.

## What is fixed

`tasks/` contains model inputs only: the original Russian source, typed candidate,
safe conventions, predicate definitions and unchanged overall Choice question.
Every source/claim quote has code-point offsets into the original text. No summaries,
paraphrases, translation, reconstructed source, missing-fact repair or follow-up chat.

Expected labels, interpretations and provenance are in `reviewer-only.json`.
They are never passed as CLI input, state or prompt. Task IDs and scheduling
metadata stay outside provider input. `policy.json` is the explicit caller mapping
compatible → accept, incompatible → reject, indeterminate → review; it also stays
outside model input. Native evidence is not used as a routing threshold.

All three paths use direct `CategoricalRequirement.evaluate()` and independent
one-question calls. No Mellea sampling, repeats, retries, judge, batch, repair or
escalation. The resulting policy outcome concerns acceptance of the proposed
claim, not liability, a fine or whether the source describes real-world truth.

## Provider paths and budgets

Public configurations in `configs/` freeze:

| Arm                 | Requested model | Full endpoint                                        |
| ------------------- | --------------- | ---------------------------------------------------- |
| CoreInfra Jev       | jev-1.13.0      | `https://hub.coreinfra.ai/typesafe/api/v1/systemone` |
| CoreInfra Decisions | gpt-6-luna      | `https://hub.coreinfra.ai/openai/api/v1/decisions`   |
| CoreInfra Responses | gpt-6-luna      | `https://hub.coreinfra.ai/openai/api/v1/responses`   |

Responses uses reasoning low, max_output_tokens=1024; the released provider sends
store=false, stream=false and truncation=disabled. Native paths expose no matching
generation token cap here. Same semantic input is not identical serialization or
an equal token/compute budget. Confidence scales are not assumed comparable.

`plan.json` pins the files, semantic digests, runtime and exact 12-job order:
one fresh request for each of 4 tasks × 3 arms. Each arm makes at most 4 calls;
each CLI invocation has `--max-calls 1`. The first three task blocks rotate arm
order; the fourth uses Jev → Responses → Decisions. This is only partially position
balanced and gives no latency ranking or randomized inference.

- Planned maximum: **12 actual HTTP requests / 12 questions**, serially.
- **Authorized requests: 0.** Preparation is not authorization to append `--live`.
- Per-operation timeout: 30 seconds. Proposed whole-series deadline: 420 seconds,
  including process startup, reserving before dispatch. No automatic restart.
- Stop the **whole series** on its first operational/protocol/incomplete error,
  unknown sent outcome, deadline, task/policy drift or model revision change
  within an arm; preserve the not-executed suffix. Semantic disagreement alone
  does not stop the series and must not cause prompt editing or extra calls.
  Compare available non-null returned model names within an arm; missing model
  metadata stays unknown and cannot attest a stable model revision.
- Last user-reported external account ceiling: $4. It is not a fresh experiment
  authorization, independently checked balance, predicted charge or pricing cap.
  Prices are unverified; unavailable USD/usage stays null. Confirm the authorized
  scope and applicable spending protection before any dispatch.
- `COREINFRA_API_KEY` is the only selected credential source. No key lookup or
  key value belongs in this packet, CLI arguments, configs, source or evidence.

**The existing CLI enforces the per-invocation cap, not the whole 12-job schedule
or 420-second outer deadline.** Before an authorized execution, the operator's
single bounded orchestration must count/reserve across jobs, enforce the outer
deadline, inspect each report and stop the entire series when required. This
packet is a frozen preparation artifact, not a new executor or execution permit.

## Reproduce dry-runs without inference

Use Python **3.11+**, preferably the pinned 3.13.15. SDK-free does not mean an older
system Python supports the source syntax. From the repository root:

```bash
"$PROBE_PY" -B -S evaluation/categorical_smoke.py \
  fixtures/providers/bridge-semantic-probe-v1/tasks/T01.json \
  --config fixtures/providers/bridge-semantic-probe-v1/configs/coreinfra-jev.json \
  --policy fixtures/providers/bridge-semantic-probe-v1/policy.json \
  --max-calls 1 --tactic independent
```

`$PROBE_PY` is the chosen interpreter, not a credential. Every job's `argv` in
`plan.json` provides an equivalent **dry-run** invocation; none contains `--live`.
Dry-run reads no credential, imports no SDK/Mellea, creates no capture and sends
no requests. It should return the frozen task digest/config/policy and plannedCalls=1,
calls=0. A successful dry-run does not satisfy live/reference-review authorization.

## Observations and decision rules

After a separately authorized execution, preserve a row for **every planned job**:
task/arm, expected and actual label, expected and actual policy outcome, completion
or error, requested/returned model, request ID, actual wire task match, usage,
latency, native confidence and selected-label probability when actually supplied.
Responses has neither native confidence nor a synthesized distribution; this
policy's decision.score remains null for all three arms. Missing evidence stays missing.

Report descriptive counts with explicit denominators:

1. Completed/failed/unknown/not-executed out of 12, with at most 4 completed per arm.
2. Candidate-reference agreement as count out of 4 per arm, alongside all four rows.
   Do not call it case accuracy; always disclose failures/not-executed separately.
3. False acceptance on T01 if its incompatible candidate is accepted (one opportunity
   per arm). False rejection on T02/T03 if their compatible candidates are rejected
   (two opportunities per arm).
4. Unnecessary review on T01/T02/T03 if indeterminate is returned (three determined
   candidate references per arm). Overdetermination on T04 if a definite label
   replaces the predeclared ambiguous reference (one opportunity per arm).
5. Quote-matching polarity sensitivity for **T01 vs T02**: incompatible/compatible
   is the intended contrast. Compatible/compatible is consistent with insensitivity
   or acceptance bias, but cannot prove that quote support caused the failure.
6. Explicit-unknown vs ambiguity **T03 vs T04**: compatible/indeterminate is the
   intended distinction. These different texts/claims do not isolate one causal factor.
7. Native confidence/probability, token usage, unknown costs and latency are
   observations only. Do not tune thresholds or select a winning model from them.

If all four controls match, conclude “these controls passed on this occasion”.
If T01 fails while T02 succeeds, report the polarity contrast's failure and retain
the unchanged payload. If T03/T04 expose a disputed reference, keep predictions
sealed and the comparison inconclusive pending adjudication. Operational failures
make the intended series incomplete; they are not semantic rejection or abstention.
No critical-error-free pipeline rate, extraction completeness, legal correctness,
population confidence interval or escalation benefit follows from this probe.

## Preparation evidence

Record bindings and dry-run checks in `preparation.json`. No provider response
has been produced. The packet reuses existing runtime code and current CLI;
it does not reopen the completed evaluation framework infrastructure phase.
