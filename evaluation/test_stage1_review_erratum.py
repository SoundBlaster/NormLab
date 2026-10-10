"""A versioned correction preserves the original independent-review bytes."""

import json
from pathlib import Path

from harness import digest

BUNDLE = (
    Path(__file__).resolve().parents[1]
    / "fixtures/parking-pilot/stage1-independent-review"
)


def test_erratum_preserves_raw_review_and_corrects_the_projection():
    raw = (BUNDLE / "review.json").read_bytes()
    erratum = json.loads((BUNDLE / "erratum-2026-10-10.json").read_bytes())
    corrected = json.loads((BUNDLE / "review-v2.json").read_bytes())
    historical = json.loads(raw)
    issue = next(item for item in corrected["issues"] if item["id"] == "IR-003")
    c001_v1 = next(case for case in historical["cases"] if case["case_id"] == "C001")
    c001_v2 = next(case for case in corrected["cases"] if case["case_id"] == "C001")

    assert erratum["schema"] == "normlab.stage1-independent-review-erratum/v1"
    assert erratum["historicalArtifact"]["sha256"] == digest(raw)
    assert erratum["historicalArtifact"]["preserved"] is True
    assert erratum["correctedArtifact"]["sha256"] == digest(
        (BUNDLE / "review-v2.json").read_bytes()
    )
    assert corrected["schema"] == "normlab.stage1-independent-semantic-review/v2"
    assert corrected["lineage"]["sourceSha256"] == digest(raw)
    assert "IR-003" in c001_v1["related_issues"]
    assert c001_v2["related_issues"] == []
    assert c001_v2["case_id"] not in issue["case_ids"]
    assert not {"R001", "R002"} & set(issue["record_ids"])
