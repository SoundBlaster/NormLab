"""Compare verified saved score views without importing providers or replay scorers."""

import argparse
import html
import sys
from collections import Counter
from pathlib import Path

from offline_bundle import (
    ADAPTER_FILES,
    MAX_BYTES,
    canonical,
    decode,
    identity,
    read,
    require,
    sha,
    verify,
)

SCHEMA = "normlab.offline-comparison/v1"


class SavedView:
    def __init__(self, folder):
        self.root = folder.resolve()
        self.envelope = verify(self.root)
        raw = read(self.root / "bundle.json")
        require(canonical(decode(raw)) == canonical(self.envelope), "Index changed")
        self.digest = sha(raw)
        self.tasks = {}
        for ref in self.envelope["records"]:
            task = self.value(ref)
            slot = None
            if task["armId"] == "classification":
                # Legacy repeats have no repeat number: preserve explicit record IDs.
                slot = "legacy-record:" + task["originalId"]
            elif task["armId"] == "D":
                payload = self.value(task["context"]["artifact"])
                slot = identity("source-target", payload["state"]["target"])
            key = (
                task["caseId"],
                task["candidateId"],
                task["armId"],
                task["repeat"],
                slot,
            )
            require(key not in self.tasks, "Ambiguous pair identity")
            self.tasks[key] = task
        ref = self.envelope["reference"]
        self.reference = self.value(ref["artifact"]) if ref else None

    def value(self, ref):
        path = (self.root / ref["path"]).resolve()
        require(path.is_relative_to(self.root), "Artifact escapes bundle")
        raw = read(path)
        require(
            len(raw) == ref["bytes"] and sha(raw) == ref["sha256"], "Artifact changed"
        )
        return decode(raw)

    def binding(self):
        envelope = self.envelope
        return {
            "bundleDigest": self.digest,
            "runId": envelope["run"]["id"],
            "scoreId": envelope["score"]["id"],
            "referenceId": envelope["reference"]["id"] if self.reference else None,
            "dataset": envelope["dataset"],
            "experiment": envelope["experiment"],
            "evidenceKind": envelope["run"]["evidenceKind"],
        }

    def expected(self, task):
        if self.reference is None:
            return None
        field = "expected" if self.is_s13 else "expectations"
        expected = self.reference[field][task["originalId"]]
        if not self.is_s13:
            expected = sorted(expected, key=canonical)
        return {
            "schema": self.reference["schema"],
            "status": self.reference["status"],
            "revision": self.reference.get("revision"),
            "expected": expected,
        }

    @property
    def is_s13(self):
        return self.envelope["source"]["schema"] == "normlab.s13-offline/v1"

    def outcome(self, task):
        row = self.value(task["scoreArtifact"])
        completed = task["turn"]["status"] == "completed"
        if self.is_s13:
            agreements = [q["agreement"] for q in row["questions"]]
            passed = all(agreements) if completed and agreements else None
        else:
            passed = row["probePass"] if completed else None
        return {"status": task["turn"]["status"], "selectedReferencePass": passed}


def same(left, right):
    return canonical(left) == canonical(right)


def global_reasons(baseline, candidate, policy):
    left, right = baseline.envelope, candidate.envelope
    reasons = []
    if baseline.is_s13 != candidate.is_s13:
        reasons.append("source-family-differs")
    for field in ("dataset",):
        if not same(left[field], right[field]):
            reasons.append(field + "-differs")
    for field in ("strategy", "tactic", "provider"):
        if (
            not same(left["experiment"][field], right["experiment"][field])
            and field not in policy["vary"]
        ):
            reasons.append("undeclared-" + field + "-change")
    if not same(left["experiment"]["policy"], right["experiment"]["policy"]):
        reasons.append("experiment-policy-differs")
    if not same(left["score"]["scorer"], right["score"]["scorer"]):
        reasons.append("scorer-differs")
    if left["score"]["scope"] != right["score"]["scope"]:
        reasons.append("score-scope-differs")
    if left["run"]["evidenceKind"] != right["run"]["evidenceKind"]:
        reasons.append("evidence-kind-differs")
    return reasons


def pair_reasons(baseline, candidate, left, right, policy, global_errors):
    reasons = list(global_errors)
    for field in ("familyId", "language", "sourceDigest", "taskDigest"):
        if left[field] != right[field]:
            reasons.append(field + "-differs")
    if (
        baseline.reference
        and candidate.reference
        and not same(baseline.expected(left), candidate.expected(right))
    ):
        reasons.append("reference-expectations-or-provenance-differ")
    if not baseline.reference or not candidate.reference:
        reasons.append("reference-unavailable")
    lc, rc = left["context"], right["context"]
    if lc["kind"] == "unavailable" or rc["kind"] == "unavailable":
        if policy["context"] == "strict":
            reasons.append("exact-context-unavailable")
    elif (
        lc["policy"] != rc["policy"]
        or lc["artifact"]["sha256"] != rc["artifact"]["sha256"]
    ):
        reasons.append("logical-context-differs")
    return sorted(set(reasons))


