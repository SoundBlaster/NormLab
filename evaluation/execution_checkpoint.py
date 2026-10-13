"""Atomic mock checkpoints and bounded read-only replay; POSIX local files only."""

import copy
import fcntl
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from execution_plan import MAX_JOURNAL_BYTES, Store
from execution_records import CAP_FIELDS, run_shape
from execution_replay import replay
from offline_bundle import (
    MAX_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    canonical,
    object_keys,
    require,
    sha,
)

CHECKPOINT = "normlab.mock-checkpoint/v1"
VIEW_FIELDS = {"journalHead", "lastClockNs", "state", "stopReason", "counts"}


def bounded_read(path, limit):
    with os.fdopen(
        os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb"
    ) as handle:
        info = os.fstat(handle.fileno())
        require(
            stat.S_ISREG(info.st_mode) and info.st_size <= limit,
            "Bounded regular mock file",
        )
        raw = handle.read(limit + 1)
    require(len(raw) <= limit, "Mock file grew beyond cap")
    return raw


@contextmanager
def reader_lock(root):
    """Reject an active writer; inspection never writes or acquires execution authority."""
    with os.fdopen(
        os.open(
            Path(root) / ".writer.lock", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        ),
        "rb",
    ) as handle:
        require(stat.S_ISREG(os.fstat(handle.fileno()).st_mode), "Regular writer lock")
        fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
        yield


class SnapshotStore(Store):
    def __init__(self, root, run, journal):
        super().__init__(root)
        self.snapshot = {"run.json": canonical(run), "journal.json": canonical(journal)}

    def read(self, name):
        if name in self.snapshot:
            return self.snapshot[name]
        return super().read(name)


def build_checkpoint(intent, events, store, script_digest):
    """Build a candidate view, then use the strict 5a reader before publication."""
    run = copy.deepcopy(intent)
    counts = {
        "reserved": {key: 0 for key in CAP_FIELDS.split()},
        "observedDispatches": 0,
        "knownInputTokens": 0,
        "knownOutputTokens": 0,
        "unknownUsageAttempts": 0,
    }
    attempts, active, stopped = {}, None, None
    for event in events:
        if event["type"] == "attempt-reserved":
            active = event["attemptId"]
            attempts[active] = None
            for key, value in event["budgetDelta"].items():
                counts["reserved"][key] += value
        elif event["type"] in {"attempt-observed", "attempt-terminal"}:
            attempts[event["attemptId"]] = store.value(event["outcome"])
            if event["type"] == "attempt-terminal":
                active = None
        else:
            stopped = event["stopReason"]
    for saved in attempts.values():
        if saved is None:
            counts["unknownUsageAttempts"] += 1
            continue
        counts["observedDispatches"] += saved["dispatchObserved"] is True
        counts["unknownUsageAttempts"] += any(
            value is None for value in saved["usage"].values()
        )
        for key, total in (
            ("inputTokens", "knownInputTokens"),
            ("outputTokens", "knownOutputTokens"),
        ):
            if saved["usage"][key] is not None:
                counts[total] += saved["usage"][key]
    run.update(
        journalHead=events[-1]["id"] if events else None,
        lastClockNs=events[-1]["clockNs"] if events else intent["clock"]["startNs"],
        state="finished"
        if stopped
        else "paused-unknown"
        if active
        else "running"
        if events
        else "created",
        stopReason=stopped or ("unknown-outcome" if active else None),
        counts=counts,
    )
    replay(SnapshotStore(store.root, run, events))
    return {
        "schema": CHECKPOINT,
        "intentDigest": sha(canonical(intent)),
        "scriptDigest": script_digest,
        "run": run,
        "journal": events,
    }


