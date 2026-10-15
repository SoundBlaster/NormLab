"""Explicit Stage1 public wire extensions; no rewrite of historical requests."""

from execution_records import text
from offline_bundle import object_keys, require

DECISIONS = "openai-decisions-input/v1"
RESPONSES = "openai-responses-stage1/v1"


def validate(body, task, questions, decode, prompt):
    require(task["questionIds"] == ["classification"], "Stage1 single classification")
    definition = questions["classification"]
    require(definition["type"] == "choice", "Stage1 choice definition")
    object_keys(prompt, "type instructions criteria")
    require(
        prompt["type"] == "choice"
        and isinstance(prompt["criteria"], dict)
        and list(prompt["criteria"]) == definition["labels"],
        "Pinned Stage1 criteria/order",
    )
    text(prompt["instructions"])
    for description in prompt["criteria"].values():
        text(description)
    if "questions" in body:
        require(isinstance(body["input"], str), "Decision string input")
        require(
            isinstance(decode(body["input"].encode()), dict), "Decision state object"
        )
        require(
            isinstance(body["questions"], list) and len(body["questions"]) == 1,
            "Stage1 question coverage",
        )
        question = body["questions"][0]
        object_keys(question, "type name instructions choices")
        require(
            question["type"] == "choice" and question["name"] == "classification",
            "Decision classification question",
        )
        text(question["instructions"])
        require(
            question["instructions"] == prompt["instructions"],
            "Pinned Decision instructions",
        )
        choices = question["choices"]
        require(
            isinstance(choices, list) and len(choices) == len(definition["labels"]),
            "Decision choice coverage",
        )
        for choice, label in zip(choices, definition["labels"]):
            object_keys(choice, "value description")
            require(choice["value"] == label, "Decision choice order")
            text(choice["description"])
            require(
                choice["description"] == prompt["criteria"][label],
                "Pinned Decision criteria",
            )
    else:
        require(
            body.get("store") is False and body.get("stream") is False,
            "Frozen non-streamed non-stored Responses request",
        )
        require(
            body.get("text")
            == {
                "format": {
                    "type": "json_schema",
                    "name": "selected_support",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "overall": {"type": "string", "enum": definition["labels"]}
                        },
                        "required": ["overall"],
                        "additionalProperties": False,
                    },
                }
            },
            "Stage1 overall output schema",
        )
        require(
            isinstance(body.get("input"), list) and len(body["input"]) == 1,
            "Stage1 one independent input",
        )
        message = body["input"][0]
        object_keys(message, "role content")
        require(
            message["role"] == "user"
            and isinstance(message["content"], list)
            and len(message["content"]) == 1,
            "Stage1 user message",
        )
        content = message["content"][0]
        object_keys(content, "type text")
        require(
            content["type"] == "input_text" and isinstance(content["text"], str),
            "Stage1 input text",
        )
        value = decode(content["text"].encode())
        object_keys(value, "state questions")
        require(isinstance(value["state"], dict), "Stage1 state object")
        object_keys(value["questions"], "overall")
        embedded = value["questions"]["overall"]
        object_keys(embedded, "type instructions criteria")
        require(
            embedded == prompt
            and isinstance(embedded["criteria"], dict)
            and list(embedded["criteria"]) == definition["labels"],
            "Pinned embedded Stage1 question/criteria/order",
        )


def overall(value, task, questions):
    object_keys(value, "overall")
    require(
        task["questionIds"] == ["classification"]
        and value["overall"] in questions["classification"]["labels"],
        "Stage1 overall label",
    )
    return [
        {"questionId": "classification", "type": "choice", "value": value["overall"]}
    ]
