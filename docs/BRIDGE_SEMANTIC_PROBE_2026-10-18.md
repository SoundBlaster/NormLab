# Direct-evaluate semantic probe: four controls, 2026-10-18

Research task: [#145](https://github.com/SoundBlaster/NormLab/issues/145).
[Prepared protocol](../fixtures/providers/bridge-semantic-probe-v1/README.md),
[all observations](evidence/bridge-semantic-controls-2026-10-18/observations.json),
[evidence ZIP](evidence/bridge-semantic-controls-2026-10-18/evidence.zip).

## Scope and execution

The user explicitly authorized at most **12 requests**, no retries, a 420-second
series deadline, and reconfirmed the external CoreInfra account ceiling of $4.
The ceiling/balance and provider prices were not independently checked. It is
not the reported cost of this experiment.

- Prepared packet: `9b1d379db501593481a2abde556da93d7b0d7512`.
- Plan SHA256: `9f26b0ffa80aa0910a860b32c17d52c7fbd8b75074faa2e051aaec1db6b9f84d`.
- Runtime source: merged `9f296a277512e00fe91b4c318bf9437c86fda4cf`.
- One-off supervision/authorization committed **before dispatch** at
  `22eb41eda59123ff7e464a9991d8902c3e825178`.
- Actual Python 3.13.15 / Jev4Mellea 0.9.0 / Mellea 0.8.0 / TypeSafe 0.7.5 /
  OpenAI 3.31.0 / httpx2 2.13.1. No executable evaluation source changed from
  the pinned runtime; the one-off supervisor calls its existing categorical CLI.
- Every request uses direct `CategoricalRequirement.evaluate()`, identical
  per-task source/state/question/criteria across the three arms and the frozen
  caller policy. Reviewer explanations/expected labels stay outside model input.
- CoreInfra paths: Jev `typesafe/api/v1/systemone`, Decisions
  `openai/api/v1/decisions`, ordinary Responses `openai/api/v1/responses`.
  Requested models: `jev-1.13.0`, `gpt-6-luna`, `gpt-6-luna` respectively.
  Responses reasoning low, max_output_tokens=1024, store=false, stream=false,
  truncation=disabled. Native APIs have no equivalent output cap here.

Execution: **20:12:27–20:13:05 UTC, 38.55012 seconds**. All **12/12 requests
completed with HTTP 200**, no failures, unknown outcomes, unexecuted jobs, retries,
repair, batch or escalation. All reservations and actual requests were counted;
the 12-call authorization is exhausted. No further inference was dispatched.

The pre-dispatch plan remains a historical preparation artifact with zero
authorized calls. The separate committed authorization receipt records the
fresh grant; the execution index records its use. These are separate states.

## Expected versus actual outcomes

Category labels project through the caller policy: compatible → **accept**,
incompatible → **reject**, indeterminate → **review**. Accept concerns markup
support, not legal liability or a confirmed fact in the real world.

| Control and expected outcome                                                                                                          | Jev 1.13.0            | Luna Decisions        | Ordinary Luna Low |
| ------------------------------------------------------------------------------------------------------------------------------------- | --------------------- | --------------------- | ----------------- |
| **T01:** «Я не оплатил парковку.»; typed candidate wrongly asserts actual payment. Expected **reject**.                               | **accept — mismatch** | reject                | reject            |
| **T02:** same source/quote, only stance changes to denied. Expected **accept**.                                                       | accept                | accept                | accept            |
| **T03:** «Не помню, оплатил ли парковку.»; typed stance=unknown correctly preserves uncertainty. Expected **accept**.                 | accept                | accept                | accept            |
| **T04:** notice says «ТС стояло в зоне ПП; оплаты нет»; parking-specific placement requires clarification of ПП. Expected **review**. | **accept — mismatch** | **reject — mismatch** | review            |

Four task variants contain **three distinct authored source texts**. References
remain candidate annotations. The user confirmed unknown/abbreviation/source
semantics in a guided nonblind discussion, with the proposed interpretations
visible. This is not independent whole-task human gold. T01/T02 had no new human
whole-task review; T04 is a declared v2 R032 derivative, not a relabelled original.

| Descriptive measure, per arm                 | Jev | Decisions | Responses Low |
| -------------------------------------------- | --- | --------- | ------------- |
| Completed requests / planned                 | 4/4 | 4/4       | 4/4           |
| Agreement with the four candidate references | 2/4 | 3/4       | 4/4           |
| False acceptance on incompatible T01         | 1/1 | 0/1       | 0/1           |
| False rejection on compatible T02/T03        | 0/2 | 0/2       | 0/2           |
| Unnecessary review on determined T01/T02/T03 | 0/3 | 0/3       | 0/3           |
| Definite answer on ambiguous T04             | 1/1 | 1/1       | 0/1           |

These fractions describe this diagnostic run. They are not population accuracy,
an estimate of critical-error-free extraction, a model ranking, a calibration
study or a measurement of the benefit of escalation.

## Native confidence and returned evidence

Confidence and selected-label probability are different native fields. Neither is
invented for ordinary Responses. This consumer policy always leaves decision.score
null and does not threshold confidence.

| Task | Jev selected label | Confidence | P(selected) | Decisions selected label | Confidence | P(selected) |
| ---- | ------------------ | ---------- | ----------- | ------------------------ | ---------- | ----------- |
| T01  | compatible         | **0.85**   | **0.90**    | incompatible             | 0.34       | 0.56        |
| T02  | compatible         | 0.91       | 0.94        | compatible               | 0.33       | 0.55        |
| T03  | compatible         | 0.76       | 0.84        | compatible               | 0.37       | 0.58        |
| T04  | compatible         | 0.56       | 0.71        | incompatible             | 0.63       | 0.75        |

Jev's incorrect T01 acceptance has native confidence 0.85; its selected-label
probability is 0.90. A high native value did not establish agreement with the
reference on this occasion. Decisions' correct T01 label had confidence 0.34,
while its definite T04 rejection had confidence 0.63. Do not pick a threshold
from these four outputs or treat scales across providers as calibrated.

All available returned model names stayed stable within each arm: `jev-1.13.0`
and `gpt-6-luna`. Every report retains actual request ID, usage, distribution
when available, selected label, policy outcome and request latency. Full native
distributions and all 12 request IDs are in the observations/ZIP.

| Arm             | Provider-reported input tokens | Output tokens | USD cost    |
| --------------- | ------------------------------ | ------------- | ----------- |
| Jev             | 7,665                          | 172           | unknown     |
| Decisions       | 4,485                          | 0             | unknown     |
| Responses Low   | 4,485                          | 493           | unknown     |
| **Total known** | **16,635**                     | **665**       | **unknown** |

Decisions' zero output counts are kept exactly as reported. No cost is estimated
from the account ceiling. Rotated but incompletely position-balanced sequential
order, different serialization and native/ordinary compute settings prevent a
latency/efficiency ranking from this run.

## Interpretation

**Supported by this run:**

- All three checked paths completed the direct bridge contract. Actual wire
  state/question/criteria match the frozen per-task inputs; category-to-policy
  projections match the frozen policy. Ordinary T04 review remains a completed
  evaluation, not an operational failure or a silent reject.
- The known Jev T01 false acceptance reproduced under the new bridge. Jev also
  accepted T02; this run did not show the required incompatible/compatible
  distinction when only typed stance changes under the same quote/source.
- Correctly represented unknown T03 was accepted by every arm. Unknown in the
  source did not itself force a verifier abstention here.
- Ordinary Responses preserved the requested ambiguity handling for T04 on this
  occasion. Jev accepted and Decisions rejected a proposal requiring clarification.

**Still inconclusive:**

- Quote/source agreement masking the typed stance defect remains a plausible
  explanation of Jev's T01/T02 pattern, alongside acceptance bias or a task/prompt
  interpretation problem. This run did not vary quotation authority and cannot
  establish which explanation caused the outputs.
- Four single observations per arm cannot establish reliability, model ability,
  model superiority or general usefulness of the chosen strategy. The same
  development cases have prior exposure and partially dependent references.
- SDK/normalization compatibility does not prove semantic correctness. Reports
  preserve actual submitted requests and normalized native evidence; raw HTTP
  response bodies were not retained by the existing smoke runner, so this archive
  does not independently reparse the original wire response.

## Evidence and offline verification

ZIP SHA256:
`d5cd849fbbd898f45cfceed3e1b483851be97e8d565e615c30efa9b88395d66f`.
The archive contains **35 payload files plus a hash/length manifest**: exact
packet/provenance files, pre-dispatch authorization and supervisor source,
execution index, all 12 current CLI reports and derived observations. Original
reports are bound by the execution index and manifest. The manifest itself is
protected by the published ZIP digest.

Private captures were created on TB5. A credential-value scan passed before
publication. Reports contain synthetic source text and request bodies; auth
headers, key values and raw error/response bodies are excluded. The private
directory is not used as a credential store.

Fresh archive verification with credential variables absent and network denied
checks all payload hashes/lengths, packet/reference/authorization/driver/report
bindings, 12 actual wire-to-task matches, native-vs-label-only evidence boundaries,
all policy outcomes, derived observation agreement and token totals. This is
offline evidence verification, not another inference series, new unit tests or
the native archive/scorer/MLflow pipeline. Existing framework formats are unchanged.
GitHub CI and PR review remain separate.

## Next controlled strategy experiment

Keep #145 open. The useful next variable is how the task explains the relationship
between **evidence quotation** and **the typed proposition being verified**.
Propose one generic instruction clarification: quotations are anchors, while
predicate/stance/mode/roles/scope define the candidate proposition; matching a
quote must not override conflicting typed meaning.

Compare the unchanged baseline and only that instruction change on the same
four controls using **Jev alone**: a proposed eight fresh requests, no repeats or
post-hoc reference edits. Keep both positive/unknown controls and the ambiguity
control to detect regressions. Freeze exact wording, paired ordering and caps
before dispatch; this is a proposal, **not additional execution under the exhausted
12-call grant**. It seeks a better strategy on the available model, not a ranking.
