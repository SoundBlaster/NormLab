"""Neutral Clairic smoke: dry-run by default, one HTTP attempt with --live."""

import argparse
import hashlib
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path

STATE = (
    "Report R-104 dated 2026-10-19. Monthly income is $5000. Rent is $1500. "
    "Contacts: Dana Ruiz and Priya Shah."
)
FIELDS = {
    "report_id": {"type": "text", "instructions": "Report identifier"},
    "report_date": {"type": "date", "instructions": "Explicit report date"},
    "monthly_income": {"type": "number", "instructions": "Monthly income in USD"},
    "monthly_rent": {"type": "number", "instructions": "Monthly rent in USD"},
    "contacts": {"type": "list", "items": "text", "instructions": "Contact names"},
    "purchase_order": {"type": "text", "instructions": "Purchase order identifier"},
}
EXPECTED = {
    "report_id": "R-104",
    "report_date": "2026-10-19",
    "monthly_income": 5000,
    "monthly_rent": 1500,
    "contacts": ["Dana Ruiz", "Priya Shah"],
    "purchase_order": None,
}
MAX_BODY = 1024 * 1024
ABLATION_CASES = tuple(
    "ablation-" + name for name in ("original", "unicode-clean", "ascii-quotes", "both")
)
LINEBREAK_CASES = ("linebreak-original", "linebreak-sentences")
QUOTE_CASES = ("quote-inner", "quote-whole")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def load_case(name):
    if name == "neutral":
        return {"state": STATE, "fields": FIELDS, "expected": EXPECTED}
    if name in (*ABLATION_CASES, *LINEBREAK_CASES, *QUOTE_CASES):
        if name in ABLATION_CASES:
            filename, prefix = "clairic-text-ablation-v1.json", "ablation-"
        elif name in LINEBREAK_CASES:
            filename, prefix = "clairic-linebreak-ablation-v1.json", "linebreak-"
        else:
            filename, prefix = "clairic-quote-target-v1.json", "quote-"
        path = Path(__file__).resolve().parents[1] / "fixtures/providers" / filename
        raw = path.read_bytes()
        plan = json.loads(raw)
        case = dict(plan["variants"][name.removeprefix(prefix)])
        case.setdefault("fields", plan.get("fields"))
        case["fixture_sha256"] = hashlib.sha256(raw).hexdigest()
        return case
    path = (
        Path(__file__).resolve().parents[1]
        / "fixtures/providers/clairic-ru-unicode-v1.json"
    )
    raw = path.read_bytes()
    case = json.loads(raw)
    case["fixture_sha256"] = hashlib.sha256(raw).hexdigest()
    return case


def anchor_diagnostics(case, answers, result):
    """Compare frozen occurrences across candidates; never rewrite provider offsets."""
    state = case["state"]
    systems = ("code_points", "utf16_code_units", "utf8_bytes")
    common = set(systems)
    fields = {}
    for name, (start, end) in case["expected_codepoint_spans"].items():
        assert state[start:end] == case["expected"][name]
        expected = {
            "code_points": [start, end],
            "utf16_code_units": [
                len(state[:n].encode("utf-16-le")) // 2 for n in (start, end)
            ],
            "utf8_bytes": [len(state[:n].encode("utf-8")) for n in (start, end)],
        }
        answer = answers.get(name)
        actual = answer.get("span") if isinstance(answer, dict) else None
        valid = (
            isinstance(actual, list)
            and len(actual) == 2
            and all(type(n) is int for n in actual)
        )
        matches = [key for key, span in expected.items() if valid and actual == span]
        common.intersection_update(matches)
        fields[name] = {
            "provider_span": actual,
            "expected_spans": expected,
            "matching_candidates": matches,
        }
    source_compatible = "state_text" not in result or result["state_text"] == state
    if not source_compatible:
        common.clear()
    return {
        "fields": fields,
        "source_basis_compatible": source_compatible,
        "consistent_candidates": sorted(common),
        "one_candidate_matches_all": len(common) == 1,
        "scope": "Observed exclusive-end candidates only; no production coordinate inference",
    }


