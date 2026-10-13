"""Read-only permit and unknown-resolution preflight; never applies decisions."""

from execution_records import (
    PREFIX,
    authorization,
    caps,
    digest,
    integer,
    items,
    scope_digest,
    utc,
)
from offline_bundle import canonical, object_keys, require, sha


def permit_caps(plan, run, store):
    """Validate saved authorization declarations, not current permission to execute."""
    if run["evidenceKind"] == "mock":
        require(run["permit"] is None, "Mocks cannot consume a live permit")
        return dict(plan["caps"]), None
    require(run["permit"] is not None, "Live capture requires bound permit")
    permit = store.value(run["permit"])
    object_keys(
        permit,
        "schema runId planDigest scopeDigest caps expiresAt authorization externalSpending",
    )
    require(permit["schema"] == PREFIX + "permit/v1", "Permit schema")
    require(
        permit["runId"] == run["id"]
        and permit["planDigest"] == sha(canonical(plan))
        and permit["scopeDigest"] == scope_digest(plan),
        "Permit run/plan/provider scope binding",
    )
    caps(permit["caps"])
    authorization(permit["authorization"])
    require(
        utc(permit["authorization"]["authorizedAt"]) < utc(permit["expiresAt"]),
        "Permit authorization/expiry order",
    )
    spending = permit["externalSpending"]
    object_keys(spending, "currency ceilingMicros confirmationRef provenance")
    require(
        spending["currency"] == "USD" and spending["provenance"] == "operator-asserted",
        "External spending declaration provenance",
    )
    integer(spending["ceilingMicros"])
    digest(spending["confirmationRef"])
    return {
        key: min(value, plan["caps"][key]) for key, value in permit["caps"].items()
    }, permit


def resolution_preflight(resolution, run, replay, store):
    object_keys(
        resolution,
        "schema runId planDigest journalHead attemptId action evidence authorization",
    )
    require(resolution["schema"] == PREFIX + "resolution/v1", "Resolution schema")
    require(
        resolution["runId"] == run["id"]
        and resolution["planDigest"] == run["planDigest"]
        and resolution["journalHead"] == run["journalHead"]
        and resolution["journalHead"] is not None,
        "Resolution exact run/plan/journal head",
    )
    require(
        resolution["attemptId"] in replay["unknownAttemptIds"],
        "Resolution must target an original unknown reservation",
    )
    authorization(resolution["authorization"])
    if replay["lastObservedAt"] is not None:
        require(
            utc(resolution["authorization"]["authorizedAt"])
            >= utc(replay["lastObservedAt"]),
            "Resolution authorization predates journal head",
        )
    require(
        resolution["action"] in ("stop", "adopt-saved-outcome"), "Resolution action"
    )
    items(resolution["evidence"], maximum=1)
    require(
        len(resolution["evidence"])
        == (1 if resolution["action"] == "adopt-saved-outcome" else 0),
        "Resolution evidence coverage",
    )
    for ref in resolution["evidence"]:
        # Preserve and verify bytes; adoption/normalization proof is a later gate.
        store.artifact(ref)
    return {
        "action": resolution["action"],
        "attemptId": resolution["attemptId"],
        "structuralPreflight": "passed",
        "applied": False,
        "adoptionValidated": False,
        "authorizedDispatches": 0,
        "requiredGate": "5c",
    }
