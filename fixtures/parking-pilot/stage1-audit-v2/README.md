# Stage 1 contrast corpus v2

Offline diagnostic revision: **16 authored synthetic sources, 13 families, 32 candidates**.
Original source texts, sentence offsets and source digests are identical to v1.
`reviewer-only.json` remains candidate annotation, not expert ground truth.

## Files and boundaries

- `sources.json`: original source text and family metadata; no answer labels.
- `candidates.json`: two neutral-ID candidates per text; no mutation labels.
- `reviewer-only.json`: selected-claim support labels and one-field mutations.
- `conventions.json`: explicit identity, actor, scope, operator and ambiguity semantics.
- `definitions.json`, `classification-schema.json`, `fragment-contract.json`: unchanged production snapshots, not the richer diagnostic IR.
- `experiment.json`: hashes of inputs and audited code; zero API-call budget.
- `audit-report.json`: reproducible typed-representability audit, not model predictions.

The previous dataset, runner, report and independent review are preserved under
`../stage1-audit/` and `../stage1-independent-review/`. V2 does not overwrite their evidence.
A change to text, annotations, convention policy, contract or pinned code requires
a new revision; do not silently rehash published evidence.

## Reproduce

```bash
python -S evaluation/audit_stage1_v2.py fixtures/parking-pilot/stage1-audit-v2/experiment.json
python -m unittest discover -s evaluation -p 'test_stage1*.py'
```

Run from repository root. CLI output is a summary; `--output` requires a new file.
No SDK, network, credentials, inference or billing is involved.

## Annotation changes

1. Unmentioned vehicles use null references. C014 no longer asserts that the same
   parking facility implies the same vehicle. Person and episode IDs are local.
2. `actor-payment` is payment by a named person; `episode-payment` omits the payer.
   Denial of the former does not imply nobody paid. Typed actor/scope must survive projection.
3. `stance` applies under `mode` to the scoped relation. Negating a speech act
   leaves actual payment open. R007, R015 and R019 now flip stance within the same
   relation; operator wrappers no longer make the intended contrast questionable.
4. C016 selects raw `standing`, outside the production catalog. It does not infer
   that ПП is a parking place. Abbreviation uncertainty remains in source notes.
5. C007/C016 baseline compatibility concerns only selected claims. Other source
   ambiguity is recorded separately. Compatibility asserts neither real-world
   truth nor complete extraction.

## Result

Both whole-sentence and claim layouts preserve all selected typed semantics in
**1/16 cases (C004)**; **15/16 are lossy**. Splitting sentences alone does not add
actor/scope/modality or nullable references to the production schema.

These counts use stricter semantics than v1 and cannot be compared as model
quality. All 16 cases stay in the denominator. `criticalErrorFreeRate` stays null.
[Repeated review](../stage1-independent-review-v2/README.md): 32 agree, no new blocker.
This is the same reviewer’s nonblind regression; candidate status is preserved.
