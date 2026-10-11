"""Offline integrity and selected-field representability audit; no semantic judge."""

import argparse
import json
from collections import Counter
from pathlib import Path

from classification_v3 import build_schema
from harness import artifact, digest, identifier, load_json, require

ROOT = Path(__file__).resolve().parents[1]
CLAIM_FIELDS = {
    "id",
    "sentenceId",
    "quote",
    "start",
    "end",
    "predicate",
    "stance",
    "mode",
    "subject",
    "aboutEntity",
    "actor",
    "claimant",
    "episode",
    "grammaticalSubject",
    "scope",
}
SUPPORTED_FIELDS = {"predicate", "stance", "subject", "claimant", "episode"}


def span(value, source):
    require(
        type(value["start"]) is int
        and type(value["end"]) is int
        and 0 <= value["start"] < value["end"] <= len(source),
        "Unicode source span",
    )
    require(
        source[value["start"] : value["end"]] == value["quote"], "Exact source quote"
    )


def audit(path):
    manifest, raw = load_json(path)
    require(
        manifest["schema"] == "normlab.stage1-audit/v1"
        and identifier(manifest["experimentId"]),
        "Audit manifest identity",
    )
    require(manifest["budget"] == {"maxCalls": 0}, "Offline audit budget")
    require(
        set(manifest["codePins"])
        == {
            "evaluation/discovery_v2.py",
            "evaluation/classification_v3.py",
            "evaluation/mellea_candidate.py",
            "server/inference-prompts.json",
        },
        "Pinned current contract files",
    )
    for name, expected in manifest["codePins"].items():
        require(
            digest((ROOT / name).read_bytes()) == expected,
            "Current contract drift: create a new audit version",
        )
    require(
        set(manifest["artifacts"])
        == {
            "sources",
            "reviewer-only",
            "candidates",
            "definitions",
            "classification-schema",
            "fragment-contract",
        },
        "Audit artifact coverage",
    )
    data = {
        name: artifact(path.resolve().parent, entry)
        for name, entry in manifest["artifacts"].items()
    }
    sources, labels, candidates = (
        data["sources"],
        data["reviewer-only"],
        data["candidates"],
    )
    require(
        sources["schema"] == "normlab.stage1-sources/v1"
        and sources["offsetUnit"] == "unicode-code-points"
        and sources["splitPolicy"] == "diagnostic-development-only-no-holdout"
        and sources["provenance"] == "authored-synthetic",
        "Source provenance",
    )
    require(
        labels["schema"] == "normlab.stage1-review/v1"
        and labels["labelStatus"] == "candidate-not-independent",
        "Candidate review status",
    )
    require(
        candidates["schema"] == "normlab.stage1-candidates/v1"
        and candidates["representation"] == "diagnostic-oracle-not-production-contract",
        "Candidate representation",
    )
    sources_digest = manifest["artifacts"]["sources"]["sha256"]
    require(
        all(
            d["datasetId"] == sources["datasetId"]
            and d["sourcesDigest"] == sources_digest
            for d in (labels, candidates)
        ),
        "Dataset binding",
    )
    require(
        data["classification-schema"]
        == build_schema(["fragment_1"], data["definitions"]),
        "Schema snapshot drift",
    )
    contract = data["fragment-contract"]
    require(
        contract["fragmentAttributes"] == ["subject", "aboutEpisode", "speaker"]
        and contract["classificationFields"] == ["predicate", "stance", "valueText"]
        and contract["productionOntologyAudited"] is False,
        "Audit scope",
    )
    cases = {c["id"]: c for c in sources["cases"]}
    reviews = {r["caseId"]: r for r in labels["cases"]}
    require(
        len(cases) == len(sources["cases"]) == 16
        and len(reviews) == len(labels["cases"])
        and set(cases) == set(reviews),
        "Case/review coverage",
    )
    record_map = {r["id"]: r for r in candidates["records"]}
    record_labels = {r["recordId"]: r for r in labels["records"]}
    require(
        len(record_map) == len(candidates["records"]) == 32
        and len(record_labels) == len(labels["records"])
        and set(record_map) == set(record_labels),
        "Record/label coverage",
    )
    rows = []
    for case_id, case in cases.items():
        review = reviews[case_id]
        source = case["sourceText"]
        require(
            identifier(case_id)
            and identifier(case["familyId"])
            and case["language"] == "ru"
            and case["split"] == "diagnostic-development",
            "Diagnostic split",
        )
        require(
            case["sourceDigest"] == review["sourceDigest"] == digest(source.encode()),
            "Source/review digest",
        )
        require(
            review["reviewStatus"] == "candidate"
            and review["independentReview"] is False,
            "No independent review yet",
        )
        sentences = {s["id"]: s for s in case["sentences"]}
        require(len(sentences) == len(case["sentences"]), "Unique sentence IDs")
        for sentence in sentences.values():
            span(sentence, source)
        oracle = review["claims"]
        require(
            oracle and len({c["id"] for c in oracle}) == len(oracle),
            "Unique oracle claims",
        )
        for claim in oracle:
            require(
                set(claim) == CLAIM_FIELDS
                and identifier(claim["id"])
                and claim["sentenceId"] in sentences,
                "Oracle claim contract",
            )
            span(claim, source)
            sentence = sentences[claim["sentenceId"]]
            require(
                sentence["start"] <= claim["start"] < claim["end"] <= sentence["end"],
                "Claim within sentence",
            )
            require(
                claim["stance"] in contract["stanceValues"]
                and all(
                    isinstance(claim[k], str) and claim[k]
                    for k in (
                        "predicate",
                        "mode",
                        "subject",
                        "aboutEntity",
                        "claimant",
                        "episode",
                        "scope",
                    )
                ),
                "Oracle semantic fields",
            )
        selected = [r for r in candidates["records"] if r["caseId"] == case_id]
        require(len(selected) == 2, "One neutral contrast pair per case")
        compatible = [r for r in selected if record_labels[r["id"]]["mutation"] is None]
        require(
            len(compatible) == 1 and compatible[0]["claims"] == oracle,
            "Oracle candidate consistency",
        )
        for record in selected:
            label = record_labels[record["id"]]
            require(
                label["caseId"] == case_id and len(record["claims"]) == len(oracle),
                "Record case binding",
            )
            mutation = label["mutation"]
            expected_status = (
                "incompatible"
                if mutation
                else "indeterminate"
                if review["alternativeReadings"]
                else "compatible"
            )
            require(
                label["expectation"] == expected_status, "Candidate expectation status"
            )
            differences = []
            for original, candidate in zip(oracle, record["claims"]):
                require(
                    set(candidate) == CLAIM_FIELDS
                    and candidate["id"] == original["id"],
                    "Candidate claim identity",
                )
                differences.extend(
                    (original["id"], k, original[k], candidate[k])
                    for k in CLAIM_FIELDS
                    if candidate[k] != original[k]
                )
            require(
                differences == []
                if mutation is None
                else len(differences) == 1
                and differences[0]
                == (
                    mutation["claimId"],
                    mutation["field"],
                    mutation["from"],
                    mutation["to"],
                ),
                "Exactly one declared field mutation",
            )
        reasons = [
            f"no-typed-field:{field}"
            for field in review["requiredTypedFields"]
            if field not in SUPPORTED_FIELDS
        ]
        reasons += [
            f"predicate-outside-catalog:{c['predicate']}"
            for c in oracle
            if c["predicate"] not in data["definitions"]
        ]
        grouped = {}
        for claim in oracle:
            grouped.setdefault(claim["sentenceId"], set()).add(
                (claim["subject"], claim["claimant"], claim["episode"])
            )
        whole_reasons = (
            reasons + ["multiple-attributions-in-one-sentence"]
            if any(len(group) > 1 for group in grouped.values())
            else reasons.copy()
        )

        def status(issues):
            return (
                "ambiguous"
                if review["alternativeReadings"]
                else "lossy"
                if issues
                else "representable"
            )

        rows.append(
            {
                "caseId": case_id,
                "familyId": case["familyId"],
                "focus": review["focus"],
                "sentenceProjection": status(whole_reasons),
                "claimProjection": status(reasons),
                "sentenceIssues": sorted(set(whole_reasons)),
                "claimIssues": sorted(set(reasons)),
                "reviewStatus": "candidate",
                "notMentioned": review["notMentioned"],
                "alternativeReadings": review["alternativeReadings"],
            }
        )
    return {
        "schema": "normlab.stage1-audit-report/v1",
        "experimentId": manifest["experimentId"],
        "manifestDigest": digest(raw),
        "liveCalls": 0,
        "cases": len(rows),
        "families": len({r["familyId"] for r in rows}),
        "candidateRecords": len(record_map),
        "labelStatus": "candidate-not-independent",
        "auditScope": "selected-typed-fields-not-full-ontology-or-semantic-correctness",
        "counts": {
            layout: dict(Counter(r[layout] for r in rows))
            for layout in ("sentenceProjection", "claimProjection")
        },
        "criticalErrorFreeRate": None,
        "independentReviewCompleted": False,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.manifest)
    if args.output:
        require(not args.output.exists(), "New report path required")
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps({k: v for k, v in report.items() if k != "rows"}, ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
