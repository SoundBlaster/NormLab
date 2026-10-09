"""Regression for the schema actually passed to Mellea generation, without HTTP."""

import asyncio
import importlib.util
import json
import unittest
from unittest.mock import AsyncMock

from mellea_candidate_v2 import (
    INSTRUCTION,
    SEMANTIC_REQUIREMENT,
    fixture_backend,
    run_candidate,
    sha,
)
from test_mellea_candidate import PARENT, REQUEST, VALID


@unittest.skipUnless(importlib.util.find_spec("mellea"), "Optional Mellea runtime")
class PromptContractTests(unittest.TestCase):
    def test_actual_generation_matches_recorded_contract_in_every_arm(self):
        from types import SimpleNamespace

        from mellea import MelleaSession

        class Verifier:
            def evaluate(self, _text):
                return SimpleNamespace(outcome="pass", p_yes=0.98)

        for arm in ("baseline", "deterministic", "jev"):
            with self.subTest(arm=arm):
                backend = fixture_backend([VALID])
                backend._generate_from_context = AsyncMock(
                    wraps=backend._generate_from_context
                )
                session = MelleaSession(backend=backend)
                session.ainstruct = AsyncMock(wraps=session.ainstruct)
                result = asyncio.run(
                    run_candidate(session, REQUEST, PARENT, arm, Verifier())
                )
                self.assertTrue(result["accepted"])
                self.assertEqual(result["schema"], "normlab.mellea-classification/v2")
                self.assertTrue(result["pipeline"].endswith("-v2"))
                sent = session.ainstruct.call_args
                self.assertEqual(sent.args, (INSTRUCTION,))
                self.assertIn("{{schema}}", INSTRUCTION)
                variables = sent.kwargs["user_variables"]
                self.assertEqual(variables, result["userVariables"])
                action = backend._generate_from_context.call_args.args[0]
                rendered = action.format_for_llm().args["description"]
                self.assertIn(variables["schema"], rendered)
                self.assertIn(variables["fragments"], rendered)
                self.assertNotIn("{{schema}}", rendered)
                self.assertNotIn("{{fragments}}", rendered)
                self.assertEqual(
                    json.loads(variables["schema"]), result["classificationSchema"]
                )
                self.assertEqual(
                    json.loads(variables["fragments"]), PARENT["fragments"]
                )
                contract = {
                    "instruction": sent.args[0],
                    "userVariables": variables,
                    "semantic": SEMANTIC_REQUIREMENT if arm == "jev" else None,
                }
                self.assertEqual(
                    result["promptDigest"],
                    sha(
                        json.dumps(
                            contract,
                            ensure_ascii=False,
                            sort_keys=True,
                        ).encode()
                    ),
                )


if __name__ == "__main__":
    unittest.main()
