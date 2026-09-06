"""Unit tests for AI provider authentication header injection (TDD Specification)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from devops_cli.ai.providers.anthropic import AnthropicProvider
from devops_cli.ai.providers.openai import OpenAIProvider
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage


def test_openai_provider_injects_authorization_header() -> None:
    """Verify OpenAIProvider sends Authorization: Bearer header when api_key is provided."""
    config = AIConfig(provider="openai", model="gpt-4o", api_base_url="https://api.openai.com/v1")
    provider = OpenAIProvider(config, api_key="sk-test-secret-key-1234567890abcdef")

    with patch("httpx2.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "Hello"}}]}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        messages = [ChatMessage(role="user", content="Hi")]
        provider.generate(messages)

        assert mock_post.called
        call_kwargs = mock_post.call_args.kwargs
        headers = call_kwargs.get("headers", {})
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer sk-test-secret-key-1234567890abcdef"


def test_openai_provider_falls_back_to_keyring_or_env() -> None:
    """Verify OpenAIProvider falls back to environment or keyring when not passed explicitly."""
    config = AIConfig(provider="openai", model="gpt-4o", api_base_url="https://api.openai.com/v1")
    provider = OpenAIProvider(config)

    with (
        patch(
            "devops_cli.ai.providers.openai.get_keyring_secret",
            return_value="sk-from-keyring-12345678",
        ),
        patch("httpx2.post") as mock_post,
    ):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "Hello"}}]}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        messages = [ChatMessage(role="user", content="Hi")]
        provider.generate(messages)

        headers = mock_post.call_args.kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer sk-from-keyring-12345678"


def test_anthropic_provider_injects_x_api_key_header() -> None:
    """Verify AnthropicProvider sends x-api-key header when api_key is provided."""
    config = AIConfig(
        provider="claude", model="claude-3-5-sonnet", api_base_url="https://api.anthropic.com/v1"
    )
    provider = AnthropicProvider(config, api_key="sk-ant-test-secret-key-1234567890")

    with patch("httpx2.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"content": [{"text": "Hello"}]}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        messages = [ChatMessage(role="user", content="Hi")]
        provider.generate(messages)

        headers = mock_post.call_args.kwargs.get("headers", {})
        assert headers.get("x-api-key") == "sk-ant-test-secret-key-1234567890"
