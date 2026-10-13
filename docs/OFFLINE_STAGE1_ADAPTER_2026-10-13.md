# Offline comparison regressions and Stage 1 adapter

Date: 2026-10-13 (Europe/Moscow). Task: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Base: `d46313b67881c306b7bfc8f7b3751aebb437a655` (#86).
[Adapter contract](OFFLINE_STAGE1_ADAPTER_V1.md).

## Comparator first

Added and ran 11 comparator regression tests: conditional denominators,
strict/diagnostic context, missing reference, binding mismatches, declared
provider variables, unmatched keys in both directions, offsetting regression
and rescue, global incompatibilities in Markdown, invalid policies, artifact
tampering, deterministic portable output and exclusive export.

Then implemented the Stage 1 adapter. CI now discovers `test_offline_*.py`.
Existing frozen planners, executors, scorers and their source pins are unchanged.

## Adapter checks

The final common offline suite passed **43 tests in 54.993 seconds**:
16 existing bundle tests, 11 comparator tests and 16 Stage 1 tests.

```bash
python3 -B -S -m unittest discover -s evaluation -p 'test_offline_*.py' -v
```

Stage 1 coverage includes provider completion/failure/sent, retry recovery and
exhaustion, missing child, available plan without child capture, completed child
with unfinished outer checkpoint, zero-cap corpus, full 288-task corpus,
first/final outcomes, usage once per attempt, child-tree capture identity,
projection metric/attempt mutations, illegal retry suffix, wire/code drift,
adjacent-file exclusion, path escape, completed responses without usage and
explicit rejection of unsupported schemas.

Stage 1 transport fixtures were constructed from public mock wire bodies and
native plan/export functions. No SDK client or provider transport was created;
this is not a fresh SDK interoperability or provider accuracy test.
CLI subprocesses use `-B -S`, a credential-free minimal environment and audit
hooks that deny socket operations, nested subprocess dispatch, provider/HTTP
SDK imports including `httpx2`. Explicit blocked-import/socket controls passed.
The portable reader and comparator ran outside the repository with only their
declared modules and prompt asset, without repository fixtures or SDKs.

The full mock corpus retains 288 completed tasks, 288 attempts and known usage
28,800 input / 2,880 output tokens. These are synthetic fixture counters,
not actual consumption. Pending completed children retain known usage while
their accepted label remains null; missing children keep unknown dispatches.

## Two historical live captures, imported offline

Read-only imports of saved local captures from 2026-10-11 passed with the same
network/SDK audit guard. No new live calls were made.

| Historical capture                    | Planned | Started jobs | Attempts | Retries | Completed final | Known input/output | Attempts without usage |
| ------------------------------------- | ------: | -----------: | -------: | ------: | --------------: | -----------------: | ---------------------: |
| `stage1-coreinfra-live-20261011-1408` |      36 |            3 |        3 |       0 |               2 |          2961 / 43 |                      1 |
| `stage1-retry-v2-live-20261011-1904`  |      36 |            7 |       12 |       5 |               6 |         7851 / 202 |                      6 |

The retry capture has first outcomes 2 completed / 5 failed / 29 unexecuted;
final outcomes 6 completed / 1 failed / 29 unexecuted. There are 6 completed and
6 failed attempts. These are transport availability counts, not semantic rescues
or evidence that a strategy improved quality. Failed usage remains unknown.

Local exports: `.artifacts/stage1-offline-adapter-20261013/`. Raw historical
captures remain in the original checkout's ignored `.artifacts/` directory;
neither raw capture trees nor credentials are committed by this change.

## Static validation

Ruff lint passed for the evaluation directory; all 73 Python files passed its
format check. Markdown/YAML formatting and 38 relative documentation links
passed; offline modules parsed. Existing fixtures, prompt asset, native
planners/executors/scorers and frozen classification/S1.3 sources are byte-unchanged
against the base commit. GitHub CI and PR review are separate from this local
evidence and remain pending at publication.

## Boundaries and next step

Stage 1 reference labels/native score views are not imported in this slice.
Quality remains `not-evaluated`; unavailable language remains null. Native replay
validates the saved plan/capture tree, not independent source authenticity or
regeneration from the original corpus. No inference, resume or deployment.

Next: review the adapter, then implement versioned seal/reference/score imports,
followed by idempotent MLflow projection. #77 remains open until its complete
acceptance criteria have evidence.

## Review fix: malformed source text

The P2 review finding on PR #87 identified a traceback when a saved JSON job
contained non-string `task.state.sourceText`. The importer now validates its
type before encoding or hashing it. It rejects malformed input with the fixed
CLI validation diagnostic instead of an `AttributeError` traceback.

A new CLI regression test covers null, number, boolean, list and object values,
with the task digest and indexed artifact hash recomputed so validation reaches
the source-text check. All five variants reproduced the traceback before the
fix and passed after it. The common network-denied offline suite then passed
**44 tests in 58.289 seconds** (16 bundle, 11 comparator, 17 Stage 1). Ruff lint
and the format check for all 73 Python files passed. No new inference was made.
The previous CI run passed all five jobs for `cfab579`; CI for this review fix
must be checked separately after publication.
