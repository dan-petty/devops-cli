"""Test-first specifications for native Pydantic AI Ollama model and provider integration."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

import pytest

from devops_cli.ai.agents.testing import TestModel
from devops_cli.config.settings import Settings

pytestmark = pytest.mark.usefixtures("public_dns")


def test_native_ollama_reexports() -> None:
    """Verify devops_cli.ai.models.ollama exports all native classes, helpers, and profiles."""
    from pydantic_ai.models.ollama import OllamaModel
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.profiles import ModelProfileSpec
    from pydantic_ai.profiles.cohere import cohere_model_profile
    from pydantic_ai.profiles.deepseek import deepseek_model_profile
    from pydantic_ai.profiles.google import google_model_profile
    from pydantic_ai.profiles.harmony import harmony_model_profile
    from pydantic_ai.profiles.meta import meta_model_profile
    from pydantic_ai.profiles.mistral import mistral_model_profile
    from pydantic_ai.profiles.openai import OpenAIJsonSchemaTransformer, OpenAIModelProfile
    from pydantic_ai.profiles.qwen import qwen_model_profile
    from pydantic_ai.providers.ollama import OllamaProvider
    from pydantic_ai.settings import ModelSettings

    import devops_cli.ai.models.ollama as devops_ollama
    from devops_cli.ai.models.ollama import (
        create_ollama_model,
        create_ollama_provider,
        normalize_ollama_base_url,
    )

    # Core classes
    assert devops_ollama.OllamaModel is OllamaModel
    assert devops_ollama.OllamaProvider is OllamaProvider
    assert devops_ollama.OpenAIChatModel is OpenAIChatModel
    assert devops_ollama.OpenAIJsonSchemaTransformer is OpenAIJsonSchemaTransformer
    assert devops_ollama.OpenAIModelProfile is OpenAIModelProfile
    assert devops_ollama.ModelSettings is ModelSettings
    assert devops_ollama.ModelProfileSpec is ModelProfileSpec

    # Built-in profile builders
    assert devops_ollama.qwen_model_profile is qwen_model_profile
    assert devops_ollama.deepseek_model_profile is deepseek_model_profile
    assert devops_ollama.meta_model_profile is meta_model_profile
    assert devops_ollama.mistral_model_profile is mistral_model_profile
    assert devops_ollama.google_model_profile is google_model_profile
    assert devops_ollama.cohere_model_profile is cohere_model_profile
    assert devops_ollama.harmony_model_profile is harmony_model_profile

    # Domain helpers
    assert devops_ollama.normalize_ollama_base_url is normalize_ollama_base_url
    assert devops_ollama.create_ollama_provider is create_ollama_provider
    assert devops_ollama.create_ollama_model is create_ollama_model


def test_normalize_ollama_base_url() -> None:
    """Verify normalize_ollama_base_url standardizes URLs with clean /v1 suffix and no duplication."""
    from devops_cli.ai.models.ollama import normalize_ollama_base_url

    # Standard endpoint without path
    assert normalize_ollama_base_url("http://localhost:11434") == "http://localhost:11434/v1"
    assert normalize_ollama_base_url("http://localhost:11434/") == "http://localhost:11434/v1"

    # Endpoint with existing /v1 suffix (prevents /v1/v1 duplication)
    assert normalize_ollama_base_url("http://localhost:11434/v1") == "http://localhost:11434/v1"
    assert normalize_ollama_base_url("http://localhost:11434/v1/") == "http://localhost:11434/v1"

    # Ollama Cloud & custom subdomains
    assert normalize_ollama_base_url("https://ollama.com") == "https://ollama.com/v1"
    assert normalize_ollama_base_url("https://ollama.com/v1") == "https://ollama.com/v1"
    assert normalize_ollama_base_url("https://api.ollama.com/v1/") == "https://api.ollama.com/v1"

    # Whitespace stripping
    assert normalize_ollama_base_url("  http://127.0.0.1:11434  ") == "http://127.0.0.1:11434/v1"


def test_normalize_ollama_base_url_refuses_other_schemes() -> None:
    """Verify normalize_ollama_base_url refuses a URL whose scheme is not http or https.

    The check reads the URL only. The address, cloud metadata among them, is the connect's to check.
    """
    from devops_cli.ai.models.ollama import normalize_ollama_base_url
    from devops_cli.exceptions import InvalidURLError

    refused = []
    for url in ("ftp://example.com:11434", "file:///etc/passwd"):
        with pytest.raises(InvalidURLError, match="Invalid Ollama URL scheme"):
            normalize_ollama_base_url(url)
        refused.append(url)

    assert refused == ["ftp://example.com:11434", "file:///etc/passwd"]


@pytest.mark.parametrize("flag", [False, True], ids=["without-flag", "with-flag"])
def test_the_ollama_provider_dials_at_the_configured_level(flag: bool) -> None:
    """Verify the provider gets a factory client at the configured level of its AI configuration.

    Without a client of its own, pydantic-ai would build one that resolves the host again at the
    socket. The factory client checks each address at the connect: loopback, or private with
    `ai.allow_private_network`.
    """
    from devops_cli.ai.models.ollama import create_ollama_model, create_ollama_provider
    from devops_cli.config.settings import AIConfig
    from devops_cli.http.egress import EgressLevel
    from tests.web_fakes import egress_level_of

    ai_config = AIConfig(allow_private_network=flag)
    provider = create_ollama_provider(base_url="http://example.com:11434", ai_config=ai_config)
    model = create_ollama_model(
        "qwen3-coder:30b", base_url="http://example.com:11434", ai_config=ai_config
    )

    expected = EgressLevel.PRIVATE if flag else EgressLevel.LOOPBACK
    assert (
        egress_level_of(provider.client._client._transport),
        egress_level_of(model.client._client._transport),
    ) == (expected, expected)


def test_the_ollama_model_keeps_the_pydantic_ai_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a request of the Ollama model has the timeouts of the client pydantic-ai built before.

    pydantic-ai gives its own client 600 s and a 5 s connect, and openai uses the timeout of the
    client that it gets. The factory client of the provider (#2422) keeps these bounds, so an
    Ollama node that takes more than 1 s to accept the connect still answers.
    """
    import asyncio

    import httpx2

    from devops_cli.ai.models.ollama import create_ollama_model
    from devops_cli.config.settings import AIConfig
    from tests.web_fakes import PUBLIC_ADDRESS, http_response, record_connects

    recorder = record_connects(monkeypatch, [http_response(200, '{"object": "list", "data": []}')])
    model = create_ollama_model(
        "qwen3-coder:30b", base_url="http://example.com:11434", ai_config=AIConfig()
    )

    asyncio.run(model.client.with_options(max_retries=0).models.list())

    assert (recorder.timeouts_of(PUBLIC_ADDRESS), model.client.timeout) == (
        [5.0],
        httpx2.Timeout(600, connect=5),
    )


