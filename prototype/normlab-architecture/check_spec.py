#!/usr/bin/env python3
"""Restricted local lint for this draft. Not the reference Hypercode parser."""
from __future__ import annotations
import ast
import json
import re
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
IDENT = r"[A-Za-z][A-Za-z0-9_-]*"
NODE = re.compile(rf"({IDENT})(?:\.({IDENT}))?(?:#({IDENT}))?$")
SELECTOR = re.compile(rf"[.#]?{IDENT}(?:\s*>\s*[.#]?{IDENT})*$")
CONSTRAINT = re.compile(r"(string|int|float|bool)(?:\s*>=\s*(-?\d+(?:\.\d+)?))?(?:\s*<=\s*(-?\d+(?:\.\d+)?))?$")

@dataclass
class Node:
    kind: str
    cls: str | None
    id: str | None
    parent: Node | None
    line: int
    props: dict[str, Any] = field(default_factory=dict)


def fail(where: str, message: str) -> None:
    raise ValueError(f"{where}: {message}")


def parse_hc(path: Path) -> list[Node]:
    nodes: list[Node] = []
    stack: list[Node] = []
    ids: set[str] = set()
    for ln, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        where = f"{path.name}:{ln}"
        if "\t" in line:
            fail(where, "tabs not supported by this draft")
        indent = len(line) - len(line.lstrip(" "))
        if indent % 2:
            fail(where, "expected two-space indentation")
        depth = indent // 2
        if depth > len(stack):
            fail(where, "indentation skipped a level")
        m = NODE.fullmatch(line.strip())
        if not m:
            fail(where, "outside documented core command grammar")
        kind, cls, id_ = m.groups()
        if id_ and id_ in ids:
            fail(where, "duplicate consumer ID")
        if id_:
            ids.add(id_)
        stack = stack[:depth]
        node = Node(kind, cls, id_, stack[-1] if stack else None, ln)
        nodes.append(node)
        stack.append(node)
    return nodes


def scalar(text: str) -> Any:
    if text[:1] in ('"', "'"):
        value = ast.literal_eval(text)
        if not isinstance(value, str):
            raise ValueError("expected quoted string")
        return value
    if text in ("true", "false"):
        return text == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    return text


def parse_selector(text: str) -> str:
    text = text.strip()
    if text[:1] in ('"', "'"):
        text = ast.literal_eval(text)
    if not SELECTOR.fullmatch(text):
        raise ValueError(f"unsupported selector: {text}")
    return text


def read_hcs(path: Path, seen: set[Path] | None = None,
             stack: tuple[Path, ...] = ()) -> tuple[list[dict], list[dict]]:
    seen = set() if seen is None else seen
    path = path.resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("import escaped the package root")
    if path in stack:
        raise ValueError("cyclic import")
    if path in seen:
        return [], []
    seen.add(path)
    rules, contracts = [], []
    current = None
    mode = "normal"
    context = None
    started = False
    for ln, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        where = f"{path.name}:{ln}"
        if "\t" in line:
            fail(where, "tabs unsupported")
        indent = len(line) - len(line.lstrip(" "))
        text = line.strip()
        if indent == 0:
            if text.startswith("@import "):
                if started:
                    fail(where, "imports must precede all blocks")
                target = ast.literal_eval(text[len("@import "):])
                child_rules, child_contracts = read_hcs(
                    path.parent / target, seen, stack + (path,))
                rules.extend(child_rules)
                contracts.extend(child_contracts)
                continue
            started = True
            current = None
            context = None
            if text == "@contract:":
                mode = "contract"
                continue
            dimension = re.fullmatch(rf"@({IDENT})\[({IDENT})\]:", text)
            if dimension:
                mode = "context"
                context = dict([dimension.groups()])
                continue
            if not text.endswith(":"):
                fail(where, "expected selector block")
            mode = "normal"
            current = {"selector": parse_selector(text[:-1]), "props": {},
                       "context": None, "where": where}
            rules.append(current)
            continue
        if mode in ("contract", "context") and indent == 2:
            if not text.endswith(":"):
                fail(where, "expected nested selector")
            current = {"selector": parse_selector(text[:-1]), "props": {},
                       "context": context, "where": where}
            (contracts if mode == "contract" else rules).append(current)
            continue
        expected_indent = 2 if mode == "normal" else 4
        if current is None or indent != expected_indent or ":" not in text:
            fail(where, "invalid property indentation")
        key, value = map(str.strip, text.split(":", 1))
        if not re.fullmatch(rf"{IDENT}(?:\[\?\])?", key):
            fail(where, "invalid property name")
        if key in current["props"]:
            fail(where, "duplicate property within selector block")
        if mode == "contract":
            match = CONSTRAINT.fullmatch(value)
            if not match:
                fail(where, "unsupported contract expression")
            current["props"][key] = match.groups()
        else:
            current["props"][key] = scalar(value)
    return rules, contracts


