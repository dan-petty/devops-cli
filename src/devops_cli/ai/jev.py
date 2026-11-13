"""TypeSafe Jev (`typesafe/jev-1.14`) System One decision model integration.

This module implements the TypeSafe Jev cookbook patterns (`https://docs.typesafe.ai/cookbooks`)
on top of `pydantic_ai`'s native `DecisionModel` and `SystemOneModel` primitives:
1. Model routing by calibrated probability and complexity rubric (`route_with_jev`).
2. Auto mode for agentic tool calls (`build_auto_tool_model`, `select_skill_with_jev`,
   `gate_tool_call_with_jev`).
3. Structured evaluation judging (`judge_with_jev`, `create_jev_judge_evaluators`).
4. Parallel RAG passage classification (`filter_rag_passages_with_jev`).
"""

from __future__ import annotations

import atexit
import threading
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
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
    NoulCriteria,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)

from devops_cli.ai.pydantic_ai_bridge import build_auto_tool_model, resolve_pydantic_ai_model
from devops_cli.config.constants import (
    CONST_AI_JEV_DEFAULT_BOOLEAN_THRESHOLD,
    CONST_AI_JEV_DEFAULT_ROUTE_THRESHOLD,
    CONST_AI_JEV_HIGH_RISK_THRESHOLD,
    CONST_AI_JEV_MODEL,
)
from devops_cli.config.settings import Settings, load_settings

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

_TOOL_HARM_RUBRIC: Final[list[JsonValue]] = [
    "0: Read-only inspection or deterministic local check with no side effects.",
    "1: Scoped workspace file edit or test execution inside the repository.",
    "2: External network call, GitHub mutation, or cluster state change.",
    "3: Irreversible deletion, secret exposure, or security boundary bypass.",
]

_EVAL_QUALITY_RUBRIC: Final[list[JsonValue]] = [
    "0: Incorrect, fabricated, or contradicts the source material and rubric.",
    "1: Partially addresses the prompt but misses key rubric requirements.",
    "2: Meets the baseline rubric with minor omissions.",
    "3: Accurately and completely satisfies the rubric with grounded evidence.",
    "4: Exemplary, precise, and fully verified against every source and constraint.",
]

_NONE_SKILL: Final[str] = "none"


@dataclass(frozen=True)
class JevRouteDecision:
    """Calibrated routing decision from `route_with_jev`."""

    selected_model: str
    picked_model: str
    route_probability: float
    route_confidence: float
    probabilities: dict[str, float]
    complexity_score: float
    high_risk_probability: float
    reasoning_effort: Literal["low", "medium", "high"]
    escalated: bool


@dataclass(frozen=True)
class JevSkillSelection:
    """Two-step skill suggestion result from `select_skill_with_jev`."""

    skill: str | None
    candidate: str
    choice_probability: float
    choice_confidence: float
    verification_probability: float
    probabilities: dict[str, float]


@dataclass(frozen=True)
class ToolCallGateDecision:
    """Guardrail verdict for a proposed agent tool call from `gate_tool_call_with_jev`."""

    verdict: Literal["run", "review", "block"]
    aligned_probability: float
    destructive_probability: float
    secret_risk_probability: float
    harm_score: float
    harm_confidence: float


@dataclass(frozen=True)
class JevEvalVerdict:
    """Structured evaluation verdict from `judge_with_jev`."""

    passed: bool
    rubric_probability: float
    source_support_probability: float
    citation_status: Literal["supported", "contradicted", "unverified"]
    citation_confidence: float
    quality_score: float
    quality_confidence: float


