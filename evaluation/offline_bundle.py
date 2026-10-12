"""Bounded, unsigned offline evidence bundles; stdlib only, no dispatch path."""

import hashlib
import json
import re

SCHEMA = "normlab.offline-bundle/v1"
TASK_SCHEMA = "normlab.offline-task/v1"
MAX_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_FILES = 4096
MAX_TASKS = 1024
ADAPTER_FILES = (
    "offline_adapters.py",
    "offline_bundle.py",
    "offline_contract.py",
    "offline_task_contract.py",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def identity(kind, value):
    return kind + "-" + sha(canonical(value))


def object_keys(value, keys):
    require(
        isinstance(value, dict) and set(value) == set(keys.split()), "Object fields"
    )


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("Nonfinite JSON")

    require(len(raw) <= MAX_BYTES, "Artifact byte limit")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def read(path):
    require(
        path.is_file() and path.stat().st_size <= MAX_BYTES, "Bounded file required"
    )
    raw = path.read_bytes()
    require(len(raw) <= MAX_BYTES, "Artifact grew beyond byte limit")
    return raw


def digest_value(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value)


def check_ref(ref):
    object_keys(ref, "path sha256 bytes")
    require(digest_value(ref["sha256"]), "Artifact digest")
    require(ref["path"] == f"artifacts/{ref['sha256']}.blob", "Content-addressed path")
    require(
        type(ref["bytes"]) is int and 0 <= ref["bytes"] <= MAX_BYTES, "Artifact size"
    )


class Builder:
    def __init__(self):
        self.files = {}
        self.total = 0

    def add(self, raw):
        require(isinstance(raw, bytes) and len(raw) <= MAX_BYTES, "Bounded bytes")
        digest = sha(raw)
        path = f"artifacts/{digest}.blob"
        if path not in self.files:
            require(len(self.files) < MAX_FILES, "Artifact count cap")
            require(self.total + len(raw) <= MAX_TOTAL_BYTES, "Bundle byte cap")
            self.files[path] = raw
            self.total += len(raw)
        return {"path": path, "sha256": digest, "bytes": len(raw)}

    def json(self, value):
        return self.add(canonical(value))

    def file(self, path, expected=None):
        raw = read(path)
        require(expected is None or sha(raw) == expected, "Source artifact drift")
        return self.add(raw)

    def value(self, ref):
        return decode(self.files[ref["path"]])

    def export(self, envelope, output):
        envelope = {
            **envelope,
            "artifacts": [
                {"path": path, "sha256": sha(raw), "bytes": len(raw)}
                for path, raw in sorted(self.files.items())
            ],
        }
        validate(envelope, lambda ref: self.files[ref["path"]])
        raw = canonical(envelope)
        require(len(raw) <= MAX_BYTES, "Bundle index byte cap")
        # Exclusive directory creation; no replacement or resume of old/partial exports.
        output.mkdir(mode=0o700, parents=True, exist_ok=False)
        (output / "artifacts").mkdir(mode=0o700)
        for path, data in self.files.items():
            with (output / path).open("xb") as handle:
                handle.write(data)
        # Commit marker written last. Failed exports remain visibly incomplete.
        with (output / "bundle.json").open("xb") as handle:
            handle.write(raw)
        return envelope


def validate(envelope, fetch):
    from offline_contract import validate as validate_contract

    return validate_contract(envelope, fetch)


def verify(folder):
    root = folder.resolve()
    index = (root / "bundle.json").resolve()
    require(index.is_relative_to(root), "Index escapes bundle")
    envelope = decode(read(index))

    def fetch(ref):
        check_ref(ref)
        path = (root / ref["path"]).resolve()
        require(path.is_relative_to(root), "Artifact escapes bundle")
        return read(path)

    return validate(envelope, fetch)
