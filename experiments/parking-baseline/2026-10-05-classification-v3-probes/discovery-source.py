"""Direct literal discovery candidate; source text is never normalized."""

import json
from types import SimpleNamespace

PROMPT = """Извлеки явные утверждения только из сообщения пользователя.
Каждый statement — дословная цитата целого предложения: сохрани язык, регистр,
отрицание, время, место и вводные слова об источнике. Ничего не переводи,
не перефразируй и не добавляй отсутствующие факты. Сохрани обе стороны противоречия.
subject=vehicle_1 для одного автомобиля; разные автомобили — vehicle_1, vehicle_2.
Лица при необходимости — person_1, person_2. narrator НЕ является subject.
aboutEpisode=episode_1 обязателен и при отсутствии времени или даты.
Только явно разные стоянки получают разные эпизоды episode_1, episode_2.
speaker — происхождение утверждения: narrator для собственных слов рассказчика,
letter_1 для утверждения из письма, notice_1 из уведомления/постановления,
note_1 из заметки. Это действует и для косвенного пересказа: утверждение письма
всегда получает letter_1, НЕ narrator. Сохрани вводные слова о письме в цитате.
Разные документы одного типа различай по номеру. Не оценивай достоверность слов.
Ответ — только JSON по схеме; все поля обязательны и не могут быть пустыми.
"""


def discover(client, source, schema, calls):
    params = {
        "model": "openai/gpt-oss-20b",
        "messages": [
            {
                "role": "system",
                "content": PROMPT + "\n" + json.dumps(schema, ensure_ascii=False),
            },
            {"role": "user", "content": source},
        ],
        "temperature": 0,
        "seed": 42,
        "max_tokens": 8192,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "discovery", "strict": True, "schema": schema},
        },
    }
    call = {"stage": "discovery", "request": params}
    calls.append(call)
    response = client.chat.completions.create(**params)
    call["response"] = response.model_dump(mode="json")
    choice = response.choices[0]
    call["output"] = choice.message.content
    if choice.finish_reason != "stop" or choice.message.refusal:
        raise ValueError("Incomplete or refused discovery response")
    parsed = json.loads(choice.message.content)
    if not isinstance(parsed, dict) or set(parsed) != {"extractions"}:
        raise ValueError("Discovery object contract")
    items = parsed["extractions"]
    if not isinstance(items, list) or len(items) > 256:
        raise ValueError("Discovery array contract")
    extractions = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {
            "statement",
            "statement_attributes",
        }:
            raise ValueError("Discovery item contract")
        attrs = item["statement_attributes"]
        if not isinstance(attrs, dict) or set(attrs) != {
            "subject",
            "aboutEpisode",
            "speaker",
        }:
            raise ValueError("Discovery attributes contract")
        extractions.append(
            SimpleNamespace(
                extraction_text=item["statement"], attributes=attrs, char_interval=None
            )
        )
    return SimpleNamespace(extractions=extractions)
