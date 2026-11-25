"""Unit tests for TypeSafe Jev (`typesafe/jev-1.14`) System One integration (`devops_cli.ai.jev`)."""

from __future__ import annotations

import json
from typing import Any, Literal

import httpx2
import pytest
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.system_one import SystemOneModel
from pydantic_ai.profiles.typesafe import typesafe_model_profile
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.system_one import SystemOneProvider

from devops_cli.ai.jev import (
    build_auto_tool_model,
    create_jev_model,
    route_with_jev,
)
from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model
from devops_cli.config.constants import CONST_AI_JEV_MODEL, CONST_URL_TYPESAFE_API_BASE
from devops_cli.config.settings import Settings
from tests.support.fakes.http import WebFake

_EXAMPLE_GATEWAY = "http://example.com:4000/v1"


def _gateway_settings(provider: str = "gateway") -> Settings:
    settings = Settings()
    settings.ai.provider = provider
    settings.ai.gateway_url = _EXAMPLE_GATEWAY
    return settings


def _mock_jev_model(handler: Any) -> SystemOneModel:
    client = httpx2.AsyncClient(
        transport=httpx2.MockTransport(handler),
        base_url=_EXAMPLE_GATEWAY,
    )
    provider = SystemOneProvider(
        api_key="sk-test",
        base_url=_EXAMPLE_GATEWAY,
        http_client=client,
    )
    return SystemOneModel(
        CONST_AI_JEV_MODEL,
        provider=provider,
        profile=typesafe_model_profile(CONST_AI_JEV_MODEL),
    )


def _score_answer(probs: list[float], confidence: float = 0.90) -> dict[str, Any]:
    """Build a valid System One `score` answer whose score matches its level probabilities."""
    score = round(sum(level * p for level, p in enumerate(probs)), 2)
    return {
        "type": "score",
        "score": score,
        "probabilities": {str(level): p for level, p in enumerate(probs)},
        "confidence": confidence,
    }


def _system_one_json(answers: dict[str, Any], input_tokens: int = 64) -> dict[str, Any]:
    """Build a valid `/v1/systemone` response payload."""
    return {
        "model": CONST_AI_JEV_MODEL,
        "answers": answers,
        "usage": {"input_tokens": input_tokens, "output_tokens": len(answers)},
    }


