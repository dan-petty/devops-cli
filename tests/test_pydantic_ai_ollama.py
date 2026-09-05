"""Test-first specifications for native Pydantic AI Ollama model and provider integration."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

from devops_cli.ai.agents.testing import TestModel
from devops_cli.config.settings import Settings


def test_native_ollama_reexports() -> None:
    """Verify devops_cli.ai.models.ollama exports all native classes, helpers, and profiles."""
    import devops_cli.ai.models.ollama as devops_ollama

    # Core classes
    assert hasattr(devops_ollama, "OllamaModel")
    assert hasattr(devops_ollama, "OllamaProvider")
    assert hasattr(devops_ollama, "OpenAIChatModel")
    assert hasattr(devops_ollama, "OpenAIJsonSchemaTransformer")
    assert hasattr(devops_ollama, "OpenAIModelProfile")
    assert hasattr(devops_ollama, "ModelSettings")
    assert hasattr(devops_ollama, "ModelProfileSpec")

    # Built-in profile builders
    assert callable(devops_ollama.qwen_model_profile)
    assert callable(devops_ollama.deepseek_model_profile)
    assert callable(devops_ollama.meta_model_profile)
    assert callable(devops_ollama.mistral_model_profile)
    assert callable(devops_ollama.google_model_profile)
    assert callable(devops_ollama.cohere_model_profile)
    assert callable(devops_ollama.harmony_model_profile)

    # Domain helpers
    assert callable(devops_ollama.normalize_ollama_base_url)
    assert callable(devops_ollama.is_ollama_cloud)
    assert callable(devops_ollama.get_recommended_output_mode)
    assert callable(devops_ollama.create_ollama_provider)
    assert callable(devops_ollama.create_ollama_model)


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


def test_is_ollama_cloud() -> None:
    """Verify is_ollama_cloud accurately identifies cloud endpoints and cloud model suffixes."""
    from devops_cli.ai.models.ollama import is_ollama_cloud

    # By base_url
    assert is_ollama_cloud(base_url="https://ollama.com/v1") is True
    assert is_ollama_cloud(base_url="https://api.ollama.com/v1") is True
    assert is_ollama_cloud(base_url="http://localhost:11434/v1") is False
    assert is_ollama_cloud(base_url="http://192.168.1.50:11434/v1") is False

    # By model_name
    assert is_ollama_cloud(model_name="qwen3-cloud") is True
    assert is_ollama_cloud(model_name="deepseek-r1-cloud") is True
    assert is_ollama_cloud(model_name="qwen2.5-coder:14b") is False

    # Combinations
    assert is_ollama_cloud(base_url="http://localhost:11434", model_name="qwen3-cloud") is True
    assert is_ollama_cloud(base_url="https://ollama.com", model_name="llama3.2") is True
    assert is_ollama_cloud(base_url="http://localhost:11434", model_name="llama3.2") is False


def test_get_recommended_output_mode() -> None:
    """Verify get_recommended_output_mode recommends native vs tool output based on cloud status."""
    from devops_cli.ai.models.ollama import get_recommended_output_mode

    # Self-hosted Ollama (v0.5.0+) supports grammar-constrained JSON schema decoding
    assert get_recommended_output_mode("http://localhost:11434/v1", "qwen2.5-coder") == "native"
    assert get_recommended_output_mode("http://workhorse.lan:11434", "deepseek-r1") == "native"

    # Ollama Cloud accepts json_schema without error but does not enforce it upstream yet
    assert get_recommended_output_mode("https://ollama.com/v1", "llama3.2") == "tool"
    assert get_recommended_output_mode("http://localhost:11434", "qwen3-cloud") == "tool"


def test_create_ollama_provider() -> None:
    """Verify create_ollama_provider builds native OllamaProvider with cluster and auth support."""
    from pydantic_ai.providers.ollama import OllamaProvider

    from devops_cli.ai.models.ollama import create_ollama_provider

    # 1. From explicit base_url
    p1 = create_ollama_provider(base_url="http://localhost:11434")
    assert isinstance(p1, OllamaProvider)
    assert p1.base_url == "http://localhost:11434/v1/"

    # 2. From cluster URLs list
    p2 = create_ollama_provider(urls=["http://node1.lan:11434", "http://node2.lan:11434"])
    assert isinstance(p2, OllamaProvider)
    assert p2.base_url in {"http://node1.lan:11434/v1/", "http://node2.lan:11434/v1/"}

    # 3. With API key for authenticated proxies or Ollama Cloud
    p3 = create_ollama_provider(base_url="https://ollama.com", api_key="test-key-123")
    assert isinstance(p3, OllamaProvider)
    assert p3.base_url == "https://ollama.com/v1/"

    # 4. Fallback to OLLAMA_BASE_URL environment variable
    with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://env-host:11434/v1"}):
        p4 = create_ollama_provider()
        assert p4.base_url == "http://env-host:11434/v1/"


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
    """Verify Ollama models and helper functions are re-exported across public package tiers."""
    import devops_cli.ai as ai
    import devops_cli.ai.agents as agents
    import devops_cli.ai.agents.pydantic_agent as pydantic_agent
    import devops_cli.ai.models as models
    import devops_cli.ai.models.ollama as ollama

    for pkg in (ollama, models):
        assert hasattr(pkg, "OllamaModel")
        assert hasattr(pkg, "OllamaProvider")
        assert hasattr(pkg, "create_ollama_model")
        assert hasattr(pkg, "create_ollama_provider")
        assert hasattr(pkg, "normalize_ollama_base_url")
        assert hasattr(pkg, "is_ollama_cloud")
        assert hasattr(pkg, "get_recommended_output_mode")

    for pkg in (ai, agents, pydantic_agent):
        assert hasattr(pkg, "OllamaModel")
        assert hasattr(pkg, "OllamaProvider")
        assert hasattr(pkg, "create_ollama_model")
        assert hasattr(pkg, "create_ollama_provider")
