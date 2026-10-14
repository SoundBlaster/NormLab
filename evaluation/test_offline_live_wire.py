"""Native protocol and HTTP control flow with offline socket-denying fixtures."""

import copy
import json
import unittest
from unittest.mock import patch

from execution_live_http import NativeHTTP
from execution_live_wire import adapter_revision, metadata, normalized, projection
from execution_outcomes import answer_schema
from execution_plan import Store, prepare
from execution_test_support import ExecutionCase, canonical


def body(protocol):
    common = {
        "model": "mock-model",
        "id": "fixture-id",
        "usage": {"input_tokens": 17, "output_tokens": 5},
    }
    entries = {
        "supported": {"type": "noul", "noul": 0.92},
        "team": {
            "type": "choice",
            "choice": "billing",
            "confidence": 0.8,
            "probabilities": {"billing": 0.8, "legal": 0.2},
        },
        "urgency": {
            "type": "score",
            "score": 1.5,
            "confidence": 0.5,
            "probabilities": {"0": 0.0, "1": 0.5, "2": 0.5},
            "legend": {"0": "later", "1": "week", "2": "now"},
        },
    }
    if protocol == "typesafe-systemone/v1":
        return {**common, "answers": entries}
    if protocol == "openai-decisions/v1":
        entries["supported"] = {"type": "predicate", "probability": 0.92}
        for key in ("team", "urgency"):
            answer = entries[key]
            answer["probabilities"] = [
                {
                    "value": k if key == "team" else int(k),
                    "probability": p,
                    **({"label": answer["legend"][k]} if key == "urgency" else {}),
                }
                for k, p in answer["probabilities"].items()
            ]
        return {**common, "answers": [{"name": k, **v} for k, v in entries.items()]}
    text = json.dumps(
        {
            "answers": [
                {"questionId": "supported", "type": "noul", "value": 0.92},
                {"questionId": "team", "type": "choice", "value": "billing"},
                {"questionId": "urgency", "type": "score", "value": 1.5},
            ]
        }
    )
    if protocol == "openai-chat-completions/v1":
        return {
            **common,
            "usage": {"prompt_tokens": 17, "completion_tokens": 5},
            "choices": [{"finish_reason": "stop", "message": {"content": text}}],
        }
    return {
        **common,
        "status": "completed",
        "output": [
            {
                "type": "message",
                "status": "completed",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
    }


class LiveWireTests(ExecutionCase):
    def wire(self, protocol):
        fixture = self.fixture(protocol=protocol, tasks=1)
        fixture.plan["arms"][0]["adapter"] = adapter_revision()
        fixture.save()
        store = Store(fixture.folder)
        plan = prepare(store)
        return (
            plan["tasks"][0],
            plan["arms"][0],
            answer_schema(store.value(plan["pins"]["outputSchema"])),
            store,
        )

    def test_four_protocols_roundtrip_and_optional_usage(self):
        for protocol in (
            "typesafe-systemone/v1",
            "openai-decisions/v1",
            "openai-chat-completions/v1",
            "openai-responses/v1",
        ):
            task, arm, questions, _ = self.wire(protocol)
            raw = canonical(body(protocol))
            response = projection(200, raw, "fixture-id", "offline-placeholder-key")
            with self.subTest(protocol=protocol):
                self.assertEqual(
                    [
                        v["value"]
                        for v in normalized(response, task, arm, questions)["answers"]
                    ],
                    [0.92, "billing", 1.5],
                )
                self.assertEqual(
                    metadata(response, protocol)[2],
                    {"inputTokens": 17, "outputTokens": 5},
                )
                response["body"].pop("usage")
                self.assertEqual(
                    metadata(response, protocol)[2],
                    {"inputTokens": None, "outputTokens": None},
                )

    def test_duplicate_names_probabilities_score_legend_and_pin_drift_reject(self):
        for protocol in ("typesafe-systemone/v1", "openai-decisions/v1"):
            task, arm, questions, _ = self.wire(protocol)
            original = projection(
                200, canonical(body(protocol)), "fixture-id", "offline-placeholder-key"
            )
            for mutation in ("coverage", "distribution", "pin"):
                changed = copy.deepcopy(original)
                changed_arm = copy.deepcopy(arm)
                if mutation == "pin":
                    changed_arm["adapter"]["sha256"] = "f" * 64
                elif mutation == "coverage":
                    if protocol == "typesafe-systemone/v1":
                        changed["body"]["answers"].pop("team")
                    else:
                        changed["body"]["answers"][1]["name"] = "supported"
                elif protocol == "typesafe-systemone/v1":
                    changed["body"]["answers"]["urgency"]["legend"]["0"] = "changed"
                else:
                    changed["body"]["answers"][1]["probabilities"][0]["probability"] = (
                        True
                    )
                with (
                    self.subTest(protocol=protocol, mutation=mutation),
                    self.assertRaises(ValueError),
                ):
                    normalized(changed, task, changed_arm, questions)

    def test_error_malformed_reasoning_and_credential_projection(self):
        for status, raw in [
            (403, b'{"error":"offline-placeholder-key"}'),
            (200, b"{broken"),
            (200, b'{"model":"offline-placeholder-key"}'),
        ]:
            saved = projection(
                status, raw, "offline-placeholder-key", "offline-placeholder-key"
            )
            self.assertIsNone(saved["body"])
            self.assertIsNone(saved["requestId"])
            self.assertNotIn(b"offline-placeholder-key", canonical(saved))
        raw = body("openai-responses/v1")
        raw["output"].insert(0, {"type": "reasoning", "encrypted_content": "opaque"})
        self.assertNotIn(
            b"encrypted_content",
            canonical(projection(200, canonical(raw), "fixture-id", "placeholder")),
        )

    def test_chat_and_responses_partial_or_unstructured_output_reject(self):
        for protocol in ("openai-chat-completions/v1", "openai-responses/v1"):
            task, arm, questions, _ = self.wire(protocol)
            raw = body(protocol)
            if protocol == "openai-responses/v1":
                raw["status"] = "incomplete"
            else:
                raw["choices"][0]["finish_reason"] = "length"
            with self.assertRaises(ValueError):
                normalized(
                    projection(200, canonical(raw), "fixture-id", "placeholder"),
                    task,
                    arm,
                    questions,
                )

    def test_http_uses_exact_ordered_body_one_request_and_no_redirect(self):
        _, _, _, store = self.wire("typesafe-systemone/v1")
        task = store.json("plan.json")["tasks"][0]
        calls = []

        class Socket:
            def settimeout(self, value):
                self.value = value

        class Response:
            status = 302

            def read(self, count):
                return b""

            def getheader(self, name):
                return None

        class Connection:
            def __init__(self, *args, **kwargs):
                self.sock = Socket()

            def connect(self):
                pass

            def request(self, *args, **kwargs):
                calls.append((args, kwargs))

            def getresponse(self):
                return Response()

            def close(self):
                pass

        with (
            patch("execution_live_http.http.client.HTTPSConnection", Connection),
            patch(
                "socket.create_connection", side_effect=AssertionError("network denied")
            ),
        ):
            response = NativeHTTP().dispatch(
                store.artifact(task["request"]),
                "placeholder-key",
                lambda: 1_000_000_000,
            )
        self.assertEqual(len(calls), 1)
        self.assertEqual(response["response"]["httpStatus"], 302)
        sent = json.loads(calls[0][1]["body"])
        self.assertEqual(list(sent["questions"]), task["questionIds"])


if __name__ == "__main__":
    unittest.main()