def load_checkpoint(root):
    """Caller must hold the writer or shared reader lock; no repair or resume."""
    root = Path(root)
    raw = {
        name: bounded_read(root / name, limit)
        for name, limit in (
            ("intent.json", MAX_BYTES),
            ("mock-script.json", MAX_BYTES),
            ("checkpoint.json", MAX_JOURNAL_BYTES),
        )
    }
    intent = Store.decode_json(raw["intent.json"])
    checkpoint = Store.decode_json(raw["checkpoint.json"])
    object_keys(checkpoint, "schema intentDigest scriptDigest run journal")
    require(checkpoint["schema"] == CHECKPOINT, "Mock checkpoint schema")
    require(
        checkpoint["intentDigest"] == sha(raw["intent.json"])
        and checkpoint["scriptDigest"] == sha(raw["mock-script.json"]),
        "Immutable intent/script binding",
    )
    run = checkpoint["run"]
    require(isinstance(run, dict) and isinstance(intent, dict), "Mock intent/run")
    require(
        {k: v for k, v in run.items() if k not in VIEW_FIELDS}
        == {k: v for k, v in intent.items() if k not in VIEW_FIELDS},
        "Immutable execution binding",
    )
    require(
        run["evidenceKind"] == "mock"
        and run["permit"] is None
        and run["predecessor"] is None,
        "Mock-only fresh execution",
    )
    store = SnapshotStore(root, run, checkpoint["journal"])
    store.files.update(raw)
    store.total = sum(map(len, raw.values()))
    require(store.total <= MAX_TOTAL_BYTES, "Mock checkpoint byte cap")
    plan = store.json("plan.json")
    run_shape(intent, plan)
    require(
        intent["state"] == "created" and intent["journalHead"] is None, "Initial intent"
    )
    replay(SnapshotStore(root, intent, []))
    report = replay(store)
    report["mockExecution"] = {
        "checkpointSchema": CHECKPOINT,
        "scriptDigest": checkpoint["scriptDigest"],
        "clockSimulated": True,
        "durabilityPolicy": "posix-fsync-atomic-checkpoint/v1",
        "committedMockOutcomes": sum(
            e["type"] == "attempt-terminal" for e in checkpoint["journal"]
        ),
        "resumeSupported": False,
    }
    return checkpoint, report


def inspect_checkpoint(root):
    with reader_lock(root):
        return load_checkpoint(root)[1]


class DurableWriter:
    """Fresh directory, exclusive local lock, immutable artifacts, atomic checkpoint."""

    def __init__(self, output, hook=None):
        self.root = Path(output)
        self.hook = hook or (lambda point: None)
        self.lock = None
        self.poisoned = False
        self.inventory = {}

    @staticmethod
    def flush_directory(path):
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def __enter__(self):
        require(self.lock is None and not self.poisoned, "Fresh healthy mock writer")
        require(os.name == "posix", "POSIX mock writer required")
        parent = self.root.parent.resolve(strict=True)
        self.root = parent / self.root.name
        self.root.mkdir(mode=0o700)  # Never reopen or overwrite an existing execution.
        try:
            self.flush_directory(parent)
            self.lock = os.open(
                self.root / ".writer.lock",
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.fsync(self.lock)
            (self.root / "artifacts").mkdir(mode=0o700)
            self.flush_directory(self.root)
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *_):
        if self.lock is not None:
            os.close(self.lock)
            self.lock = None

    def publish(self, name, raw, *, phase, replace=False):
        require(
            self.lock is not None and not self.poisoned, "Healthy exclusive mock writer"
        )
        require(
            name in {"plan.json", "intent.json", "mock-script.json", "checkpoint.json"}
            or (name.startswith("artifacts/") and len(Path(name).parts) == 2),
            "Mock publication path",
        )
        require(
            replace == (name == "checkpoint.json"), "Only checkpoint can be replaced"
        )
        limit = MAX_JOURNAL_BYTES if replace else MAX_BYTES
        require(len(raw) <= limit, "Mock publication size cap")
        require(
            name in self.inventory or len(self.inventory) < MAX_FILES,
            "Mock publication count cap",
        )
        require(
            sum(self.inventory.values()) - self.inventory.get(name, 0) + len(raw)
            <= MAX_TOTAL_BYTES,
            "Mock publication byte cap",
        )
        path = self.root / name
        temporary = path.parent / (".pending-" + str(uuid4()))
        try:
            self.hook(phase + ":before-write")
            with os.fdopen(
                os.open(
                    temporary,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                ),
                "wb",
            ) as handle:
                handle.write(raw)
                self.hook(phase + ":before-file-flush")
                handle.flush()
                os.fsync(handle.fileno())
                self.hook(phase + ":after-file-flush")
            if replace:
                os.replace(temporary, path)
            else:
                os.link(temporary, path, follow_symlinks=False)
                temporary.unlink()
            self.hook(phase + ":after-replace")
            self.flush_directory(path.parent)
            self.hook(phase + ":after-directory-flush")
            self.inventory[name] = len(raw)
        except BaseException:
            self.poisoned = True
            raise  # Preserve both committed and uncommitted bytes for inspection.

    def put(self, raw, *, phase):
        require(
            self.lock is not None and not self.poisoned, "Healthy exclusive mock writer"
        )
        ref = {
            "path": f"artifacts/{sha(raw)}.blob",
            "sha256": sha(raw),
            "bytes": len(raw),
        }
        if ref["path"] in self.inventory:
            require(
                Store(self.root).artifact(ref) == raw, "Existing immutable artifact"
            )
        else:
            self.publish(ref["path"], raw, phase=phase)
        return ref
