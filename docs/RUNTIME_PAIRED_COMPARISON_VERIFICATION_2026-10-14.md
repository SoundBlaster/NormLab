# Runtime paired comparison: offline verification

Date: 2026-10-14. Task: [Issue 77](https://github.com/SoundBlaster/NormLab/issues/77).
Base: `0848f91b923e73ad5ac1b47dac25f232ae3b0a27`.
Contract: [runtime paired comparison v1](RUNTIME_PAIRED_COMPARISON_V1.md).

## Scope

Three additive layers: verified planned-question pairing/compatibility,
deterministic comparator, and fresh JSON/Markdown export/verify CLI. All 137
existing files under `evaluation/` are byte-identical to the base. Existing
producer/scorer/archive pins, legacy comparator and MLflow importer are preserved.
No dependencies, SDK adapters or CI jobs are added; existing SDK-free discovery
includes the new offline tests.

## Executed local checks

- Python 3.10.19, focused pairing/comparator/export suite: **18/18 passed**.
- Python 3.14.8, full SDK-free offline discovery: **225/225 passed** in 123.875 s.
- Ruff 0.15.0: `check --select E4,E7,E9,F,I evaluation` passed;
  `format --check evaluation` passed for all **135** Python files.

Commands from the repository root:

```bash
python3.14 -B -S -m unittest discover -s evaluation -p 'test_offline_*.py' -v
```

Focused Python 3.10 invocation from `evaluation/`:

```bash
python -B -S -m unittest test_offline_runtime_pairing \
  test_offline_runtime_compare test_offline_runtime_compare_cli -v
```

The first focused invocation from the repository root used package-qualified
module names and failed three imports because these tests use sibling-module
imports. Re-running from `evaluation/` passed all 18; no production change was
needed. Full discovery already uses the correct import path.

## Covered behavior

- Every planned question remains in the union, including partial/unstarted,
  missing-side, incompatible and unselected rows. Matching ignores execution
  task IDs but preserves them in side evidence; ambiguous pair keys reject.
- A regression/rescue uses one common selected paired denominator. Empty
  denominators yield null rates/delta. First-attempt and final results remain
  separate. Failure-to-completed is operational recovery, not semantic rescue.
- Strict request/context differences exclude pairs. Explicit same-protocol
  body comparison permits only the declared model/provider variation; changed
  prompts and different wire protocols remain incompatible. Caps differences
  are disclosed and suppress operational completion delta.
- Attempts and token usage are counted per task, not duplicated per question.
- Rehashed edits to metrics, statuses, policy units, source bindings or positive
  evidence flags fail regeneration. Markdown edits and extra output entries
  reject; both archives are validated before reading saved scores.
- Fresh export never overwrites committed or partial directories; an injected
  pre-publication fsync failure leaves no JSON commit marker. Output paths
  inside either archive, including symlink aliases, reject without mutation.
- CLI subprocess guards deny sockets and provider/MLflow SDK imports. Input
  bytes remain unchanged across export/verify. Markdown escapes identifiers
  and previews at most 50 rows; JSON retains the complete union.
- A 288-task unstarted fixture preserves all 864 question pairs and exports
  within the 2 MiB artifact cap; all remain not-evaluated.

## Limits and next slice

These are unsigned mock fixtures and local implementation checks. They establish
neither model quality nor live provider compatibility, independent observations,
host clock continuity, current authorization or release readiness. Confidence
intervals, case-level critical-error-free rate and actual cost remain null.
No inference, registry write or deployment occurred. GitHub CI/review is separate
evidence, recorded on the PRs and in the ledger after publication.

Next: review the three-layer stack, then implement native live transport and
runtime clock/current-authorization capability gates before a bounded live smoke.
