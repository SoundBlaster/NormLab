"""Pinned Stage1 compilation, full corpus export and mutation rejection, offline."""

import copy
import unittest
from unittest.mock import patch

from execution_plan import Store
from execution_stage1_plan import build, compile_stage1, ordered, verify_stage1
from execution_test_support import ROOT, ExecutionCase, canonical
from stage1_provider_plan import ARMS
from stage1_provider_plan import prepare as source_prepare

MANIFEST = ROOT / "fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json"


def options():
    return {
        "acceptedModels": {
            arm: ["jev-1.13.0"] if arm == ARMS[0] else ["gpt-6-luna"] for arm in ARMS
        },
        "inputTokenCap": 20000,
        "decisionOutputTokenCap": 1024,
    }


class Stage1NativePlanTests(ExecutionCase):
    def test_pilot_and_corpus_preserve_exact_requests_rotation_and_denominators(self):
        with patch(
            "socket.create_connection", side_effect=AssertionError("network denied")
        ):
            for profile, count in (("pilot", 36), ("corpus", 288)):
                output = self.root / profile
                report = compile_stage1(MANIFEST, output, options(), profile=profile)
                plan, source = verify_stage1(Store(output))
                self.assertEqual(report["tasks"], count)
                self.assertEqual(report["authorizedDispatches"], 0)
                self.assertEqual(plan["caps"]["dispatches"], count)
                self.assertFalse((output / "run.json").exists())
                self.assertEqual(len(source["jobs"]), count)
                for task, job in zip(plan["tasks"], source["jobs"]):
                    request = Store(output).value(task["request"])
                    self.assertEqual(
                        ordered(request["body"]), ordered(job["request"]["body"])
                    )
                    self.assertEqual(task["key"], job["jobId"])
                    self.assertEqual(task["armId"], job["armId"])
                    self.assertEqual(task["source"]["sha256"], job["sourceDigest"])
                self.assertLess((output / "plan.json").stat().st_size, 2 * 1024 * 1024)
                self.assertTrue(
                    all(
                        p.stat().st_size <= 2 * 1024 * 1024
                        for p in (output / "artifacts").iterdir()
                    )
                )

    def test_corrupt_context_and_metadata_reject_after_rehash(self):
        output = self.root / "mutation"
        compile_stage1(MANIFEST, output, options())
        path = output / "plan.json"
        plan = Store(output).json("plan.json")
        for field in ("key", "caseId", "repeat", "armId"):
            value = copy.deepcopy(plan)
            value["tasks"][0][field] = 99 if field == "repeat" else "edited"
            path.write_bytes(canonical(value))
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify_stage1(Store(output))
        path.write_bytes(canonical(plan))
        self.assertEqual(verify_stage1(Store(output))[0], plan)

    def test_source_request_cannot_be_rewritten_internally(self):
        source = source_prepare(MANIFEST)
        source["jobs"][0]["request"]["body"]["state"]["sourceText"] = "Changed"
        with self.assertRaises(ValueError):
            build(source, options(), MANIFEST.read_bytes())

    def test_explicit_acceptance_and_fresh_output_required(self):
        source = source_prepare(MANIFEST)
        for key in ("acceptedModels", "inputTokenCap", "decisionOutputTokenCap"):
            value = options()
            del value[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                build(source, value, MANIFEST.read_bytes())
        output = self.root / "fresh"
        compile_stage1(MANIFEST, output, options())
        with self.assertRaises(FileExistsError):
            compile_stage1(MANIFEST, output, options())


if __name__ == "__main__":
    unittest.main()