def paired_row(baseline, candidate, key, policy, global_errors):
    left, right = baseline.tasks.get(key), candidate.tasks.get(key)
    task = left or right
    row = {
        "key": list(key),
        "caseId": task["caseId"],
        "familyId": task["familyId"],
        "language": task["language"],
        "armId": task["armId"],
        "repeat": task["repeat"],
        "baseline": baseline.outcome(left) if left else None,
        "candidate": candidate.outcome(right) if right else None,
        "baselineTaskId": left["id"] if left else None,
        "candidateTaskId": right["id"] if right else None,
        "category": None,
        "reasons": [],
        "transition": None,
    }
    if left is None or right is None:
        row["category"] = "candidate-only" if left is None else "baseline-only"
        return row
    row["reasons"] = pair_reasons(
        baseline, candidate, left, right, policy, global_errors
    )
    blocking = set(row["reasons"]) - {
        "reference-unavailable",
        "exact-context-unavailable",
    }
    if blocking:
        row["category"] = "incompatible"
    elif row["reasons"]:
        row["category"] = "not-evaluated"
    elif (
        row["baseline"]["selectedReferencePass"] is None
        or row["candidate"]["selectedReferencePass"] is None
    ):
        row["category"] = "not-evaluated"
        row["reasons"] = ["both-completed-scored-outcomes-required"]
    else:
        row["category"] = "evaluated"
        lv, rv = (
            row["baseline"]["selectedReferencePass"],
            row["candidate"]["selectedReferencePass"],
        )
        row["transition"] = (
            "rescue"
            if not lv and rv
            else "regression"
            if lv and not rv
            else "unchanged"
        )
    return row


def summarize(rows):
    evaluated = [row for row in rows if row["category"] == "evaluated"]
    counts = Counter(row["category"] for row in rows)
    left = sum(row["baseline"]["selectedReferencePass"] is True for row in evaluated)
    right = sum(row["candidate"]["selectedReferencePass"] is True for row in evaluated)
    matched = [
        row
        for row in rows
        if row["baseline"] is not None and row["candidate"] is not None
    ]
    return {
        "unionTasks": len(rows),
        "baselinePlannedTasks": sum(row["baseline"] is not None for row in rows),
        "candidatePlannedTasks": sum(row["candidate"] is not None for row in rows),
        "matchedTasks": len(matched),
        "baselineOnly": counts["baseline-only"],
        "candidateOnly": counts["candidate-only"],
        "incompatible": counts["incompatible"],
        "notEvaluated": counts["not-evaluated"],
        "evaluatedPairs": len(evaluated),
        "regressions": sum(row["transition"] == "regression" for row in rows),
        "rescues": sum(row["transition"] == "rescue" for row in rows),
        "unchanged": sum(row["transition"] == "unchanged" for row in rows),
        "selectedReferenceAgreement": {
            "scope": "paired-tasks-with-both-completed-scored-outcomes",
            "baselineNumerator": left,
            "candidateNumerator": right,
            "denominator": len(evaluated),
            "candidateMinusBaseline": (right - left) / len(evaluated)
            if evaluated
            else None,
        },
        "matchedStatusCounts": {
            side: dict(Counter(row[side]["status"] for row in matched))
            for side in ("baseline", "candidate")
        },
        "plannedStatusCounts": {
            side: dict(
                Counter(row[side]["status"] for row in rows if row[side] is not None)
            )
            for side in ("baseline", "candidate")
        },
        "uniqueCases": len({row["caseId"] for row in rows}),
        "uniqueFamilies": len({row["familyId"] for row in rows}),
    }


