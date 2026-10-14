"""Closed fresh comparison export with readable bounded Markdown and shared readers."""

import fcntl
import html
import os
from pathlib import Path

from execution_checkpoint import bounded_read, reader_lock
from offline_bundle import MAX_BYTES, canonical, decode, require
from runtime_compare import verify_comparison


def cell(value):
    text = (
        html.escape(str(value)[:120], quote=True).replace("\n", " ").replace("\r", " ")
    )
    for character in ("\\", "|", "*", "_", "`", "[", "]"):
        text = text.replace(character, "\\" + character)
    return text


def markdown(result):
    summary = result["summary"]
    final = summary["final"]
    lines = [
        "# Runtime paired comparison",
        "",
        "Comparison ID: " + result["comparisonId"],
        "",
        "Unit: planned question. Context: " + cell(result["contextEvidence"]) + ".",
        "",
        "| Measure | Value |",
        "| --- | --- |",
        "| Union questions | " + str(summary["unionQuestions"]) + " |",
        "| Matched questions | " + str(summary["matchedQuestions"]) + " |",
        "| Final paired denominator | " + str(final["denominator"]) + " |",
        "| Baseline passed | " + str(final["baselinePassed"]) + " |",
        "| Candidate passed | " + str(final["candidatePassed"]) + " |",
        "| Agreement delta | " + str(final["delta"]) + " |",
        "",
        "## States",
        "",
    ]
    lines.extend(
        "- " + state + ": " + str(number) for state, number in summary["states"].items()
    )
    lines.extend(
        [
            "",
            "## Operational completion",
            "",
            "Planned tasks: "
            + str(result["operational"]["baseline"]["plannedTasks"])
            + " / "
            + str(result["operational"]["candidate"]["plannedTasks"])
            + ".",
            "Completed tasks: "
            + str(result["operational"]["baseline"]["completedTasks"])
            + " / "
            + str(result["operational"]["candidate"]["completedTasks"])
            + ".",
            "Completion delta: " + str(result["operational"]["completionDelta"]) + ".",
            "",
            "## Global incompatibilities",
            "",
        ]
    )
    lines.extend(
        ["- " + cell(reason) for reason in result["globalIncompatibilities"]]
        or ["None."]
    )
    lines.extend(
        [
            "",
            "## Changed or excluded pairs",
            "",
            "Preview: first 50 rows; identifiers abbreviated to 120 characters. Full details in report.json.",
            "",
            "| Case | Arm | Question | State | Transition | Reasons |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    changed = [
        row
        for row in result["rows"]
        if row["state"] != "evaluated" or row["verdict"] != "unchanged"
    ]
    for row in changed[:50]:
        lines.append(
            "| "
            + " | ".join(
                cell(v)
                for v in [
                    row["key"][0],
                    row["key"][2],
                    row["key"][5],
                    row["state"],
                    row["verdict"],
                    ", ".join(row["reasons"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "Unsigned mock evidence. Selected-reference agreement is not case quality.",
            "Execution independence is not established; confidence interval and critical-error-free rate remain null.",
            "",
        ]
    )
    raw = "\n".join(lines).encode()
    require(len(raw) <= MAX_BYTES, "Comparison Markdown cap")
    return raw


def flush_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def export(result, output):
    raw, md = canonical(result), markdown(result)
    require(len(raw) <= MAX_BYTES, "Comparison JSON cap")
    root = Path(output)
    root.mkdir(mode=0o700)
    flush_directory(root.parent)
    with (root / ".writer.lock").open("xb+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        os.fsync(lock.fileno())
        flush_directory(root)
        for name, content in [("report.md", md), (".report.tmp", raw)]:
            with (root / name).open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        # Readers wait on the lock while the fresh, non-overwriting marker is published.
        os.link(root / ".report.tmp", root / "report.json")
        (root / ".report.tmp").unlink()
        flush_directory(root)


def verify_export(
    output, baseline_archive, baseline_score, candidate_archive, candidate_score
):
    root = Path(output).resolve(strict=True)
    with reader_lock(root):
        names = {p.name for p in root.iterdir()}
        require(
            names == {"report.json", "report.md", ".writer.lock"},
            "Closed comparison report inventory",
        )
        require(
            all(not p.is_symlink() and p.is_file() for p in root.iterdir()),
            "Regular comparison report files",
        )
        require(bounded_read(root / ".writer.lock", 0) == b"", "Empty comparison lock")
        saved = decode(bounded_read(root / "report.json", MAX_BYTES))
        result = verify_comparison(
            baseline_archive, baseline_score, candidate_archive, candidate_score, saved
        )
        require(
            bounded_read(root / "report.md", MAX_BYTES) == markdown(result),
            "Regenerated comparison Markdown binding",
        )
    return result
