# Active P1 repairs and evidence lineage — 2026-10-10

This revision follows `a2686204eea7b0b184d399ddb5d8e93b6baa3775` (PR #42).
It repairs the four active P1 findings in the [review snapshot](OPEN_PR_REVIEW_2026-10-10.md).
The snapshot remains a historical record of the findings before these repairs.

| Finding | Current contract | Compatibility |
| --- | --- | --- |
| #30 hosted consumer rejects Decisions | Parking review explicitly accepts `hosted-v1` and `hosted-decisions-v1`, preserving the returned pipeline in `originalExtraction` | Existing hosted and local v3 extraction identities remain distinct; unknown pipeline names fail before revision write |
| #32 generation omits hashed schema | `mellea_candidate_v2.py` sends schema and fragments as instruction variables; `promptDigest` hashes the exact instruction, all variables and the semantic requirement | `run_mellea.py` now emits classification/comparison v2 and archives the v2 source; historical v1 generation results are not reclassified |
| #34 final holdout used for selection | Development/validation comparison, frozen selection record, then one untouched final test of the chosen pipeline | Existing diagnostic datasets remain development; no independent test score exists yet |
| #35 real model names rejected | `harness_v2.py` validates requested/returned model names with bounded ASCII metadata including `.`, `/`, `:` | Other identifiers retain the v1 grammar; new replay reports are v2, with original input schema and current code hashes |

## Frozen evidence remains independently checkable

The following files are retained byte for byte at their existing paths:

- `evaluation/mellea_candidate.py`: SHA256 `c9b23618204a80f19ffdd95da1424e7b908489e4a956bf7612a1d1cc6d7499c0`.
- `evaluation/harness.py`: SHA256 `395fbf66d149e1b05fedf9b5710421fb4894614daf87dd2372b453446a1d1af5`.
- `evaluation/plan_stage1_comparison.py` and `fixtures/parking-pilot/stage1-comparison-v1/experiment.json` are unchanged.

Stage1 audit v1/v2 manifests pin the first file. The frozen Stage1 comparison
planner/manifest pins the second. These historical consumers keep importing v1;
their existing code-pin checks and reports continue to validate without changing
any manifest or raw evidence. No historical captures, labels, review records or
reports are rewritten. The Stage1 executor retains its separate existing
model-name contract.

The v2 modules deliberately retain their own small bounded implementations.
Moving shared code out of frozen v1 would invalidate its source pins; silently
injecting new policies into v1 would make historical reproduction ambiguous.
Future edits belong to the v2 lineage or a later explicitly versioned contract.
The frozen modules are archival compatibility surfaces, not recommended
entrypoints for new generation or classification replay.

A v1 manifest/capture can be rescored through `harness_v2.py` without modifying
its bytes or labels binding. The result is explicitly `normlab.evaluation-replay/v2`,
with `inputSchema`, `replayContract: model-metadata/v2`, scorer/dependency hashes
and a new output directory. `classification-selected-probes/v1` is retained
because payment-probe scoring semantics did not change. Such a report is new
replay evidence, not a replacement for the original experiment. Verifier replay
continues to use its separate existing verifier contract.

## New experiment conditions

All new Mellea runs use `normlab.mellea-classification/v2`, pipelines
`mellea-frozen-discovery/<arm>-v2`, and `normlab.mellea-comparison/v2` inventories.
The saved instruction, `userVariables`, schema and prompt digest allow checking
what was passed to generation. V1 digests included a schema absent from actual
generation: preserving those files does not endorse that earlier claim.
No live model or verifier calls were made for this repair, and v2 prompt delivery
is offline control-flow evidence only. A later explicitly authorized live run
must have its own artifact directory and experiment identity.

Selection records freeze pipeline/model/settings, prompts/schema, scorer,
acceptance rule and budget before opening final test outcomes. A test that
informs a subsequent change becomes development evidence; the changed pipeline
needs a fresh untouched final test. Families/incident variants never cross
splits.

## Validation and remaining scope

Local regression coverage checks both accepted hosted pipelines and rejection of
unknown/local pipeline identities at the hosted boundary; actual Mellea sampling
with fixed generation/verifier output checks schema delivery and prompt digests
in all three arms; replay checks real model IDs, unchanged strict identifiers,
byte-identical v2 rescore and frozen code pins. Executed locally:

- 46 Stage1 unittest: all passed, including original audit/comparison pins.
- 63 provider/capture/Mellea/harness pytest: all passed.
- 72 domain/API TypeScript tests: all passed (includes the new hosted boundary regression).
- `npm run check`, `npm run lint:code`, `npm run format:check`, `npm run build`, Ruff lint/format: passed.
- SDK-free v2 harness preflight: 3 records, zero live calls.
- Current `run_mellea.py` fixture CLI: new local artifact directory `.artifacts/p1-repairs-mellea-v2-20261010`; baseline exhausts its single attempt as expected, deterministic/Jev accept after one repair. V2 inventory hashes, output versions and prompt digests were checked. This is a new offline fixture run, not semantic or live-provider evidence.

The P2 findings in the review snapshot remain separate, including Mellea failure
attempt accounting and non-BMP quote limits, unfinished verifier-state invariants,
predicate-catalog cross-checking and the historical review metadata erratum. This
repair layer addresses them without rewriting frozen v1 sources:

- Mellea v2 records validated generation attempts when sampling raises and bounds
  quote length in UTF-16 code units; the v1 source and manifests stay unchanged.
- Verifier replay validates `prepared`, `sent`, and `failed` turn states against
  allowed calls, requests, statuses, errors, and timing fields.
- The separately versioned Stage 1 audit v3 compares its frozen catalog with the
  pinned runtime definitions; audit v1/v2 files and manifests remain unchanged.
- The original independent-review `review.json` remains byte-identical; the
  versioned `review-v2.json` and erratum remove C001's stray IR-003 association.
- Stage 1 rounded-choice tolerance is introduced by `stage1_wire_v2.py` and
  `stage1_executor_v2.py`. The v1 executor, parser, reports, and code pins remain
  frozen and replayable.

The Jev adapter 0.3.0 review concern was an availability observation, not a code
defect; clean PyPI download and CI verification are required before resolving it.

These repairs do not establish semantic model quality, live interoperability or
production readiness. The expanded native stack is intended to merge atomically
only after changed heads have fresh successful checks and actionable review
threads are addressed.
