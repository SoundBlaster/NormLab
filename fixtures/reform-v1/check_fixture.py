#!/usr/bin/env python3
"""Finite arithmetic audit of a source fixture; not a runtime or proof checker."""
from fractions import Fraction
from itertools import product
import json
from pathlib import Path
import sys

def require(condition, message):
    if not condition:
        raise ValueError(message)

def key(x):
    require(set(x) == {"group", "M", "N", "E"}, "Unexpected input fields")
    require(all(type(x[p]) is bool for p in ("M", "N", "E")), "Non-boolean input")
    return (x["group"], x["M"], x["N"], x["E"])

def evaluate(model, x, omitted=None):
    rules = [r for r in model["provisions"] if r["id"] != omitted]
    active = [r for r in rules if x["group"] in r["groups"]]
    bases = [r for r in active if r["operation"]["kind"] == "baseline"]
    require(len(bases) == 1, "Expected one matching baseline")
    base = bases[0]["operation"]
    excluded = x["N"] and any(
        r["operation"]["kind"] == "exclude" and x[r["operation"]["trigger"]]
        for r in active)
    months = Fraction(base["prisonMonths"])
    ledger = {}
    for r in rules:
        op = r["operation"]
        if r not in active:
            status = "inapplicable"
        elif op["kind"] == "baseline":
            status = "applied"
        elif op["kind"] == "exclude":
            status = "applied" if excluded else "inapplicable"
        elif not x[op["trigger"]]:
            status = "inapplicable"
        elif op["trigger"] == "N" and excluded:
            status = "excluded"
        else:
            status = "applied"
        ledger[r["id"]] = status
    for trigger in ("M", "N"):
        matching = [r for r in active if r["operation"].get("trigger") == trigger]
        require(len(matching) == 1, f"Expected one transform for {trigger}")
        r = matching[0]
        if ledger[r["id"]] == "applied":
            op = r["operation"]
            months *= Fraction(op["numerator"], op["denominator"])
    require(months.denominator == 1, "Non-integral consequence")
    return {"qualification": x["group"], "prisonMonths": int(months),
            "fineAmount": base["fineAmount"], "currency": "DEMO"}, ledger

