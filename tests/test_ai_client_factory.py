"""Tests for client factory consolidating LLMClient instantiations (#1001)."""

from __future__ import annotations

import pytest

from devops_cli.ai.client import LLMClient, build_llm_client, get_llm_client
from devops_cli.config.settings import AIConfig, Settings

pytestmark = pytest.mark.usefixtures("mock_keyring")


def test_get_llm_client_default() -> None:
    """Verify get_llm_client builds a client from active application settings."""
    client = get_llm_client()
    assert isinstance(client, LLMClient)
    assert client._config is not None


def test_get_llm_client_task() -> None:
    """Verify get_llm_client configures client for a specific task."""
    client = get_llm_client(task="chat")
    assert isinstance(client, LLMClient)
    assert client._config.task_name == "chat"


def test_get_llm_client_explicit_config() -> None:
    """Verify get_llm_client honours explicitly provided AIConfig."""
    cfg = AIConfig(provider="ollama", model="test-custom-model")
    client = get_llm_client(config=cfg, cache_enabled=False)
    assert isinstance(client, LLMClient)
    assert client.model == "test-custom-model"
    assert client._config.provider == "ollama"


def test_get_llm_client_model_override() -> None:
    """Verify get_llm_client applies model override."""
    cfg = AIConfig(provider="ollama", model="initial-model")
    client = get_llm_client(config=cfg, model="overridden-model")
    assert client.model == "overridden-model"


def test_get_llm_client_explicit_settings_and_key() -> None:
    """Verify get_llm_client honours passed Settings and explicit api_key."""
    settings = Settings()
    client = get_llm_client(settings=settings, api_key="sk-override-token")
    assert client._api_key == "sk-override-token"


def test_build_llm_client_alias() -> None:
    """Verify build_llm_client alias behaves identically to get_llm_client."""
    assert build_llm_client is get_llm_client


def test_config_settings_does_not_export_get_llm_client() -> None:
    """Verify get_llm_client is completely deleted from config.settings (#1001)."""
    import devops_cli.config.settings as settings_mod

    assert not hasattr(settings_mod, "get_llm_client")