def test_create_ollama_provider() -> None:
    """Verify create_ollama_provider builds native OllamaProvider with cluster and auth support."""
    from pydantic_ai.providers.ollama import OllamaProvider

    from devops_cli.ai.models.ollama import create_ollama_provider

    # 1. From explicit base_url
    p1 = create_ollama_provider(base_url="http://localhost:11434")
    assert isinstance(p1, OllamaProvider)
    assert p1.base_url == "http://localhost:11434/v1/"

    # 2. From cluster URLs list
    p2 = create_ollama_provider(urls=["http://example.com:11434", "http://example.com:11435"])
    assert isinstance(p2, OllamaProvider)
    assert p2.base_url in {"http://example.com:11434/v1/", "http://example.com:11435/v1/"}

    # 3. With API key for authenticated proxies or Ollama Cloud
    p3 = create_ollama_provider(base_url="https://example.com", api_key="test-key-123")
    assert isinstance(p3, OllamaProvider)
    assert p3.base_url == "https://example.com/v1/"

    # 4. Fallback to OLLAMA_BASE_URL environment variable
    with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://example.com:11434/v1"}):
        p4 = create_ollama_provider()
        assert p4.base_url == "http://example.com:11434/v1/"


def test_create_ollama_model() -> None:
    """Verify create_ollama_model instantiates native OllamaModel with domain settings & profiles."""
    from pydantic_ai.models.ollama import OllamaModel

    from devops_cli.ai.models.ollama import create_ollama_model

    # 1. Basic model creation
    model = create_ollama_model("qwen2.5-coder:14b", base_url="http://localhost:11434")
    assert isinstance(model, OllamaModel)
    assert model.model_name == "qwen2.5-coder:14b"
    assert model.base_url == "http://localhost:11434/v1/"

    # 2. Settings propagation (temperature, max_tokens, reasoning_effort)
    model_with_settings = create_ollama_model(
        "deepseek-r1:14b",
        base_url="http://localhost:11434",
        temperature=0.3,
        max_tokens=2048,
    )
    assert isinstance(model_with_settings, OllamaModel)
    assert model_with_settings.settings is not None
    assert model_with_settings.settings.get("temperature") == 0.3
    assert model_with_settings.settings.get("max_tokens") == 2048

    # 3. Model profile resolution (Qwen vs DeepSeek thinking profile)
    assert model_with_settings.profile.get("supports_thinking") is True


