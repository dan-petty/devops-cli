"""TypeSafe Jev (`typesafe/jev-1.14`) System One decision model integration.

This module implements the TypeSafe Jev cookbook patterns (`https://docs.typesafe.ai/cookbooks`)
on top of `pydantic_ai`'s native `DecisionModel` and `SystemOneModel` primitives:
Model routing by calibrated probability and a complexity rubric (`route_with_jev`), and the
`auto` mode of the agentic tool calls (`build_auto_tool_model`). The other cookbook functions had
no caller and left (#5276).
"""

from __future__ import annotations

import atexit
import threading
from collections.abc import Mapping
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import Any, Final, Literal, cast

from anyio.from_thread import BlockingPortal, start_blocking_portal
from pydantic import JsonValue
from pydantic_ai.models.decision import (
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionModel,
    DecisionModelSettings,
    DecisionQuestion,
    DecisionRequest,
    DecisionResponse,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)

from devops_cli.ai.pydantic_ai_bridge import build_auto_tool_model, resolve_pydantic_ai_model
from devops_cli.config.constants import (
    CONST_AI_JEV_CONTEXT_WINDOW,
    CONST_AI_JEV_DEFAULT_BOOLEAN_THRESHOLD,
    CONST_AI_JEV_DEFAULT_ROUTE_THRESHOLD,
    CONST_AI_JEV_HIGH_RISK_THRESHOLD,
    CONST_AI_JEV_MODEL,
)
from devops_cli.config.settings import Settings, load_settings


def context_window(model_name: str = CONST_AI_JEV_MODEL) -> int:
    """The context window that genai-prices gives for `model_name` (#5209).

    The constant is the fallback for a model that the data does not name, so a change of the model
    data changes the window and the diff cap of the completeness check with it.
    """
    from genai_prices.data_snapshot import get_snapshot

    name = model_name.split("/", 1)[-1]
    for provider in get_snapshot().providers:
        for entry in provider.models:
            if entry.id in (name, f"{name}.0") and entry.context_window:
                return entry.context_window
    return CONST_AI_JEV_CONTEXT_WINDOW


def max_diff_tokens() -> int:
    """The diff cap of the Jev completeness check: one fourth of the window (#4308, #5209)."""
    return context_window() // 4


DEFAULT_ROUTING_TIERS: Final[dict[str, str]] = {
    "devops-coder": "Fast local coder tier for routine edits, formatting, and single-file changes.",
    "deepseek-v4.1-flash-1017": (
        "Mid-tier hosted model for multi-file analysis, verification, and standard bug fixes."
    ),
    "claude-sonnet-5-5": (
        "Frontier reasoning tier for complex architecture, security-critical code, and hard repairs."
    ),
}

_COMPLEXITY_RUBRIC: Final[list[JsonValue]] = [
    "0: Trivial lookup, formatting change, or single-line configuration edit.",
    "1: Standard single-module code change or unit test update.",
    "2: Multi-module feature, bug fix, or workflow integration.",
    "3: Complex architectural refactor, security control, or multi-step root-cause repair.",
]


@dataclass(frozen=True)
class JevRouteDecision:
    """Calibrated routing decision from `route_with_jev`. `extra_probabilities` holds the Noul
    probability of each question that the caller gave in `extra_questions`, by name, and is empty
    for a call with none (#4284)."""

    selected_model: str
    picked_model: str
    route_probability: float
    route_confidence: float
    probabilities: dict[str, float]
    complexity_score: float
    high_risk_probability: float
    reasoning_effort: Literal["low", "medium", "high"]
    escalated: bool
    extra_probabilities: dict[str, float] = field(default_factory=dict)


