"""The chat providers accept the loopback endpoints of `config.example.yaml`."""

from __future__ import annotations

import pytest
import yaml

from devops_cli.ai.client import LLMClient
from devops_cli.config.settings import Settings
from tests.support.paths import REPO_ROOT

EXAMPLE_CONFIG = REPO_ROOT / "config.example.yaml"


@pytest.fixture
def example_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Settings loaded from `config.example.yaml`, with no private-network override set."""
    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    return Settings.model_validate(yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8")))


def test_the_example_config_chat_providers_accept_its_loopback_endpoints(
    example_settings: Settings,
) -> None:
    """Verify the chat client takes the example's loopback Ollama and gateway endpoints."""
    ai = example_settings.ai
    gateway = LLMClient(ai.model_copy(update={"provider": "gateway"}), api_key="sk-test")

    assert (
        LLMClient(ai)._validate_base_url(ai.get_ollama_urls[0], purpose="Ollama"),
        gateway._api_base(),
    ) == ("http://localhost:11434", "http://localhost:4000/v1")
