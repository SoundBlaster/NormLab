"""Offline regression for streamed SDK requests and stop-on-failure capture."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx2
from provider_config import configuration
from provider_smoke import read_json, run


class ProviderSmokeTests(unittest.TestCase):
    def test_streamed_requests_are_captured_and_http_failure_stops_both_formats(self):
        data = read_json(Path(__file__).parents[1] / "fixtures/providers/smoke.json")
        key = "offline-placeholder-not-a-real-credential"
        for preset in ("coreinfra-jev", "coreinfra-decisions"):
            with self.subTest(preset=preset), tempfile.TemporaryDirectory() as temp:
                config = configuration(preset, key_env="NORMLAB_OFFLINE_TEST_KEY")
                received = []

                def reject(request):
                    received.append(json.loads(request.read()))
                    return httpx2.Response(503, json={"error": "unavailable"})

                with patch.dict(os.environ, {config.key_env: key}):
                    report = run(
                        config,
                        data,
                        Path(temp) / "capture",
                        3,
                        transport=httpx2.MockTransport(reject),
                    )
                self.assertEqual(len(received), 1)
                self.assertEqual(report["calls"], 1)
                self.assertEqual(report["requests"][0]["httpStatus"], 503)
                self.assertEqual(report["requests"][0]["body"], received[0])
                self.assertEqual(received[0]["model"], config.model)
                self.assertEqual(report["records"]["payment_claim"]["status"], "failed")
                self.assertEqual(
                    report["records"]["vehicle_match"]["status"], "not-executed"
                )
                self.assertEqual(
                    report["records"]["certainty"]["status"], "not-executed"
                )
                self.assertNotIn("configurationError", report)
                self.assertNotIn(key, json.dumps(report))
                saved = json.loads((Path(temp) / "capture/report.json").read_text())
                self.assertEqual(saved, report)


if __name__ == "__main__":
    unittest.main()
