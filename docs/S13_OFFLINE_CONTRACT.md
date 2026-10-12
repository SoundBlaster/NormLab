# S1.3: offline contract v1

Canonical task: [NormLab #66](https://github.com/SoundBlaster/NormLab/issues/66),
within [research #63](https://github.com/SoundBlaster/NormLab/issues/63).
This document specifies a diagnostic experiment. It does not report model quality
or authorize inference. Live pilot and reference review remain separate tasks:
[#67](https://github.com/SoundBlaster/NormLab/issues/67) and
[#64](https://github.com/SoundBlaster/NormLab/issues/64).
Issue #64 currently reviews the external RCB/judicial corpus. It does not itself
adjudicate the 16 development sources or new S1.3 axis/global labels used here.

## Hypothesis and comparison limits

Local questions may make selected-claim defects easier to identify than one
whole-task question. The alternative is that they add cost or inconsistent
answers without useful discrimination. This contract permits either result.

| Arm | Input and task | Logical calls × repetitions | Semantic questions |
| --- | --- | --- | --- |
| A | Full source + one candidate; whole-task Noul | 32 × 3 = 96 | 96 |
| B | Same source/candidate; four local Noul axes per selected claim, batched in one logical request | 32 × 3 = 96 | 552 |
| C | Same source/candidate and byte-identical whole instruction; binary Choice `yes` / `no` | 32 × 3 = 96 | 96 |
| D | Full source + explicit predicate/focus/query frame; source-only stance Choice | 55 × 3 = 165 | 165 |
| Total | 16 sources, 32 candidate records | **453** | **909** |

These are logical tasks, not executed HTTP requests. A later transport adapter
must document batching/splitting, bind supplier/model/version/settings and count
HTTP attempts separately. No supplier or model is chosen by this offline manifest.

- **A/C:** binary semantics and context match, but response format and abstention
  differ. Noul uses `p_yes >= 0.8` → `yes`, `p_yes <= 0.2` → `no`, otherwise
  verifier `uncertain`. C forces a binary answer. A difference cannot establish
  a pure primitive effect independent of this response policy; probabilities are
  not assumed calibrated.
- **A/B:** decomposition, granularity, aggregation and question count change
  together. Axis scores are diagnostic; they are not independent defect counts.
- **A/D:** task, target selection and answer space change together. D measures
  stance recovery and limited candidate stance comparison, not whole-candidate
  compatibility or a primitive-only causal effect.
- Three repetitions of a source do not create three independent cases. Future
  comparisons must be paired by case/candidate/repetition, with case as the
  clustering unit. The 16 development sources cannot support a population claim.

Ordering is deterministic SHA-256 ordering with a pinned seed and repetition.
It mixes arms without consulting expected answers; it is not a Latin-square
counterbalancing design. Future live work must freeze model/version/context and
record actual order and returned model identifiers before interpreting differences.

## Inputs, targets and label isolation

The [manifest](../fixtures/parking-pilot/s13-offline-v1/experiment.json) pins the
existing `stage1-audit-v2` sources, candidates, definitions and conventions,
new prompts, and compiler/scorer bytes. Historical sources and labels are unchanged.

`compile_plan()` reads an allowlist of public artifacts. It never opens reviewer
labels. `payload` contains source, definitions, conventions, candidate (A/B/C)
or target (D), and questions. Candidate IDs and job metadata remain outside the
payload. No correct/wrong sibling label, mutation explanation or expected answer
is supplied to the verifier. Each B/D question names its fragment and predicate
in the instruction, with character offsets; D also includes UTF-8 byte anchors.

D has **23 focused targets**, the deduplicated union of candidate
`case/span/predicate` keys, plus a fixed 16 × 2 global grid (`payment`,
`paidRegime`). Its target catalogue is candidate-informed. It hides candidate
stance/mode/roles, but is not candidate-free discovery or an exhaustive source
search. Global targets are deliberate absence/operator controls, not a
completeness inventory.

The source is always complete; focus identifies the relation being asked about.
Identity conventions distinguish payer, narrator, vehicle, claimant and episode.
Null vehicle bindings assert neither identity nor distinctness. Reported actual
content preserves what its claimant says; it is not independently verified fact.

## Local axes and routing

| Axis | Target | Example defect |
| --- | --- | --- |
| Content | Predicate and stance under the source operator | Explicit uncertainty changed to an assertion; denied speech act changed to asserted |
| Attribution | Claimant, actor, grammatical subject | Letter's position assigned to narrator; friend payment assigned to narrator |
| Scope | Mode, subject, aboutEntity, episode, typed scope | Obligation made actual; payment transferred between vehicles/sessions |
| Projection | Epistemic boundary | Unknown made definite; modal made actual; reported position made narrator's own |

Projection here is an **epistemic projection check**, not the existing production
schema losslessness gate. It deliberately overlaps content/attribution/scope.
A simple polarity flip is a content defect, not automatically an epistemic
upgrade. Candidate expectations for these axes are proposals needing adjudication.

For A/B/C, any `no` gives `incompatible`; otherwise any `uncertain` gives
`indeterminate`; otherwise `compatible`. For B, each `no` carries
`claimId` + `axis` in `defectLocations`. Failure, deadline and invalid answer
remain failures and never become acceptance. A later runtime may route
`indeterminate` or failures to human review. This offline runner performs no
repair or production action.

**Whole-source completeness is not evaluated.** These questions cannot find all
omissions. A separate source-level reference review must identify required claims,
unknowns, contradictions and unsupported topics before completeness scoring.

## D stance alternatives

Alternatives are frozen before any provider output:

| Value | Meaning |
| --- | --- |
| `asserted` | Source affirms the qualifying relation |
| `denied` | Source denies it |
| `explicit_unknown` | Source explicitly expresses uncertainty |
| `not_mentioned` | No qualifying position in the requested query frame |
| `ambiguous` | Source has unresolved readings affecting that stance |
| `multiple_positions` | Several qualifying positions remain distinct |
| `verifier_uncertain` | Verifier cannot reliably choose; this is not a source fact |

For focused targets, `selected-relation-under-source-operator` preserves the
original operator: an asserted conditional antecedent is not an actual payment.
For global controls, `actual-event-commitment` asks only about commitments to an
actual event, including attributed positions. `not_mentioned` means absence
**in that frame**: a payment word inside a denied speech act, obligation or
hypothesis does not establish an actual payment position.

Global `multiple_positions` does not imply contradiction: vehicles, sessions or
speakers may differ. `C007` necessity and `C016` abbreviation `ПП` have explicitly
proposed ambiguous global labels in reviewer-only rationales; these are not human
gold. Focused answers may still be unambiguous under the selected operator.

For a focused D answer in `{asserted, denied, explicit_unknown}`, the scorer
compares it with each matching candidate stance in code (`unknown` maps to
`explicit_unknown`). Other alternatives and failures yield `null`, not a match
or rejection. Global controls are not compared to individual candidate claims.
This comparison does not check candidate attribution, mode, scope or completeness;
D's `overallSelectedClaimVerdict` is always `null`.

## Frozen resource bounds

| Bound | Value |
| --- | --- |
| Authorized live calls | **0** |
| Planned logical calls / maximum attempts | 453 / 453 |
| Semantic questions | 909 total; at most 8 per request |
| Retries | 0 |
| Logical request bytes | At most 65,536 UTF-8 bytes |
| Input / output tokens | At most 8,192 / 1,024 per attempt |
| Total token ceiling | 4,174,848 (453 × 9,216), a ceiling, not usage or a price estimate |
| Request / serial run deadline | 60 s / 27,180 s, draft ceilings, not observed duration |

The compiler validates counts, byte bounds and cap consistency. Replay validates
recorded token usage and records `deadline`; no timer, tokenizer, HTTP client,
credentials or live execution exists here. The later dispatcher must enforce a
single monotonic run deadline, bound each attempt by remaining time, and freeze
adapter/provider/token accounting plus an actual monetary budget and stopping
rule. The large theoretical ceilings are not a recommended live spend.

## Offline commands and evidence

Run from repository root with Python 3.10+; only the standard library is used.

```sh
rtk proxy python3 -B -S evaluation/s13_offline.py check
rtk proxy python3 -B -S evaluation/s13_offline.py export --output .artifacts/s13-plan
rtk proxy python3 -B -S evaluation/s13_offline.py replay --output .artifacts/s13-replay.json
```

Export writes canonical JSONL chunks no larger than 1 MiB, chunk hashes and a
summary; it refuses an existing output directory. Replay refuses to overwrite
an output file. This keeps individual exports below the prior 2 MiB JSON artifact
limit without changing that harness's limits or claiming live integration.

`requestDigest` hashes canonical logical payload bytes. `planDigest` binds ordered
jobs, repetitions and question mappings; `manifestDigest` also binds code/config.
Replay validates capture bindings and seals `captureDigest` before reading
references. It counts **every planned job**, including missing rows as
`not-dispatched`. Per-arm call/question counts, schema/transport/deadline outcomes,
agreement/disagreement/unevaluated questions and known/unknown token usage remain
separate. The aggregate agreement count is bookkeeping, not a pooled quality score.

The 19 hand-authored mock capture rows exercise acceptance, rejection, verifier
uncertainty, source unknown/absence/ambiguity/multiple positions, malformed
answers, transport failures and a deadline. Uncaptured jobs deliberately stay
`not-dispatched`. Mock answers are not copied from the reference. Their token
numbers are mock accounting values, not billed provider usage.

Frozen replay: 13 `completed`, 3 `invalid-schema`, 2 `transport-failed`,
1 `deadline`, 434 `not-dispatched`. `providerQualityScore` is `null`,
`wholeSourceCompleteness` is `not-evaluated`, and `inferenceCalls` is **0**.
`check` verifies frozen plan, examples and replay summary; CI runs this same
offline integrity command. It is not semantic adjudication.

### Local verification — 2026-10-12

- `check` reproduced frozen plan and mock summary with zero inference calls.
- Two final exports matched byte for byte: 453 jobs in three chunks; largest
  chunk 1,044,693 bytes. Chunk SHA-256 hashes and line/job counts matched.
- Compilation succeeded with access to `reviewer-only.json` explicitly denied.
- The R010 local example identified `A02/attribution` and `A02/projection`;
  focused D stance comparison distinguished the two C001 candidate polarities.
- An offline candidate reference probe changed one label/revision. Re-scoring
  kept the capture digest unchanged and changed agreement from 18 to 17; this
  verifies revision plumbing, not human adjudication or accuracy.
- Ruff 0.15.0 lint/format and Prettier workflow formatting passed locally.

Full local unit/integration suites and live provider checks were not run for
this task. GitHub CI evidence is tracked in #66 and its PR, separately from these
local checks.

## Reference revision and next gate

The default [reference](../fixtures/parking-pilot/s13-offline-v1/reviewer-only.json)
is `s13-candidate-v1`, `candidate-not-independent`. It pins the historical
reviewer-only file, adds proposed local/global labels and rationales, and covers
all planned questions. It is never a provider input or held-out evaluation set.

For human scoring of this plan, review these exact sources/targets/axis labels;
completion of the external-corpus task #64 is not sufficient. After that
plan-specific adjudication, add a **new file/revision** with the same plan binding,
complete question coverage, status `human-adjudicated` and nonempty
`adjudicationEvidence` links to actual review. Preserve the candidate reference
and every capture unchanged. An evidence string is a traceability requirement;
the scorer cannot establish reviewer independence by itself.

```sh
rtk proxy python3 -B -S evaluation/s13_offline.py replay \
  --capture path/to/unchanged-capture.json \
  --reference path/to/new-reference.json \
  --output .artifacts/s13-rescored.json
```

Record old/new reference digests and revisions with the unchanged capture digest.
If adjudication requires changing task meaning, target catalogue, prompts or
public conventions, publish a new experiment version and plan; do not relabel a
changed task as the same replay. Freeze/bind/authorize the live pilot separately
before any inference. A successful offline replay supplies contract evidence only.