def create_jev_model(
    model_name: str = CONST_AI_JEV_MODEL,
    *,
    settings: Settings | None = None,
    route_threshold: float | None = CONST_AI_JEV_DEFAULT_ROUTE_THRESHOLD,
    boolean_threshold: float | None = CONST_AI_JEV_DEFAULT_BOOLEAN_THRESHOLD,
) -> DecisionModel[Any]:
    """Build a configured TypeSafe Jev `DecisionModel` instance."""
    active_settings = settings or load_settings()
    resolved = resolve_pydantic_ai_model(model_name, settings=active_settings)
    model_settings: DecisionModelSettings = {}
    if route_threshold is not None:
        model_settings["decision_route_threshold"] = route_threshold
    if boolean_threshold is not None:
        model_settings["decision_boolean_threshold"] = boolean_threshold
    if model_settings and hasattr(resolved, "_settings"):
        merged = dict(getattr(resolved, "_settings", None) or {})
        merged.update(model_settings)
        resolved._settings = merged
    return cast(DecisionModel[Any], resolved)


_portal_lock = threading.Lock()
_portal_stack: ExitStack | None = None
_portal: BlockingPortal | None = None


def jev_portal() -> BlockingPortal:
    """The one event loop that runs every Jev request of this process, started on first use.

    The HTTP client of a model dials on the event loop of its first request, and its pooled
    connections belong to that loop. `asyncio.run` closes the loop at the end of each request, so
    a second request on the same model failed with `RuntimeError: Event loop is closed` (#4319).
    An anyio blocking portal keeps one loop open in a thread until the process ends.
    """
    global _portal, _portal_stack
    with _portal_lock:
        if _portal is None:
            _portal_stack = ExitStack()
            _portal = _portal_stack.enter_context(start_blocking_portal())
        return _portal


def reset_jev_portal() -> None:
    """Stop the loop of the Jev requests. The next request starts a new one. A model that has
    served a request on the stopped loop must not serve another one, so tests call this between
    tests and the process calls it at exit."""
    global _portal, _portal_stack
    with _portal_lock:
        stack, _portal, _portal_stack = _portal_stack, None, None
    if stack is not None:
        stack.close()


atexit.register(reset_jev_portal)


