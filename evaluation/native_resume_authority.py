"""Verify an existing owner-private local run claim; never create or renew it."""

import os
import stat

import execution_live_authority as authority
from execution_checkpoint import bounded_read
from offline_bundle import MAX_BYTES, canonical, require


def verify_claim(intent, output):
    root = authority.AUTHORITY_ROOT.absolute()
    require(root.resolve(strict=True) == root, "Unaliased existing authority directory")
    target = output.resolve(strict=True)
    require(
        not root.is_relative_to(target) and not target.is_relative_to(root),
        "Authority outside native execution tree",
    )
    for path in (root, root / (intent["id"] + ".json")):
        info = path.lstat()
        require(
            (stat.S_ISDIR(info.st_mode) if path == root else stat.S_ISREG(info.st_mode))
            and info.st_uid == os.geteuid()
            and info.st_mode & 0o077 == 0,
            "Existing regular owner-private native run claim",
        )
    require(
        bounded_read(root / (intent["id"] + ".json"), MAX_BYTES)
        == canonical(
            {
                "schema": "normlab.local-run-claim/v1",
                "runId": intent["id"],
                "planDigest": intent["planDigest"],
                "permitDigest": intent["permit"]["sha256"],
                "output": str(target),
            }
        ),
        "Exact existing native claim/run/plan/permit/output continuity",
    )
