# Stage 1: annotation revision v2 — 2026-10-09

## Scope

This revision resolves annotation conventions exposed by the [first independent
LLM review](STAGE1_INDEPENDENT_REVIEW_2026-10-09.md). It retains all 16 source texts,
13 scenario families and 32 contrast records. No generation, production schema
change, hosted rollout or paid provider request is included.

[Dataset and reproduction](../fixtures/parking-pilot/stage1-audit-v2/README.md)
contains the machine-readable conventions, hashes and offline report. The v1
runner, dataset, numerical report and blind review artifacts remain unchanged.

## Corrections

| Issue | V2 resolution |
| --- | --- |
| IR-001: ungrounded vehicle identity | Null subject/aboutEntity wherever a vehicle is unmentioned, including C014. Different episode IDs do not assert different vehicles. |
| IR-002: nested speech-act semantics | Explicit outer-relation/operator convention. R015 flips denied → asserted on speechAct while keeping its wrappers. |
| IR-003: personal vs general nonpayment | actor-payment and episode-payment scopes; actor recorded for first-person claims. Projection audits these fields for all related cases. |
| IR-004: unknown ПП | C016 selects raw standing instead of parking-specific placement. standing is deliberately outside the production catalog. |
| IR-005: ambiguity policy | Selected-claim support is separate from source ambiguity. C007 necessity and C016 raw standing/payment can be supported without resolving omitted facts. |

R007 now denies placement; R019 denies conditional antecedent content. Both are
valid diagnostic IR. This also removes the analogous problem where changing mode
left an antecedent scope in place. Each contrast still changes exactly one field.

`compatible` means text supports the selected claim under the declared conventions;
it does not mean the narrative is true, exhaustive or legally adjudicated. The
annotations remain candidates. A modal claim does not entail actual payment.
The two payment reports in C005/C006 have different scopes as well as claimants;
they must be retained, with their joint interpretation left to later analysis.

## Offline result

| Layout | Representable | Lossy | Selected ambiguity |
| --- | ---: | ---: | ---: |
| Whole sentence | 1 | 15 | 0 |
| Selected claim | 1 | 15 | 0 |

C004 fits the actual v3 consumer. Splitting other claims does not create missing
typed fields. Eleven cases require unbound vehicle references; the production
fragment contract requires a nonempty vehicle/person ID. Payment actor/scope,
modal operators, and diagnostic predicates expose additional losses.

These are **representability counts**, not Jev/Luna results or an accuracy
percentage. V1 counted narrower selected fields and prioritized source ambiguity;
its 7/9 representable counts and v2's 1/1 are not paired model-quality observations.
No case has been dropped to improve a score. `criticalErrorFreeRate` remains null.

| Case | Claim projection | Reasons |
| --- | --- | --- |
| C001 | lossy | `no-typed-field:actor`, `no-typed-field:scope`, `unresolved-subject-reference` |
| C002 | lossy | `no-typed-field:actor`, `no-typed-field:scope`, `unresolved-subject-reference` |
| C003 | lossy | `no-typed-field:actor`, `no-typed-field:scope`, `unresolved-subject-reference` |
| C004 | representable |  |
| C005 | lossy | `no-typed-field:actor`, `no-typed-field:scope`, `unresolved-subject-reference` |
| C006 | lossy | `no-typed-field:actor`, `no-typed-field:scope`, `unresolved-subject-reference` |
| C007 | lossy | `no-typed-field:actor`, `no-typed-field:mode`, `no-typed-field:scope`, `unresolved-subject-reference` |
| C008 | lossy | `no-typed-field:actor`, `no-typed-field:mode`, `no-typed-field:scope`, `predicate-outside-catalog:speechAct` |
| C009 | lossy | `no-typed-field:actor`, `no-typed-field:mode`, `no-typed-field:scope`, `unresolved-subject-reference` |
| C010 | lossy | `no-typed-field:actor`, `no-typed-field:mode`, `no-typed-field:scope`, `unresolved-subject-reference` |
| C011 | lossy | `no-typed-field:mode`, `no-typed-field:scope`, `unresolved-subject-reference` |
| C012 | lossy | `no-typed-field:aboutEntity`, `no-typed-field:actor`, `no-typed-field:scope` |
| C013 | lossy | `no-typed-field:actor`, `no-typed-field:scope` |
| C014 | lossy | `no-typed-field:actor`, `no-typed-field:scope`, `unresolved-subject-reference` |
| C015 | lossy | `no-typed-field:scope`, `unresolved-subject-reference` |
| C016 | lossy | `no-typed-field:scope`, `predicate-outside-catalog:standing` |

## Verification and review

- Offline runner checks input/code hashes, v1 lineage, unchanged texts/spans,
  explicit labels, valid diagnostic candidates and one-field mutations.
- Regression checks reject rehashed malformed claims and silent required-field
  deletion; the real production consumer accepts C004 and rejects null subject.
- V1 tests remain in the same CI discovery command as v2 tests.
- Repeat LLM review is a regression review: the reviewer has seen v1 labels. It
  is not fresh blind annotation or legal expert validation.

### Repeated review result

[Raw review and provenance](../fixtures/parking-pilot/stage1-independent-review-v2/README.md):
**32 agree / 0 revise / 0 unresolved**. IR-001–IR-005 are resolved under the supplied
conventions; no new blocker was found in this bounded pass. Integration checked
four dataset hashes, all 32 verdict/label bindings and 58 exact review evidence
spans. Raw reviewer outputs were copied unchanged.

The same LLM reviewer saw v1. This is targeted nonblind regression evidence;
labels remain `candidate-not-independent`, with LLM review stored separately.
It does not approve expert ground truth, an accuracy metric, paid calls or a
production promotion. Audit code was inspected but not run/pinned by the reviewer;
the integration manifest separately pins final code and the reproducible report.

Validation on the integrated revision:

- `python -m unittest discover -s evaluation -p 'test_stage1*.py'`: 22 passed.
- Provider contracts, verifier capture, Mellea control flow and Stage 1: 80 offline tests passed.
- Ruff 0.15.0: `check --select E4,E7,E9,F,I evaluation` and `format --check evaluation` passed.

The annotation-regression hold is resolved. Fair comparison still requires a
frozen protocol and call budget; Stage 1 as a whole is not complete.

## Next experiment

Freeze the fair Jev/Luna comparison contract: same selected-support questions,
source/candidate context isolation, no reviewer labels, actual model/version
capture, fixed repeats and a separately approved call budget. Rich IR candidates
must not be advertised as outputs the current production extractor can emit.