def summarize(document, case=None):
    """Check the fixed smoke values; this is not general semantic validation."""
    if not isinstance(document, dict):
        raise ValueError("Expected a JSON object")
    if document.get("success") is False:
        raise ValueError("Cloudflare returned success=false")
    # Workers AI REST envelope and the direct model shape shown in model docs.
    result = document.get("result") if "result" in document else document
    if not isinstance(result, dict) or not isinstance(result.get("answers"), dict):
        raise ValueError("Missing result.answers object")
    case = case or load_case("neutral")
    answers = result["answers"]
    checks = {}
    for name, expected in case["expected"].items():
        answer = answers.get(name)
        present = isinstance(answer, dict) and "value" in answer
        actual = answer.get("value") if present else None
        matches = present and type(actual) is type(expected) and actual == expected
        if isinstance(expected, (int, float)):
            matches = present and type(actual) in (int, float) and actual == expected
        if isinstance(expected, list):
            matches = (
                present
                and isinstance(actual, list)
                and all(isinstance(item, str) for item in actual)
                and sorted(actual) == sorted(expected)
            )
        checks[name] = {
            "expected": expected,
            "actual": actual,
            "present": present,
            "pass": matches and answer.get("type") == case["fields"][name]["type"],
        }
    complete = result.get("truncated") is False
    summary = {
        "model": result.get("model"),
        "truncated": result.get("truncated"),
        "usage": result.get("usage"),
        "answers": answers,
        "checks": checks,
        "pass": complete and all(check["pass"] for check in checks.values()),
        "scope": "Fixed neutral values only; source offsets and general quality unverified",
    }
    if "expected_codepoint_spans" in case:
        diagnostics = anchor_diagnostics(case, answers, result)
        summary.update(
            anchor_diagnostics=diagnostics, fixture_sha256=case["fixture_sha256"]
        )
        anchor_pass = (
            diagnostics["one_candidate_matches_all"]
            if case.get("require_unique_coordinate_candidate", True)
            else bool(diagnostics["consistent_candidates"])
        )
        summary["pass"] = summary["pass"] and anchor_pass
        summary["scope"] = (
            "One authored RU probe: fixed values and frozen occurrences; not general quality"
        )
    return summary


def emit(report, token="", account=""):
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    for secret in (token, account):
        if secret:
            # Replace escaped JSON strings too, before anything reaches stdout.
            text = text.replace(json.dumps(secret)[1:-1], "[redacted]")
    print(text)


def reject_constant(value):
    raise ValueError("Non-finite JSON number")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        choices=(
            "neutral",
            "ru-unicode",
            *ABLATION_CASES,
            *LINEBREAK_CASES,
            *QUOTE_CASES,
        ),
        default="neutral",
    )
    parser.add_argument("--live", action="store_true", help="Make one billable request")
    args = parser.parse_args()
    case = load_case(args.case)
    payload = {"model": "clairic", "state": case["state"], "fields": case["fields"]}
    if not args.live:
        emit(
            {
                "mode": "dry-run",
                "case": args.case,
                "attempts": 0,
                "request": payload,
                "expected": case["expected"],
                "fixture_sha256": case.get("fixture_sha256"),
            }
        )
        return 0

    account = os.environ.get("CF_ACCOUNT_ID", "")
    token = os.environ.get("CF_API_TOKEN", "")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", account) or not token.strip():
        emit({"error": "Set CF_ACCOUNT_ID (32 hex characters) and CF_API_TOKEN"})
        return 2
    if token != token.strip() or any(
        ord(char) < 33 or ord(char) > 126 for char in token
    ):
        emit({"error": "CF_API_TOKEN contains whitespace or non-ASCII characters"})
        return 2

    endpoint = (
        f"https://api.cloudflare.com/client/v4/accounts/{account}"
        "/ai/run/@cf/cloudflare/clairic"
    )
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = time.monotonic()
    report = {"mode": "live", "case": args.case, "attempts": 1, "retries": 0}
    exit_code = 3
    try:
        with urllib.request.build_opener(NoRedirect()).open(
            request, timeout=30
        ) as response:
            report.update(
                http_status=response.status, cf_ray=response.headers.get("cf-ray")
            )
            raw = response.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY:
            raise ValueError("Response exceeds 1 MiB")
        report.update(summarize(json.loads(raw, parse_constant=reject_constant), case))
        exit_code = 0 if report["pass"] else 1
    except urllib.error.HTTPError as exc:
        report.update(
            http_status=exc.code,
            cf_ray=exc.headers.get("cf-ray"),
            error={
                401: "Authentication failed",
                403: "Token permissions/account access/model access denied",
                404: "Account endpoint or model unavailable",
                429: "Rate limit or account quota; no retry performed",
            }.get(exc.code, "HTTP failure; no retry performed"),
            usage="unknown",
        )
        exc.close()
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError):
        report.update(
            error="Network/TLS/timeout failure", outcome="unknown", usage="unknown"
        )
    except (ValueError, TypeError, UnicodeError):
        report.update(error="Invalid or unsuccessful model response", usage="unknown")
        exit_code = 4
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    emit(report, token, account)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
