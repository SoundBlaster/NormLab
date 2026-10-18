"""Offline fresh score export and exact replay verification; no provider SDK."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from offline_bundle import canonical, decode, read
from runtime_consumer import read_archive
from runtime_reference import reference
from runtime_score import score, verify_score


def publish(value, output):
    """Link a fully flushed temporary file to a fresh name; never overwrite."""
    raw = canonical(value)
    parent = output.parent.resolve(strict=True)
    target = parent / output.name
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=parent, prefix=".runtime-score-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)
        descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def brief(view):
    return {
        key: view[key]
        for key in (
            "schema",
            "scoreId",
            "archiveId",
            "captureRevisionId",
            "summary",
            "evidenceKind",
            "semanticQualityEvidence",
            "executionReady",
            "inferenceCallsExecuted",
        )
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("score")
    export.add_argument("archive", type=Path)
    export.add_argument("labels", type=Path)
    export.add_argument("--review", type=Path, action="append", default=[])
    export.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("archive", type=Path)
    verify.add_argument("score", type=Path)
    args = parser.parse_args()
    try:
        # Reject an invalid capture before opening labels or saved reference inputs.
        archive = read_archive(args.archive)
        if args.command == "score":
            from offline_bundle import require

            archive_root = args.archive.resolve(strict=True)
            require(
                not args.output.parent.resolve(strict=True).is_relative_to(archive_root)
                and not args.output.resolve().is_relative_to(archive_root),
                "Score output must be outside archive",
            )
            require(len(args.review) <= 16, "Review inventory cap")
            selected = reference(
                archive, read(args.labels), [read(path) for path in args.review]
            )
            view = score(archive, selected)
            publish(view, args.output)
        else:
            view = verify_score(archive, decode(read(args.score)))
        print(json.dumps(brief(view), ensure_ascii=False))
    except Exception as error:
        print("Runtime score failed: " + type(error).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