def record_jev_spend(response: DecisionResponse) -> None:
    """Record one Jev decision call in the spend ledger (#4296).

    A Jev call runs no Agent, so the spend hook of `build_agent` never sees it. The ledger prices
    the answer at the Jev price of `_HOSTED_GROUP_PRICES`, and the call stays intact when the
    ledger cannot write or the answer names no usage.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    from devops_cli.ai.spend.ledger import track_request_spend
    from devops_cli.config.constants import CONST_AI_GATEWAY_PROVIDER

    try:
        track_request_spend(
            provider=CONST_AI_GATEWAY_PROVIDER,
            model=CONST_AI_JEV_MODEL,
            server=CONST_AI_JEV_MODEL,
            served_model=CONST_AI_JEV_MODEL,
            prompt_tokens=getattr(usage, "input_tokens", 0),
            completion_tokens=getattr(usage, "output_tokens", 0),
            reasoning_tokens=getattr(usage, "output_reasoning_tokens", 0),
        )
    except OSError, RuntimeError, TypeError, ValueError, KeyError:
        # The spend record is a report, and a Jev answer that the caller holds is worth more. The
        # ledger refuses a broken row with these errors, and a settings file with no data dir.
        return


def decide_with_jev(
    request: DecisionRequest,
    *,
    model: DecisionModel[Any] | None = None,
    settings: Settings | None = None,
    model_settings: DecisionModelSettings | None = None,
) -> DecisionResponse:
    """Send one request to a Jev model and return the typed response.

    Without `model`, the function builds the Jev model from `settings`. The call may come from any
    thread, also from a thread that runs an event loop, and the same model may serve any number of
    calls. `model_settings` of the call win over the settings of the model. The function raises
    the exception that `DecisionModel.decide` raises.
    """
    decision_model = model or create_jev_model(settings=settings)
    effective_settings = cast(
        DecisionModelSettings,
        {**(getattr(decision_model, "settings", None) or {}), **(model_settings or {})},
    )
    response = jev_portal().call(decision_model.decide, request, effective_settings)
    record_jev_spend(response)
    return response


def _effort_for_score(score: float, *, escalated: bool) -> Literal["low", "medium", "high"]:
    """Map a 0-3 complexity score to a reasoning effort level."""
    if escalated or score >= 2.0:
        return "high"
    if score >= 1.0:
        return "medium"
    return "low"


def route_with_jev(
    state: JsonValue,
    *,
    tiers: Mapping[str, str] | None = None,
    model: DecisionModel[Any] | None = None,
    settings: Settings | None = None,
    route_threshold: float = CONST_AI_JEV_DEFAULT_ROUTE_THRESHOLD,
    high_risk_threshold: float = CONST_AI_JEV_HIGH_RISK_THRESHOLD,
    extra_questions: Mapping[str, DecisionQuestion] | None = None,
) -> JevRouteDecision:
    """Route a task state across model tiers using Jev's probability and rubric primitives.

    Implements the TypeSafe "Routing by probability" cookbook:
    - Evaluates `tier` (`ChoiceQuestion`), `complexity` (`ScoreQuestion`), and `high_risk`
      (`NoulQuestion`) in one parallel request.
    - Escalates to the highest capability tier when `high_risk` meets `high_risk_threshold` or
      when the picked tier's probability falls below `route_threshold`.

    `extra_questions` adds one Noul question for each entry to the same request, and the answer of
    each goes to `extra_probabilities`, by name (#4284).
    """
    candidate_tiers = dict(tiers or DEFAULT_ROUTING_TIERS)
    if len(candidate_tiers) < 2:
        raise ValueError("tiers must contain at least two candidate models.")
    decision_model = model or create_jev_model(settings=settings, route_threshold=route_threshold)
    questions: dict[str, DecisionQuestion] = {
        "tier": ChoiceQuestion(
            instructions="Which model tier best fits this task state?",
            criteria=cast(dict[str, JsonValue], candidate_tiers),
        ),
        "complexity": ScoreQuestion(
            instructions="How complex is this engineering task?",
            criteria=list(_COMPLEXITY_RUBRIC),
        ),
        "high_risk": NoulQuestion(
            instructions=(
                "Does this task modify credentials, access controls, network boundaries, "
                "cluster secrets, or production state?"
            ),
        ),
    }
    questions.update(extra_questions or {})
    response = decide_with_jev(
        DecisionRequest(state=state, questions=questions), model=decision_model
    )
    tier_ans = cast(ChoiceAnswer, response.answers["tier"])
    comp_ans = cast(ScoreAnswer, response.answers["complexity"])
    risk_ans = cast(NoulAnswer, response.answers["high_risk"])
    extra = {
        name: cast(NoulAnswer, response.answers[name]).noul for name in (extra_questions or {})
    }

    picked = tier_ans.choice
    picked_prob = tier_ans.probabilities.get(picked, 0.0)
    top_tier = list(candidate_tiers.keys())[-1]
    escalated = (
        risk_ans.noul >= high_risk_threshold
        or picked_prob < route_threshold
        or comp_ans.score >= 2.5
    )
    selected = top_tier if escalated else picked
    return JevRouteDecision(
        selected_model=selected,
        picked_model=picked,
        route_probability=picked_prob,
        route_confidence=tier_ans.confidence,
        probabilities=dict(tier_ans.probabilities),
        complexity_score=comp_ans.score,
        high_risk_probability=risk_ans.noul,
        reasoning_effort=_effort_for_score(comp_ans.score, escalated=escalated),
        escalated=escalated,
        extra_probabilities=extra,
    )


__all__ = [
    "DEFAULT_ROUTING_TIERS",
    "JevRouteDecision",
    "build_auto_tool_model",
    "create_jev_model",
    "decide_with_jev",
    "jev_portal",
    "route_with_jev",
]
