# Native live consumers: offline verification

Date: 2026-10-15. Issue: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Base: `3d5f55171433c77042f4fb2d205ebb05a1eb2936`.
Contract: [native evidence consumers](LIVE_RUNTIME_ARCHIVE_V2.md).

## Delivered scope

Three layers: explicit native capture reader; versioned durable archive export and
portable verification; evidence-aware reference/score/local MLflow consumers.
Mock v1 schemas keep their meaning. Native consumer schemas use v2 and retain the
source `live-capture` declaration, original pins, requests, permit, recorded
observations and unknown outcomes. Reader/import operations retain zero inference
authority. No native execution producer or fixture was rewritten.

## Executed local checks

| Check                                                         | Result                                                 |
| ------------------------------------------------------------- | ------------------------------------------------------ |
| Python 3.14.8, `-B -S`, complete offline discovery            | **288/288**, 151.611 s                                 |
| Python 3.10.19, native capture/archive/consumer suite         | **19/19**, 6.529 s                                     |
| Python 3.13.15, pinned MLflow 3.16.1, all local import suites | **38/38**, 48.137 s                                    |
| Exact Ruff `E4,E7,E9,F,I` and formatter                       | Passed, **157 Python files**                           |
| Original native execution module and fixture comparison       | **22 modules** and all fixtures byte-identical to base |
| Documentation formatting and relative links                   | Prettier passed; Relative links checked after review   |

A native Stage1 archive produced on Python 3.14 was additionally verified by a
separate Python 3.10 process with SDK/network denied and credential-free environment.
Its source dependency pins were retained, `readerRuntimePinsMatched=false`,
`recordedRuntimeVerified=false`, operation inference count zero. This checks actual
interpreter-version portability on one Mac; it does not establish a real Linux
provider run or physical clock attestation.

## Evidence covered

- Native one-attempt and Stage1 checkpoint shapes; permit/source lineage; complete
  planned denominators, known usage and unknown reservations without orphan adoption.
- Copied trusted reader outside the repository after source deletion, with writes,
  network and provider SDK access denied. The initial copied-reader test exposed a
  frozen producer's transitive import of extraction/server JSON. An independent pure
  Stage1 lineage verifier removed this read-path dependency; final test passes.
- Live archive schema/evidence-kind separation, fully rehashed metadata/counter
  mutations, active writer rejection and incomplete marker publication rejection.
  Existing mock archive fault/portable-reader tests also pass.
- Candidate-only reference provenance, native selected-question score v2, partial
  and unknown rows, rehashed score evidence-kind rejection and SDK-free CLI/dry-run.
- Real pinned local MLflow with socket transport denied: repeat import reuses IDs,
  preserves one metric history, retains archived evidence after source deletion,
  preserves unknown dispatch/usage and creates a separate child for a new reference.
  Existing registry artifact/recovery/score regressions remain green.

MLflow's SQLAlchemy paths emitted `ResourceWarning` messages about unclosed SQLite
connections during the suite; the 38 tests completed successfully. These warnings
are retained in the local log and do not establish clean resource lifecycle.

## Review corrections

- PR #129 requested recorded test authorization evidence. The
  [authorization record](EVALUATION_VERIFICATION_AUTHORIZATION.md) cites the existing
  human requests from this conversation; no new permission or policy waiver was
  invented. Unrelated/future work is outside that record.
- PR #130: provider formats/settings/configuration now use a closed contract, are
  tied to the corresponding protocol/arm and bind to the retained manifest.
  Rehashed mutations include a syntactically valid changed environment reference.
- PR #130: intermediate mock-only score/registry/MLflow consumers explicitly reject
  live archives. The top consumer layer enables evidence-aware implementations and
  verifies preservation instead. One scoped rebase conflict in the registry binding
  was resolved with the separate native execution binding retained.
- PR #131: registry-plan verification and the symmetric export-projection verifier
  validate schema/evidence kind before selecting the native reader. Round-trip and
  partial receipt reuse controls cover these public APIs, plus kind mismatch rejection.

All four threads were replied/reacted/resolved after push and read back through
GraphQL. The table above records final current-tree checks. The initial pre-review run
had 285/285 offline checks and 16/16 focused checks. CI/review provenance is independent of local
evidence and no fresh bot approval on rewritten heads is inferred.

A manual large-corpus native check also passed: all 288 planned tasks survive an
initial pre-reservation interruption with zero attempts/dispatches. Durable export
and independent replay retain 827 content files / 833 published entries and
5,142,021 content bytes within existing caps, without one oversized source-plan blob.

One focused invocation after stack rebase initially ran on the intermediate branch,
where top-layer test modules/evidence-aware consumers were absent. It failed as
such; the narrow guard changes were moved to the intended top branch and the
12-test focused run then passed. Final table results are on the corrected stack.

## Limits and next step

All native provider-shaped observations here are fake-produced fixtures. No real
API calls, provider-key retrieval, paid inference, production registry writes or
deployment. The MLflow dependency was installed in an ignored local environment;
test registries lived in temporary directories. CI/review are separate evidence.

Signed source authenticity, source-runtime attestation, native continuation and a
separately authorized bounded live smoke remain outside this delivery. Prediction
seals/JSON validity/candidate agreement do not establish case-level accuracy. #77
remains open; next implementation slice is explicit native resume/reconciliation.
