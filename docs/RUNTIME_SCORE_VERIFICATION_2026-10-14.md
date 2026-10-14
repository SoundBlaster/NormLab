# Runtime reference and score verification

Date: 2026-10-14. Task: [Issue 77](https://github.com/SoundBlaster/NormLab/issues/77).
Contracts: [reference](RUNTIME_REFERENCE_V1.md),
[score view](RUNTIME_SCORE_VIEW_V1.md), [CLI](RUNTIME_SCORE_CLI_V1.md).

## Local evidence

| Check                                                       | Result                                |
| ----------------------------------------------------------- | ------------------------------------- |
| Complete SDK-free offline suite, Python 3.14.8              | 201/201, 119.592 s                    |
| Dedicated reference checks, Python 3.10.19                  | 6/6                                   |
| Dedicated scorer and CLI checks, Python 3.10.19             | 12/12, 3.929 s; final containment fix |
| Ruff with CI rules including I and format                   | Passed; 124 Python files              |
| AST / unchanged base evaluation files / relative docs links | Passed / 127 unchanged / 44 valid     |

The 18 new checks cover source/review binding, source SHA-256 and exact bytes,
candidate/declaration distinction, repeat identity, defensive copies, continuation
reuse, wrong plan/dataset, invalid/duplicate selections, label types, wrong review
scope/digest, duplicate reviews and byte caps.

Score checks retain all planned questions for partial, unknown, unselected and
terminal failure outcomes. Retry checks separate first failure from final
completion and retain both attempts. Full scoring never implies a complete
case-quality evaluation. Rehashed edits to summaries, statuses, provenance status,
policy and scorer pins reject on recomputation; a score from another capture
revision also rejects. Caller mutation of returned policy does not alter the
fixed policy used by later score computations.

CLI checks run with network and SDK imports forbidden. They verify after original
label files and runtime source are deleted, preserve archive bytes, reject
existing output names, clean temporary files after pre-publication fsync failure,
sanitize errors, reject invalid archives before opening labels, and reject
rehashed score-summary edits. The full 288-task / 864-question unstarted plan
exports within 2 MiB, verifies again, and keeps all 864 selected questions
unevaluated with null agreement rate.

PR109 P2 found JSON byte encoding autodetection accepting UTF-16/32 before
UTF-8-only embedded inputs. Fixed in the bottom reference layer and propagated
to both descendants. The regression rejects UTF-16/32, with/without BOMs, for
source and review artifacts before projection and preserves exact Cyrillic
UTF-8 bytes. Replied/reacted and resolved the original review thread. Fresh CI
on rewritten heads remains separate evidence.

PR111 P2 identified score output paths inside the closed archive tree. Added
resolved output/parent containment rejection before labels/publication. Root,
source-subdirectory and symlink-alias output regressions preserve exact archive
bytes, readable inventory and no temporary files after rejection. Replied/reacted
and resolved the source review thread.

## Scope and limits

New modules are additive. All 127 base evaluation files remain byte-identical,
including archive producer pins, legacy scorers and MLflow importer. Existing
offline CI discovers the new tests without changing workflow dependencies.
No MLflow SDK integration checks were rerun: this slice changes no registry code.
Score-child import into MLflow remains a later slice, not a delivered capability.

Source/review declarations are unsigned. Test review artifacts are synthetic;
they are not independent human reference review. Scorer code pins require matching
trusted installed modules and are not signatures. Fixed selected-question
agreement is not full-case accuracy, critical-error-free rate or release approval.
Partial captures retain unsealed prediction status. Unknown outcomes never gain
fabricated answers. Actual cost and critical-error-free rate remain null;
semantic evidence, readiness and release approval remain false for mock inputs.

Fresh-name publication uses a flushed temporary file and local POSIX hard link.
A failure after publication may leave the complete output; verify it explicitly.
This evidence does not attest physical power-loss behavior.

No provider calls, inference, credentials, added dependencies, registry writes
or deployment. Remote CI and independent review remain separate from local checks.
Full Issue 77 acceptance remains incomplete. Next after review: registry score-child
projection and idempotent import tied to capture/reference/policy revisions.
