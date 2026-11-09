"""The chat providers accept the loopback endpoints of `config.example.yaml`."""

from __future__ import annotations

import httpx2
import pytest
import yaml

from devops_cli.ai.client import LLMClient
from devops_cli.config.settings import Settings
from tests.support.fakes.http import WebFake
from tests.support.llm_stream_fakes import serve_llm
from tests.support.paths import REPO_ROOT

EXAMPLE_CONFIG = REPO_ROOT / "config.example.yaml"


@pytest.fixture
def example_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Settings loaded from `config.example.yaml`, with no private-network override set."""
    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    return Settings.model_validate(yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    ("provider", "endpoint"),
    [
        ("ollama", "http://localhost:11434/"),
        ("gateway", "http://localhost:4000/v1/chat/completions"),
    ],
)
def test_the_example_config_chat_providers_accept_its_loopback_endpoints(
    provider: str, endpoint: str, example_settings: Settings, web: WebFake
) -> None:
    """The chat client sends a chat to the loopback Ollama and gateway endpoints of the example."""
    sent = serve_llm(
        web,
        lambda request: httpx2.Response(
            200, json={"choices": [{"message": {"content": "OK"}}], "message": {"content": "OK"}}
        ),
    )
    ai = example_settings.ai.model_copy(update={"provider": provider})

    reply = LLMClient(ai, api_key="sk-test", cache_enabled=False).chat(
        "You are terse.", "Reply with OK.", use_cache=False
    )

    assert (str(reply), [str(request.url).startswith(endpoint) for request in sent]) == (
        "OK",
        [True],
    )
