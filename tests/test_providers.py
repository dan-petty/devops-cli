"""Unit tests for LLM provider abstraction layer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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


def test_anthropic_provider() -> None:
    """Test AnthropicProvider generation and availability."""
    config = AIConfig(
        provider="claude", api_base_url="https://api.anthropic.com/v1", model="claude-3-7-sonnet"
    )
    provider = AnthropicProvider(config)
    assert provider.name == "claude"
    assert provider.is_available() is True

    messages = [
        ChatMessage(role="system", content="System instruction"),
        ChatMessage(role="user", content="Hello Claude"),
    ]

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"content": [{"type": "text", "text": "Hello world"}]}
    mock_resp.raise_for_status.return_value = None

    with patch("httpx2.post", return_value=mock_resp) as mock_post:
        res = provider.generate(messages, max_tokens=1000)
        assert res == {"content": [{"type": "text", "text": "Hello world"}]}
        mock_post.assert_called_once()


def test_ollama_provider() -> None:
    """Test OllamaProvider availability and chat completion generation."""
    config = AIConfig(
        provider="ollama", model="qwen2.5-coder:7b", ollama_urls=["http://localhost:11434"]
    )
    provider = OllamaProvider(config)
    assert provider.name == "ollama"

    mock_tags = MagicMock()
    mock_tags.status_code = 200
    with patch("httpx2.get", return_value=mock_tags):
        assert provider.is_available() is True

    with patch("httpx2.get", side_effect=Exception("Connection refused")):
        assert provider.is_available() is False

    messages = [ChatMessage(role="user", content="Hello Ollama")]
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": "Ollama response"}}
    mock_resp.raise_for_status.return_value = None

    with patch("httpx2.post", return_value=mock_resp) as mock_post:
        res = provider.generate(messages, stream=False)
        assert res == {"message": {"content": "Ollama response"}}
        mock_post.assert_called_once()

    # Test reasoning_effort parameter passed to payload
    config_reasoning = AIConfig(provider="ollama", model="qwen3.8:27b", reasoning_effort="low")
    provider_reasoning = OllamaProvider(config_reasoning)
    with patch("httpx2.post", return_value=mock_resp) as mock_post:
        provider_reasoning.generate(messages)
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["reasoning_effort"] == "low"


def test_openai_provider() -> None:
    """Test OpenAIProvider generation and availability."""
    config = AIConfig(
        provider="openai",
        api_base_url="https://api.openai.com/v1",
        model="gpt-4o",
        reasoning_effort="medium",
    )
    provider = OpenAIProvider(config)
    assert provider.name == "openai"
    assert provider.is_available() is True

    messages = [ChatMessage(role="user", content="Hello GPT")]
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": "GPT reply"}}]}
    mock_resp.raise_for_status.return_value = None

    with patch("httpx2.post", return_value=mock_resp) as mock_post:
        res = provider.generate(messages)
        assert res == {"choices": [{"message": {"content": "GPT reply"}}]}
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["reasoning_effort"] == "medium"


def test_copilot_provider() -> None:
    """Test CopilotProvider generation."""
    config = AIConfig(provider="copilot", model="gpt-4o")
    provider = CopilotProvider(config)
    assert provider.name == "copilot"
    assert provider.is_available() is True

    messages = [ChatMessage(role="user", content="Hello Copilot")]
    res = provider.generate(messages)
    assert res["model"] == "gpt-4o"
    assert res["messages"] == messages
