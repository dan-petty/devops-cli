"""Provider gateway talks only to the gateway, never to a base URL meant for another provider."""

from __future__ import annotations

import pytest

from devops_cli.ai.client import LLMClient
from devops_cli.ai.pydantic_ai_bridge import _resolve_remote_provider_endpoint
from devops_cli.config.settings import AIConfig, AITaskOverride, Settings

GATEWAY_URL = "http://gateway.example.com:4000/v1"
OPENAI_URL = "https://api.example.com/v1"
TASK_GATEWAY_URL = "http://task-gateway.example.com:4000/v1"


@pytest.fixture(autouse=True)
def _allow_private_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")


def _openai_setup_with_gateway_chat(chat_api_base_url: str | None = None) -> AIConfig:
    """Global OpenAI setup whose chat task alone uses the gateway."""
    ai = AIConfig(provider="openai", api_base_url=OPENAI_URL, gateway_url=GATEWAY_URL)
    ai.tasks.chat = AITaskOverride(provider="gateway", api_base_url=chat_api_base_url)
    return ai


def test_gateway_task_ignores_global_api_base_url() -> None:
    """Verify a gateway task sends to gateway_url, not the global OpenAI base URL."""
    client = LLMClient(_openai_setup_with_gateway_chat().for_task("chat"))

    assert (client._api_base(), client.backend_host) == (GATEWAY_URL, "gateway.example.com:4000")


def test_gateway_task_api_base_url_overrides_gateway_url() -> None:
    """Verify a gateway task's own api_base_url is that task's gateway address."""
    chat = _openai_setup_with_gateway_chat(TASK_GATEWAY_URL).for_task("chat")

    assert (chat.gateway_url, LLMClient(chat)._api_base()) == (TASK_GATEWAY_URL, TASK_GATEWAY_URL)


def test_global_gateway_provider_ignores_global_api_base_url() -> None:
    """Verify provider gateway uses gateway_url even when api_base_url is set beside it."""
    ai = AIConfig(provider="gateway", api_base_url=OPENAI_URL, gateway_url=GATEWAY_URL)

    assert LLMClient(ai)._api_base() == GATEWAY_URL


def test_task_switching_provider_does_not_inherit_global_api_base_url() -> None:
    """Verify only tasks that keep the global provider inherit its api_base_url."""
    ai = AIConfig(provider="openai", api_base_url=OPENAI_URL)
    ai.tasks.analysis = AITaskOverride(provider="claude")
    ai.tasks.compose = AITaskOverride(provider="openai")

    assert (
        ai.for_task("analysis").api_base_url,
        ai.for_task("compose").api_base_url,
        ai.for_task("metadata").api_base_url,
    ) == (None, OPENAI_URL, OPENAI_URL)


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("litellm:devops-coder", ("devops-coder", GATEWAY_URL)),
        ("portkey:devops-coder", ("devops-coder", "http://portkey.example.com:8787/v1")),
        ("lightllm:devops-coder", ("devops-coder", "http://lightllm.example.com:8000/v1")),
    ],
)
def test_bridge_gateway_prefixes_use_their_configured_urls(
    model: str, expected: tuple[str, str]
) -> None:
    """Verify gateway model prefixes resolve to their configured gateways, not api_base_url."""
    settings = Settings(
        ai=AIConfig(
            api_base_url=OPENAI_URL,
            gateway_url=GATEWAY_URL,
            portkey_url="http://portkey.example.com:8787/v1",
            lightllm_url="http://lightllm.example.com:8000/v1",
        )
    )

    assert _resolve_remote_provider_endpoint(model, settings) == expected
