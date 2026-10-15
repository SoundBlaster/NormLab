"""Stage1 protocol extensions preserve input and output contracts without SDKs."""

import copy
import json
import unittest

from execution_live_wire import adapter_revision, metadata, normalized, projection
from execution_plan import Store, prepare
from execution_stage1_protocol import DECISIONS, RESPONSES, validate
from execution_test_support import ROOT, ExecutionCase, canonical
from stage1_provider_plan import prepare as stage1_prepare


class Stage1NativeWireTests(ExecutionCase):
    def wire(self, arm_index):
        old = stage1_prepare(
            ROOT / "fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json"
        )
        job = old["jobs"][arm_index]
        protocol = ("typesafe-systemone/v1", DECISIONS, RESPONSES)[arm_index]
        fixture = self.fixture(tasks=1)
        arm, task = fixture.plan["arms"][0], fixture.plan["tasks"][0]
        labels = list(job["task"]["questions"]["overall"]["criteria"])
        fixture.plan["pins"]["outputSchema"] = fixture.put(
            {
                "schema": "normlab.execution-answer-schema/v1",
                "questions": [
                    {"id": "classification", "type": "choice", "labels": labels}
                ],
            }
        )
        arm.update(
            protocol=protocol,
            model=job["request"]["body"]["model"],
            acceptedModels=[job["request"]["body"]["model"]],
            endpoint=job["request"]["endpoint"],
            adapter=adapter_revision(),
        )
        if protocol == RESPONSES:
            arm["settings"].update(reasoningEffort="low", maxOutputTokens=1024)
            arm["requestCaps"]["outputTokens"] = 1024
        task["questionIds"] = ["classification"]
        task["request"] = fixture.put(
            {
                "method": "POST",
                "url": arm["endpoint"],
                "headers": {"Content-Type": "application/json"},
                "body": job["request"]["body"],
            },
            ordered=True,
        )
        context = fixture.value(task["context"])
        context.update(
            requestDigest=task["request"]["sha256"], questionIds=task["questionIds"]
        )
        task["context"] = fixture.put(context)
        fixture.save()
        prepare(Store(fixture.folder))
        return fixture, arm, task, labels

    def test_exact_frozen_bodies_validate_all_three_protocols(self):
        for i in range(3):
            with self.subTest(arm=i):
                self.wire(i)

    def test_stage1_responses_overall_and_decisions_normalize(self):
        for i in (1, 2):
            fixture, arm, task, labels = self.wire(i)
            questions = {
                "classification": {
                    "id": "classification",
                    "type": "choice",
                    "labels": labels,
                }
            }
            body = {
                "id": "offline-id",
                "model": arm["model"],
                "usage": {"input_tokens": 10, "output_tokens": 2},
            }
            if i == 1:
                body["answers"] = [
                    {
                        "name": "classification",
                        "type": "choice",
                        "choice": labels[0],
                        "confidence": 1.0,
                        "probabilities": [
                            {"value": k, "probability": float(k == labels[0])}
                            for k in labels
                        ],
                    }
                ]
            else:
                body.update(
                    status="completed",
                    output=[
                        {
                            "type": "message",
                            "status": "completed",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": json.dumps({"overall": labels[0]}),
                                }
                            ],
                        }
                    ],
                )
            response = projection(200, canonical(body), "header-id", "offline-key")
            result = normalized(response, task, arm, questions)
            self.assertEqual(result["answers"][0]["value"], labels[0])
            self.assertEqual(metadata(response, arm["protocol"])[2]["inputTokens"], 10)
            if i == 2:
                self.assertEqual(metadata(response, arm["protocol"])[1], "offline-id")

    def test_changed_labels_stream_store_and_decision_order_reject(self):
        for i in (1, 2):
            fixture, arm, task, labels = self.wire(i)
            original = fixture.value(task["request"])["body"]
            questions = {"classification": {"type": "choice", "labels": labels}}
            for kind in ("choices",) if i == 1 else ("stream", "store", "schema"):
                value = copy.deepcopy(original)
                if kind == "choices":
                    value["questions"][0]["choices"].reverse()
                elif kind == "schema":
                    value["text"]["format"]["schema"]["properties"]["overall"][
                        "enum"
                    ].reverse()
                else:
                    value[kind] = True
                with self.subTest(arm=i, mutation=kind), self.assertRaises(ValueError):
                    validate(value, task, questions, Store.decode_json)


if __name__ == "__main__":
    unittest.main()
