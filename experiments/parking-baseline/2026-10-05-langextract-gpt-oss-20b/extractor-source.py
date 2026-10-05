"""Local-only LangExtract statement proposal; source checks remain independent."""

import dataclasses
import hashlib
import importlib.metadata
import json
import sys
import time
import uuid
from pathlib import Path

import langextract as lx
from langextract.providers.openai import OpenAILanguageModel

PREDICATES = [
    "eventTime",
    "inMoscow",
    "cityParking",
    "placement",
    "paidRegime",
    "subjectScope",
    "attribution",
    "payment",
    "paymentStart",
    "departure",
    "paymentComplexity",
    "permit",
    "disabilityConditions",
    "specialTariff",
    "faultAndExclusions",
]
PROMPT = """Extract explicit statements from the source narrative, not legal conclusions.
Use these extraction classes: %s.
Every extraction_text must be an exact source substring. Retain both asserted and
denied statements even when they contradict. 'Not mentioned' is unknown, not denied.
Extract each explicit negative separately. Do not infer fault, disability conditions,
special tariffs or paid regime from absence of corrections, benefits or a zone name.
Use attributes stance (asserted/denied/unknown), subject (neutral key, never a name),
aboutEpisode (neutral episode key), valueText (the explicit fact).
In a single episode use episode_1. Keep different vehicles distinguishable in valueText.
Preserve payment corrections and wrong vehicle/zone details as paymentComplexity.
Unknown mandatory conditions must be explained later during review, not invented here.
""" % ", ".join("nlinput:" + name for name in PREDICATES)

# Independent teaching narrative: never use P01/P02/P04/P09 as few-shot examples.
EXAMPLE_TEXT = (
    "В учебном эпизоде автомобиль стоял на городской парковке Тулы. "
    "Я сообщил: оплата произведена. В моём письме сказано: я не оплатил парковку. "
    "Оплата относилась к другому автомобилю."
)
EXAMPLES = [
    lx.data.ExampleData(
        text=EXAMPLE_TEXT,
        extractions=[
            lx.data.Extraction(
                extraction_class="nlinput:cityParking",
                extraction_text="городской парковке Тулы",
                attributes={
                    "stance": "asserted",
                    "subject": "place_1",
                    "aboutEpisode": "episode_1",
                    "valueText": "городская парковка Тулы",
                },
            ),
            lx.data.Extraction(
                extraction_class="nlinput:payment",
                extraction_text="оплата произведена",
                attributes={
                    "stance": "asserted",
                    "subject": "episode_1",
                    "aboutEpisode": "episode_1",
                    "valueText": "оплата произведена",
                },
            ),
            lx.data.Extraction(
                extraction_class="nlinput:payment",
                extraction_text="я не оплатил парковку",
                attributes={
                    "stance": "denied",
                    "subject": "episode_1",
                    "aboutEpisode": "episode_1",
                    "valueText": "оплата отсутствует",
                },
            ),
            lx.data.Extraction(
                extraction_class="nlinput:paymentComplexity",
                extraction_text="Оплата относилась к другому автомобилю",
                attributes={
                    "stance": "asserted",
                    "subject": "episode_1",
                    "aboutEpisode": "episode_1",
                    "valueText": "неверный автомобиль",
                },
            ),
        ],
    )
]


def main():
    source_path, output_path = map(Path, sys.argv[1:3])
    request = json.loads(source_path.read_text())
    source = request["narrative"]
    if not 0 < len(source.encode("utf-16-le")) // 2 <= 32768:
        raise ValueError("Source length outside contract")
    source_digest = hashlib.sha256(source.encode()).hexdigest()
    if request.get("sourceDigest", source_digest) != source_digest:
        raise ValueError("Source digest mismatch")
    calls = []

    class CapturingModel(OpenAILanguageModel):
        def _process_single_prompt(self, prompt, config):
            result = super()._process_single_prompt(prompt, config)
            calls.append({"prompt": prompt, "output": result.output})
            return result

    model = CapturingModel(
        model_id="openai/gpt-oss-20b",
        api_key="local-only",
        base_url="http://127.0.0.1:1234/v1",
        temperature=0,
        max_workers=1,
        max_output_tokens=8192,
        seed=42,
    )
    model._client = model._client.with_options(max_retries=0, timeout=180)
    started = time.perf_counter()
    result = None
    error = None
    try:
        result = lx.extract(
            text_or_documents=source,
            prompt_description=PROMPT,
            examples=EXAMPLES,
            model=model,
            max_workers=1,
            extraction_passes=1,
            max_char_buffer=32768,
            resolver_params={
                "enable_fuzzy_alignment": False,
                "accept_match_lesser": False,
            },
        )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    statements, quarantine, raw = [], [], []
    for extraction in (result.extractions or []) if result is not None else []:
        attributes = extraction.attributes or {}
        interval = extraction.char_interval
        item = {
            "class": extraction.extraction_class,
            "text": extraction.extraction_text,
            "attributes": attributes,
            "interval": dataclasses.asdict(interval) if interval else None,
            "alignmentStatus": str(extraction.alignment_status),
        }
        raw.append(item)
        # Never trust LangExtract's alignment status as proof of literal source identity.
        if (
            interval is None
            or interval.start_pos is None
            or interval.end_pos is None
            or interval.end_pos <= interval.start_pos
            or source[interval.start_pos : interval.end_pos]
            != extraction.extraction_text
            or extraction.extraction_class not in ["nlinput:" + p for p in PREDICATES]
            or attributes.get("stance") not in ["asserted", "denied", "unknown"]
            or not all(
                isinstance(attributes.get(k), str) and attributes[k].strip()
                for k in ["subject", "aboutEpisode", "valueText"]
            )
        ):
            quarantine.append(item)
            continue
        statements.append(
            {
                "id": str(uuid.uuid4()),
                "predicate": extraction.extraction_class,
                "stance": attributes["stance"],
                "subject": attributes["subject"],
                "aboutEpisode": attributes["aboutEpisode"],
                "valueText": attributes["valueText"],
                "quote": extraction.extraction_text,
                "startOffset": len(source[: interval.start_pos].encode("utf-16-le"))
                // 2,
                "endOffset": len(source[: interval.end_pos].encode("utf-16-le")) // 2,
                "origin": "model",
                "decision": "pending",
                "rationale": "",
            }
        )
    payload = {
        "schema": "normlab.langextract-statements/v1",
        "sourceDigest": source_digest,
        "langextractVersion": importlib.metadata.version("langextract"),
        "model": "openai/gpt-oss-20b",
        "provider": "lm-studio-openai-compatible",
        "schemaConstraints": "library-default",
        "passes": 1,
        "fuzzyAlignment": False,
        "latencyMs": round((time.perf_counter() - started) * 1000),
        "error": error,
        "prompt": PROMPT,
        "exampleText": EXAMPLE_TEXT,
        "statements": statements,
        "quarantine": quarantine,
        "rawExtractions": raw,
        "calls": calls,
        "reviewState": "unreviewed",
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    if error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
