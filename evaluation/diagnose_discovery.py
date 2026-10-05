"""Bounded discovery ablation; preserves requests and complete local responses."""

import hashlib
import importlib.metadata
import json
import sys
import time
from pathlib import Path

import langextract as lx
from langextract.providers.openai import OpenAILanguageModel
from langextract.providers.schemas.openai import OpenAISchema
from openai import OpenAI
from two_stage import DISCOVERY_PROMPT, EXAMPLES, object_schema

CASES = {
    "payment": ["Я оплатил парковку"],
    "negation": ["Я не оплатил парковку"],
    "conflict": ["Я оплатил парковку", "В письме написано: я не оплатил парковку"],
}
VARIANTS = [
    "direct-text",
    "direct-schema",
    "direct-example-schema",
    "langextract",
    "direct-russian-schema",
]


def main():
    destination = Path(sys.argv[1])
    destination.mkdir(parents=True, exist_ok=False)
    worker_bytes = Path(__file__).read_bytes()
    (destination / "worker.py.snapshot").write_bytes(worker_bytes)
    variants = sys.argv[2:] or VARIANTS
    if any(variant not in VARIANTS for variant in variants):
        raise ValueError("Unknown diagnostic variant")
    client = OpenAI(
        api_key="local-only",
        base_url="http://127.0.0.1:1234/v1",
        max_retries=0,
        timeout=180,
    )
    string = {"type": "string"}
    schema = object_schema(
        {
            "extractions": {
                "type": "array",
                "items": object_schema(
                    {
                        "statement": string,
                        "statement_attributes": object_schema(
                            {
                                key: string
                                for key in ["subject", "aboutEpisode", "speaker"]
                            }
                        ),
                    }
                ),
            }
        }
    )
    response_format = OpenAISchema(schema_dict=schema, strict=True).response_format
    example = {
        "extractions": [
            {
                "statement": extraction.extraction_text,
                "statement_attributes": extraction.attributes,
            }
            for extraction in EXAMPLES[0].extractions
        ]
    }
    results = []
    for case_id, clauses in CASES.items():
        source = ". ".join(clauses) + "."
        for variant in variants:
            calls = []
            started = time.perf_counter()
            record = {
                "case": case_id,
                "variant": variant,
                "source": source,
                "sourceDigest": hashlib.sha256(source.encode()).hexdigest(),
                "expectedClauses": clauses,
                "calls": calls,
                "error": None,
            }
            try:
                if variant == "langextract":

                    class CapturingModel(OpenAILanguageModel):
                        def _process_single_prompt(self, prompt, config):
                            params = self._build_chat_completions_params(prompt, config)
                            call = {"request": params}
                            calls.append(call)
                            response = client.chat.completions.create(**params)
                            call["response"] = response.model_dump(mode="json")
                            return self._response_to_scored_output(response)

                    model = CapturingModel(
                        model_id="openai/gpt-oss-20b",
                        api_key="local-only",
                        base_url="http://127.0.0.1:1234/v1",
                        temperature=0,
                        seed=42,
                        max_workers=1,
                        max_output_tokens=8192,
                    )
                    model.apply_schema(OpenAISchema(schema_dict=schema, strict=True))
                    lx.extract(
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
                else:
                    prompt = (
                        DISCOVERY_PROMPT
                        + "\nReturn JSON with shape described by this schema:\n"
                        + json.dumps(schema, ensure_ascii=False)
                    )
                    if variant == "direct-russian-schema":
                        prompt = (
                            "Извлеки явные утверждения только из сообщения пользователя. "
                            "Каждый statement — дословная цитата целого предложения: "
                            "сохрани язык, регистр, отрицание и указание автора. "
                            "Ничего не переводи и не перефразируй. "
                            "Сохрани обе стороны противоречия. "
                            "Не добавляй отсутствующие факты. "
                            "Для одного автомобиля используй subject=vehicle_1, "
                            "для одного эпизода aboutEpisode=episode_1. "
                            "speaker=narrator для рассказчика, letter_1 для письма. "
                            "Ответ — JSON по схеме:\n"
                            + json.dumps(schema, ensure_ascii=False)
                        )
                    if variant == "direct-example-schema":
                        prompt += (
                            "\nExample narrative:\n"
                            + EXAMPLES[0].text
                            + "\nExample answer:\n"
                            + json.dumps(example, ensure_ascii=False)
                        )
                    params = {
                        "model": "openai/gpt-oss-20b",
                        "messages": [
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": source},
                        ],
                        "temperature": 0,
                        "seed": 42,
                        "max_tokens": 8192,
                        "response_format": response_format
                        if variant != "direct-text"
                        else {"type": "text"},
                    }
                    call = {"request": params}
                    calls.append(call)
                    response = client.chat.completions.create(**params)
                    call["response"] = response.model_dump(mode="json")
                choice = calls[-1]["response"]["choices"][0]
                content = choice["message"]["content"]
                record["finishReason"] = choice["finish_reason"]
                parsed = json.loads(content)
                quotes = [item["statement"] for item in parsed["extractions"]]
                record["quotes"] = quotes
                record["literalSourcePass"] = bool(quotes) and all(
                    isinstance(quote, str) and bool(quote) and quote in source
                    for quote in quotes
                )
                record["clauseCoveragePass"] = all(
                    any(clause in quote for quote in quotes) for clause in clauses
                )
                record["pass"] = (
                    record["literalSourcePass"]
                    and record["clauseCoveragePass"]
                    and choice["finish_reason"] == "stop"
                )
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
                record["pass"] = False
            record["latencyMs"] = round((time.perf_counter() - started) * 1000)
            (destination / f"{case_id}-{variant}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n"
            )
            results.append(record)
            print(case_id, variant, record["pass"], record.get("quotes"), flush=True)
    summary = {
        "schema": "normlab.discovery-diagnostic/v1",
        "langextractVersion": importlib.metadata.version("langextract"),
        "models": client.models.list().model_dump(mode="json"),
        "workerDigest": hashlib.sha256(worker_bytes).hexdigest(),
        "limitations": "Development probes; not a quality estimate. Direct versus LangExtract changes message packaging and schema instruction placement together.",
        "results": [
            {key: value for key, value in record.items() if key != "calls"}
            for record in results
        ],
    }
    (destination / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
