"""Offline v2 audit of selected semantics; v1 evidence remains immutable."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from audit_stage1 import CLAIM_FIELDS, ROOT, span
from classification_v3 import build_schema
from harness import artifact, digest, identifier, load_json, require

SCOPES = {
    "proposition",
    "actor-payment",
    "episode-payment",
    "antecedent-actor-payment",
    "assertion-of-payment",
    "payment-actor",
}
MODES = {
    "actual",
    "necessity",
    "obligation",
    "conditional",
    "hypothetical",
    "speech-act",
}
CONTRACT_PINS = {
    "evaluation/discovery_v2.py",
    "evaluation/classification_v3.py",
    "evaluation/mellea_candidate.py",
    "server/inference-prompts.json",
    "evaluation/audit_stage1.py",
    "evaluation/audit_stage1_v2.py",
}


def required_fields(claims):
    fields = set()
    for claim in claims:
        if claim["predicate"] == "payment":
            fields.add("scope")
            if claim["actor"]:
                fields.add("actor")
        if claim["mode"] != "actual":
            fields.add("mode")
        if claim["predicate"] == "speechAct":
            fields.update({"scope", "actor"})
        if claim["scope"] == "payment-actor":
            fields.update({"scope", "aboutEntity"})
    return sorted(fields)


def validate_claim(claim, source, sentences, predicates):
    require(set(claim) == CLAIM_FIELDS and identifier(claim["id"]), "Claim shape")
    require(claim["sentenceId"] in sentences, "Claim sentence binding")
    span(claim, source)
    sentence = sentences[claim["sentenceId"]]
    require(
        sentence["start"] <= claim["start"] < claim["end"] <= sentence["end"],
        "Claim within sentence",
    )
    require(claim["predicate"] in predicates, "Declared diagnostic predicate")
    require(claim["stance"] in {"asserted", "denied", "unknown"}, "Claim stance")
    require(claim["mode"] in MODES and claim["scope"] in SCOPES, "Claim operators")
    for field in ("subject", "aboutEntity"):
        value = claim[field]
        require(
            value is None
            or isinstance(value, str)
            and re.fullmatch(r"(?:vehicle|person)_[1-9][0-9]*", value),
            "Nullable entity reference",
        )
    actor = claim["actor"]
    require(
        actor is None
        or isinstance(actor, str)
        and re.fullmatch(r"person_[1-9][0-9]*", actor),
        "Actor reference",
    )
    require(
        isinstance(claim["episode"], str)
        and re.fullmatch(r"episode_[1-9][0-9]*", claim["episode"]),
        "Episode reference",
    )
    require(
        claim["claimant"] == "narrator"
        or isinstance(claim["claimant"], str)
        and re.fullmatch(r"(?:letter|notice)_[1-9][0-9]*", claim["claimant"]),
        "Claimant reference",
    )
    require(
        claim["grammaticalSubject"] is None
        or isinstance(claim["grammaticalSubject"], str),
        "Grammatical subject",
    )
    if claim["predicate"] == "payment":
        require(
            claim["scope"]
            in {"actor-payment", "episode-payment", "antecedent-actor-payment"},
            "Payment scope",
        )
        require(
            (actor is None) == (claim["scope"] == "episode-payment"),
            "Payment actor scope",
        )
    if claim["predicate"] == "speechAct" or claim["mode"] == "speech-act":
        require(
            claim["predicate"] == "speechAct"
            and claim["mode"] == "speech-act"
            and claim["scope"] == "assertion-of-payment"
            and actor is not None,
            "Outer speech relation",
        )


def audit(path):
    path = path.resolve()
    manifest, raw = load_json(path)
    require(
        manifest["schema"] == "normlab.stage1-audit/v2"
        and identifier(manifest["experimentId"]),
        "V2 manifest",
    )
    require(manifest["budget"] == {"maxCalls": 0}, "Offline budget")
    require(set(manifest["codePins"]) == CONTRACT_PINS, "Code pin coverage")
    for name, expected in manifest["codePins"].items():
        require(
            digest((ROOT / name).read_bytes()) == expected,
            "Contract drift: new audit version required",
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
            "conventions",
        },
        "Artifact coverage",
    )
    data = {
        name: artifact(path.parent, entry)
        for name, entry in manifest["artifacts"].items()
    }
    sources, labels, candidates, conventions = (
        data[k] for k in ("sources", "reviewer-only", "candidates", "conventions")
    )
    require(
        sources["schema"] == "normlab.stage1-sources/v1"
        and sources["offsetUnit"] == "unicode-code-points"
        and sources["provenance"] == "authored-synthetic"
        and sources["splitPolicy"] == "diagnostic-development-only-no-holdout",
        "Source provenance",
    )
    require(
        labels["schema"] == "normlab.stage1-review/v2"
        and labels["labelStatus"] == "candidate-not-independent"
        and labels["evaluationPolicy"] == "selected-claim-support",
        "Candidate label policy",
    )
    require(
        candidates["schema"] == "normlab.stage1-candidates/v2"
        and candidates["representation"] == "diagnostic-oracle-not-production-contract",
        "Candidate representation",
    )
    require(
        conventions["schema"] == "normlab.stage1-conventions/v1"
        and conventions["evaluationPolicy"] == labels["evaluationPolicy"]
        and conventions["qualityMetricAllowed"] is False,
        "Convention policy",
    )
    require(conventions["sourceUnchanged"] is True, "Immutable source policy")
    parent = ROOT / "fixtures/parking-pilot/stage1-audit"
    require(
        digest((parent / "experiment.json").read_bytes())
        == conventions["lineage"]["parentManifestDigest"],
        "Parent lineage",
    )
    parent_sources, _ = load_json(parent / "sources.json")
    require(
        sources["cases"] == parent_sources["cases"],
        "Unchanged texts, families and spans",
    )
    require(
        all(
            d["datasetId"] == sources["datasetId"]
            and d["sourcesDigest"] == manifest["artifacts"]["sources"]["sha256"]
            for d in (labels, candidates)
        ),
        "Dataset binding",
    )
    require(
        data["classification-schema"]
        == build_schema(["fragment_1"], data["definitions"]),
        "Production schema snapshot",
    )
    contract = data["fragment-contract"]
    require(
        contract["fragmentAttributes"] == ["subject", "aboutEpisode", "speaker"]
        and contract["classificationFields"] == ["predicate", "stance", "valueText"]
        and contract["productionOntologyAudited"] is False,
        "Projection contract",
    )
    cases = {c["id"]: c for c in sources["cases"]}
    reviews = {c["caseId"]: c for c in labels["cases"]}
    records = {r["id"]: r for r in candidates["records"]}
    record_labels = {r["recordId"]: r for r in labels["records"]}
    require(
        len(cases)
        == len(sources["cases"])
        == len(reviews)
        == len(labels["cases"])
        == 16
        and cases.keys() == reviews.keys(),
        "Case coverage",
    )
    require(
        len(records)
        == len(candidates["records"])
        == len(record_labels)
        == len(labels["records"])
        == 32
        and records.keys() == record_labels.keys(),
        "Record coverage",
    )
    predicates = set(data["definitions"]) | set(conventions["diagnosticPredicates"])
    rows = []
    for cid, case in cases.items():
        review = reviews[cid]
        source = case["sourceText"]
        require(
            identifier(cid)
            and identifier(case["familyId"])
            and case["language"] == "ru"
            and case["split"] == "diagnostic-development",
            "Case identity",
        )
        require(
            case["sourceDigest"] == review["sourceDigest"] == digest(source.encode()),
            "Source binding",
        )
        require(
            review["reviewStatus"] == "candidate"
            and review["independentReview"] is False,
            "No expert promotion",
        )
        sentences = {s["id"]: s for s in case["sentences"]}
        require(len(sentences) == len(case["sentences"]), "Unique sentence IDs")
        for sentence in sentences.values():
            span(sentence, source)
        oracle = review["claims"]
        require(
            oracle and len({c["id"] for c in oracle}) == len(oracle), "Unique claims"
        )
        for claim in oracle:
            validate_claim(claim, source, sentences, predicates)
        require(
            review["requiredTypedFields"] == required_fields(oracle),
            "Derived required fields",
        )
        require(
            review["baselineExpectation"] in {"compatible", "indeterminate"},
            "Explicit selected support",
        )
        selected = [r for r in records.values() if r["caseId"] == cid]
        require(len(selected) == 2, "Contrast pair coverage")
        baselines = [r for r in selected if record_labels[r["id"]]["mutation"] is None]
        require(
            len(baselines) == 1 and baselines[0]["claims"] == oracle,
            "Baseline equality",
        )
        for record in selected:
            label = record_labels[record["id"]]
            require(
                label["caseId"] == cid and len(record["claims"]) == len(oracle),
                "Record binding",
            )
            mutation = label["mutation"]
            require(
                label["expectation"]
                == ("incompatible" if mutation else review["baselineExpectation"]),
                "Selected expectation",
            )
            differences = []
            for original, candidate in zip(oracle, record["claims"]):
                validate_claim(candidate, source, sentences, predicates)
                require(candidate["id"] == original["id"], "Claim identity")
                differences.extend(
                    (original["id"], k, original[k], candidate[k])
                    for k in sorted(CLAIM_FIELDS)
                    if original[k] != candidate[k]
                )
            require(
                differences
                == (
                    []
                    if mutation is None
                    else [
                        (
                            mutation["claimId"],
                            mutation["field"],
                            mutation["from"],
                            mutation["to"],
                        )
                    ]
                ),
                "One declared field mutation",
            )
        reasons = [f"no-typed-field:{f}" for f in required_fields(oracle)]
        reasons += [
            f"predicate-outside-catalog:{c['predicate']}"
            for c in oracle
            if c["predicate"] not in data["definitions"]
        ]
        if any(c["subject"] is None for c in oracle):
            reasons.append("unresolved-subject-reference")
        grouped = {}
        for claim in oracle:
            grouped.setdefault(claim["sentenceId"], set()).add(
                (claim["subject"], claim["claimant"], claim["episode"])
            )
        whole = reasons + (
            ["multiple-attributions-in-one-sentence"]
            if any(len(g) > 1 for g in grouped.values())
            else []
        )

        def status(issues):
            return (
                "ambiguous"
                if review["baselineExpectation"] == "indeterminate"
                else "lossy"
                if issues
                else "representable"
            )

        rows.append(
            {
                "caseId": cid,
                "familyId": case["familyId"],
                "sentenceProjection": status(whole),
                "claimProjection": status(reasons),
                "sentenceIssues": sorted(set(whole)),
                "claimIssues": sorted(set(reasons)),
                "sourceAmbiguity": review["alternativeReadings"],
                "baselineExpectation": review["baselineExpectation"],
                "reviewStatus": "candidate",
            }
        )
    return {
        "schema": "normlab.stage1-audit-report/v2",
        "experimentId": manifest["experimentId"],
        "manifestDigest": digest(raw),
        "liveCalls": 0,
        "cases": len(rows),
        "families": len({r["familyId"] for r in rows}),
        "candidateRecords": len(records),
        "labelStatus": "candidate-not-independent",
        "auditScope": "faithful-selected-typed-semantics-not-model-quality",
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
