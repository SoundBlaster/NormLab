"""Separate literal assertion discovery from ontology classification, locally."""

import dataclasses
import hashlib
import importlib.metadata
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import langextract as lx
from anchor import anchor
from langextract.providers.openai import OpenAILanguageModel
from langextract.providers.schemas.openai import OpenAISchema

DEFINITIONS = {
    "eventTime": "Время или дата события.",
    "inMoscow": "Место события находится в Москве.",
    "cityParking": "Место является городской парковкой; одного названия зоны недостаточно.",
    "placement": "Автомобиль находился на парковке.",
    "paidRegime": "В момент события действовал платный режим. Отсутствие льгот или разрешений НЕ означает отсутствие платного режима.",
    "subjectScope": "Статус лица: физическое лицо, личное использование автомобиля.",
    "attribution": "Связь лица с автомобилем или действием.",
    "payment": "Оплата конкретной парковки. Платный режим НЕ является фактом оплаты.",
    "paymentStart": "Время начала оплаты или платежа.",
    "departure": "Время отъезда автомобиля.",
    "paymentComplexity": "Ошибки оплаты, неверная машина/зона или последующие исправления. Если ошибок и исправлений НЕ было, stance=denied.",
    "permit": "Наличие разрешения или абонемента.",
    "disabilityConditions": "Явно названные обстоятельства инвалидности; отсутствие льгот не доказывает отсутствие инвалидности.",
    "specialTariff": "Явно названный специальный тариф; отсутствие льгот не доказывает отсутствие специального тарифа.",
    "faultAndExclusions": "Явно названная вина или исключающие ответственность обстоятельства. Не выводить из отсутствия ошибок оплаты.",
}
DISCOVERY_PROMPT = """Find explicit factual assertions in the ORIGINAL narrative.
Use only class statement with attributes subject, aboutEpisode, speaker (neutral keys).
Copy complete literal clauses, including negation, dates and context. Never rewrite,
normalize spelling/case, classify legal predicates, resolve contradictions or invent
unmentioned facts. Preserve every opposing assertion, including quoted statements.
Use episode_1 for one episode; distinguish vehicles and speakers where explicit.
Overlapping exact clauses are allowed; cover all explicit facts, not just payment.
"""
EXAMPLE_TEXT = (
    "В Туле машина стояла с 09:00. Я оплатил парковку. В письме: я не оплатил парковку."
)
EXAMPLES = [
    lx.data.ExampleData(
        text=EXAMPLE_TEXT,
        extractions=[
            lx.data.Extraction(
                extraction_class="statement",
                extraction_text=quote,
                attributes={
                    "subject": "vehicle_1",
                    "aboutEpisode": "episode_1",
                    "speaker": speaker,
                },
            )
            for quote, speaker in [
                ("В Туле машина стояла с 09:00", "narrator"),
                ("Я оплатил парковку", "narrator"),
                ("я не оплатил парковку", "letter_1"),
            ]
        ],
    )
]


