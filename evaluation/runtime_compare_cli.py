"""Offline runtime comparison/export and source-bound replay verification."""

import argparse
import json
import sys
from pathlib import Path

from offline_bundle import decode, read, require
from runtime_archive_reader import read_archive
from runtime_compare import compare
from runtime_compare_report import export, verify_export


def brief(result):
    return {
        k: result[k]
        for k in (
            "schema",
            "comparisonId",
            "policy",
            "summary",
            "operational",
            "globalIncompatibilities",
            "semanticQualityEvidence",
            "inferenceCallsExecuted",
        )
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("compare", "verify"):
        command = commands.add_parser(name)
        for field in (
            "baseline_archive",
            "baseline_score",
            "candidate_archive",
            "candidate_score",
        ):
            command.add_argument(field, type=Path)
        if name == "compare":
            command.add_argument(
                "--context",
                choices=["strict-wire", "same-protocol-body"],
                default="strict-wire",
            )
            command.add_argument(
                "--vary",
                choices=["provider", "strategy", "tactic"],
                action="append",
                default=[],
            )
            command.add_argument("--output", type=Path)
        else:
            command.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        baseline, candidate = (
            read_archive(args.baseline_archive),
            read_archive(args.candidate_archive),
        )
        if args.command == "compare" and args.output is not None:
            target = args.output.resolve()
            require(
                not any(
                    target.is_relative_to(path.resolve())
                    for path in (args.baseline_archive, args.candidate_archive)
                ),
                "Report outside both archives",
            )
        baseline_score, candidate_score = (
            decode(read(args.baseline_score)),
            decode(read(args.candidate_score)),
        )
        if args.command == "compare":
            result = compare(
                baseline,
                baseline_score,
                candidate,
                candidate_score,
                context=args.context,
                vary=args.vary,
            )
            if args.output is not None:
                export(result, args.output)
        else:
            result = verify_export(
                args.report, baseline, baseline_score, candidate, candidate_score
            )
        print(json.dumps(brief(result), ensure_ascii=False))
    except Exception as error:
        print("Runtime comparison failed: " + type(error).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
