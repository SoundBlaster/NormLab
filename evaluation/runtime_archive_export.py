"""Fresh local durable archive publication; existing/partial exports never resume."""

import fcntl
import os
from pathlib import Path
from uuid import uuid4

from execution_checkpoint import DurableWriter
from offline_bundle import require, sha
from runtime_archive_format import (
    ArchivePlan,
    check_index,
    directories,
    prepare_archive,
    producer_pins,
)
from runtime_capture import capture_runtime
from runtime_export import prepare_export


def validate_plan(plan):
    require(type(plan) is ArchivePlan, "Validated archive plan required")
    inventory = check_index(plan.index)
    require(
        plan.index["producerPins"] == producer_pins(), "Current trusted producer pins"
    )
    require(set(plan.files) == set(inventory), "Complete archive publication inventory")
    for name, raw in plan.files.items():
        ref = inventory[name]
        require(
            type(raw) is bytes
            and len(raw) == ref["bytes"]
            and sha(raw) == ref["sha256"],
            "Exact archive publication bytes",
        )


class ArchiveWriter:
    def __init__(self, output, hook=None):
        self.root = Path(output)
        self.hook = hook or (lambda point: None)
        self.lock = None
        self.poisoned = False
        self.committed = False

    def __enter__(self):
        require(
            os.name == "posix"
            and self.lock is None
            and not self.poisoned
            and not self.committed,
            "Fresh POSIX archive writer",
        )
        self.root = self.root.parent.resolve(strict=True) / self.root.name
        self.root.mkdir(mode=0o700)
        try:
            DurableWriter.flush_directory(self.root.parent)
            self.hook("root:after-parent-flush")
            self.lock = os.open(
                self.root / ".writer.lock",
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.fsync(self.lock)
            DurableWriter.flush_directory(self.root)
            self.hook("lock:after-flush")
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *_):
        if self.lock is not None:
            os.close(self.lock)
            self.lock = None

    def _write_file(self, name, raw, phase):
        require(
            self.lock is not None and not self.poisoned and not self.committed,
            "Healthy archive publication phase",
        )
        with os.fdopen(
            os.open(
                self.root / name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            ),
            "wb",
        ) as handle:
            self.hook(phase + ":before-write")
            require(handle.write(raw) == len(raw), "Full archive file write")
            handle.flush()
            self.hook(phase + ":before-file-flush")
            os.fsync(handle.fileno())
            self.hook(phase + ":after-file-flush")
        DurableWriter.flush_directory((self.root / name).parent)
        self.hook(phase + ":after-directory-flush")

    def publish(self, plan):
        require(
            self.lock is not None and not self.poisoned and not self.committed,
            "Healthy exclusive archive writer",
        )
        validate_plan(plan)
        try:
            for name in sorted(
                directories(plan.files), key=lambda value: (value.count("/"), value)
            ):
                (self.root / name).mkdir(mode=0o700)
                DurableWriter.flush_directory((self.root / name).parent)
            self.hook("directories:after-flush")
            for name, raw in sorted(plan.files.items()):
                self._write_file(name, raw, "content")
            self.hook("before-marker")
            temporary = ".pending-" + str(uuid4())
            self._write_file(temporary, plan.index_bytes, "marker")
            os.replace(self.root / temporary, self.root / "archive.json")
            self.hook("marker:after-replace")
            DurableWriter.flush_directory(self.root)
            self.hook("marker:after-directory-commit")
            self.committed = True
        except BaseException:
            self.poisoned = True
            raise


def export_archive(plan, output, *, hook=None):
    validate_plan(plan)  # Reject before output creation.
    with ArchiveWriter(output, hook) as writer:
        writer.publish(plan)
    return {
        "archiveId": plan.index["archiveId"],
        "captureRevisionId": plan.index["captureRevisionId"],
        "durabilityAcknowledged": True,
        "inferenceCallsExecuted": 0,
    }


def export_runtime_archive(source, output, *, hook=None):
    return export_archive(
        prepare_archive(prepare_export(capture_runtime(source))), output, hook=hook
    )
