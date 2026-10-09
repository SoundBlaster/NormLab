# Open PR review — 2026-10-10

Snapshot: 00:36 Moscow, before publishing the offline executor PR. Read-only
inspection of all 12 open NormLab PRs, their checks, mergeability and every
GraphQL review thread (no remaining pages). No merges or review-thread mutations.

## Delivery state

All 12 PRs had successful CI and `MERGEABLE` / `CLEAN` against their **current
base branches**. This does not establish approval or compatibility after retargeting.
No PR had a formal `APPROVED` review decision.

Dependency chain, earliest first:

`main ← #29 ← #30 ← #32 ← #34 ← #35 ← #36 ← #37 ← #38 ← #39 ← #40 ← #41`

[#33](https://github.com/SoundBlaster/NormLab/pull/33) is a separate branch based on
#32, outside that chain. #29, #33, #40 and #41 had no unresolved threads.

## Unresolved threads and current disposition

11 threads remain open, including five originally marked P1. Code inspection and
a clean PyPI download identify **four active P1 findings**, five other findings,
and two findings already addressed by code or external availability.

| PR | Priority | Finding | Current disposition |
| --- | --- | --- | --- |
| [#30](https://github.com/SoundBlaster/NormLab/pull/30) | P1 | Decisions emits `hosted-decisions-v1`; parking review accepts only the older hosted pipeline literal. | Confirmed in `server/parking-review.ts`; successful extraction can be rejected at the consumer boundary. |
| [#32](https://github.com/SoundBlaster/NormLab/pull/32) | P1 | Live Mellea generation does not receive the schema included in the prompt digest. | Confirmed in `evaluation/mellea_candidate.py`; recorded conditions differ from actual generation. |
| #32 | P2 | Sampling failure loses the number of generation attempts. | Confirmed; incomplete operational accounting. |
| #32 | P2 | Quote length uses Python characters before a UTF-16 anchor bound. | Confirmed; non-BMP input can cross the later limit. |
| [#34](https://github.com/SoundBlaster/NormLab/pull/34) | P1 | Selecting pipelines on the final holdout compromises an independent final score. | Still present in the roadmap. Select on development/validation data, freeze the choice, then evaluate an untouched test set. |
| [#35](https://github.com/SoundBlaster/NormLab/pull/35) | P1 | Generic identifier validation rejects real model names with dots, slashes or colons. | Confirmed in `evaluation/harness.py`; ordinary model metadata can block replay. |
| #35 | P2 | Duplicate probe pairs were not inserted into the seen set. | Already fixed: current code contains `pairs.add(pair)`. Thread remains open. |
| [#36](https://github.com/SoundBlaster/NormLab/pull/36) | P1 | Adapter 0.3.0 could not be downloaded from PyPI. | No longer reproduced: fresh `pip download --no-cache-dir --no-deps --index-url https://pypi.org/simple mellea-jev-adapter==0.3.0` succeeded. This is availability evidence, not adapter semantic validation. |
| [#37](https://github.com/SoundBlaster/NormLab/pull/37) | P2 | Unfinished verifier states allow contradictory request/call/status/error combinations. | Confirmed in `evaluation/verifier_capture.py`; requires state-specific invariants. |
| [#38](https://github.com/SoundBlaster/NormLab/pull/38) | P2 | Audit validation lacks a runtime predicate-catalog cross-check. | Validation gap remains; current fixture and runtime definitions agree. |
| [#39](https://github.com/SoundBlaster/NormLab/pull/39) | P2 | Historical independent-review issue metadata omits C001 from scope. | Historical metadata inconsistency; annotation v2 has a separate regression review. Preserve the original raw review and record an erratum separately. |

## Consequence for the next stage

The stack is **not ready for an unconditional bulk merge**. Start with the active
P1 fixes and recheck dependent heads after each change. No fixes are silently
claimed by the offline executor: it has a separate capture schema, permits real
model-name punctuation, and validates its own states, but leaves the old consumer
and capture implementations untouched.

Earlier experiments pin several existing source files by hash. Repairing those
files must explicitly update their evidence lineage rather than rewriting old
reports or treating changed code as the original experiment.
