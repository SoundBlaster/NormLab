"""Explicit dispatch for additive continuation consumers; frozen readers stay closed."""

from pathlib import Path

from execution_checkpoint import bounded_read
from execution_plan import Store
from offline_bundle import MAX_BYTES
from runtime_archive_reader import VerifiedArchive


def verified_archive(value):
    if type(value) is VerifiedArchive:
        return True
    from runtime_resume_archive import VerifiedResumeArchive

    return type(value) in (VerifiedArchive, VerifiedResumeArchive)


def version(archive):
    if type(archive) is VerifiedArchive:
        return 1 if archive.index["evidenceKind"] == "mock" else 2
    from offline_bundle import require
    from runtime_resume_archive import VerifiedResumeArchive

    require(type(archive) is VerifiedResumeArchive, "Verified archive version")
    return 3


def read_archive(root):
    index = Store.decode_json(bounded_read(Path(root) / "archive.json", MAX_BYTES))
    if index.get("schema") == "normlab.runtime-archive/v3":
        from runtime_resume_archive import read_archive as read
    else:
        from runtime_archive_reader import read_archive as read
    return read(root)


def archive_file_limit(archive, name):
    from runtime_resume_archive import VerifiedResumeArchive

    if type(archive) is VerifiedResumeArchive:
        from runtime_resume_archive import file_limit
    else:
        from runtime_archive_format import file_limit
    return file_limit(name)
