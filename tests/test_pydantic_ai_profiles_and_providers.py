"""Unit tests for the native Pydantic AI provider factory and the bridge model resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.providers import create_pydantic_ai_provider
from devops_cli.ai.thinking_stream import (
    ThinkingStreamProcessor,
    extract_think_blocks,
    strip_think_blocks,
)
from devops_cli.config.settings import Settings


class TestPydanticAIProviders:
    """Test suite for native Pydantic AI providers subsystem."""

    @pytest.mark.usefixtures("public_dns")
    def test_create_pydantic_ai_provider_factory(self) -> None:
        """Test unified create_pydantic_ai_provider factory."""
        from pydantic_ai.providers.anthropic import AnthropicProvider as NativeAnthropicProvider
        from pydantic_ai.providers.ollama import OllamaProvider as NativeOllamaProvider
        from pydantic_ai.providers.openai import OpenAIProvider as NativeOpenAIProvider

        ollama_p = create_pydantic_ai_provider("ollama", base_url="http://localhost:11434")
        assert (isinstance(ollama_p, NativeOllamaProvider), ollama_p.base_url) == (
            True,
            "http://localhost:11434",
        )

        openai_p = create_pydantic_ai_provider(
            "openai", api_key="sk-test-key", base_url="https://api.openai.com/v1"
        )
        assert (
            isinstance(openai_p, NativeOpenAIProvider),
            str(openai_p.base_url).rstrip("/"),
        ) == (True, "https://api.openai.com/v1")

        anthropic_p = create_pydantic_ai_provider("anthropic", api_key="sk-ant-test")
        assert isinstance(anthropic_p, NativeAnthropicProvider)


class TestThinkingStreamWithDynamicTags:
    """Test thinking stream parser with dynamic model thinking tags."""

    def test_strip_and_extract_custom_tags(self) -> None:
        """Verify strip_think_blocks and extract_think_blocks handle custom thinking tags."""
        anthropic_text = "<thinking>Analyzing architecture</thinking>Here is the plan."
        assert strip_think_blocks(anthropic_text, thinking_tags=("<thinking>", "</thinking>")) == (
            "Here is the plan."
        )

        thinks, clean = extract_think_blocks(
            anthropic_text, thinking_tags=("<thinking>", "</thinking>")
        )
        assert thinks == ["Analyzing architecture"]
        assert clean == "Here is the plan."

    def test_thinking_stream_processor_with_anthropic_tags(self) -> None:
        """Verify ThinkingStreamProcessor state machine with Anthropic thinking tags."""
        chunks_thought: list[str] = []
        chunks_content: list[str] = []

        processor = ThinkingStreamProcessor(
            show_thinking=True,
            thinking_tags=("<thinking>", "</thinking>"),
            on_think_chunk=lambda c: chunks_thought.append(c),
            on_content_chunk=lambda c: chunks_content.append(c),
        )

        stream = ["Hello ", "<thinking>", "deliberating ", "carefully", "</thinking>", " World!"]
        for chunk in stream:
            processor.feed(chunk)
        processor.flush()

        assert "".join(chunks_thought) == "deliberating carefully"
        assert "".join(chunks_content) == "Hello  World!"


class TestBridgeModelResolutionWithProviders:
    """Test resolve_pydantic_ai_model with native providers and profiles."""

    def test_resolve_model_with_configured_settings(self) -> None:
        """Verify resolve_pydantic_ai_model uses provider factory and credentials."""
        from devops_cli.ai.pydantic_ai_bridge import resolve_pydantic_ai_model

        settings = Settings()
        settings.ai.provider = "ollama"
        settings.ai.model = "qwen2.5-coder:7b"

        model = resolve_pydantic_ai_model("ollama:qwen2.5-coder:7b", settings=settings)
        assert model is not None


_EXAMPLE_BASE = "https://example.com/v1"
_EXAMPLE_GATEWAY = "http://example.com:4000/v1"
_EXAMPLE_PORTKEY = "http://example.com:8787/v1"
_EXAMPLE_OLLAMA = "http://example.com:11434"


@pytest.fixture
def remote_bridge(monkeypatch: pytest.MonkeyPatch, public_dns: str) -> Any:
    """The bridge with model requests allowed and the AI key fixed, so nothing reads a keyring.

    The example.com endpoints resolve to a public address, as they do outside tests.
    """
    from devops_cli.ai import pydantic_ai_bridge

    monkeypatch.setattr(pydantic_ai_bridge, "_is_testing_mode_active", lambda: False)
    monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _settings: "sk-test")
    return pydantic_ai_bridge


def _remote_settings(provider: str, **ai_fields: Any) -> Settings:
    settings = Settings()
    settings.ai.provider = provider
    for field, value in ai_fields.items():
        setattr(settings.ai, field, value)
    return settings


@pytest.mark.parametrize(
    ("provider", "model", "ai_fields", "expected"),
    [
        ("openai", "gpt-4o", {"api_base_url": _EXAMPLE_BASE}, ("gpt-4o", f"{_EXAMPLE_BASE}/")),
        (
            "claude",
            "claude-sonnet-4-5",
            {"api_base_url": "https://example.com"},
            ("claude-sonnet-4-5", "https://example.com"),
        ),
        ("copilot", "gpt-4o", {}, ("gpt-4o", "https://api.githubcopilot.com")),
        (
            "gateway",
            "devops-review",
            {"gateway_url": _EXAMPLE_GATEWAY},
            ("devops-review", f"{_EXAMPLE_GATEWAY}/"),
        ),
        (
            "gateway",
            "qwen3-coder:30b",
            {"gateway_url": _EXAMPLE_GATEWAY},
            ("qwen3-coder:30b", f"{_EXAMPLE_GATEWAY}/"),
        ),
        (
            "openai",
            "litellm:devops-coder",
            {"api_base_url": _EXAMPLE_BASE, "gateway_url": _EXAMPLE_GATEWAY},
            ("devops-coder", f"{_EXAMPLE_GATEWAY}/"),
        ),
        (
            "openai",
            "portkey:devops-coder",
            {"portkey_url": _EXAMPLE_PORTKEY},
            ("devops-coder", f"{_EXAMPLE_PORTKEY}/"),
        ),
        (
            "gateway",
            "mistral:7b",
            {"gateway_url": _EXAMPLE_GATEWAY},
            ("mistral:7b", f"{_EXAMPLE_GATEWAY}/"),
        ),
        (
            "gateway",
            "openai:gpt-4o",
            {"gateway_url": _EXAMPLE_GATEWAY},
            ("openai:gpt-4o", f"{_EXAMPLE_GATEWAY}/"),
        ),
        (
            "gateway",
            "portkey:devops-coder",
            {"gateway_url": _EXAMPLE_GATEWAY, "portkey_url": _EXAMPLE_PORTKEY},
            ("devops-coder", f"{_EXAMPLE_PORTKEY}/"),
        ),
        (
            "ollama",
            "litellm:devops-coder",
            {"gateway_url": _EXAMPLE_GATEWAY},
            ("devops-coder", f"{_EXAMPLE_GATEWAY}/"),
        ),
    ],
    ids=[
        "openai-bare",
        "claude-bare",
        "copilot-bare",
        "gateway-bare",
        "gateway-route-with-tag",
        "litellm",
        "portkey",
        "gateway-route-named-like-a-provider",
        "gateway-route-with-a-provider-prefix",
        "gateway-portkey",
        "ollama-litellm",
    ],
)
def test_remote_model_is_sent_to_its_configured_endpoint(
    remote_bridge: Any, provider: str, model: str, ai_fields: dict[str, Any], expected: Any
) -> None:
    """Verify a remote model resolves to a model pointed at the endpoint its settings name."""
    resolved = remote_bridge.resolve_pydantic_ai_model(
        model, settings=_remote_settings(provider, **ai_fields)
    )

    assert (resolved.model_name, str(resolved.base_url)) == expected


@pytest.mark.parametrize(
    ("model", "ai_fields", "key"),
    [
        ("openai:gpt-4o", {"api_base_url": "localhost:8000/v1"}, "ai.api_base_url"),
        ("litellm:devops-coder", {"gateway_url": "localhost:4000/v1"}, "ai.gateway_url"),
        ("portkey:devops-coder", {"portkey_url": "ftp://example.com/v1"}, "ai.portkey_url"),
    ],
)
def test_remote_model_with_malformed_base_url_raises(
    remote_bridge: Any, model: str, ai_fields: dict[str, Any], key: str
) -> None:
    """Verify an endpoint URL that cannot be used raises an error naming its setting."""
    from devops_cli.exceptions import ConfigurationError, InvalidURLError

    with pytest.raises(ConfigurationError) as caught:
        remote_bridge.resolve_pydantic_ai_model(
            model, settings=_remote_settings("openai", **ai_fields)
        )

    assert (
        caught.value.details["key"],
        str(caught.value).startswith(f"{key} cannot serve model {model!r}"),
        isinstance(caught.value.__cause__, InvalidURLError),
    ) == (key, True, True)


_PRIVATE_BASE = "http://192.0.2.10:4000/v1"


@pytest.mark.parametrize(
    ("provider", "model", "setting"),
    [
        ("openai", "gpt-4o", "api_base_url"),
        ("gateway", "devops-review", "gateway_url"),
        ("openai", "litellm:devops-coder", "gateway_url"),
        ("openai", "portkey:devops-coder", "portkey_url"),
    ],
)
def test_remote_model_on_a_private_host_needs_the_opt_in(
    remote_bridge: Any, monkeypatch: pytest.MonkeyPatch, provider: str, model: str, setting: str
) -> None:
    """Verify a non-public endpoint is refused, naming its setting, until private hosts are allowed.

    The bridge's URLs follow `validate_configured_service_url`, as the LLM client's do, so
    pydantic-ai is not handed a URL, the prompts and the key that `LLMClient` refuses.
    """
    from devops_cli.exceptions import ConfigurationError, SSRFBlockedError

    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    with pytest.raises(ConfigurationError) as caught:
        remote_bridge.resolve_pydantic_ai_model(
            model,
            settings=_remote_settings(
                provider, allow_private_network=False, **{setting: _PRIVATE_BASE}
            ),
        )
    allowed = remote_bridge.resolve_pydantic_ai_model(
        model,
        settings=_remote_settings(provider, allow_private_network=True, **{setting: _PRIVATE_BASE}),
    )

    assert (
        caught.value.details["key"],
        str(caught.value).startswith(f"ai.{setting} cannot serve model {model!r}: Refusing "),
        isinstance(caught.value.__cause__, SSRFBlockedError),
        str(allowed.base_url),
    ) == (f"ai.{setting}", True, True, f"{_PRIVATE_BASE}/")


def test_provider_factory_allows_a_private_base_url_only_when_told(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the provider factory takes loopback, and a private host only with the opt-in."""
    from devops_cli.exceptions import SSRFBlockedError

    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    with pytest.raises(SSRFBlockedError):
        create_pydantic_ai_provider("openai", base_url=_PRIVATE_BASE, api_key="sk-test")
    allowed = create_pydantic_ai_provider(
        "openai", base_url=_PRIVATE_BASE, api_key="sk-test", allow_private_network=True
    )
    loopback = create_pydantic_ai_provider(
        "openai", base_url="http://localhost:4000/v1", api_key="sk-test"
    )

    assert (str(allowed.base_url), str(loopback.base_url)) == (
        f"{_PRIVATE_BASE}/",
        "http://localhost:4000/v1/",
    )


