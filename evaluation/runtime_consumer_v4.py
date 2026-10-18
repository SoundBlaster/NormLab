"""Additive stop-control dispatch; the pinned v1/v2/v3 dispatcher stays unchanged."""

from pathlib import Path

import runtime_consumer as previous
from execution_checkpoint import bounded_read
from execution_plan import Store
from offline_bundle import MAX_BYTES


def verified_archive(value):
    from runtime_stop_archive import VerifiedStopArchive

    return type(value) is VerifiedStopArchive or previous.verified_archive(value)


def version(archive):
    from runtime_stop_archive import VerifiedStopArchive

    return 4 if type(archive) is VerifiedStopArchive else previous.version(archive)


def read_archive(root):
    index = Store.decode_json(bounded_read(Path(root) / "archive.json", MAX_BYTES))
    if index.get("schema") == "normlab.runtime-archive/v4":
        from runtime_stop_archive import read_archive as read

        return read(root)
    return previous.read_archive(root)


def archive_file_limit(archive, name):
    from runtime_stop_archive import VerifiedStopArchive, file_limit

    return (
        file_limit(name)
        if type(archive) is VerifiedStopArchive
        else previous.archive_file_limit(archive, name)
    )
