# Stage 1 contrast set v1

16 authored synthetic Russian sources, 13 scenario families, 32 neutral candidate
records. Development diagnostics only: no holdout, news, court decisions, personal
data or claims about real events. These are selected probes, not exhaustive legal
or narrative annotations. No normative legal conclusions are expected.

## Files and isolation

- `sources.json`: immutable text and manually selected sentence spans. IDs/family
  IDs do not encode the expected verdict. Offsets use Python Unicode code points,
  **not JavaScript UTF-16**; this is an evaluation artifact, not a UI interchange.
- `candidates.json`: one hand-authored diagnostic oracle and one single-field
  mutation per source. Record order alternates; no correctness labels included.
  Extended claim representation is experimental and is not the production schema.
- `reviewer-only.json`: oracle claims, selected omissions, alternative readings,
  expectations and mutation provenance. Never include this file in model context.
  All labels remain `candidate-not-independent`; self-checking is not independent
  expert review. Sentence decomposition is also manual diagnostic evidence.
- `definitions.json`, `classification-schema.json`, `fragment-contract.json`:
  frozen catalog, generated v3 schema and the audited fragment field description.
- `experiment.json`: artifact digests, current-code pins and zero-call budget.
- `audit-report.json`: reproducible integrity/selected-field audit; no predictions.

The full source must accompany any future target claim: attribution may be stated
outside its minimal quote. `claimant` describes the source of the proposition;
`grammaticalSubject`, payment `actor`, domain `subject` and `aboutEntity` are
separate diagnostic roles. A letter is not a vehicle or the narrator.

`mode` distinguishes actual assertions, obligations, conditionals, hypotheses and
speech acts. Explicit unknown concerns a predicate named by the text; not mentioned
is a reviewer-side omission, not an additional negative/unknown model assertion.
Some speech-act predicates intentionally fall outside the current domain catalog.
All fields describe textual claims, not confirmed facts or findings.

## Offline command

```bash
python3 evaluation/audit_stage1.py fixtures/parking-pilot/stage1-audit/experiment.json
python3 -m unittest discover -s evaluation -p test_stage1_audit.py -v
```

The command performs **zero API calls**, needs no external packages/credentials,
and rejects drift from the pinned current discovery/classification contracts.
Change of schema/catalog/prompt requires a new audit version. Optional `--output`
accepts only a new report path.

## Audit interpretation

`representable` means the selected required typed fields are available under the
fixed projection; it does not prove full semantic fidelity, a correct oracle, or
that an extractor can produce the annotation. `lossy` records specific required
fields/catalog entries or per-claim attribution absent from this projection.
`ambiguous` retains alternate readings and takes priority over schema issues.
The original quote/valueText can still preserve nuance as free text: the audit
asks whether consumers can reliably address that nuance structurally.

Scope: current `discovery_v2` → `classification_v3` evaluation slice. The richer
ontology contract and all production/human-editing paths are **not** audited.
Minimal claims are a manual counterfactual arm; no parser has been implemented.
Family IDs, translations and mutations must remain together in any future split.
This small chosen set does not estimate general error rates or significance.

## Before model comparison

1. Independently review source spans, roles, modality and uncertain readings.
2. Decide how unsupported/mixed cases are represented; preserve them in reports.
3. Freeze instructions, definitions, policy and scorer. Feed one neutral candidate
   per request; source-only reconstruction is a separate arm.
4. Fix provider/tactic matrix, repeats and billable budget before any live run.
   This audit authorizes and executes no corpus inference.

## Subsequent independent model review

[Review 2026-10-09](../../../docs/STAGE1_INDEPENDENT_REVIEW_2026-10-09.md) covered
all 16 cases / 32 expectations with a source-only first phase. Comparison is held
for C014 identity, R015 field composition and scope conventions. Original v1
artifacts remain unchanged; reviewer judgments do not promote expert labels.
