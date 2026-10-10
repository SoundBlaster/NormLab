"""V3 audit resists a rehashed fixture catalog that diverges from runtime."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from audit_stage1_v3 import audit
from classification_v3 import build_schema
from harness import digest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/parking-pilot/stage1-audit-v2"


class Stage1AuditV3Tests(unittest.TestCase):
    def test_report_identifies_v3_catalog_contract_and_pins(self):
        report = audit(FIXTURE / "experiment.json")
        self.assertEqual(report["schema"], "normlab.stage1-audit-report/v3")
        self.assertEqual(
            report["runtimeCatalogSha256"],
            digest((FIXTURE.parents[2] / "server/inference-prompts.json").read_bytes()),
        )
        self.assertIn("evaluation/audit_stage1_v3.py", report["auditorCodePins"])

    def test_rehashed_fixture_cannot_replace_pinned_runtime_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dataset"
            shutil.copytree(FIXTURE, root)
            definitions_path = root / "definitions.json"
            definitions = json.loads(definitions_path.read_bytes())
            definitions["payment"] = "Adversarial replacement definition."
            definitions_path.write_text(json.dumps(definitions, ensure_ascii=False))
            schema_path = root / "classification-schema.json"
            schema_path.write_text(
                json.dumps(
                    build_schema(["fragment_1"], definitions), ensure_ascii=False
                )
            )
            manifest_path = root / "experiment.json"
            manifest = json.loads(manifest_path.read_bytes())
            for name in ("definitions", "classification-schema"):
                manifest["artifacts"][name]["sha256"] = digest(
                    (root / f"{name}.json").read_bytes()
                )
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "differs from pinned runtime"):
                audit(manifest_path)


if __name__ == "__main__":
    unittest.main()