@dataclass(frozen=True)
class RankedPassage:
    """A RAG passage scored by `filter_rag_passages_with_jev`."""

    index: int
    passage: str
    probability: float


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
    return jev_portal().call(decision_model.decide, request, effective_settings)


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
) -> JevRouteDecision:
    """Route a task state across model tiers using Jev's probability and rubric primitives.

    Implements the TypeSafe "Routing by probability" cookbook:
    - Evaluates `tier` (`ChoiceQuestion`), `complexity` (`ScoreQuestion`), and `high_risk`
      (`NoulQuestion`) in one parallel request.
    - Escalates to the highest capability tier when `high_risk` meets `high_risk_threshold` or
      when the picked tier's probability falls below `route_threshold`.
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
    response = decide_with_jev(
        DecisionRequest(state=state, questions=questions), model=decision_model
    )
    tier_ans = cast(ChoiceAnswer, response.answers["tier"])
    comp_ans = cast(ScoreAnswer, response.answers["complexity"])
    risk_ans = cast(NoulAnswer, response.answers["high_risk"])

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
    )


def select_skill_with_jev(
    state: JsonValue,
    catalog: Mapping[str, str],
    *,
    model: DecisionModel[Any] | None = None,
    settings: Settings | None = None,
    threshold: float = CONST_AI_JEV_DEFAULT_ROUTE_THRESHOLD,
) -> JevSkillSelection:
    """Pick at most one skill from `catalog` using the two-step TypeSafe "Skill suggestion" recipe.

    Step 1 ranks the catalog options (plus `none`) with a `ChoiceQuestion`.
    Step 2 re-checks the winning skill with a `NoulQuestion` and accepts it only when its
    probability reaches `threshold`.
    """
    if not catalog:
        raise ValueError("catalog must contain at least one skill.")
    decision_model = model or create_jev_model(settings=settings, route_threshold=threshold)
    criteria: dict[str, JsonValue] = {
        **catalog,
        _NONE_SKILL: "No skill from the catalog is needed for this turn.",
    }
    step_one = decide_with_jev(
        DecisionRequest(
            state=state,
            questions={
                "skill": ChoiceQuestion(
                    instructions="Which skill from the catalog should handle this request?",
                    criteria=criteria,
                )
            },
        ),
        model=decision_model,
    )
    choice_ans = cast(ChoiceAnswer, step_one.answers["skill"])
    picked = choice_ans.choice
    picked_prob = choice_ans.probabilities.get(picked, 0.0)
    if picked == _NONE_SKILL:
        return JevSkillSelection(
            skill=None,
            candidate=picked,
            choice_probability=picked_prob,
            choice_confidence=choice_ans.confidence,
            verification_probability=0.0,
            probabilities=dict(choice_ans.probabilities),
        )

    skill_desc = catalog[picked]
    step_two = decide_with_jev(
        DecisionRequest(
            state=state,
            questions={
                "verify": NoulQuestion(
                    instructions=f"Does this request require the skill '{picked}' ({skill_desc})?",
                    criteria=NoulCriteria(
                        true=f"The request directly calls for '{picked}': {skill_desc}",
                        false="The request does not need this skill or can be answered without it.",
                    ),
                )
            },
        ),
        model=decision_model,
    )
    verify_ans = cast(NoulAnswer, step_two.answers["verify"])
    accepted = verify_ans.noul >= threshold and picked_prob >= threshold
    return JevSkillSelection(
        skill=picked if accepted else None,
        candidate=picked,
        choice_probability=picked_prob,
        choice_confidence=choice_ans.confidence,
        verification_probability=verify_ans.noul,
        probabilities=dict(choice_ans.probabilities),
    )


def gate_tool_call_with_jev(
    tool_name: str,
    arguments: Mapping[str, Any],
    context: str,
    *,
    model: DecisionModel[Any] | None = None,
    settings: Settings | None = None,
    run_threshold: float = CONST_AI_JEV_DEFAULT_ROUTE_THRESHOLD,
    high_risk_threshold: float = CONST_AI_JEV_HIGH_RISK_THRESHOLD,
) -> ToolCallGateDecision:
    """Screen a proposed tool call with TypeSafe Jev guardrails and probability thresholds.

    Implements the "Guardrails for LLMs" and "Routing by probability" cookbooks:
    - Low-risk calls run when alignment probability reaches `run_threshold`.
    - Destructive calls require `high_risk_threshold` alignment and zero secret/egress risk,
      or are routed to `"review"` / `"block"`.
    """
    decision_model = model or create_jev_model(settings=settings, route_threshold=run_threshold)
    state: JsonValue = {
        "context": context,
        "tool_name": tool_name,
        "arguments": dict(arguments),
    }
    questions: dict[str, DecisionQuestion] = {
        "aligned": NoulQuestion(
            instructions="Is this tool call directly aligned with the user context and task goal?"
        ),
        "destructive": NoulQuestion(
            instructions="Could this tool call delete data, overwrite history, or mutate shared state?"
        ),
        "secret_risk": NoulQuestion(
            instructions="Could this tool call expose secrets, bypass a check, or exfiltrate private data?"
        ),
        "harm": ScoreQuestion(
            instructions="What is the operational risk level of executing this tool call?",
            criteria=list(_TOOL_HARM_RUBRIC),
        ),
    }
    response = decide_with_jev(
        DecisionRequest(state=state, questions=questions), model=decision_model
    )
    aligned = cast(NoulAnswer, response.answers["aligned"]).noul
    destructive = cast(NoulAnswer, response.answers["destructive"]).noul
    secret_risk = cast(NoulAnswer, response.answers["secret_risk"]).noul
    harm = cast(ScoreAnswer, response.answers["harm"])

    if secret_risk >= 0.5 or harm.score >= 2.5 or aligned < 0.4:
        verdict: Literal["run", "review", "block"] = "block"
    elif destructive >= 0.5:
        verdict = "run" if aligned >= high_risk_threshold and harm.score < 2.0 else "review"
    elif aligned >= run_threshold:
        verdict = "run"
    else:
        verdict = "review"

    return ToolCallGateDecision(
        verdict=verdict,
        aligned_probability=aligned,
        destructive_probability=destructive,
        secret_risk_probability=secret_risk,
        harm_score=harm.score,
        harm_confidence=harm.confidence,
    )


def judge_with_jev(
    output: JsonValue,
    *,
    rubric: str,
    inputs: JsonValue | None = None,
    sources: Sequence[str] | None = None,
    model: DecisionModel[Any] | None = None,
    settings: Settings | None = None,
    pass_threshold: float = CONST_AI_JEV_DEFAULT_ROUTE_THRESHOLD,
) -> JevEvalVerdict:
    """Judge an output against a rubric and reference sources in one System One request.

    Implements the TypeSafe "Verifying LLM answers against sources" and "Double-checking
    citations" cookbooks using `Noul`, `Choice`, and `Score` questions in parallel.
    """
    decision_model = model or create_jev_model(settings=settings, route_threshold=pass_threshold)
    state: dict[str, JsonValue] = {"output": output, "rubric": rubric}
    if inputs is not None:
        state["inputs"] = inputs
    if sources is not None:
        state["sources"] = list(sources)

    questions: dict[str, DecisionQuestion] = {
        "meets_rubric": NoulQuestion(
            instructions=f"Does the output satisfy this rubric: {rubric}?"
        ),
        "supported_by_sources": NoulQuestion(
            instructions="Does every factual claim in the output follow from the provided inputs and sources?"
        ),
        "citation_check": ChoiceQuestion(
            instructions="How do the provided sources relate to the claims and citations in the output?",
            criteria={
                "supported": "The sources directly support the claims and citations in the output.",
                "contradicted": "The sources contradict one or more claims or citations in the output.",
                "unverified": "The output makes claims not covered by the provided sources.",
            },
        ),
        "quality": ScoreQuestion(
            instructions="Rate the overall quality and accuracy of the output against the rubric.",
            criteria=list(_EVAL_QUALITY_RUBRIC),
        ),
    }
    response = decide_with_jev(
        DecisionRequest(state=state, questions=questions), model=decision_model
    )
    meets = cast(NoulAnswer, response.answers["meets_rubric"]).noul
    supported = cast(NoulAnswer, response.answers["supported_by_sources"]).noul
    citation = cast(ChoiceAnswer, response.answers["citation_check"])
    quality = cast(ScoreAnswer, response.answers["quality"])

    citation_status = cast(Literal["supported", "contradicted", "unverified"], citation.choice)
    passed = (
        meets >= pass_threshold
        and supported >= pass_threshold
        and citation_status != "contradicted"
        and quality.score >= 2.0
    )
    return JevEvalVerdict(
        passed=passed,
        rubric_probability=meets,
        source_support_probability=supported,
        citation_status=citation_status,
        citation_confidence=citation.confidence,
        quality_score=quality.score,
        quality_confidence=quality.confidence,
    )


def create_jev_judge_evaluators(
    rubric: str,
    *,
    criteria: str | None = None,
    evaluation_steps: Sequence[str] | None = None,
    score_range: tuple[int, int] = (1, 5),
    include_input: bool = True,
    include_expected_output: bool = False,
    model: DecisionModel[Any] | None = None,
    settings: Settings | None = None,
) -> list[Any]:
    """Create `pydantic_evals` `LLMJudge` and optional `GEval` evaluators backed by Jev."""
    from pydantic_evals.evaluators import GEval, LLMJudge

    decision_model = model or create_jev_model(settings=settings)
    evaluators: list[Any] = [
        LLMJudge(
            rubric=rubric,
            model=decision_model,
            include_input=include_input,
            include_expected_output=include_expected_output,
            score={"evaluation_name": "jev_rubric_score"},
            assertion={"evaluation_name": "jev_rubric_pass"},
        )
    ]
    if criteria and evaluation_steps:
        evaluators.append(
            GEval(
                criteria=criteria,
                evaluation_steps=list(evaluation_steps),
                score_range=score_range,
                include_input=include_input,
                model=decision_model,
                evaluation_name="jev_g_eval",
            )
        )
    return evaluators


def filter_rag_passages_with_jev(
    query: str,
    passages: Sequence[str],
    *,
    model: DecisionModel[Any] | None = None,
    settings: Settings | None = None,
    threshold: float = CONST_AI_JEV_DEFAULT_BOOLEAN_THRESHOLD,
) -> list[RankedPassage]:
    """Score retrieved RAG passages in parallel and keep those meeting `threshold`.

    Implements the TypeSafe "Classifying RAG passages" cookbook by sending all passages in one
    `DecisionRequest` with one `NoulQuestion` per passage.
    """
    if not passages:
        return []
    decision_model = model or create_jev_model(settings=settings, boolean_threshold=threshold)
    state: JsonValue = {
        "query": query,
        "passages": {f"passage_{idx}": text for idx, text in enumerate(passages)},
    }
    questions: dict[str, DecisionQuestion] = {
        f"passage_{idx}": NoulQuestion(
            instructions=(
                f"Does passage_{idx} contain relevant evidence that helps answer the query?"
            )
        )
        for idx in range(len(passages))
    }
    response = decide_with_jev(
        DecisionRequest(state=state, questions=questions), model=decision_model
    )
    kept: list[RankedPassage] = []
    for idx, text in enumerate(passages):
        ans = cast(NoulAnswer, response.answers[f"passage_{idx}"])
        if ans.noul >= threshold:
            kept.append(RankedPassage(index=idx, passage=text, probability=ans.noul))
    kept.sort(key=lambda item: item.probability, reverse=True)
    return kept


__all__ = [
    "DEFAULT_ROUTING_TIERS",
    "JevEvalVerdict",
    "JevRouteDecision",
    "JevSkillSelection",
    "RankedPassage",
    "ToolCallGateDecision",
    "build_auto_tool_model",
    "create_jev_judge_evaluators",
    "create_jev_model",
    "decide_with_jev",
    "filter_rag_passages_with_jev",
    "gate_tool_call_with_jev",
    "jev_portal",
    "judge_with_jev",
    "route_with_jev",
    "select_skill_with_jev",
]