def compare(baseline, candidate, context="strict", vary=()):
    require(context in {"strict", "legacy-logical-diagnostic"}, "Context policy")
    require(set(vary) <= {"provider", "strategy", "tactic"}, "Declared variables")
    policy = {"id": "offline-paired/v1", "context": context, "vary": sorted(set(vary))}
    global_errors = global_reasons(baseline, candidate, policy)
    keys = sorted(set(baseline.tasks) | set(candidate.tasks), key=canonical)
    rows = [paired_row(baseline, candidate, key, policy, global_errors) for key in keys]
    report = {
        "schema": SCHEMA,
        "policy": policy,
        "policyDigest": sha(canonical(policy)),
        "comparatorDigest": sha(read(Path(__file__))),
        "readerCodeDigests": {
            name: sha(read(Path(__file__).with_name(name))) for name in ADAPTER_FILES
        },
        "baseline": baseline.binding(),
        "candidate": candidate.binding(),
        "sameRun": baseline.envelope["run"]["id"] == candidate.envelope["run"]["id"],
        "sameCaptureSet": baseline.envelope["run"]["captureDigest"]
        == candidate.envelope["run"]["captureDigest"],
        "sameScoreView": baseline.envelope["score"]["id"]
        == candidate.envelope["score"]["id"],
        "executionIndependence": "not-established",
        "globalIncompatibilities": global_errors,
        "summary": summarize(rows),
        "slices": [
            {
                "armId": arm,
                "familyId": family,
                "summary": summarize(
                    [
                        row
                        for row in rows
                        if (row["armId"], row["familyId"]) == (arm, family)
                    ]
                ),
            }
            for arm, family in sorted({(row["armId"], row["familyId"]) for row in rows})
        ],
        "rows": rows,
        "inferenceCallsExecuted": 0,
        "criticalErrorFreeRate": None,
        "uncertaintyIntervals": None,
    }
    report["id"] = identity("comparison", report)
    return report


def markdown(report):
    summary = report["summary"]
    lines = [
        "# Offline paired comparison",
        "",
        f"ID: `{report['id']}`",
        "",
        f"Context policy: `{report['policy']['context']}`; same run: `{report['sameRun']}`.",
        "",
        "| Count | Value |",
        "| --- | ---: |",
    ]
    for key in (
        "unionTasks",
        "matchedTasks",
        "baselineOnly",
        "candidateOnly",
        "incompatible",
        "notEvaluated",
        "evaluatedPairs",
        "regressions",
        "rescues",
        "unchanged",
    ):
        lines.append(f"| {key} | {summary[key]} |")
    metric = summary["selectedReferenceAgreement"]
    lines += [
        "",
        f"Selected-reference agreement: {metric['baselineNumerator']} → {metric['candidateNumerator']} / {metric['denominator']} paired completed/scored tasks.",
        "",
        "Zero denominator means not evaluated. Failures and missing tasks remain in JSON rows/status counts. This is selected-reference agreement, not case-level accuracy or causal model ranking. Repeats/families are correlated; no uncertainty intervals are computed.",
        "",
        "Full rows, reasons, family/arm slices and source bindings: `report.json`.",
        "",
    ]
    if report["globalIncompatibilities"]:
        lines += [
            "## Global incompatibilities",
            "",
            "These apply to the entire comparison, including unmatched tasks. The incompatible count above counts matched rows only.",
            "",
        ]
        lines += [f"- `{reason}`" for reason in report["globalIncompatibilities"]]
        lines += [""]
    reasons = Counter(reason for row in report["rows"] for reason in row["reasons"])
    if reasons:
        lines += ["## Exclusion reasons", "", "| Reason | Rows |", "| --- | ---: |"]
        lines += [
            f"| {reason} | {count} |" for reason, count in sorted(reasons.items())
        ]
        lines += [""]
    events = [
        row
        for row in report["rows"]
        if row["transition"] in {"regression", "rescue"}
        or row["category"] in {"baseline-only", "candidate-only", "incompatible"}
    ]
    if events:

        def cell(value):
            text = html.escape(str(value)).replace("\\", "\\\\")
            for char in ("|", "[", "]", "`"):
                text = text.replace(char, "\\" + char)
            return text.replace("\n", " ").replace("\r", " ")

        lines += [
            "## Changed or unpaired tasks",
            "",
            "| Case | Arm | Repeat | Outcome |",
            "| --- | --- | --- | --- |",
        ]
        lines += [
            f"| {cell(row['caseId'])} | {cell(row['armId'])} | {cell(row['repeat'])} | {cell(row['transition'] or row['category'])} |"
            for row in events[:50]
        ]
        lines += [
            "",
            f"Showing {min(50, len(events))}/{len(events)} events; full keys and reasons are in report.json.",
            "",
        ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument(
        "--context", choices=("strict", "legacy-logical-diagnostic"), default="strict"
    )
    parser.add_argument(
        "--vary",
        action="append",
        choices=("provider", "strategy", "tactic"),
        default=[],
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = compare(
            SavedView(args.baseline), SavedView(args.candidate), args.context, args.vary
        )
        raw = canonical(report)
        require(len(raw) <= MAX_BYTES, "Comparison report byte cap")
        if args.output:
            args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
            with (args.output / "report.json").open("xb") as handle:
                handle.write(raw)
            with (args.output / "report.md").open("x", encoding="utf-8") as handle:
                handle.write(markdown(report))
        print(
            canonical(
                {
                    "id": report["id"],
                    "sameRun": report["sameRun"],
                    "summary": report["summary"],
                    "inferenceCallsExecuted": 0,
                }
            ).decode()
        )
    except (ValueError, OSError, TypeError, KeyError, RecursionError):
        print("Offline comparison validation/export failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
