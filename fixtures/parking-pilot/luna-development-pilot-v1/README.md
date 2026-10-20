# Luna development pilot:10 narratives and human correction

Prepared2026-10-19 MSK. Task:[#79](https://github.com/SoundBlaster/NormLab/issues/79),
corpus:[#65](https://github.com/SoundBlaster/NormLab/issues/65),
primary route:[#70](https://github.com/SoundBlaster/NormLab/issues/70).

Start with the [readable10-case book](casebook.md). It contains source texts,
candidate whole-input readings and applicable clarification targets; it is reviewer-only.
[source-only.json](source-only.json) permits source-first annotation. Model-facing
inputs/ contain only the unchanged narrative and its application-owned source digest.
Selection reasons, expectations, rubric and review/correction logs stay outside inference.

## Selected slice

| ID     | Scenario                               | Main checks                                   |
| ------ | -------------------------------------- | --------------------------------------------- |
| DEV001 | Positive payment control               | Payment assertion; no invented tariff/date    |
| DEV002 | Explicit denial                        | Negation; actor-specific payment              |
| DEV003 | Unknown payment outcome                | Unknown distinct from denied/missing          |
| DEV006 | Payment for another vehicle            | Placement/payment vehicle identity            |
| DEV013 | 12:00–12:30 placement,12:05:01 payment | Exact time; no legal deadline computation     |
| DEV017 | Application and SMS failed             | Failure versus payment; no invented exemption |
| DEV027 | Morning paid, evening unpaid           | Two episodes; user selects, no false conflict |
| DEV028 | Narrator paid, notice says unpaid      | Attribution and unresolved conflict           |
| DEV032 | Kazan, unpaid                          | Known outside Moscow; source claims retained  |
| DEV044 | Wife's car, typo, complaint question   | Roles, payment object, procedural noise       |

All source texts and candidate review records are selected unchanged from the
45-case packet in [PR146](https://github.com/SoundBlaster/NormLab/pull/146), pinned
at3704929f4ed42f458c714e7137a0e7fa14cdfbeb. The complete rubric is copied byte-for-byte.
The current branch need not contain that whole packet: selection.json records its
original whole-file hashes, selected input/manifest hashes, source URLs/locators,
privacy/publication limitations and prior family constraints. This preparation does
not merge PR146, adjudicate its annotations or recheck primary publications.

There are9 synthetic sources and1 existing editorial paraphrase,7 primary families.
Inherited full-pool source-connection groups have9 and1 selected members; omitted
bridges are retained conservatively through parent group IDs. These are leakage
constraints, not independent incidents. All10 remain DEV-ALL-SEEN, holdoutEligible=false.
No population estimate, representative sampling or model ranking follows. Permit,
disability, systematic modality operators and long raw user narratives remain gaps.

## Exact strategy to evaluate later

Full narrative → existing hosted literal discovery → ordinary Luna classification:
`server/hosted-extraction.ts:runHostedExtraction`, classifier=openai,
`literal-discovery-then-classification/hosted-v1`. CoreInfra Responses, gpt-6-luna,
low reasoning; preserve existing16384 discovery/8192 classification output limits,
8-fragment batches and3-batch concurrency. modelInput files are request DTOs for
this existing entry point, not prompts for a generic new task.

The current categorical CLI evaluates an already prepared candidate. Its four
controls and default-route checks do not evaluate this extraction pipeline. The
ontology request helper in server/parking-extraction.ts is a separate contract helper
and is not wired into this hosted path. Keep strategy identity explicit.

Hosted-v1 returns statements with predicate, stance, subject, speaker, episode and
source spans. It has no dedicated list of clarification questions or complete scope/
relationship/modality IR. Review whether nuance survives in available fields/valueText;
when it cannot be expressed, record a contract limitation. No schema/prompt is changed
in this packet to conceal that limitation or claim a complete assisted workflow.

## Before and after manual correction

Copy review-log.template.json to a NEW private run directory after an authorized
run. It is a worksheet, not a runtime archive/scorer schema. Existing reports/readers
must not be told to import it. Keep original source, run output and hashes immutable.

1. Record operational outcome first, including invalid schema, failure, unknown,
   all attempts and unexecuted cases. A valid JSON response is not a semantic pass.
2. Review the entire source and output in both directions before edits. Use rubric
   POL/FAB/ROLE/CONFLICT/UNKNOWN/OMIT/GAP/SCOPE, with error source span and output
   JSON pointer/statement ID. Reference readings are candidate only; allow alternatives
   and unresolved disagreements. Missing material facts are not limited to listed probes.
3. Record applicable missing inputs/questions separately from explicit unknown or
   denial. Follow requiredWhen; outside-scope Kazan does not require Moscow details.
   Review both episodes before user selection; do not qualify an arbitrary episode.
4. Correct using the existing draft workflow. Preserve rejected statements, edit
   content in a new revision, save and confirm separately. Content edits reset the
   checklist/confirmations as the current workflow requires. Rejection is not deletion.
5. Source-text changes create a new linked draft and reset dependent choices and
   calculations. Preserve the previous result. No automatic extraction/recalculation
   or extra provider call is authorized by answering a question or editing text.
6. Save corrected artifact/revision hashes linked to baseline. New facts provided by
   the person are human input, never counted as model-extracted facts. Re-review the
   whole result and remaining conflicts/gaps; user confirmation is not independent gold.

An edit event records eventId/time, operation type, target output location/source span,
before/after values, changed fields and reason. Suggested operation types: add-claim,
change-stance/actor/claimant/episode/evidence, reject-claim, answer-clarification,
change-source. One logical operation may change multiple fields; count both operations
and field changes. Count confirmation actions and clarification answers separately.

Use actual timing: active review/correction seconds, paused seconds and clarification
wait separately. Do not use model latency or wall time with long pauses as human
correction time. Unobserved durations/counts/pass flags remain null; empty event lists
in the template do not mean observed zero effort. Participants/sessions are not invented.

## Reporting and completion

Fixed planned denominator:10 texts. Report operational completion, whole-source
extraction critical errors, full assisted-task completion and post-correction residuals
separately. Failures/unexecuted/unreviewed cases remain visible; do not silently compute
success on completed easy cases. A complete-case pass requires whole-output review.
Unresolved status is not automatically a factual error, a pass or a missing count.

Separate error layer: model-semantic, output-contract, workflow/UI, human-review or
unresolved. The absence of a required clarification field can be a contract/workflow
gap; it still prevents full-task completion. It must not become a claim that the
LLM hallucinated or that the full pipeline passed because the schema omits the field.
Known missing facts surfaced for the person are a useful outcome, not failed inference.

Before/after correction use the same source/rubric and explicit differences in added
human context. Report counts plus active time/edit/clarification burden, not a hidden
single score. The project50% demo aspiration is not an achieved rate or a gate from
this convenience slice. No holdout or statistical significance claim.

## Execution proposal and boundaries

**Authorized provider calls:0.** User requested preparation only. Proposed full series:
10 cases, at most30 provider attempts total, no retries/repair/LLM judge,300s per
extraction and900s outer deadline.20 requests is only the estimate if discovery
produces one classification batch per case; actual fragments can require more.
Existing gateway quota/deadlines do not enforce this aggregate call cap. Before live
execution, freeze actual runtime/dependencies and add bounded transport accounting/
capture to the specific run, then obtain separate input/route/call/deadline/spend
authorization. No general framework/UI implementation is part of this preparation.

Record every reservation/send/response, known/unknown usage and full raw output
privately. Stop on first operational/protocol/unknown outcome, input/config drift or
aggregate cap; preserve any in-flight outcomes and unexecuted suffix without replay.
Semantic errors do not trigger repeats. Keep expected cards and prior outputs away
from model requests. Previous$4 external account cap is user-reported, not new
permission, a checked balance, provider price or an experiment cost estimate.

preparation.json records actual data/hash/anchor/coverage/template checks. No inference,
automatic predictions, human sessions, runtime build, new unit tests or deployed UI
verification were performed. Independent full-input reference review and publication
fidelity remain pending. Next: review these10 cases and protocol, then authorize a
bounded run of the existing hosted strategy and perform actual whole-output/correction
review. PR merge alone will not complete that experiment or Issue79 acceptance.
