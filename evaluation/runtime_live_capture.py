"""Read-only native checkpoint verifier; recorded runtime pins grant no authority."""

from pathlib import Path

from execution_checkpoint import SnapshotStore, bounded_read
from execution_live_kernel import checkpoint, requirements, verify_normalization
from execution_plan import MAX_JOURNAL_BYTES, Store, prepare
from execution_records import digest
from execution_replay import replay
from offline_bundle import MAX_BYTES, canonical, object_keys, require, sha


def stage1_lineage(store, plan):
    """Rebuild the public projection, retaining the captured runtime dependency pin.

    Same trusted code is mandatory; a different reader Python is not a new source
    runtime attestation and cannot replace the immutable plan's dependency digest.
    """
    from execution_stage1_plan import build

    lineage = store.value(plan["pins"]["definitions"])
    object_keys(lineage, "schema sourcePlanDigest manifest metadata jobs options")
    require(
        lineage["schema"] == "normlab.stage1-native-lineage/v1", "Native Stage1 lineage"
    )
    source = {
        **lineage["metadata"],
        "jobs": [store.value(ref) for ref in lineage["jobs"]],
    }
    require(
        sha(canonical(source)) == lineage["sourcePlanDigest"],
        "Stage1 source plan digest",
    )
    expected, files = build(
        source, lineage["options"], store.artifact(lineage["manifest"])
    )
    expected["pins"]["dependencies"] = plan["pins"]["dependencies"]
    require(
        canonical(plan) == canonical(expected), "Recorded-runtime Stage1 projection"
    )
    for name, raw in files.items():
        require(store.read(name) == raw, "Exact Stage1 lineage bytes")


class NativeCapture:
    """Caller holds the source writer lock or an immutable archive lock.

    Never samples a clock, reads credentials, claims a UUID or constructs transport.
    Supported installed code is required; arbitrary producer code is never executed.
    """

    def __init__(self, root):
        root = Path(root)
        self.store = Store(root)
        metadata = {
            "intent.json": bounded_read(root / "intent.json", MAX_BYTES),
            "checkpoint.json": bounded_read(
                root / "checkpoint.json", MAX_JOURNAL_BYTES
            ),
        }
        self.store.files.update(metadata)
        self.store.total = sum(map(len, metadata.values()))
        self.raw = metadata["checkpoint.json"]
        self.checkpoint = Store.decode_json(self.raw)
        saved = self.checkpoint
        mode = saved.get("mode")
        object_keys(
            saved,
            "schema intentDigest codePins run journal"
            + (" mode" if mode is not None else ""),
        )
        require(
            saved["schema"]
            == (
                "normlab.live-checkpoint/v1"
                if mode is None
                else "normlab.live-checkpoint/v2"
            )
            and (mode is None or mode == "stage1-bounded-schedule/v1"),
            "Native checkpoint version/mode",
        )
        self.plan = prepare(self.store)
        self.intent = Store.decode_json(metadata["intent.json"])
        require(
            self.intent["evidenceKind"] == "live-capture"
            and self.intent["predecessor"] is None
            and saved["intentDigest"] == sha(metadata["intent.json"]),
            "Fresh native intent binding",
        )
        installed = requirements()
        pins = self.plan["pins"]
        require(
            pins["code"] == installed["code"]
            and all(
                arm["adapter"] == installed["adapter"] for arm in self.plan["arms"]
            ),
            "Supported native execution code/adapter pins",
        )
        object_keys(pins["dependencies"], "python-stdlib-runtime")
        digest(pins["dependencies"]["python-stdlib-runtime"])
        recorded = {
            "code": pins["code"],
            "dependencies": pins["dependencies"],
            "adapter": installed["adapter"],
        }
        require(
            canonical(saved["codePins"]) == canonical(recorded),
            "Recorded checkpoint/plan pins",
        )
        if mode is not None:
            stage1_lineage(self.store, self.plan)
        self.store.artifact(self.intent["permit"])
        replay(SnapshotStore(root, self.intent, []))
        self.events = saved["journal"]
        expected = checkpoint(self.intent, self.events, self.store, mode=mode)
        expected["codePins"] = recorded
        require(
            canonical(saved) == canonical(expected),
            "Regenerated native capture checkpoint",
        )
        require(
            mode is not None
            or sum(e["type"] == "attempt-reserved" for e in self.events) <= 1,
            "Native one-attempt denominator",
        )
        verify_normalization(self.plan, self.intent, self.events, self.store, mode=mode)
        self.report = replay(SnapshotStore(root, saved["run"], self.events))
        self.report["nativeBoundary"] = {
            "mode": mode or "fresh-one-attempt/v1",
            "resumeSupported": False,
            "historicalReplayOnly": True,
            "executionCodePinsMatched": True,
            "readerRuntimePinsMatched": pins["dependencies"]
            == installed["dependencies"],
            "recordedRuntimeVerified": False,
        }
