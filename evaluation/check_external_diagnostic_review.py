"""Check candidate review provenance and spans offline, not semantic correctness."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "fixtures/external-diagnostics-v1"
REVIEW = ROOT / "fixtures/external-diagnostics-review-v1"
RELATIONS = {
    "supported-in-frame",
    "not-established",
    "ambiguous",
    "incompatible-in-same-episode",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_records(path: Path) -> dict:
    records = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
    by_id = {record["id"]: record for record in records}
    require(len(by_id) == len(records), f"Duplicate IDs: {path.name}")
    return by_id


def check_anchor(source: str, evidence: dict, label: str) -> None:
    quote = evidence["quote"]
    require(isinstance(quote, str) and bool(quote), f"Empty quote: {label}")
    for key in ("charStart", "charEnd", "byteStart", "byteEnd"):
        require(type(evidence[key]) is int, f"Invalid {key}: {label}")
    start, end = evidence["charStart"], evidence["charEnd"]
    require(0 <= start < end <= len(source), f"Invalid char range: {label}")
    require(source[start:end] == quote, f"Char quote mismatch: {label}")
    byte_start = len(source[:start].encode("utf-8"))
    byte_end = len(source[:end].encode("utf-8"))
    require(
        (evidence["byteStart"], evidence["byteEnd"]) == (byte_start, byte_end),
        f"Byte range mismatch: {label}",
    )
    require(
        source.encode("utf-8")[byte_start:byte_end] == quote.encode("utf-8"),
        f"Byte quote mismatch: {label}",
    )


def check() -> dict:
    manifest = json.loads((REVIEW / "manifest.json").read_text("utf-8"))
    expected_flags = {
        "schema": "normlab.external-diagnostic-candidate-review/v1",
        "reviewerKind": "assistant-candidate-review",
        "upstreamLabelsVisible": True,
        "modelPredictionsReadForThisReview": False,
        "humanReviewed": False,
        "adjudicated": False,
        "goldCasePassRate": None,
        "independentReview": False,
        "fullExtractionCompletenessReviewed": False,
        "providerInputEligible": False,
        "holdoutEligibleCount": 0,
        "sourceCorpus": "../external-diagnostics-v1",
        "reviewFile": "candidate-reviews.jsonl",
        "spanConvention": "zero-based half-open; char=Unicode-code-points; byte=UTF-8",
        "licenseNotice": "../external-diagnostics-v1/LICENSES.md",
    }
    for key, value in expected_flags.items():
        require(
            type(manifest.get(key)) is type(value) and manifest[key] == value,
            f"Review boundary changed: {key}; use a new version",
        )
    require(
        manifest["sourceManifestSha256"]
        == sha256((CORPUS / "manifest.json").read_bytes()),
        "Source manifest changed",
    )
    require(
        manifest["reviewFileSha256"]
        == sha256((REVIEW / "candidate-reviews.jsonl").read_bytes()),
        "Review file changed without a new hash snapshot",
    )
    inputs = load_records(CORPUS / "inputs.jsonl")
    upstream = load_records(CORPUS / "reviewer-annotations.jsonl")
    reviews = load_records(REVIEW / "candidate-reviews.jsonl")
    expected_ids = {f"EXT-RCB-{n:03}" for n in range(1, 25)} | {
        f"EXT-SUD-{n:03}" for n in range(1, 13)
    }
    require(
        set(reviews) == set(inputs) == set(upstream) == expected_ids,
        "ID coverage changed",
    )
    probe_ids = set()
    anchor_count = 0
    for key, record in reviews.items():
        source = inputs[key]["sourceText"]
        source_file = CORPUS / "texts" / f"{key}.source.txt"
        require(
            source_file.read_bytes() == source.encode("utf-8"),
            f"Source mismatch: {key}",
        )
        require(
            record["sourceSha256"] == sha256(source_file.read_bytes()),
            f"Source hash: {key}",
        )
        for flag in ("humanReviewed", "adjudicated"):
            require(record[flag] is False, f"Unexpected completed review: {key}/{flag}")
        for flag in ("criticalErrorFree", "expectedGaps"):
            require(record[flag] is None, f"Unexpected full-case label: {key}/{flag}")
        if key.startswith("EXT-RCB-"):
            require(
                record["coverage"] == "whole-pair-targeted-semantics",
                f"Coverage: {key}",
            )
            require(record["proposedRelation"] in RELATIONS, f"Relation: {key}")
            require(bool(record["requiredFrame"]), f"Missing frame: {key}")
            require(
                record["adjudicationPriority"] in ("normal", "high"),
                f"Adjudication priority: {key}",
            )
            require(
                record["unqualifiedProjection"]
                in ("do-not-project", "candidate-only-with-original-text-frame"),
                f"Projection policy: {key}",
            )
            require(
                record["upstreamLabel"] == upstream[key]["upstreamAnnotation"]["label"],
                f"Upstream label changed: {key}",
            )
            require(
                record["candidateSha256"]
                == sha256(inputs[key]["candidateText"].encode("utf-8")),
                f"Candidate hash: {key}",
            )
            require(bool(record["evidence"]), f"Missing evidence: {key}")
            for evidence in record["evidence"]:
                check_anchor(source, evidence, key)
                anchor_count += 1
            require(
                bool(record["safeReading"]) and bool(record["mustNotInfer"]),
                f"Reading: {key}",
            )
        else:
            require(
                record["coverage"] == "targeted-attribution-spans-only",
                f"Coverage: {key}",
            )
            require(
                record["identityPolicy"]
                == "case-local-roles; FIO-is-not-a-stable-person-id",
                f"Identity policy: {key}",
            )
            require(
                record["documentForm"]
                in (
                    "editorial-digest-of-decision",
                    "dataset-decision-text-not-officially-verified",
                ),
                f"Document form: {key}",
            )
            require(
                record["privacyReview"]
                in ("residual-identifiers-observed", "not-assessed"),
                f"Privacy status: {key}",
            )
            require(4 <= len(record["probes"]) <= 5, f"Targeted probe coverage: {key}")
            for index, probe in enumerate(record["probes"], start=1):
                probe_id = f"{key}-A{index:02}"
                require(
                    probe["id"] == probe_id and probe_id not in probe_ids,
                    f"Probe ID: {key}",
                )
                probe_ids.add(probe_id)
                require(
                    all(
                        isinstance(probe[field], str) and probe[field]
                        for field in ("voice", "safeReading", "mustNotInfer")
                    ),
                    f"Empty interpretation: {probe_id}",
                )
                check_anchor(source, probe["evidence"], probe_id)
                anchor_count += 1
    for field, count in (
        ("recordCount", 36),
        ("rcbPairCount", 24),
        ("courtTextCount", 12),
        ("courtProbeCount", len(probe_ids)),
    ):
        require(
            type(manifest[field]) is int and manifest[field] == count, f"Count: {field}"
        )
    require(len(probe_ids) == 50, "Expected 50 targeted judicial probes")
    return {
        "records": 36,
        "rcbPairs": 24,
        "courtTexts": 12,
        "courtProbes": 50,
        "exactAnchors": anchor_count,
        "semanticCorrectness": "not-validated",
        "humanReview": "pending",
        "inferenceCalls": 0,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(check(), ensure_ascii=False, sort_keys=True))
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"Candidate review integrity failed: {error}", file=sys.stderr)
        sys.exit(1)
