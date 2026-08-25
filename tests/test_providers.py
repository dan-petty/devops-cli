"""Unit tests for LLM provider abstraction layer."""

from __future__ import annotations

from devops_cli.ai.providers import (
    AnthropicProvider,
    CopilotProvider,
    MockProvider,
    OllamaProvider,
    OpenAIProvider,
    get_provider,
)
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage


def test_provider_factory() -> None:
    config = AIConfig()
    ollama = get_provider("ollama", config)
    assert isinstance(ollama, OllamaProvider)
    assert ollama.name == "ollama"

    openai = get_provider("openai", config)
    assert isinstance(openai, OpenAIProvider)
    assert openai.name == "openai"

    claude = get_provider("claude", config)
    assert isinstance(claude, AnthropicProvider)
    assert claude.name == "claude"

    copilot = get_provider("copilot", config)
    assert isinstance(copilot, CopilotProvider)
    assert copilot.name == "copilot"

    mock = get_provider("mock", config)
    assert isinstance(mock, MockProvider)
    assert mock.name == "mock"


def test_mock_provider_execution() -> None:
    config = AIConfig()
    provider = MockProvider(config, default_response='{"findings": [{"title": "test"}]}')
    assert provider.is_available() is True

    messages = [ChatMessage(role="user", content="hello")]
    res = provider.generate(messages)
    assert res == '{"findings": [{"title": "test"}]}'
    assert len(provider.invocations) == 1
    assert provider.invocations[0] == messages