class TestJevModelResolution:
    """Verify bridge resolution of TypeSafe Jev and `auto` tool-call models."""

    def test_resolve_jev_model_builds_system_one_model_with_typesafe_profile(
        self, monkeypatch: pytest.MonkeyPatch, web: WebFake
    ) -> None:
        """Verify `typesafe/jev-1.14` resolves to `SystemOneModel` with the TypeSafe profile."""
        from devops_cli.ai import pydantic_ai_bridge

        monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _s: "sk-test")

        for provider in ("gateway", "ollama"):
            model = create_jev_model(settings=_gateway_settings(provider))
            assert isinstance(model, SystemOneModel)
            assert model.model_name == CONST_AI_JEV_MODEL
            assert model.profile.get("decision_max_choice_options") == 255
            assert model.profile.get("decision_max_score_levels") == 10

    def test_resolve_system_one_prefix_uses_typesafe_api_base_when_api_base_unset(
        self, monkeypatch: pytest.MonkeyPatch, web: WebFake
    ) -> None:
        """Verify `system-one:typesafe/jev-1.14` falls back to `CONST_URL_TYPESAFE_API_BASE`."""
        from devops_cli.ai import pydantic_ai_bridge

        monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _s: "sk-test")
        settings = Settings()
        settings.ai.provider = "openai"
        settings.ai.api_base_url = None

        resolved = resolve_pydantic_ai_model("system-one:typesafe/jev-1.14", settings=settings)

        assert isinstance(resolved, SystemOneModel)
        assert resolved.model_name == CONST_AI_JEV_MODEL
        assert CONST_URL_TYPESAFE_API_BASE.rstrip("/") in str(resolved._provider.base_url)

    def test_resolve_auto_model_pairs_jev_with_fallback_language_model(
        self, monkeypatch: pytest.MonkeyPatch, web: WebFake
    ) -> None:
        """Verify `auto` and `auto:<model>` resolve to `FallbackModel(SystemOneModel, ...)`."""
        from devops_cli.ai import pydantic_ai_bridge

        monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _s: "sk-test")
        settings = _gateway_settings("gateway")

        auto_default = resolve_pydantic_ai_model("auto", settings=settings)
        auto_named = resolve_pydantic_ai_model("auto:devops-coder", settings=settings)

        assert isinstance(auto_default, FallbackModel)
        assert isinstance(auto_default.models[0], SystemOneModel)
        assert auto_default.models[0].model_name == CONST_AI_JEV_MODEL

        assert isinstance(auto_named, FallbackModel)
        assert isinstance(auto_named.models[0], SystemOneModel)
        assert auto_named.models[1].model_name == "devops-coder"

    def test_router_target_does_not_resolve_to_system_one_model(
        self, monkeypatch: pytest.MonkeyPatch, web: WebFake
    ) -> None:
        """Verify `openai-chat:jev-router` and Ollama `typesafe/jev-router` are not SystemOne."""
        from devops_cli.ai import pydantic_ai_bridge

        monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _s: "sk-test")
        assert pydantic_ai_bridge._is_jev_decision_name("openai-chat:jev-router") is False

        chat_settings = Settings()
        chat_settings.ai.provider = "openai"
        chat_settings.ai.api_base_url = _EXAMPLE_GATEWAY
        resolved = resolve_pydantic_ai_model("openai-chat:jev-router", settings=chat_settings)
        assert not isinstance(resolved, SystemOneModel)

        ollama_settings = _gateway_settings("ollama")
        assert pydantic_ai_bridge._model_prefix_and_target(
            "typesafe/jev-router", ollama_settings.ai
        ) == (
            "",
            "typesafe/jev-router",
        )
        assert pydantic_ai_bridge._model_prefix_and_target(
            "typesafe/jev-1.14", ollama_settings.ai
        ) == (
            "litellm",
            "typesafe/jev-1.14",
        )


