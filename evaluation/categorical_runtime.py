"""Current categorical policy bridge; explicit evaluation, no sampling or routing."""

from contextlib import contextmanager
from dataclasses import asdict

from provider_config import require
from provider_runtime import build_provider as native_provider
from responses_runtime import ResponsesConfig, result_document, task, validate_task
from responses_runtime import build_provider as responses_provider

POLICY_SCHEMA = "normlab.categorical-policy/v1"
OUTCOMES = {"accept", "reject", "review"}


def validate_policy(data, policy):
    """Require explicit routing for every configured label; never infer gold."""
    validate_task(data)
    require(
        isinstance(policy, dict)
        and set(policy) == {"schema", "questions"}
        and policy["schema"] == POLICY_SCHEMA
        and isinstance(policy["questions"], dict)
        and set(policy["questions"]) == set(data["questions"]),
        "Policy must map every task question",
    )
    for name, question in data["questions"].items():
        mapping = policy["questions"][name]
        require(
            isinstance(mapping, dict)
            and set(mapping) == set(question["criteria"])
            and all(isinstance(v, str) and v in OUTCOMES for v in mapping.values()),
            "Policy must explicitly map every configured label to accept/reject/review",
        )
    return policy


def validate_tactic(config, data, tactic):
    validate_task(data)
    require(tactic in {"independent", "batch"}, "Explicit categorical tactic")
    require(
        isinstance(config, ResponsesConfig)
        or tactic == "independent"
        or len(data["questions"]) == 1,
        "Native categorical wrappers do not support multi-question batches",
    )


@contextmanager
def build_provider(config, *, key_file=None, transport=None):
    """Own the underlying provider lifetime; SDK wrappers only borrow it."""
    if isinstance(config, ResponsesConfig):
        with responses_provider(
            config, key_file=key_file, transport=transport
        ) as provider:
            yield provider
    else:
        with native_provider(config, key_file=key_file, transport=transport) as native:
            from mellea_jev import (
                OpenAICategoricalProvider,
                TypeSafeCategoricalProvider,
            )

            wrapper = (
                TypeSafeCategoricalProvider
                if config.api_format == "typesafe-systemone"
                else OpenAICategoricalProvider
            )
            yield wrapper(native)


def evaluate(provider, data, policy):
    """One classify via direct evaluate(); review stays data, errors propagate.

    No generated Mellea candidate/context is involved: bind the caller's exact
    state and questions, including any typed candidate, to an SDK task snapshot.
    """
    validate_policy(data, policy)
    from mellea_jev import CategoricalDecision, CategoricalRequirement

    bound = task(data)
    # Snapshot policy too; provider callbacks cannot mutate this evaluation's rules.
    rules = {name: dict(mapping) for name, mapping in policy["questions"].items()}

    def decide(result):
        outcomes = {rules[name][label] for name, label in result.answers.items()}
        if "review" in outcomes:
            outcome = "review"
        elif "reject" in outcomes:
            outcome = "reject"
        else:
            outcome = "accept"
        return CategoricalDecision(
            outcome, "Explicit caller label policy; no confidence threshold."
        )

    return CategoricalRequirement(
        provider,
        task_builder=lambda _: bound,
        policy=decide,
        description="Evaluate the caller-bound Choice task under explicit application policy.",
    ).evaluate(None)


def evaluation_document(evaluation, policy):
    """Serialize selected evidence only, not raw SDK bodies or exception text."""
    result = evaluation.result
    return {
        **result_document(result),
        "native_results": (
            {name: asdict(value) for name, value in result.native_results.items()}
            if result.native_results is not None
            else None
        ),
        "decision": asdict(evaluation.decision),
        "questionDecisions": {
            name: policy["questions"][name][label]
            for name, label in result.answers.items()
        },
    }
