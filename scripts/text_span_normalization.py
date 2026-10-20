"""Explicit, source-backed output rules; no domain policy or provider imports."""

import hashlib
from dataclasses import dataclass
from typing import Literal

RULESET_VERSION = "quote-boundaries/v2"


@dataclass(frozen=True)
class TextSpan:
    value: str
    start: int
    end: int


@dataclass(frozen=True)
class QuoteRule:
    id: str
    opening: str
    closing: str


RULES = (
    QuoteRule("single-trailing-guillemet/v1", "«", "»"),
    QuoteRule("single-trailing-ascii-quote/v1", '"', '"'),
)
ALL_RULE_IDS = tuple(rule.id for rule in RULES)
DEFAULT_RULE_IDS = ("single-trailing-guillemet/v1",)


@dataclass(frozen=True)
class NormalizationResult:
    status: Literal["applied", "unchanged", "review"]
    raw: TextSpan
    derived: TextSpan | None
    source_sha256: str
    coordinate_system: str
    target: str
    ruleset_version: str
    enabled_rules: tuple[str, ...] = ()
    applied_rules: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    supporting_quote_span: tuple[int, int] | None = None


def _flat_pairs(source, rule):
    """Conservative grammar: balanced, unescaped, unnested selected delimiters."""
    if any("\\" + mark in source for mark in (rule.opening, rule.closing)):
        return None
    pairs = []
    opening = None
    for index, char in enumerate(source):
        if rule.opening == rule.closing and char == rule.opening:
            if opening is None:
                opening = index
            else:
                pairs.append((opening, index))
                opening = None
        elif char == rule.opening:
            if opening is not None:
                return None
            opening = index
        elif char == rule.closing:
            if opening is None:
                return None
            pairs.append((opening, index))
            opening = None
    return pairs if opening is None else None


def normalize_span(
    source: str,
    raw: TextSpan,
    *,
    coordinate_system: str,
    target: str,
    enabled_rules: tuple[str, ...] = DEFAULT_RULE_IDS,
) -> NormalizationResult:
    """Derive inner quote content only when the source proves a flat quote pair.

    Caller must establish the coordinate system. Confidence is not transferred
    to the derived span; technical normalization is not semantic acceptance.
    """
    if target not in ("inner_content", "whole_quote"):
        raise ValueError("Unknown normalization target")
    enabled_rules = tuple(enabled_rules)
    if set(enabled_rules) - set(ALL_RULE_IDS):
        raise ValueError("Unknown rule ID")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()

    def result(status, reason, derived=None, rule=None, support=None):
        return NormalizationResult(
            status=status,
            raw=raw,
            derived=derived,
            source_sha256=digest,
            coordinate_system=coordinate_system,
            target=target,
            ruleset_version=RULESET_VERSION,
            enabled_rules=enabled_rules,
            applied_rules=(rule.id,) if rule else (),
            findings=(reason,),
            supporting_quote_span=support,
        )

    if coordinate_system != "code_points":
        return result("review", "unsupported_or_unverified_coordinate_system")
    if (
        type(raw.start) is not int
        or type(raw.end) is not int
        or not 0 <= raw.start <= raw.end <= len(source)
        or not isinstance(raw.value, str)
    ):
        return result("review", "invalid_span")
    if source[raw.start : raw.end] != raw.value:
        return result("review", "raw_source_mismatch")
    if target != "inner_content":
        return result("unchanged", "rule_not_for_requested_target", raw)
    if (
        raw.value.endswith('"')
        and "single-trailing-ascii-quote/v1" not in enabled_rules
    ):
        return result("review", "ascii_quote_requires_explicit_contextual_opt_in")

    for rule in RULES:
        if rule.id not in enabled_rules or not raw.value.endswith(rule.closing):
            continue
        if len(raw.value) <= 1 or raw.value.count(rule.closing) != 1:
            continue
        if rule.opening != rule.closing and rule.opening in raw.value:
            continue
        content = raw.value[:-1]
        if not content.strip():
            return result("review", "empty_quote_content")
        if any(
            mark in content for item in RULES for mark in (item.opening, item.closing)
        ):
            return result("review", "mixed_or_nested_quote_content")
        if raw.start == 0 or source[raw.start - 1] != rule.opening:
            return result("review", "no_adjacent_source_opening_quote")
        prefix = source[: raw.start - 1].rstrip()
        if rule.opening == '"' and prefix and prefix[-1].isdigit():
            return result("review", "possible_numeric_unit_quote")
        pairs = _flat_pairs(source, rule)
        if pairs is None or (raw.start - 1, raw.end - 1) not in pairs:
            return result("review", "ambiguous_source_quote_structure")
        derived = TextSpan(content, raw.start, raw.end - 1)
        return result(
            "applied",
            "source_pair_confirms_single_trailing_closer",
            derived,
            rule,
            (raw.start - 1, raw.end),
        )
    return result("unchanged", "no_applicable_rule", raw)