def test_resolve_pydantic_ai_model_ollama() -> None:
    """Verify resolve_pydantic_ai_model delegates cleanly to create_ollama_model."""
    from pydantic_ai.models.ollama import OllamaModel

    from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model

    settings = Settings()
    settings.ai.provider = "ollama"
    settings.ai.model = "qwen2.5-coder:14b"
    settings.ai.ollama_urls = ["http://localhost:11434"]
    settings.ai.temperature = 0.2
    settings.ai.max_tokens = 4096

    # Resolve from explicit ollama: string prefix
    m1 = resolve_pydantic_ai_model("ollama:qwen2.5-coder:14b", settings=settings)
    assert isinstance(m1, OllamaModel)
    assert m1.model_name == "qwen2.5-coder:14b"
    assert m1.base_url == "http://localhost:11434/v1/"
    assert m1.settings is not None
    assert m1.settings.get("temperature") == 0.2

    # Resolve bare model name when provider is ollama
    m2 = resolve_pydantic_ai_model("llama3.2:3b", settings=settings)
    assert isinstance(m2, OllamaModel)
    assert m2.model_name == "llama3.2:3b"

    # Offline test mode bypass
    from pydantic_ai.models.test import TestModel as PyAITestModel

    with patch("devops_cli.ai.agents.testing.ALLOW_MODEL_REQUESTS", False):
        m3 = resolve_pydantic_ai_model("ollama:qwen2.5-coder:14b", settings=settings)
        assert isinstance(m3, PyAITestModel)


def test_pydantic_agent_with_ollama_model() -> None:
    """Verify PydanticAgent accepts OllamaModel and executes lifecycle with test model override."""
    from devops_cli.ai.agents.agent import PydanticAgent
    from devops_cli.ai.models.ollama import create_ollama_model

    model = create_ollama_model("qwen2.5-coder:14b", base_url="http://localhost:11434")
    agent: PydanticAgent[Any, Any] = PydanticAgent(
        model=model,
        name="OllamaTestAgent",
        instructions="You are an Ollama-powered test assistant.",
    )

    with agent.override(model=TestModel(custom_output_text="Ollama response text")):
        res = agent.run("Hello Ollama")
        assert res.content == "Ollama response text"


def test_public_package_reexports() -> None:
    """Verify Ollama models and helper functions are re-exported in ai.models."""
    import devops_cli.ai.models as models
    import devops_cli.ai.models.ollama as ollama

    assert models.OllamaModel is ollama.OllamaModel
    assert models.OllamaProvider is ollama.OllamaProvider
    assert models.create_ollama_model is ollama.create_ollama_model
    assert models.create_ollama_provider is ollama.create_ollama_provider
    assert models.normalize_ollama_base_url is ollama.normalize_ollama_base_url
