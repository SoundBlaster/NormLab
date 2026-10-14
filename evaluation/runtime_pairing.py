"""Verified runtime score pairing with conservative, explicit compatibility rules."""

from execution_outcomes import answer_schema
from offline_bundle import canonical, decode, require, sha
from runtime_archive_reader import VerifiedArchive
from runtime_score import verify_score


def same(left, right):
    return canonical(left) == canonical(right)


def policy(context="strict-wire", vary=()):
    require(context in {"strict-wire", "same-protocol-body"}, "Runtime context policy")
    require(
        isinstance(vary, (tuple, list))
        and len(vary) <= 3
        and all(
            isinstance(v, str) and v in {"provider", "strategy", "tactic"} for v in vary
        ),
        "Declared variation fields",
    )
    require(len(set(vary)) == len(vary), "Unique declared variations")
    return {
        "id": "runtime-paired-comparison/v1",
        "context": context,
        "vary": sorted(vary),
        "unit": "planned-question",
    }


class RuntimeView:
    def __init__(self, archive, saved):
        require(type(archive) is VerifiedArchive, "Verified runtime archive required")
        self.archive = archive
        self.score = verify_score(archive, saved)
        self.plan = archive.snapshot.plan
        self.arms = {arm["id"]: arm for arm in self.plan["arms"]}
        self.questions = answer_schema(
            decode(archive.snapshot.files[self.plan["pins"]["outputSchema"]["path"]])
        )
        tasks = {t["key"]: t for t in self.plan["tasks"]}
        self.rows = {}
        for row in self.score["rows"]:
            task = tasks[row["taskKey"]]
            for question in row["questions"]:
                key = (
                    row["caseId"],
                    task["candidate"]["sha256"],
                    row["armId"],
                    row["repeat"],
                    task["stage"],
                    question["questionId"],
                )
                require(key not in self.rows, "Ambiguous runtime pair identity")
                self.rows[key] = {"task": task, "row": row, "question": question}

    def binding(self):
        return {
            **{
                k: self.score[k]
                for k in (
                    "archiveId",
                    "executionId",
                    "captureRevisionId",
                    "scoreId",
                    "planDigest",
                )
            },
            "scoreDigest": sha(canonical(self.score)),
            "referenceId": self.score["reference"]["referenceId"],
            "referenceStatus": self.score["reference"]["status"],
            "referenceRevision": self.score["reference"]["revision"],
            "experiment": self.plan["experiment"],
            "dataset": self.plan["dataset"],
            "strategy": self.plan["strategy"],
            "tactic": self.plan["tactic"],
            "arms": self.plan["arms"],
            "summary": self.score["summary"],
            "runtimeCounts": self.score["runtimeCounts"],
            "executionConditions": {
                k: self.plan[k]
                for k in (
                    "caps",
                    "wallTimeNs",
                    "retryPolicy",
                    "contextPolicy",
                    "clockPolicy",
                )
            },
            "evidenceKind": self.score["evidenceKind"],
        }

    def review_declarations(self):
        return [
            {
                k: v
                for k, v in decode(raw.encode()).items()
                if k not in {"sourceDigest", "planDigest"}
            }
            for raw in self.score["referenceInputs"]["reviewsUtf8"]
        ]


def global_reasons(left, right, selected_policy):
    reasons = []
    for field in ("experiment", "dataset", "contextPolicy", "retryPolicy"):
        if not same(left.plan[field], right.plan[field]):
            reasons.append(field + "-differs")
    for field in ("strategy", "tactic"):
        if field not in selected_policy["vary"] and not same(
            left.plan[field], right.plan[field]
        ):
            reasons.append("undeclared-" + field + "-change")
    for field in ("definitions", "prompt", "outputSchema", "code", "dependencies"):
        a, b = left.plan["pins"][field], right.plan["pins"][field]
        if field in {"definitions", "prompt", "outputSchema"}:
            a, b = a["sha256"], b["sha256"]
        if not same(a, b):
            reasons.append(field + "-pins-differ")
    for field in ("policy", "scorerCodePins", "evidenceKind"):
        if not same(left.score[field], right.score[field]):
            reasons.append(field + "-differs")
    for field in ("schema", "status", "revision", "scope"):
        if not same(left.score["reference"][field], right.score["reference"][field]):
            reasons.append("reference-" + field + "-differs")
    if not same(left.review_declarations(), right.review_declarations()):
        reasons.append("review-declarations-differ")
    return reasons


def pair_reasons(left, right, a, b, selected_policy, global_errors):
    reasons = list(global_errors)
    ta, tb = a["task"], b["task"]
    qa, qb = a["question"], b["question"]
    for field in ("source", "candidate"):
        if ta[field]["sha256"] != tb[field]["sha256"]:
            reasons.append(field + "-differs")
    if not same(left.questions[qa["questionId"]], right.questions[qb["questionId"]]):
        reasons.append("question-definition-differs")
    if not same(
        {k: qa[k] for k in ("selected", "expected")},
        {k: qb[k] for k in ("selected", "expected")},
    ):
        reasons.append("reference-selection-or-expectation-differs")
    ar, br = left.arms[ta["armId"]], right.arms[tb["armId"]]
    if "provider" not in selected_policy["vary"] and not same(ar, br):
        reasons.append("undeclared-provider-change")
    if selected_policy["context"] == "strict-wire":
        for field in ("request", "context"):
            if ta[field]["sha256"] != tb[field]["sha256"]:
                reasons.append(field + "-differs")
    else:
        if ar["protocol"] != br["protocol"]:
            reasons.append("wire-protocol-differs")

        def logical(view, task):
            request = decode(view.archive.snapshot.files[task["request"]["path"]])
            body = {k: v for k, v in request["body"].items() if k != "model"}
            context = decode(view.archive.snapshot.files[task["context"]["path"]])
            return {
                "method": request["method"],
                "headers": request["headers"],
                "body": body,
                "context": {k: v for k, v in context.items() if k != "requestDigest"},
            }

        if not same(logical(left, ta), logical(right, tb)):
            reasons.append("logical-request-differs")
    return reasons
