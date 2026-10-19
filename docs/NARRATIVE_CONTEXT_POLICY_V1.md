# Narrative context policy v1

2026-10-19. [Ledger #70](https://github.com/SoundBlaster/NormLab/issues/70).
Parent: [DEV017 smoke / PR161](https://github.com/SoundBlaster/NormLab/pull/161),
[observed output](HOSTED_SCHEMA_SMOKE_2026-10-19.md).

**Status: policy and candidate reference packet.** Not connected to hosted runtime,
UI, prompts, legal calculation or model scoring. User decisions are distinguished
from authored examples. No new inference.

## 1. Classify the whole narrative before selecting a case pipeline

### Current implementation

The hosted entry accepts narrative/sourceDigest, performs literal discovery and
classifies its fragments with the parking predicate catalogue. There is no
whole-text relevance/intent/episode-routing result before discovery. `cityParking`
and `paidRegime` are fragment predicates, not a topic router. See
[hosted entry](../server/hosted-extraction.ts),
[prompts](../server/inference-prompts.json),
[predicate domains](../shared/parking-contracts.ts).

The selected parking UI/profile provides application context, not evidence that
the described event involved an automobile or paid parking.

### Proposed contextual result

First make a logical routing decision from the **whole original narrative**:

| Dimension | Candidate values / purpose                                                            |
| --------- | ------------------------------------------------------------------------------------- |
| Topic     | parking / other / unclear / mixed                                                     |
| Intent    | incident / information / unclear                                                      |
| Route     | parking-review / clarify / other-topic / not-a-case / choose-episode                  |
| Evidence  | Exact source spans and a short explanation; UI-selected profile identified separately |

This selects a pipeline and possible clarification; it does not populate legal
findings. A parking-related text can be about tariffs/news, and a fine can concern
another offence. An ambiguous text gets a clarification, not a confident
rejection. Mixed episodes need selection before facts from one episode enter
another. Preserve original text and permit user correction of routing.

**Topic «платная парковка» is not `paidRegime=asserted`.** Only a source-bound
statement can propose the latter; explicit wording itself remains a claim awaiting
human review, not independently established truth. Paying a fine is not paying a
parking session. A document alleging nonpayment is not proof of every element.

The first implementation may share an existing model call or use an explicit
user-selected profile; this policy does not mandate a third paid call. Compare
routing with/without this context as a separate strategy factor later, with the
same inputs, full downstream output and extra latency/call accounting. No
posthoc confidence threshold or silent fallback: API failure is operational, not
a label «other».

## 2. Separate source-supported references and hypotheses

`subject` is the target of a domain claim; `speaker` records who reports it.
The narrator, driver, payer and owner are distinct roles until the source links
them. Pronouns/ellipsis may resolve against an explicit referent in the same
relevant episode; the noun need not be repeated in every sentence. Do not infer
an owner from payment or a driver from ownership.

| Wording/context                            | Source-supported interpretation                                   | Hypothesis / next action                                           |
| ------------------------------------------ | ----------------------------------------------------------------- | ------------------------------------------------------------------ |
| «Я стоял на городской парковке»            | Narrator's presence/place                                         | Do not create a car or placement; clarify event if necessary       |
| «Мой автомобиль стоял на парковке»         | Explicit automobile and placement claim                           | Driver/payer remain separate questions                             |
| «Я припарковался»                          | Narrator reports parking action                                   | **Separate car hypothesis**, explicit human confirmation required  |
| «Автомобиль стоял… Его парковку я оплатил» | Vehicle referent from previous sentence; narrator reports payment | Preserve role boundaries; not an ungrounded new entity             |
| «Оплатить парковку не удалось» alone       | Failed payment is reported; referent not supplied                 | Keep text, ask for scope; do not invent person/car to fill a field |
| Friend driving / narrator paying           | Distinct reported roles                                           | Do not merge driver, payer and owner                               |

User explicitly chose **«Автомобиль — отдельная гипотеза»** for «Я припарковался»
in this conversation. This is a product policy decision, not human adjudication
of the other fixtures or permission to treat every parking-related text as a car
incident. «Я стоял на парковке» does not introduce that hypothesis.

A hypothesis must carry its originating quote/context, proposed content and an
explicit confirmation requirement. It is not accepted by default and cannot feed
legal computation before confirmation; confirmation also does not satisfy other
missing legal conditions. Rejecting/editing it must not remove the source quote.

### Current representation limit

Hosted `subject` only accepts person/vehicle IDs; the review DTO has
`origin=model|human` and `decision=pending|confirmed|rejected`. All model statements
are pending, so **pending alone cannot distinguish an inferred entity hypothesis
from a source-supported proposition**. No unknown-subject ID, app-as-subject, fake
vehicle or reused person ID should disguise a representability gap.

A later small implementation needs an explicit hypothesis/clarification boundary
with source provenance and user confirmation. Until then, retain the original
text/quote and show that clarification is needed before calculation. Do not
mislabel a relevant unrepresentable claim as `no-supported-predicate`. This
packet does not silently extend either DTO or claim those UI behaviors exist.

## 3. Preserve the stated strength and source of causality

| Source                                                | Permitted source-bound summary                        | Forbidden promotion                                      |
| ----------------------------------------------------- | ----------------------------------------------------- | -------------------------------------------------------- |
| App/SMS failed; payment failed                        | Retain both claims without adding a causal connective | Definite «payment failed because…» solely from adjacency |
| «Не смог оплатить, потому что приложение не работало» | Narrator reports a causal explanation                 | Established external cause, legal fault or exemption     |
| «Возможно, из-за этого…»                              | Keep uncertainty in the causal link                   | Remove «возможно» or make the cause certain              |
| «Не удалось…, но не из-за сбоя»                       | Failed payment plus denial of this cause              | Flip payment polarity or infer that every system worked  |
| Letter reports cause / narrator disputes it           | Preserve each claim and speaker separately            | Choose a winner or silently change document attribution  |
| App failed, no payment outcome stated                 | Retain technical failure                              | Invent unpaid/failed/successful payment or fault         |

«Мне не удалось оплатить» does not establish «никто не оплатил». Preserve the
scope of the speaker's action; a different payer remains possible. Uncertainty
about a cause does not erase a clearly reported failed payment. Preserve full
quotes, negations, modality, episode and source before summarizing.

These are semantic entailment rules, not a ban-list for the word «из-за». It is
valid when the source asserts it, and causality can be added without that exact
word. A keyword regex cannot certify this policy. Current `paymentComplexity`
records payment problems; no new legal causal/fault relation is created here.

## 4. Candidate contrasts and verification boundary

[17 cases](../fixtures/parking-pilot/narrative-context-policy-v1/cases.json):
A01–A06 actor/reference, C01–C06 causal strength/provenance, T01–T05 routing.
A01 is the exact original DEV017 input; the others are authored contrasts.
Families group related examples, not independent incidents. These are development
references, not a new holdout or adjudicated gold corpus.

Each case retains exact whole-sentence source anchors/digest, routing expectation,
source-bound summary, forbidden promotions and any separate hypothesis. These
fields describe policy expectations, **not a proposed LLM output JSON contract**.
No model was evaluated on this packet and no case pass rate is supplied. See the
[mechanical verification record](../fixtures/parking-pilot/narrative-context-policy-v1/verification.json). Integrity
checks establish IDs, exact anchors, provenance and declaration consistency only;
they cannot prove the semantic correctness of authored expectations.

The observed PR161 result stays immutable: operational pass with candidate
vehicle/causality concerns. It is never replaced by A01's authored reference.

## 5. Small implementation sequence and acceptance

1. Review these boundaries/examples, including implicit car hypothesis and topic
   versus event fact. Preserve semantic disagreements explicitly.
2. Implement explicit contextual/hypothesis metadata and confirmation boundary in
   one product slice; keep raw source and editable routing/episode choice.
   No automatic promotion to legal calculation or collapse of participants.
3. Apply a separately versioned hosted-only strategy change. Preserve historical
   shared prompts/captures/pins; evaluate on the same development inputs with
   full output, routing errors, false assumptions and missing facts counted.
4. Agree a bounded live comparison later. Extra classification calls/latency and
   correction effort must be visible; no guaranteed improvement is assumed.

Acceptance for that future slice: no car in A01 source claims; A03 car appears
only as a separate unconfirmed hypothesis; no ownership/driver/payer collapse;
no categorical cause in A01; preserve reported/hedged/denied causal source claims;
T02 clarification, T03 unsupported topic, T04 no invented personal case, T05
episode selection, and no paid-regime finding solely from topic. Exact quote
anchoring is necessary but insufficient.

No framework expansion, new legal ontology, native provider capability or model
quality result is a prerequisite for reviewing this policy packet.
