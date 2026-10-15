"""Persistent local run-ID reservation; no refund, renewal or cross-host claim."""

import os
from pathlib import Path

from execution_checkpoint import DurableWriter
from execution_records import run_id
from offline_bundle import MAX_BYTES, canonical, require

AUTHORITY_ROOT = Path.home() / ".local/share/normlab/execution-authority/v1"


def claim_run(intent, input_root, output):
    root, target = AUTHORITY_ROOT.absolute(), Path(output).resolve()
    require(root.resolve() == root, "Authority path must not contain symlink aliases")
    require(
        not root.is_relative_to(input_root)
        and not input_root.is_relative_to(root)
        and not root.is_relative_to(target)
        and not target.is_relative_to(root),
        "Authority outside input/output trees",
    )
    run_id(intent["id"])
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = root.stat()
    require(
        info.st_uid == os.geteuid() and info.st_mode & 0o077 == 0,
        "Owner-private authority directory",
    )
    raw = canonical(
        {
            "schema": "normlab.local-run-claim/v1",
            "runId": intent["id"],
            "planDigest": intent["planDigest"],
            "permitDigest": intent["permit"]["sha256"],
            "output": str(target),
        }
    )
    require(len(raw) <= MAX_BYTES, "Authority claim byte cap")
    path = root / (intent["id"] + ".json")
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
    ) as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    for directory in (root, *root.parents):
        DurableWriter.flush_directory(directory)
    # A partial claim after a crash also blocks reuse: never assume it was unsent.
