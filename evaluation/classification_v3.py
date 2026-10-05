"""Classification candidate with one explicit decision per source fragment."""

import json

PROMPT = """Обработай КАЖДЫЙ переданный фрагмент, включая все фрагменты после первого.
Верни results с обязательной записью для каждого fragmentId по схеме.
Не создавай новые цитаты, участников, эпизоды или источники. Их задаёт приложение.
Один фрагмент может соответствовать нескольким признакам из definitions.

status=classified: заполни classifications всеми явно поддержанными признаками,
reason оставь пустым. valueText — непустое краткое описание утверждения на русском.
status=no-supported-predicate: classifications пустой, reason содержит конкретное
объяснение, почему ни один признак из definitions не поддержан данным фрагментом.
Не используй этот статус, чтобы пропустить оплату, разрешение или явную неизвестность.

stance=asserted, если признак явно утверждается; denied, если явно отрицается;
unknown, если сам текст сообщает, что значение неизвестно, не помнят или не знают.
Неизвестность НЕ означает denied и НЕ означает отсутствие подходящего признака.
Сначала выбери признак, о котором говорится, и только затем его stance.
Сообщение о неизвестном результате оплаты относится к payment со stance=unknown:
для выбора predicate НЕ требуется подтверждение самого факта оплаты.
Сообщение о неизвестной действительности разрешения относится к permit=unknown.
Явно неизвестные дата, город или режим относятся к eventTime, inMoscow или paidRegime
со stance=unknown соответственно. no-supported-predicate разрешён только когда
фрагмент вообще не относится к каталогу, а НЕ когда его значение неизвестно.
Отсутствие упоминания признака не даёт основания его добавлять даже с unknown.
Полярность относится к конкретному признаку, а не ко всем словам «не» в предложении.
Оплата парковки не означает, что доказан платный режим. Оплата штрафа или пополнение
баланса не являются оплатой парковочной сессии. Время оплаты относится к paymentStart,
а дата/время стоянки — к eventTime. Отсутствие разрешения не означает отсутствие
платного режима. Сбой приложения сам по себе не устанавливает вину или освобождение.
Сохрани противоположные утверждения разных источников отдельно, не выбирай победителя.
Не делай правовых выводов и не добавляй признаков по молчанию.
Definitions:\n"""


def object_schema(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def build_schema(fragment_ids, predicates):
    classification = object_schema(
        {
            "predicate": {"type": "string", "enum": list(predicates)},
            "stance": {"type": "string", "enum": ["asserted", "denied", "unknown"]},
            "valueText": {"type": "string", "minLength": 1, "maxLength": 2048},
        }
    )
    decision = object_schema(
        {
            "status": {
                "type": "string",
                "enum": ["classified", "no-supported-predicate"],
            },
            "classifications": {
                "type": "array",
                "items": classification,
                "maxItems": 30,
            },
            "reason": {"type": "string", "maxLength": 2048},
        }
    )
    return object_schema(
        {
            "results": object_schema(
                {fragment_id: decision for fragment_id in fragment_ids}
            )
        }
    )


def validate(parsed, fragment_ids, predicates):
    if not isinstance(parsed, dict) or set(parsed) != {"results"}:
        raise ValueError("Classification response object contract")
    results = parsed["results"]
    if not isinstance(results, dict) or set(results) != set(fragment_ids):
        raise ValueError("Missing or unexpected classification fragment IDs")
    flat = []
    for fragment_id in fragment_ids:
        result = results[fragment_id]
        if not isinstance(result, dict) or set(result) != {
            "status",
            "classifications",
            "reason",
        }:
            raise ValueError("Classification decision contract")
        items, reason = result["classifications"], result["reason"]
        if (
            not isinstance(items, list)
            or len(items) > 30
            or not isinstance(reason, str)
            or len(reason) > 2048
        ):
            raise ValueError("Classification decision limits")
        if result["status"] == "classified":
            if not items or reason.strip():
                raise ValueError("Classified decision requires items and empty reason")
        elif result["status"] == "no-supported-predicate":
            if items or not reason.strip():
                raise ValueError("Unsupported decision requires reason and no items")
        else:
            raise ValueError("Unknown classification decision status")
        seen = set()
        for item in items:
            if not isinstance(item, dict) or set(item) != {
                "predicate",
                "stance",
                "valueText",
            }:
                raise ValueError("Classification item contract")
            if (
                not isinstance(item["predicate"], str)
                or item["predicate"] not in predicates
                or not isinstance(item["stance"], str)
                or item["stance"] not in ["asserted", "denied", "unknown"]
                or not isinstance(item["valueText"], str)
                or not item["valueText"].strip()
                or len(item["valueText"]) > 2048
            ):
                raise ValueError(
                    "Classification predicate, stance or valueText contract"
                )
            pair = (item["predicate"], item["stance"])
            if pair in seen:
                raise ValueError("Duplicate predicate/stance for fragment")
            seen.add(pair)
            flat.append({"fragmentId": fragment_id, **item})
    return flat, results


def classify(client, fragments, definitions, schema, prompt, calls):
    params = {
        "model": "openai/gpt-oss-20b",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(fragments, ensure_ascii=False)},
        ],
        "temperature": 0,
        "seed": 42,
        "max_tokens": 8192,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "fragment_decisions",
                "strict": True,
                "schema": schema,
            },
        },
    }
    call = {"stage": "classification", "request": params}
    calls.append(call)
    response = client.chat.completions.create(**params)
    call["response"] = response.model_dump(mode="json")
    choice = response.choices[0]
    call["output"] = choice.message.content
    if choice.finish_reason != "stop" or choice.message.refusal:
        raise ValueError("Incomplete or refused classification response")
    return validate(
        json.loads(choice.message.content),
        [fragment["fragmentId"] for fragment in fragments],
        definitions,
    )