class TestJevRouting:
    """Verify `route_with_jev` probability and complexity routing."""

    def test_route_with_jev_keeps_fast_tier_when_confident_and_low_risk(self) -> None:
        """Verify a confident, low-risk tier choice is kept without escalation."""

        def handler(request: httpx2.Request) -> httpx2.Response:
            body = json.loads(request.content)
            assert set(body["questions"]) == {"tier", "complexity", "high_risk"}
            return httpx2.Response(
                200,
                json=_system_one_json(
                    {
                        "tier": {
                            "type": "choice",
                            "choice": "devops-coder",
                            "probabilities": {
                                "devops-coder": 0.88,
                                "deepseek-v4.1-flash-1017": 0.09,
                                "claude-sonnet-5-5": 0.03,
                            },
                            "confidence": 0.91,
                        },
                        "complexity": _score_answer([0.65, 0.30, 0.05, 0.00], 0.89),
                        "high_risk": {"type": "noul", "noul": 0.04, "confidence": 0.96},
                    }
                ),
            )

        decision = route_with_jev(
            {"task": "Format docstring in utils.py"},
            model=_mock_jev_model(handler),
        )

        assert decision.selected_model == "devops-coder"
        assert decision.picked_model == "devops-coder"
        assert decision.escalated is False
        assert decision.reasoning_effort == "low"
        assert decision.route_probability == pytest.approx(0.88)

    def test_route_with_jev_escalates_to_top_tier_when_high_risk(self) -> None:
        """Verify high-risk tasks escalate to the frontier tier with high reasoning effort."""

        def handler(_request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(
                200,
                json=_system_one_json(
                    {
                        "tier": {
                            "type": "choice",
                            "choice": "devops-coder",
                            "probabilities": {
                                "devops-coder": 0.75,
                                "deepseek-v4.1-flash-1017": 0.15,
                                "claude-sonnet-5-5": 0.10,
                            },
                            "confidence": 0.80,
                        },
                        "complexity": _score_answer([0.05, 0.25, 0.55, 0.15], 0.82),
                        "high_risk": {"type": "noul", "noul": 0.94, "confidence": 0.95},
                    }
                ),
            )

        decision = route_with_jev(
            {"task": "Rotate cluster Vault tokens and update egress policy"},
            model=_mock_jev_model(handler),
        )

        assert decision.selected_model == "claude-sonnet-5-5"
        assert decision.picked_model == "devops-coder"
        assert decision.escalated is True
        assert decision.reasoning_effort == "high"

    def test_route_with_jev_requires_at_least_two_tiers(self) -> None:
        """Verify `route_with_jev` rejects a single-tier mapping."""
        with pytest.raises(ValueError, match="at least two candidate models"):
            route_with_jev({"task": "noop"}, tiers={"only-one": "Single model"})


def test_the_context_window_comes_from_the_model_data() -> None:
    """The window of Jev and the diff cap of the completeness check come from genai-prices
    (#5209)."""
    from devops_cli.ai.jev import context_window, max_diff_tokens

    assert context_window() == 32_000
    assert max_diff_tokens() == 8_000


def test_auto_tool_model_executes_closed_set_tool_on_jev_and_hands_off_free_text() -> None:
    """Verify Jev answers closed-set tool calls and hands off open-ended output to the LLM."""
    calls: list[str] = []

    def jev_handler(request: httpx2.Request) -> httpx2.Response:
        calls.append("jev")
        body = json.loads(request.content)
        assert "route" in body["questions"]
        return httpx2.Response(
            200,
            json=_system_one_json(
                {
                    "route": {
                        "type": "choice",
                        "choice": "run_ci_check",
                        "probabilities": {"run_ci_check": 0.93, "TaskReport": 0.07},
                        "confidence": 0.95,
                    },
                    "run_ci_check.suite": {
                        "type": "choice",
                        "choice": "lint",
                        "probabilities": {"lint": 0.94, "unit": 0.06},
                        "confidence": 0.92,
                    },
                    "run_ci_check.fast": {
                        "type": "noul",
                        "noul": 0.91,
                        "confidence": 0.90,
                    },
                }
            ),
        )

    def lm_handler(_request: httpx2.Request) -> httpx2.Response:
        calls.append("lm")
        return httpx2.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "created": 1,
                "model": "devops-coder",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_final",
                                    "type": "function",
                                    "function": {
                                        "name": "final_result",
                                        "arguments": json.dumps({"summary": "lint passed"}),
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 6, "total_tokens": 26},
            },
        )

    class TaskReport(BaseModel):
        """Final summary report after running requested checks."""

        summary: str

    jev_model = _mock_jev_model(jev_handler)
    lm_client = httpx2.AsyncClient(
        transport=httpx2.MockTransport(lm_handler),
        base_url=_EXAMPLE_GATEWAY,
    )
    lm_model = OpenAIChatModel(
        "devops-coder",
        provider=OpenAIProvider(
            api_key="sk-test",
            base_url=_EXAMPLE_GATEWAY,
            http_client=lm_client,
        ),
    )
    auto_model = build_auto_tool_model(lm_model, jev_model=jev_model)

    agent = Agent(
        auto_model,
        output_type=TaskReport,
        instructions="Run the requested check and summarize the outcome.",
    )

    @agent.tool_plain
    def run_ci_check(suite: Literal["lint", "unit"], fast: bool) -> str:
        """Execute a deterministic CI check suite."""
        return f"{suite}:{fast}:ok"

    result = agent.run_sync("Run the fast lint check.")

    assert result.output.summary == "lint passed"
    assert calls == ["jev", "lm"]
