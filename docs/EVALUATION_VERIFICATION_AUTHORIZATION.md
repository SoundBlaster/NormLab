# Evaluation verification authorization evidence

Recorded: 2026-10-15, in the ongoing NormLab conversation.

The human user explicitly requested continued verification earlier in this same
conversation:

> пока без репо работаем, это тянет на крутой стартап вообще
> продолжай тестировать и проверять

The user subsequently requested specific runtime/export verification:

> Ок, проверяй offline export/verify, включая изменённые статусы и метрики.

These requests were followed by repeated authorizations to implement and verify
the evaluation harness. Most recently the user approved the next consumer slice
with «Ok, делай дальше» after the proposed next step was the live capture adapter
for archive/score/MLflow. No cancellation or narrower prohibition replaced the
standing request to continue testing and checking this project.

For this delivery, authorized verification includes adding/running focused
offline regression tests for capture/archive/scoring/import behavior and running
the existing local suites, including pinned MLflow against temporary local storage
with provider/network access denied. The implementation plan and Issue #77 start
entry recorded this scope before tests were added.

## Native unknown-stop verification — PR #134

Recorded: 2026-10-16 (Europe/Moscow), in the same ongoing conversation.

The standing requests quoted above also cover focused offline regression checks
for the next native reconciliation slice. The user approved continuing with
«Ок, вперед!» after the adapter upgrade was merged and native
resume/reconciliation was identified as the next step. This continuation did not
replace or revoke the explicit request to continue testing and checking.

For [PR #134](https://github.com/SoundBlaster/NormLab/pull/134), that scope is
`evaluation/test_offline_native_stop.py`: synthetic native captures, fake HTTP
and clocks, stop request/control validation, preservation of unknown reservations,
archive integrity, locking, injected failures and local process exits. The
recorded runs also include the existing SDK-free offline suite. They do not
establish live provider compatibility or semantic model quality.

Review comment
[4288329510](https://github.com/SoundBlaster/NormLab/pull/134#discussion_r4288329510)
reported that the user authorization was absent from its review context. This
section makes the existing authorization and its scope discoverable; it does not
create a new permission or change the repository rule.

## Native safe resume verification

Recorded: 2026-10-16 (Europe/Moscow), same ongoing conversation. After PR #134 was
merged and safe resume was proposed, the user requested «Хорошо, делай
возобновление». The standing explicit testing/checking requests quoted above remain
in effect. This slice's verification scope includes focused synthetic native
continuation/claim/clock/caps/retry/model/failure/process-exit checks and the
existing SDK-free offline regression. It makes no real provider calls. See
[native resume contract](NATIVE_SAFE_RESUME_V1.md) and Issue #77's pre-implementation
acceptance entry.

## Continuation consumers verification

Recorded: 2026-10-18 (Europe/Moscow), same conversation. After the native safe
resume PR was merged and continuation archive/scorer/MLflow integration proposed,
the user requested «Ок, подключай». The standing explicit testing/checking requests
above cover focused/full SDK-free consumer checks and pinned local-only
MLflow/SQLite integration with network denied and temporary storage. See
[consumer contract](CONTINUATION_CONSUMERS_V3.md) and the pre-implementation
acceptance entry in Issue #77. This does not authorize production registry writes.

This record does not authorize paid inference, provider-key retrieval, deployment,
production registry writes or merge. Those actions need their applicable user
authorization. It is evidence for this conversation's current workflow, not a
standalone grant for unrelated tasks or future sessions. AGENTS.md's rule against
unsolicited tests remains in effect.

## Resumed unknown-stop verification

Recorded: 2026-10-18 (Europe/Moscow), same conversation. After checking the
continuation consumer PR, the user requested «слей и делай далее задачи».
The standing explicit testing/checking requests above cover the selected next
bounded stop-control slice: focused/full SDK-free scenarios with synthetic
original/resumed captures, fake HTTP/clocks, guards, preservation of unknown
charges, locking, expiry/integrity checks, publication faults and process exits.
See [contract](RESUMED_UNKNOWN_STOP_V1.md) and the pre-implementation acceptance
entry in Issue #77. No provider calls, key retrieval or production writes are
included in these tests.
