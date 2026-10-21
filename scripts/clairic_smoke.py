"""Neutral Clairic smoke: dry-run by default, one HTTP attempt with --live."""

import argparse
import json
import os
import re
import signal
import socket
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager

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


class DeadlineUnavailable(RuntimeError):
    """Refuse live execution when a total deadline cannot be installed safely."""


@contextmanager
def total_deadline(seconds):
    """Bound the synchronous CLI operation, including trickling response reads."""
    if (
        not hasattr(signal, "setitimer")
        or threading.current_thread() is not threading.main_thread()
    ):
        raise DeadlineUnavailable("Live mode requires POSIX timers on the main thread")
    if seconds <= 0 or signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise DeadlineUnavailable("Invalid deadline or existing process timer")

    def expired(signum, frame):
        raise TimeoutError("Total live-request deadline exceeded")

    previous = signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def summarize(document):
    """Check the fixed smoke values; this is not general semantic validation."""
    if not isinstance(document, dict):
        raise ValueError("Expected a JSON object")
    if document.get("success") is False:
        raise ValueError("Cloudflare returned success=false")
    # Workers AI REST envelope and the direct model shape shown in model docs.
    result = document.get("result") if "result" in document else document
    if not isinstance(result, dict) or not isinstance(result.get("answers"), dict):
        raise ValueError("Missing result.answers object")
    answers = result["answers"]
    checks = {}
    for name, expected in EXPECTED.items():
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
            "pass": matches and answer.get("type") == FIELDS[name]["type"],
        }
    complete = result.get("truncated") is False
    return {
        "model": result.get("model"),
        "truncated": result.get("truncated"),
        "usage": result.get("usage"),
        "answers": answers,
        "checks": checks,
        "pass": complete and all(check["pass"] for check in checks.values()),
        "scope": "Fixed neutral values only; source offsets and general quality unverified",
    }


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
    parser.add_argument("--live", action="store_true", help="Make one billable request")
    args = parser.parse_args()
    payload = {"model": "clairic", "state": STATE, "fields": FIELDS}
    if not args.live:
        emit(
            {"mode": "dry-run", "attempts": 0, "request": payload, "expected": EXPECTED}
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
    report = {"mode": "live", "attempts": 0, "retries": 0}
    exit_code = 3
    try:
        with total_deadline(30):
            report["attempts"] = 1
            with urllib.request.build_opener(NoRedirect()).open(
                request, timeout=30
            ) as response:
                report.update(
                    http_status=response.status, cf_ray=response.headers.get("cf-ray")
                )
                raw = response.read(MAX_BODY + 1)
            if len(raw) > MAX_BODY:
                raise ValueError("Response exceeds 1 MiB")
            report.update(summarize(json.loads(raw, parse_constant=reject_constant)))
            exit_code = 0 if report["pass"] else 1
    except DeadlineUnavailable:
        report.update(
            error="Total deadline unavailable; no request sent", usage="not_started"
        )
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
