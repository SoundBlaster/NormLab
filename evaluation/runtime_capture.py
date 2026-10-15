"""Read-only capture revisions with explicit mock/native evidence boundaries."""

import copy
from types import MappingProxyType

from execution_checkpoint import reader_lock
from execution_continuation import Capture
from offline_bundle import (
    MAX_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    canonical,
    identity,
    require,
    sha,
)

SCHEMA = "normlab.runtime-capture/v1"


class RuntimeSnapshot:
    """Private validated state; callers receive copies and immutable byte inventory."""

    def __init__(self, capture):
        if type(capture) is Capture:
            evidence_kind = "mock"
        else:
            from runtime_live_capture import NativeCapture

            require(
                type(capture) is NativeCapture,
                "Validated native or mock capture required",
            )
            evidence_kind = "live-capture"
        # v1 replay and v2 replay may use separate caches. Explicitly collect every
        # journal-referenced artifact, including earlier unknown observations.
        for event in capture.events:
            for key in ("request", "control", "outcome"):
                ref = event.get(key)
                if ref is not None:
                    capture.store.artifact(ref)
            if event["outcome"] is not None:
                saved = capture.store.value(event["outcome"])
                for key in ("response", "result"):
                    if saved[key] is not None:
                        capture.store.artifact(saved[key])
        files = dict(capture.store.files)
        require(len(files) <= MAX_FILES, "Runtime snapshot file cap")
        sources = [
            {"path": path, "sha256": sha(raw), "bytes": len(raw)}
            for path, raw in sorted(files.items())
        ]
        binding = {"executionId": capture.intent["id"], "sources": sources}
        manifest = {
            "schema": SCHEMA
            if evidence_kind == "mock"
            else "normlab.runtime-capture/v2",
            "executionId": capture.intent["id"],
            "captureRevisionId": identity("capture", binding),
            "planDigest": capture.intent["planDigest"],
            "checkpointSchema": capture.checkpoint["schema"],
            "checkpointDigest": sha(capture.raw),
            "journalHead": capture.report["journalHead"],
            "state": capture.report["state"],
            "stopReason": capture.report["stopReason"],
            "evidenceKind": evidence_kind,
            "sourceFiles": sources,
            "inferenceCallsExecuted": 0,
            "executionReady": False,
            "semanticQualityEvidence": False,
        }
        if evidence_kind == "live-capture":
            manifest["recordedDependencies"] = capture.plan["pins"]["dependencies"]
            manifest["recordedDispatches"] = {
                "observed": capture.report["counts"]["observedDispatches"],
                "unknown": capture.report["unknownDispatchAttempts"],
            }
        raw = canonical(manifest)
        require(len(raw) <= MAX_BYTES, "Runtime manifest size cap")
        require(
            sum(map(len, files.values())) + len(raw) <= MAX_TOTAL_BYTES,
            "Runtime snapshot aggregate cap",
        )
        self._files = MappingProxyType(files)
        self._manifest = raw
        self._plan = copy.deepcopy(capture.plan)
        self._intent = copy.deepcopy(capture.intent)
        self._events = copy.deepcopy(capture.events)
        self._report = copy.deepcopy(capture.report)

    @property
    def files(self):
        return self._files

    @property
    def manifest(self):
        from execution_plan import Store

        return Store.decode_json(self._manifest)

    @property
    def plan(self):
        return copy.deepcopy(self._plan)

    @property
    def intent(self):
        return copy.deepcopy(self._intent)

    @property
    def events(self):
        return copy.deepcopy(self._events)

    @property
    def report(self):
        return copy.deepcopy(self._report)


def capture_runtime(root, *, evidence_kind="mock"):
    """Lock and validate once, then retain immutable source bytes in memory."""
    with reader_lock(root):
        require(
            evidence_kind in {"mock", "live-capture"}, "Explicit capture evidence kind"
        )
        if evidence_kind == "live-capture":
            from runtime_live_capture import NativeCapture

            return RuntimeSnapshot(NativeCapture(root))
        return RuntimeSnapshot(Capture(root))


def verify_capture_manifest(root, manifest, *, evidence_kind="mock"):
    """Compare with the current saved root, not with an untrusted supplied summary."""
    snapshot = capture_runtime(root, evidence_kind=evidence_kind)
    require(
        canonical(manifest) == canonical(snapshot.manifest),
        "Runtime capture manifest binding",
    )
    return snapshot