def test_remote_model_on_loopback_needs_no_opt_in(
    remote_bridge: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the default gateway on loopback resolves with private hosts not allowed."""
    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)

    resolved = remote_bridge.resolve_pydantic_ai_model(
        "devops-review", settings=_remote_settings("gateway", allow_private_network=False)
    )

    assert (resolved.model_name, str(resolved.base_url)) == (
        "devops-review",
        "http://localhost:4000/v1/",
    )


@pytest.mark.parametrize(("provider", "model"), [("mock", "gpt-4o"), ("custom", "qwen3-coder:30b")])
def test_remote_model_pydantic_ai_cannot_infer_raises(
    remote_bridge: Any, provider: str, model: str
) -> None:
    """Verify a model pydantic-ai cannot build raises naming ai.provider, ai.model and why.

    Neither provider maps to a pydantic-ai prefix, so pydantic-ai is left the bare name: it
    refuses `gpt-4o` as an unknown model, with its hint "Did you mean 'openai-chat:gpt-4o'?",
    and `qwen3-coder:30b` as naming an unknown provider.
    """
    from devops_cli.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError) as caught:
        remote_bridge.resolve_pydantic_ai_model(
            model, settings=_remote_settings(provider, api_base_url=_EXAMPLE_BASE)
        )

    assert (
        caught.value.details["key"],
        str(caught.value).startswith(
            f"ai.model {model!r} cannot be resolved for ai.provider {provider!r}: Unknown "
        ),
    ) == ("ai.model", True)


def test_remote_model_whose_provider_package_is_missing_raises(
    remote_bridge: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a provider prefix whose optional package is not installed raises naming ai.model.

    pydantic-ai raises a bare ImportError ("Please install the `mistral` package ..."), which
    would otherwise escape as an untyped error.
    """
    import sys

    from devops_cli.exceptions import ConfigurationError

    monkeypatch.setitem(sys.modules, "pydantic_ai.providers.mistral", None)
    with pytest.raises(ConfigurationError) as caught:
        remote_bridge.resolve_pydantic_ai_model(
            "mistral:large", settings=_remote_settings("openai", api_base_url=_EXAMPLE_BASE)
        )

    assert (
        caught.value.details["key"],
        str(caught.value).startswith(
            "ai.model 'mistral:large' cannot be resolved for ai.provider 'openai': "
        ),
        isinstance(caught.value.__cause__, ImportError),
    ) == ("ai.model", True, True)


def _cascade_settings(provider: str) -> Settings:
    return _remote_settings(
        provider,
        model="qwen3-coder:30b",
        gateway_url=_EXAMPLE_GATEWAY,
        portkey_url=_EXAMPLE_PORTKEY,
        ollama_urls=[_EXAMPLE_OLLAMA],
    )


@pytest.mark.parametrize("provider", ["ollama", "gateway", "openai"])
def test_cascade_reaches_each_gateway_and_then_ollama(remote_bridge: Any, provider: str) -> None:
    """Verify `cascade` is LiteLLM's and Portkey's default chat route, then `ai.model` on Ollama.

    Its members are the bare names `litellm`, `portkey` and `ollama`, which name a path rather
    than a model, so none of them is sent to a gateway as a model of that name.
    """
    cascade = remote_bridge.resolve_pydantic_ai_model(
        "cascade", settings=_cascade_settings(provider)
    )

    assert [(m.system, m.model_name, str(m.base_url)) for m in cascade.models] == [
        ("openai", "devops-chat", f"{_EXAMPLE_GATEWAY}/"),
        ("openai", "devops-chat", f"{_EXAMPLE_PORTKEY}/"),
        ("ollama", "qwen3-coder:30b", f"{_EXAMPLE_OLLAMA}/v1/"),
    ]


@pytest.mark.parametrize("provider", ["ollama", "gateway"])
def test_gateway_cascade_falls_back_through_its_routes_to_ollama(
    remote_bridge: Any, tmp_path: Path, provider: str
) -> None:
    """Verify the gateway's cascade is its own routes, then `ai.model` on Ollama directly.

    `devops-coder` fails over to `devops-chat` on the gateway; `devops-chat` fails over to
    Ollama itself (`direct-ollama`), which is the cascade's last member and not a route.
    """
    from devops_cli.ai.gateway import GatewayRouter

    settings = _cascade_settings(provider)
    router = GatewayRouter(settings.ai, state_file=tmp_path / "gateway_state.json")

    def members(virtual_model: str) -> list[tuple[str, str, str]]:
        cascade = router.build_pydantic_cascade_model(virtual_model, settings=settings)
        return [(m.system, m.model_name, str(m.base_url)) for m in cascade.models]

    ollama = ("ollama", "qwen3-coder:30b", f"{_EXAMPLE_OLLAMA}/v1/")
    assert (members("devops-coder"), members("devops-chat")) == (
        [
            ("openai", "devops-coder", f"{_EXAMPLE_GATEWAY}/"),
            ("openai", "devops-chat", f"{_EXAMPLE_GATEWAY}/"),
            ollama,
        ],
        [("openai", "devops-chat", f"{_EXAMPLE_GATEWAY}/"), ollama],
    )


def test_ollama_model_waits_the_configured_timeout(
    remote_bridge: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify an Ollama model is built with `ai.timeout` as its request timeout."""
    from devops_cli.ai.models import ollama as ollama_models

    built: list[dict[str, Any]] = []
    monkeypatch.setattr(
        ollama_models,
        "create_ollama_model",
        lambda model_name, **kwargs: built.append({"model": model_name, **kwargs}),
    )
    settings = _remote_settings("ollama", ollama_urls=["http://example.com:11434"], timeout=12.0)

    remote_bridge.resolve_pydantic_ai_model("ollama:qwen3:8b", settings=settings)

    assert [(call["model"], call["urls"], call["timeout"]) for call in built] == [
        ("ollama:qwen3:8b", ["http://example.com:11434"], 12.0)
    ]
