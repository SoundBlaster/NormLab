"""Exact application anchoring. No changes to quoted text, stance or facts."""

import uuid

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


def anchor(raw, source, include_speaker=False):
    statements, quarantine, decisions = [], [], []
    for item in raw:
        quote, attributes = item["text"], item.get("attributes") or {}
        matches, cursor = [], 0
        if quote:
            while (position := source.find(quote, cursor)) >= 0:
                matches.append(position)
                cursor = position + 1
        reason = None
        if len(matches) != 1:
            reason = (
                "quote-not-found"
                if not matches
                else "ambiguous-quote-needs-human-selection"
            )
        elif (
            item["class"] not in ["nlinput:" + p for p in PREDICATES]
            or attributes.get("stance") not in ["asserted", "denied", "unknown"]
            or not all(
                isinstance(attributes.get(k), str)
                and 0 < len(attributes[k].strip()) <= limit
                for k, limit in [
                    ("subject", 128),
                    ("aboutEpisode", 128),
                    ("valueText", 2048),
                ]
            )
            or len(quote.encode("utf-16-le")) // 2 > 4096
            or len(statements) >= 256
        ):
            reason = "statement-contract"
        if reason:
            quarantine.append({**item, "reason": reason})
            continue
        start, end = matches[0], matches[0] + len(quote)
        statement_id = str(uuid.uuid4())
        statements.append(
            {
                "id": statement_id,
                "predicate": item["class"],
                "stance": attributes["stance"],
                "subject": attributes["subject"],
                "aboutEpisode": attributes["aboutEpisode"],
                "valueText": attributes["valueText"],
                "quote": quote,
                "startOffset": len(source[:start].encode("utf-16-le")) // 2,
                "endOffset": len(source[:end].encode("utf-16-le")) // 2,
                "origin": "model",
                "decision": "pending",
                "rationale": "",
            }
        )
        if include_speaker:
            speaker = attributes.get("speaker")
            if not isinstance(speaker, str) or not 0 < len(speaker.strip()) <= 128:
                statements.pop()
                quarantine.append({**item, "reason": "speaker-contract"})
                continue
            statements[-1]["speaker"] = speaker
        decisions.append(
            {
                "statementId": statement_id,
                "libraryInterval": item.get("interval"),
                "applicationInterval": {"start_pos": start, "end_pos": end},
                "method": "unique-exact-source-search",
            }
        )
    return statements, quarantine, decisions