def object_schema(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def main(use_v2=False, use_v3=False, replay_path=None):
    if use_v3:
        use_v2 = True
    input_path, output_path = map(Path, sys.argv[1:3])
    request = json.loads(input_path.read_text())
    source = request["narrative"]
    digest = hashlib.sha256(source.encode()).hexdigest()
    if (
        request.get("sourceDigest", digest) != digest
        or not 0 < len(source.encode("utf-16-le")) // 2 <= 32768
    ):
        raise ValueError("Source binding or length invalid")
    started = time.perf_counter()
    calls, fragments, raw, quarantine = [], [], [], []
    error = None
    discovery_prompt = DISCOVERY_PROMPT
    classification_decisions = None
    replay_provenance = None

    class CapturingModel(OpenAILanguageModel):
        def _process_single_prompt(self, prompt, config):
            result = super()._process_single_prompt(prompt, config)
            calls.append(
                {"stage": "discovery", "prompt": prompt, "output": result.output}
            )
            return result

    model = CapturingModel(
        model_id="openai/gpt-oss-20b",
        api_key="local-only",
        base_url="http://127.0.0.1:1234/v1",
        temperature=0,
        seed=42,
        max_workers=1,
        max_output_tokens=8192,
    )
    model._client = model._client.with_options(max_retries=0, timeout=180)
    string = {"type": "string"}
    discovery_schema = object_schema(
        {
            "extractions": {
                "type": "array",
                "items": object_schema(
                    {
                        "statement": string,
                        "statement_attributes": object_schema(
                            {
                                "subject": string,
                                "aboutEpisode": string,
                                "speaker": string,
                            }
                        ),
                    }
                ),
            }
        }
    )
    classification_schema = object_schema(
        {
            "classifications": {
                "type": "array",
                "items": object_schema(
                    {
                        "fragmentId": string,
                        "predicate": {"type": "string", "enum": list(DEFINITIONS)},
                        "stance": {
                            "type": "string",
                            "enum": ["asserted", "denied", "unknown"],
                        },
                        "valueText": string,
                    }
                ),
            }
        }
    )
    if use_v2:
        discovery_item = discovery_schema["properties"]["extractions"]["items"]
        discovery_schema["properties"]["extractions"]["maxItems"] = 256
        discovery_item["properties"]["statement"] = {
            "type": "string",
            "minLength": 1,
            "maxLength": 4096,
        }
        attribute_schema = discovery_item["properties"]["statement_attributes"][
            "properties"
        ]
        for key in attribute_schema:
            attribute_schema[key] = {"type": "string", "minLength": 1, "maxLength": 128}
        attribute_schema["subject"]["pattern"] = "^(vehicle|person)_[1-9][0-9]*$"
        attribute_schema["aboutEpisode"]["pattern"] = "^episode_[1-9][0-9]*$"
    classification_prompt = """Classify ONLY the supplied literal assertions using the definitions.
One fragment may yield several predicates. Copy its fragmentId. No new quotes,
participants, episodes or facts. Retain both sides of contradictions separately.
stance refers to whether the PREDICATE is affirmed or denied, not whether the clause
contains any negative word. Omit unsupported predicates. Never infer absence from
silence. Definitions:\n""" + json.dumps(DEFINITIONS, ensure_ascii=False)
    try:
        if use_v2:
            from discovery_v2 import PROMPT, discover

            discovery_prompt = PROMPT
            if replay_path is not None:
                parent_bytes = replay_path.read_bytes()
                parent = json.loads(parent_bytes)
                if (
                    parent.get("sourceDigest") != digest
                    or parent.get("pipeline")
                    != "literal-discovery-then-classification/v2"
                ):
                    raise ValueError("Discovery replay source or pipeline mismatch")
                replay_provenance = {
                    "parentOutputDigest": hashlib.sha256(parent_bytes).hexdigest(),
                    "parentPipeline": parent["pipeline"],
                }
                if (
                    not isinstance(parent.get("fragments"), list)
                    or len(parent["fragments"]) > 256
                ):
                    raise ValueError("Discovery replay fragments contract")
                discovered = SimpleNamespace(
                    extractions=[
                        SimpleNamespace(
                            extraction_text=f["quote"],
                            attributes=f["attributes"],
                            char_interval=None,
                            fragment_id=f["fragmentId"],
                        )
                        for f in parent["fragments"]
                    ]
                )
                calls.extend(
                    {**call, "replayed": True}
                    for call in parent["calls"]
                    if call["stage"] == "discovery"
                )
            else:
                discovered = discover(model._client, source, discovery_schema, calls)
        else:
            model.apply_schema(OpenAISchema(schema_dict=discovery_schema, strict=True))
            discovered = lx.extract(
                text_or_documents=source,
                prompt_description=DISCOVERY_PROMPT,
                examples=EXAMPLES,
                model=model,
                extraction_passes=1,
                max_workers=1,
                max_char_buffer=32768,
                resolver_params={
                    "enable_fuzzy_alignment": False,
                    "accept_match_lesser": False,
                },
            )
        for index, extraction in enumerate(discovered.extractions or []):
            quote = extraction.extraction_text
            attrs = extraction.attributes or {}
            item = {
                "fragmentId": getattr(
                    extraction, "fragment_id", f"fragment_{index + 1}"
                ),
                "quote": quote,
                "attributes": attrs,
                "libraryInterval": dataclasses.asdict(extraction.char_interval)
                if extraction.char_interval
                else None,
            }
            if (
                not isinstance(quote, str)
                or not quote
                or source.find(quote) < 0
                or source.find(quote, source.find(quote) + 1) >= 0
                or len(quote.encode("utf-16-le")) // 2 > 4096
                or len(fragments) >= 256
                or not all(
                    isinstance(attrs.get(k), str) and 0 < len(attrs[k].strip()) <= 128
                    for k in ["subject", "aboutEpisode", "speaker"]
                )
            ):
                quarantine.append({**item, "reason": "discovery-source-or-contract"})
            else:
                fragments.append(item)
        if not fragments:
            raise ValueError("No exactly anchored assertions; review source manually")
        if fragments:
            if use_v3:
                from classification_v3 import PROMPT as CLASSIFICATION_PROMPT
                from classification_v3 import build_schema, classify

                classification_prompt = CLASSIFICATION_PROMPT + json.dumps(
                    DEFINITIONS, ensure_ascii=False
                )
                classification_schema = build_schema(
                    [fragment["fragmentId"] for fragment in fragments], DEFINITIONS
                )
                classified, classification_decisions = classify(
                    model._client,
                    fragments,
                    DEFINITIONS,
                    classification_schema,
                    classification_prompt,
                    calls,
                )
            else:
                messages = [
                    {"role": "system", "content": classification_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(fragments, ensure_ascii=False),
                    },
                ]
                completion = model._client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=messages,
                    temperature=0,
                    seed=42,
                    max_tokens=8192,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "classifications",
                            "strict": True,
                            "schema": classification_schema,
                        },
                    },
                )
                content = completion.choices[0].message.content
                calls.append(
                    {"stage": "classification", "messages": messages, "output": content}
                )
                if use_v2:
                    calls[-1]["response"] = completion.model_dump(mode="json")
                if completion.choices[0].finish_reason != "stop":
                    raise ValueError("Incomplete classification response")
                classified = json.loads(content)["classifications"]
            by_id = {f["fragmentId"]: f for f in fragments}
            for item in classified:
                fragment = by_id.get(item.get("fragmentId"))
                if fragment is None or item.get("predicate") not in DEFINITIONS:
                    quarantine.append(
                        {**item, "reason": "unknown-fragment-or-predicate"}
                    )
                    continue
                raw.append(
                    {
                        "class": "nlinput:" + item["predicate"],
                        "text": fragment["quote"],
                        "attributes": {
                            **fragment["attributes"],
                            "stance": item["stance"],
                            "valueText": item["valueText"],
                        },
                        "interval": fragment["libraryInterval"],
                        "fragmentId": fragment["fragmentId"],
                    }
                )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    statements, rejected, decisions = anchor(raw, source, include_speaker=use_v2)
    payload = {
        "schema": "normlab.langextract-statements/v1",
        "pipeline": "literal-discovery-then-classification/"
        + ("v3" if use_v3 else "v2" if use_v2 else "v1"),
        "sourceDigest": digest,
        "langextractVersion": importlib.metadata.version("langextract"),
        "model": "openai/gpt-oss-20b",
        "provider": "lm-studio-openai-compatible",
        "passes": 1 if replay_path is not None else 2,
        "latencyMs": round((time.perf_counter() - started) * 1000),
        "error": error,
        "fragments": fragments,
        "rawExtractions": raw,
        "statements": statements,
        "quarantine": quarantine + rejected,
        "alignmentDecisions": decisions,
        "calls": calls,
        "discoveryPrompt": discovery_prompt,
        "classificationPrompt": classification_prompt,
        "discoverySchema": discovery_schema,
        "classificationSchema": classification_schema,
        "exampleText": None if use_v2 else EXAMPLE_TEXT,
        "reviewState": "unreviewed",
    }
    if use_v3:
        payload["classificationDecisions"] = classification_decisions
        payload["discoveryReplay"] = replay_provenance
        payload["latencyScope"] = (
            "classification-with-replayed-discovery"
            if replay_path is not None
            else "full-pipeline"
        )
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    if error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
