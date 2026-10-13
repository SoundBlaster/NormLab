# Stage 1 seal/reference/native-score import: executed checks

Date: 2026-10-13 (Europe/Moscow). Task:
[#77](https://github.com/SoundBlaster/NormLab/issues/77).
Base: `224315d16dd2ee662b15a6e79c6cc70138d4f79b` (#87).
[Contract and CLI](OFFLINE_STAGE1_REFERENCE_V1.md).

## Delivered

Adapter `stage1-2` adds optional explicit manifest/seal/native-score inputs to
the existing Stage 1 importer. It retains the original seven scoring/provenance
files, projects candidate reference identity/expectations and first/final scores,
and requires full equality with a regenerated native score. The comparator can
now evaluate final selected-reference agreement for completed Stage 1 tasks.

Scoring-view import leaves the capture-derived run, task/turn IDs and transport
counts unchanged. Labels/report/scorer affect score identity. Native scorers,
planners, executors, source fixtures and their pins remain byte-unchanged.
The additive scoring module separates the frozen formulas from label loading;
retry metrics/paired/attempt helpers are reused directly.

## Local checks

The 10 new reference-import tests passed in **98.350 seconds**. They cover:

- Native scorer parity and original bytes across eight provider/retry states:
  provider completed, failed, sent; retry recovered, exhausted, pending child,
  missing child and zero attempts.
- Same run/capture/task identity and counts with/without a score view.
- Portable scored verification/comparison outside the repository, using only
  the 22 declared modules and prompt asset; no source fixtures or SDK packages.
- All scoring arguments required together; native score drift rejected before
  output creation; invalid reference status/expectation/provenance/duplicate
  records and changed native metrics/rows/bindings/seals rejected after rehashing.
- Derived agreement mutation rejection; all failed/unexecuted/unknown outcomes
  remain null for selected-reference comparison.
- Explicit provider variation with identical label provenance: three eligible
  pairs and no incompatibilities with `--vary provider`; 36 incompatible rows
  without that declaration.
- Full 288-task completed retry corpus, bounded artifacts/index, retained known
  usage 28,800 input / 2,880 output tokens and successful verification. These are
  synthetic fixture counters, not actual consumption.

The final common offline suite passed **54 tests in 152.011 seconds**:
16 bundle, 11 comparator, 17 Stage 1 transport and 10 Stage 1 reference tests.

```bash
python3 -B -S -m unittest discover -s evaluation -p 'test_offline_*.py' -v
```

CLI subprocesses use `-B -S`, a credential-free minimal environment and active
audit guards denying socket operations, nested subprocess dispatch and imports
of provider/HTTP SDKs. Fixture generation invokes native offline functions with
constructed public wire bodies; no SDK client or provider transport is created.

An earlier common-suite run overlapped a reader source edit and had one export
failure; the focused check passed after the edit. The final suite is run with
reader bytes fixed, because bundle verification intentionally binds those bytes.

## Two saved live captures: read-only offline import

Both original captures, seals and native reports from 2026-10-11 passed guarded
import, verification and self-comparison. **No new provider calls were made.**

| Saved capture                         | Planned | Started jobs | Attempts / retries | Completed final | Eligible self-pairs | Candidate matches in eligible pairs | Not evaluated |
| ------------------------------------- | ------: | -----------: | -----------------: | --------------: | ------------------: | ----------------------------------: | ------------: |
| `stage1-coreinfra-live-20261011-1408` |      36 |            3 |              3 / 0 |               2 |                   2 |                                   1 |            34 |
| `stage1-retry-v2-live-20261011-1904`  |      36 |            7 |             12 / 5 |               6 |                   6 |                                   4 |            30 |

The first capture retains 2 completed / 1 failed / 33 unexecuted tasks,
2961 known input / 43 output tokens and one attempt without usage. The retry
capture retains first outcomes 2 completed / 5 failed / 29 unexecuted, final
outcomes 6 completed / 1 failed / 29 unexecuted, 7851 known input / 202 output
tokens and six attempts without usage. Both supplied native reports exactly
match regeneration, including per-arm and paired metrics.

Self-comparisons prove the conditional infrastructure path; they are not
independent evaluations or evidence that one strategy/model improved. The
small, partial historical runs and candidate labels do not establish population
accuracy, statistical significance or the target critical-error-free percentage.

Local output: `.artifacts/stage1-reference-final-20261013/`, including bundles,
JSON/Markdown self-comparisons and a summary. Raw historical captures remain in
the original checkout's ignored `.artifacts/`; none are added to Git.

## Static checks and remaining scope

Ruff lint and format for all 76 Python files, documentation formatting,
45 relative links, changed-module syntax, unchanged frozen-source comparisons
and whitespace checks passed. GitHub CI/review remain separate and pending at
publication.

References remain `candidate-not-independent`; source-chain consistency is not
source authenticity or independent semantic review. The original logical task
is not regenerated from the corpus by this importer. Native seals are unsigned;
historical label isolation is not attested. Case-level quality, independent
execution and missing cost/usage are not inferred.

Next: review this slice, then idempotent MLflow projection of verified bundles
and multiple score views. #77 remains open for the remaining harness acceptance,
including execution/resume contracts. No MLflow installation, inference, resume
or deployment was performed in this slice.

## Review fix: reuse validated replay results

The P2 review finding identified repeated full capture replay in reference
snapshot loading, seal validation and native score regeneration. The original
Stage 1 CI job also failed on Python 3.13.16 because scored corpus import exceeded
the existing 60-second CLI timeout:
[failed job](https://github.com/SoundBlaster/NormLab/actions/runs/38372453327/job/115212522513).

Each projection now replays its private snapshot once, derives the exact native
binding from those immutable bytes and passes the binding/summary to seal and
score verification. Labels are still opened only after replay/seal validation.
There is no global/persistent replay cache. Independent export verification and
later `verify` calls still replay their own snapshot. Native scorers/pins and the
60-second test timeout are unchanged.

A new regression test counts native replay calls for provider and retry imports:
one for initial projection, a second for export validation, a third for a later
independent verify. It also forbids calling native scoring binding helpers that
would trigger duplicate replay. Existing score parity, mutation rejection and
portable reader checks continue to pass.

Local evidence after the fix:

- Python **3.14.8**: full offline suite **55/55**, **117.308 seconds**, including
  scored 288-task import/verify under the unchanged per-CLI 60-second timeout.
- Python **3.10.19**: all **11 reference tests**, **47.387 seconds**.
- Both historical capture/seal/score imports and independent verification passed
  again with socket/process/provider-import guards; no new inference.
- Ruff lint/format, documentation formatting, syntax and whitespace passed;
  native scorers/planners/executors/fixtures/pins remain byte-unchanged.

Fresh GitHub CI for the review fix must be checked separately after publication.
