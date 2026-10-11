# Stage 1 v2 targeted regression evidence

The same LLM reviewer repeated the review after v1 exposure. This is **nonblind
regression evidence**, not fresh independent annotation or expert ground truth.

- `review.json` and `report.md`: verbatim reviewer outputs; four dataset SHA-256
  bindings, all 16 cases/32 record verdicts, literal evidence and issue resolutions.
- `manifest.json`: integration owner’s hashes of raw outputs, final audit code,
  report, dataset manifest and preserved v1 review; explicit promotion limits.

Result: **32 agree / 0 revise / 0 unresolved** under v2 conventions; IR-001–005
resolved and no new blocker in this pass. Labels retain candidate status.
Representability remains 1/16 for both layouts, not model accuracy.

CI discovers `evaluation/test_stage1_v2_review.py`, which validates bindings,
coverage, literal source offsets, report consistency and evidence limits offline.
The comparison protocol/call budget remain pending; no production promotion.
