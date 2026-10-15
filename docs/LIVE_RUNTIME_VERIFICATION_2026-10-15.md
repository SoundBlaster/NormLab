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

| Check                                                         | Result                                                     |
| ------------------------------------------------------------- | ---------------------------------------------------------- |
| Python 3.14.8, `-B -S`, complete offline discovery            | **285/285**, 155.848 s                                     |
| Python 3.10.19, native capture/archive/consumer suite         | **16/16**, 5.086 s                                         |
| Python 3.13.15, pinned MLflow 3.16.1, all local import suites | **38/38**, 70.409 s                                        |
| Exact Ruff `E4,E7,E9,F,I` and formatter                       | Passed, **157 Python files**                               |
| Original native execution module and fixture comparison       | **22 modules** and all fixtures byte-identical to base     |
| Documentation formatting and relative links                   | Prettier passed; **139 links** resolved before this report |

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

## Limits and next step

All native provider-shaped observations here are fake-produced fixtures. No real
API calls, provider-key retrieval, paid inference, production registry writes or
deployment. The MLflow dependency was installed in an ignored local environment;
test registries lived in temporary directories. CI/review are separate evidence.

Signed source authenticity, source-runtime attestation, native continuation and a
separately authorized bounded live smoke remain outside this delivery. Prediction
seals/JSON validity/candidate agreement do not establish case-level accuracy. #77
remains open; next implementation slice is explicit native resume/reconciliation.