def audit(path):
    d = json.loads(path.read_text())
    require(d["schema"] == "normlab.reform-fixture-plan/v1", "Unsupported design schema")
    domain = d["domain"]
    require(domain["groups"] == ["K1", "K2"] and domain["predicates"] == ["M", "N", "E"],
            "Unsupported domain")
    require(domain["values"] == [False, True] and not domain["restrictions"],
            "Changed domain values or restrictions")
    cases = [dict(zip(("group", "M", "N", "E"), x)) for x in product(
        domain["groups"], domain["values"], domain["values"], domain["values"])]
    require(domain["cardinality"] == len(cases) == 16, "Wrong domain cardinality")
    p = d["profile"]
    require(p["evaluationOrder"] == ["baseline", "exclusions", "scale-M", "scale-N"]
            and p["arithmetic"] == "exact-rational-reject-non-integral"
            and p["mapping"] == "identity", "Unsupported profile semantics")
    require(p["units"] == {"prisonMonths": "month", "fineAmount": "DEMO"}
            and p["completion"] == "all-findings-terminal"
            and p["applyCount"] == 1, "Changed profile units/completion")
    require(p["findingStates"] == ["unreviewed", "established", "refuted", "not-established"]
            and p["terminalFindings"] == p["openFindingCompletions"] == ["established", "refuted"],
            "Changed finding semantics")
    models = {m["role"]: m for m in d["models"]}
    require(len(d["models"]) == len(models) == 3 and set(models) == {"A", "B", "C"},
            "Duplicate or missing model role")
    source = path.with_name("source.md").read_text()
    rules = [r for m in models.values() for r in m["provisions"]]
    ids = {r["id"] for r in rules}
    require(len(ids) == len(rules), "Duplicate provision IDs")
    for r in rules:
        require(r["sourceRef"] == f'source.md#{r["id"].lower()}'
                and f'### {r["id"]}\n' in source, f'Missing source binding: {r["id"]}')
        require(set(r["originIds"]) <= ids, "Unknown origin ID")
        require(r["mandatory"] is True and r["applyCount"] == 1
                and r["groups"] and set(r["groups"]) <= set(domain["groups"]),
                "Invalid provision scope/obligation")
        op = r["operation"]
        require(op["kind"] in {"baseline", "scale", "exclude"}, "Unsupported operation")
        if op["kind"] == "scale":
            require(op["trigger"] in {"M", "N"} and op["preserveFine"] is True
                    and type(op["numerator"]) is int and type(op["denominator"]) is int
                    and 0 < op["numerator"] <= op["denominator"], "Invalid transform")
        elif op["kind"] == "exclude":
            require(op["trigger"] == "E" and op["targetTrigger"] == "N", "Invalid exclusion")
    require([len(models[r]["provisions"]) for r in ("A", "B", "C")] == [7, 5, 5],
            "Changed provision inventory")
    rows = {key(r["input"]): r for r in d["expected"]}
    require(len(rows) == len(d["expected"]) == 16 and set(rows) == {key(x) for x in cases},
            "Duplicate or missing expected rows")
    require(len({r["id"] for r in rows.values()}) == 16, "Duplicate row IDs")
    outcomes = {}
    for x in cases:
        row = rows[key(x)]
        require(set(row["prisonMonths"]) == set(models), "Missing expected model")
        for role, model in models.items():
            outcome, ledger = evaluate(model, x)
            expected = {"qualification": x["group"], "prisonMonths": row["prisonMonths"][role],
                        "fineAmount": row["fineAmount"], "currency": "DEMO"}
            require(outcome == expected, f'Expected mismatch: {row["id"]}/{role}')
            require(len(ledger) == len(model["provisions"]), "Incomplete audit ledger")
            outcomes[role, key(x)] = outcome
    table = []
    for line in path.with_name("README.md").read_text().splitlines():
        cells = [v.strip().replace(" ", "") for v in line.split("|")[1:-1]]
        if len(cells) == 8 and cells[0] in domain["groups"]:
            table.append(cells)
    require(len(table) == 16, "README table cardinality mismatch")
    for cells, x in zip(table, cases):
        row = rows[key(x)]
        expected = [x["group"], *[str(int(x[p])) for p in ("M", "N", "E")],
                    *[str(row["prisonMonths"][r]) for r in ("A", "B", "C")], str(row["fineAmount"])]
        require(cells == expected, "README table mismatch")
    counts = {}
    for q in d["queries"]:
        require(q["domain"] == domain["id"] and q["id"] not in counts, "Invalid query binding")
        count = 0
        if q["kind"] == "monotonic-m":
            require(q["models"] == ["A", "B", "C"] and q["strict"] is True, "Changed monotonicity")
            for role in q["models"]:
                for x in cases:
                    if x["M"]:
                        continue
                    left, right = outcomes[role, key(x)], outcomes[role, key({**x, "M": True})]
                    require(right[q["target"]] < left[q["target"]], "M fails strict reduction")
                    require(all(right[f] == left[f] for f in q["preserve"]), "M changes preserved field")
                    count += 1
        else:
            for x in cases:
                if any(x[p] != v for p, v in q.get("condition", {}).items()):
                    continue
                left, right = outcomes[q["baseline"], key(x)], outcomes[q["candidate"], key(x)]
                if q["kind"] in {"equivalence", "preserved-outside"}:
                    require(left == right, f'{q["id"]}: differing consequences')
                elif q["kind"] == "component-no-increase":
                    require(right[q["target"]] <= left[q["target"]], "Reform increases target")
                    require(all(right[f] == left[f] for f in q["preserve"]), "Reform changes preserved field")
                elif q["kind"] == "strict-reduction":
                    require(right[q["target"]] < left[q["target"]], "Reform fails strict reduction")
                else:
                    raise ValueError("Unsupported query")
                count += 1
        counts[q["id"]] = count
    require(counts == {"Q-AB-equivalence": 16, "Q-AC-no-increase": 16, "Q-AC-strict-M": 8,
                       "Q-AC-outside-M": 8, "Q-M-monotonicity": 24}, "Changed query scope")
    fault = d["faultyVariant"]
    require(fault["baseModel"] == "C" and fault["omittedRule"] == "C-X"
            and fault["violatedQuery"] == "Q-AC-outside-M", "Unsupported faulty variant")
    witnesses = []
    for x in cases:
        if not x["M"]:
            wrong, _ = evaluate(models["C"], x, fault["omittedRule"])
            if wrong != outcomes["A", key(x)]:
                witnesses.append((rows[key(x)], wrong))
    require(len(witnesses) == 2, "Unexpected counterexample count")
    row, wrong = witnesses[0]
    require(fault["expectedWitness"] == {"rowId": row["id"],
            "baselinePrisonMonths": row["prisonMonths"]["A"],
            "candidatePrisonMonths": wrong["prisonMonths"], "fineAmount": wrong["fineAmount"]},
            "Counterexample mismatch")
    return {"status": "arithmetic-audited", "domainCases": 16, "modelEvaluations": 48,
            "sourceBindings": len(rules), "queryChecks": counts,
            "faultyVariantCounterexamples": len(witnesses), "firstWitness": row["id"],
            "runtimeIntegrated": False, "leanVerified": False}

if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("fixture.json")
    try:
        print(json.dumps(audit(path), indent=2))
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"Fixture audit failed: {error}", file=sys.stderr)
        sys.exit(1)
