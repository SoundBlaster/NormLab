"""Contract tests plus real Mellea sampling with a fixed DummyBackend."""

import asyncio
import copy
import importlib.util
import json
import unittest
from types import SimpleNamespace

from mellea_candidate import (
    bound_fragments,
    fixture_backend,
    parse_candidate,
    run_candidate,
    sha,
)

SOURCE = "Я оплатил парковку. В письме: парковка не оплачена."
REQUEST = {"narrative": SOURCE, "sourceDigest": sha(SOURCE.encode())}
FRAGMENTS = [
    {
        "fragmentId": f"fragment_{i + 1}",
        "quote": quote,
        "attributes": {
            "subject": "vehicle_1",
            "aboutEpisode": "episode_1",
            "speaker": "narrator" if i == 0 else "letter_1",
        },
    }
    for i, quote in enumerate(
        ["Я оплатил парковку.", "В письме: парковка не оплачена."]
    )
]
PARENT = {"sourceDigest": REQUEST["sourceDigest"], "fragments": FRAGMENTS}
VALID = json.dumps(
    {
        "results": {
            f["fragmentId"]: {
                "status": "classified",
                "reason": "",
                "classifications": [
                    {
                        "predicate": "payment",
                        "stance": "asserted" if i == 0 else "denied",
                        "valueText": f["quote"],
                    }
                ],
            }
            for i, f in enumerate(FRAGMENTS)
        }
    },
    ensure_ascii=False,
)


class ContractTests(unittest.TestCase):
    def test_bound_source_and_complete_contract(self):
        source, fragments = bound_fragments(REQUEST, PARENT)
        self.assertEqual(source, SOURCE)
        self.assertEqual(len(parse_candidate(VALID, fragments)[0]), 2)

    def test_source_binding_quotes_and_attribution_fail_before_generation(self):
        for mutation in ("digest", "quote", "duplicate", "speaker", "subject"):
            parent = copy.deepcopy(PARENT)
            if mutation == "digest":
                parent["sourceDigest"] = "0" * 64
            elif mutation == "quote":
                parent["fragments"][0]["quote"] = "Invented"
            elif mutation == "duplicate":
                parent["fragments"].append(parent["fragments"][0])
            else:
                parent["fragments"][0]["attributes"][mutation] = (
                    "" if mutation == "speaker" else "unknown-person"
                )
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                bound_fragments(REQUEST, parent)

    def test_missing_fragment_and_unsupported_predicate(self):
        for mutation in ("missing", "predicate"):
            parsed = json.loads(VALID)
            if mutation == "missing":
                del parsed["results"]["fragment_2"]
            else:
                parsed["results"]["fragment_1"]["classifications"][0]["predicate"] = (
                    "invented"
                )
            with self.assertRaises(ValueError):
                parse_candidate(json.dumps(parsed), FRAGMENTS)


@unittest.skipUnless(
    importlib.util.find_spec("mellea"), "Optional Mellea runtime not installed"
)
class SamplingTests(unittest.TestCase):
    def run_arm(self, arm, candidates, verifier=None):
        from mellea import MelleaSession

        backend = fixture_backend(candidates)
        result = asyncio.run(
            run_candidate(
                MelleaSession(backend=backend), REQUEST, PARENT, arm, verifier
            )
        )
        return result, backend

    def test_baseline_does_not_repair_or_expose_fallback(self):
        result, backend = self.run_arm("baseline", ["{}", VALID])
        self.assertFalse(result["accepted"])
        self.assertEqual(result["statements"], [])
        self.assertEqual(backend.idx, 1)

    def test_one_repair_preserves_quote_attribution_and_pending_review(self):
        result, backend = self.run_arm("deterministic", ["{}", VALID])
        self.assertTrue(result["accepted"])
        self.assertEqual(backend.idx, 2)
        self.assertEqual(
            [s["stance"] for s in result["statements"]], ["asserted", "denied"]
        )
        self.assertEqual(
            [s["speaker"] for s in result["statements"]], ["narrator", "letter_1"]
        )
        self.assertTrue(all(s["decision"] == "pending" for s in result["statements"]))
        self.assertEqual(len(result["validationAttempts"]), 2)
        self.assertIsNone(result["cost"])

    def test_exhausted_budget_returns_no_statements(self):
        result, backend = self.run_arm("deterministic", ["{}", "{}", VALID])
        self.assertFalse(result["accepted"])
        self.assertEqual(backend.idx, 2)
        self.assertEqual(result["statements"], [])

    def test_semantic_failure_repairs_but_uncertainty_and_error_stop(self):
        class Verifier:
            def __init__(self, outcomes):
                self.outcomes = iter(outcomes)
                self.calls = 0

            def evaluate(self, _candidate):
                self.calls += 1
                outcome = next(self.outcomes)
                if outcome == "error":
                    raise RuntimeError("Fixture transport failure")
                return SimpleNamespace(
                    outcome=outcome,
                    p_yes={"pass": 0.98, "fail": 0.02, "uncertain": 0.5}[outcome],
                )

        verifier = Verifier(["fail", "pass"])
        result, backend = self.run_arm("jev", [VALID, VALID], verifier)
        self.assertTrue(result["accepted"])
        self.assertEqual((backend.idx, verifier.calls), (2, 2))
        for outcome in ("uncertain", "error"):
            verifier = Verifier([outcome, "pass"])
            result, backend = self.run_arm("jev", [VALID, VALID], verifier)
            self.assertFalse(result["accepted"])
            self.assertEqual((backend.idx, verifier.calls), (1, 1))
            self.assertEqual(result["statements"], [])
            verifier = Verifier(["fail", outcome, "pass"])
            result, backend = self.run_arm("jev", [VALID, VALID, VALID], verifier)
            self.assertFalse(result["accepted"])
            self.assertEqual((backend.idx, verifier.calls), (2, 2))
            self.assertEqual(result["statements"], [])

    def test_async_generation_deadline_does_not_start_repair(self):
        from mellea import MelleaSession

        backend = fixture_backend([VALID])
        original = backend._generate_from_context

        async def slow(*args, **kwargs):
            await asyncio.sleep(0.1)
            return await original(*args, **kwargs)

        backend._generate_from_context = slow
        result = asyncio.run(
            run_candidate(
                MelleaSession(backend=backend),
                REQUEST,
                PARENT,
                "deterministic",
                timeout=0.01,
            )
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["error"], "TimeoutError")
        self.assertEqual(result["statements"], [])
        self.assertEqual(backend.idx, 0)


if __name__ == "__main__":
    unittest.main()
