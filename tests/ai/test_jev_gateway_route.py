"""The Jev client and the LLM gateway agree on one route (#4289).

`SystemOneModel` posts the Decisions protocol to `{ai.gateway_url}/systemone`. A LiteLLM
pass-through serves that path and forwards it to the System One endpoint of OpenRouter, which
takes the same request and answer as the Decisions API (https://openrouter.ai/docs/guides/community/jev).
The environment repository configures the pass-through route.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic_ai.models.decision import DecisionRequest, NoulAnswer, NoulQuestion

from devops_cli.ai.jev import decide_with_jev
from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model
from devops_cli.config.constants import CONST_AI_JEV_MODEL
from devops_cli.config.settings import Settings
from tests.support.fakes.http import WebFake

EXAMPLE_GATEWAY = "http://example.com:4000/v1"
OPENROUTER_ANSWER: dict[str, Any] = {
    "id": "gen-dec-1789738314-X5e5eKGQdvR9rblyX250",
    "model": "typesafe/jev-1.14-20261014",
    "provider": "TypeSafe",
    "answers": {"is_bug": {"type": "noul", "noul": 0.96, "confidence": 0.9}},
    "usage": {"input_tokens": 476, "output_tokens": 70, "cost": 0.000019992},
}


def _gateway_settings() -> Settings:
    settings = Settings()
    settings.ai.provider = "gateway"
    settings.ai.gateway_url = EXAMPLE_GATEWAY
    return settings


def _ask_jev_once(web: WebFake, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Send one Noul question through the model that the bridge builds, and return the request."""
    from devops_cli.ai import pydantic_ai_bridge

    monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _s: "sk-test")
    web.respond("POST", f"{EXAMPLE_GATEWAY}/systemone", 200, OPENROUTER_ANSWER)
    response = decide_with_jev(
        DecisionRequest(
            state={"report": "The page is blank after Pay."},
            questions={"is_bug": NoulQuestion(instructions="Is this a software defect?")},
        ),
        settings=_gateway_settings(),
    )
    assert isinstance(response.answers["is_bug"], NoulAnswer)
    return web.recorded[0]


def test_the_client_posts_the_body_that_openrouter_documents(
    web: WebFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The body holds `model`, `state` and `questions`, as the Decisions API documents, and the
    model is named without a gateway prefix."""
    request = _ask_jev_once(web, monkeypatch)

    assert (request.method, request.json["model"], sorted(request.json)) == (
        "POST",
        CONST_AI_JEV_MODEL,
        ["model", "questions", "state"],
    )
    assert request.json["questions"]["is_bug"] == {
        "type": "noul",
        "instructions": "Is this a software defect?",
    }
    assert request.headers["authorization"] == "Bearer sk-test"


def test_the_client_reads_the_answer_that_openrouter_adds_fields_to(
    web: WebFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`id`, `provider` and `usage.cost`, which OpenRouter adds, do not stop the client."""
    from devops_cli.ai import pydantic_ai_bridge

    monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _s: "sk-test")
    web.respond("POST", f"{EXAMPLE_GATEWAY}/systemone", 200, OPENROUTER_ANSWER)

    response = decide_with_jev(
        DecisionRequest(
            state="The page is blank after Pay.",
            questions={"is_bug": NoulQuestion(instructions="Is this a software defect?")},
        ),
        settings=_gateway_settings(),
    )

    assert (response.model_name, response.answers["is_bug"].noul, response.usage.input_tokens) == (
        "typesafe/jev-1.14-20261014",
        0.96,
        476,
    )


def test_the_bridge_sends_every_jev_name_to_the_route_of_the_gateway(
    web: WebFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bare name and the `litellm:` prefixed name reach the same URL."""
    from devops_cli.ai import pydantic_ai_bridge

    monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _s: "sk-test")
    settings = _gateway_settings()
    urls = {
        name: f"{resolve_pydantic_ai_model(name, settings=settings).base_url}/systemone"
        for name in (CONST_AI_JEV_MODEL, f"litellm:{CONST_AI_JEV_MODEL}")
    }

    assert set(urls.values()) == {f"{EXAMPLE_GATEWAY}/systemone"}