def simple_matches(node: Node, selector: str) -> bool:
    if selector.startswith("#"):
        return node.id == selector[1:]
    if selector.startswith("."):
        return node.cls == selector[1:]
    return node.kind == selector


def matches(node: Node | None, selector: str) -> bool:
    for segment in reversed(re.split(r"\s*>\s*", selector)):
        if node is None or not simple_matches(node, segment):
            return False
        node = node.parent
    return True


def specificity(selector: str) -> tuple[int, int, int]:
    parts = re.split(r"\s*>\s*", selector)
    return (sum(p.startswith("#") for p in parts),
            sum(p.startswith(".") for p in parts),
            sum(not p.startswith(("#", ".")) for p in parts))


def check(hc: str, hcs: str, context: dict[str, str]) -> tuple[dict, dict[str, Node]]:
    nodes = parse_hc(ROOT / hc)
    rules, contracts = read_hcs(ROOT / hcs)
    ids = {n.id: n for n in nodes if n.id}
    for entry in rules + contracts:
        if not any(matches(n, entry["selector"]) for n in nodes):
            fail(entry["where"], "selector matches no nodes in this draft")
    checks = refs = 0
    for node in nodes:
        applicable = [(specificity(r["selector"]), index, r)
                      for index, r in enumerate(rules)
                      if matches(node, r["selector"])
                      and (not r["context"] or all(context.get(k) == v for k, v in r["context"].items()))]
        for _, _, rule in sorted(applicable, key=lambda x: (x[0], x[1])):
            node.props.update(rule["props"])
        for contract in contracts:
            if not matches(node, contract["selector"]):
                continue
            for raw_key, (type_, low, high) in contract["props"].items():
                optional = raw_key.endswith("[?]")
                key = raw_key[:-3] if optional else raw_key
                if key not in node.props:
                    if optional:
                        continue
                    fail(hc, f"missing required {node.id or node.kind}.{key}")
                value = node.props[key]
                ok = {"string": isinstance(value, str), "bool": type(value) is bool,
                      "int": type(value) is int,
                      "float": type(value) in (int, float)}[type_]
                if not ok:
                    fail(hc, f"wrong type for {key}: {value!r}")
                if low is not None and value < float(low):
                    fail(hc, f"{key} below lower bound")
                if high is not None and value > float(high):
                    fail(hc, f"{key} above upper bound")
                checks += 1
        for key, value in node.props.items():
            if key.endswith("_ref"):
                if not isinstance(value, str) or not value.startswith("#") or value[1:] not in ids:
                    fail(hc, f"unresolved consumer reference {key}: {value!r}")
                refs += 1
    report = {"hc": hc, "hcs": hcs, "context": context, "nodes": len(nodes),
              "unique_ids": len(ids), "contract_value_checks": checks,
              "resolved_consumer_refs": refs, "status": "local-check-passed"}
    return report, ids


def main() -> None:
    reports = []
    for context in ({}, {"env": "demo"}):
        report, ids = check("normlab.architecture.hc", "normlab.architecture.hcs", context)
        for name, field_ in (("ai", "accepted_fact_write"), ("ai", "normative_rule_write"),
                            ("ai", "verified_result_write"), ("verifier", "sorry_ax_allowed"),
                            ("verifier", "native_evaluation_axioms_allowed"),
                            ("analyzer", "hcs_specificity_is_legal_priority")):
            if ids[name].props[field_] is not False:
                raise ValueError(f"draft architectural policy violated: {name}.{field_}")
        for node in ids.values():
            if node.cls in ("isolated", "sandboxed") and node.props["network"] != "deny":
                raise ValueError("sandbox network policy violated")
        reports.append(report)
    report, ids = check("examples/reduction.hc", "examples/reduction.hcs", {})
    reports.append(report)
    term = ids["prison-term"].props["amount"]
    scale = ids["scale"].props
    computed = Fraction(term * scale["numerator"], scale["denominator"])
    if computed.denominator != 1 or computed != ids["with-a"].props["expected_prison_months"]:
        raise ValueError("synthetic arithmetic mismatch")
    if term != ids["without-a"].props["expected_prison_months"]:
        raise ValueError("baseline mismatch")
    if not all(ids[scenario].props["expected_fine_amount"] == ids["fine"].props["amount"]
               for scenario in ("with-a", "without-a")):
        raise ValueError("fine mismatch")
    output = {"status": "local-check-passed", "checks": reports,
              "toy_arithmetic": {"baseline_months": term, "adjusted_months": int(computed),
                                 "fine_unchanged": True},
              "reference_hypercode_cli_executed": False, "lean_executed": False,
              "limitations": ["Restricted independently implemented syntax lint, not reference-parser conformance.",
                              "No static cascade-contract narrowing proof; current files use no contract overrides.",
                              "Architecture adapter and Legal IR compiler are not implemented.",
                              "Policy values checked, not their runtime enforcement.",
                              "No Lean theorem proved; arithmetic fixture is not a runtime integration test."]}
    (ROOT / "validation-report.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
