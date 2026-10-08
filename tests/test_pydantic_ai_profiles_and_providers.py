"""Unit tests for native Pydantic AI profiles and providers integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.profiles import (
    DEFAULT_PROFILE,
    DEFAULT_THINKING_TAGS,
    InlineDefsJsonSchemaTransformer,
    JsonSchemaTransformer,
    ModelProfile,
    StructuredOutputMode,
    ToolAdditionMode,
    ToolDeferralMode,
    amazon_model_profile,
    anthropic_model_profile,
    cohere_model_profile,
    deepseek_model_profile,
    get_model_profile_builder,
    get_model_thinking_tags,
    google_model_profile,
    google_realtime_model_profile,
    grok_model_profile,
    grok_realtime_model_profile,
    groq_model_profile,
    harmony_model_profile,
    merge_profile,
    meta_model_profile,
    mistral_model_profile,
    moonshotai_model_profile,
    openai_model_profile,
    openai_realtime_model_profile,
    qwen_model_profile,
    resolve_model_profile,
    supports_thinking,
    thinking_always_enabled,
    zai_model_profile,
)
from devops_cli.ai.providers import (
    AnthropicProvider as LegacyAnthropicProvider,
)
from devops_cli.ai.providers import (
    BaseLLMProvider,
    CopilotProvider,
    NativeAnthropicProvider,
    NativeDeepSeekProvider,
    NativeGoogleProvider,
    NativeOllamaProvider,
    NativeOpenAIProvider,
    NativeOpenRouterProvider,
    Provider,
    create_pydantic_ai_provider,
    get_provider,
    infer_provider,
    infer_provider_class,
    register_provider,
)
from devops_cli.ai.providers import (
    OllamaProvider as LegacyOllamaProvider,
)
from devops_cli.ai.providers import (
    OpenAIProvider as LegacyOpenAIProvider,
)
from devops_cli.ai.thinking_stream import (
    ThinkingStreamProcessor,
    extract_think_blocks,
    strip_think_blocks,
)
from devops_cli.config.settings import AIConfig, Settings
from tests.mock_provider import MockProvider


class TestPydanticAIProfiles:
    """Test suite for native Pydantic AI profiles subsystem."""

    def test_core_profile_constants_and_types(self) -> None:
        """Verify core profile constants and types are exposed and conform to schema."""
        assert isinstance(DEFAULT_PROFILE, dict)
        assert DEFAULT_THINKING_TAGS == ("<think>", "</think>")
        assert "supports_tools" in DEFAULT_PROFILE

        # Type alias validations
        assert ToolAdditionMode is not None
        assert ToolDeferralMode is not None
        assert StructuredOutputMode is not None
        assert JsonSchemaTransformer is not None
        assert InlineDefsJsonSchemaTransformer is not None

    def test_all_family_builders(self) -> None:
        """Verify all family model profile builders execute and return valid ModelProfiles."""
        builders = [
            amazon_model_profile("titan-text"),
            anthropic_model_profile("claude-3-5-sonnet"),
            cohere_model_profile("command-r-reasoning"),
            deepseek_model_profile("deepseek-r1"),
            google_model_profile("gemini-2.5-pro"),
            google_realtime_model_profile("gemini-2.0-flash-exp"),
            grok_model_profile("grok-beta"),
            grok_realtime_model_profile("grok-beta"),
            groq_model_profile("llama3-70b-8192"),
            harmony_model_profile("harmony-1"),
            meta_model_profile("llama-3.1-405b"),
            mistral_model_profile("mistral-large-latest"),
            moonshotai_model_profile("moonshot-v1-32k"),
            openai_model_profile("gpt-4o"),
            openai_realtime_model_profile("gpt-4o-realtime-preview"),
            qwen_model_profile("qwen2.5-coder-7b"),
            zai_model_profile("glm-4-plus"),
        ]
        for p in builders:
            if p is not None:
                assert isinstance(p, dict)
        assert isinstance(openai_model_profile("gpt-4o"), dict)
        assert isinstance(deepseek_model_profile("deepseek-r1"), dict)
        assert isinstance(anthropic_model_profile("claude-3-5-sonnet"), dict)

    def test_get_model_profile_builder_lookup(self) -> None:
        """Test registry lookup for family builders by canonical name."""
        assert get_model_profile_builder("openai") is openai_model_profile
        assert get_model_profile_builder("anthropic") is anthropic_model_profile
        assert get_model_profile_builder("google") is google_model_profile
        assert get_model_profile_builder("deepseek") is deepseek_model_profile
        assert get_model_profile_builder("qwen") is qwen_model_profile
        assert get_model_profile_builder("meta") is meta_model_profile
        assert get_model_profile_builder("mistral") is mistral_model_profile
        assert get_model_profile_builder("cohere") is cohere_model_profile
        assert get_model_profile_builder("harmony") is harmony_model_profile
        assert get_model_profile_builder("groq") is groq_model_profile
        assert get_model_profile_builder("grok") is grok_model_profile
        assert get_model_profile_builder("amazon") is amazon_model_profile
        assert get_model_profile_builder("moonshotai") is moonshotai_model_profile
        assert get_model_profile_builder("zai") is zai_model_profile
        assert get_model_profile_builder("unknown_family") is None

    def test_resolve_model_profile_with_model_strings(self) -> None:
        """Test dynamic profile resolution for various model strings."""
        openai_prof = resolve_model_profile("openai:gpt-4o")
        assert openai_prof.get("supports_json_schema_output") is True

        ollama_prof = resolve_model_profile("ollama:qwen2.5-coder:7b")
        assert ollama_prof.get("ignore_streamed_leading_whitespace") is True

        anthropic_prof = resolve_model_profile("anthropic:claude-3-5-sonnet")
        assert anthropic_prof.get("thinking_tags") == ("<thinking>", "</thinking>")

        # Bare model with provider parameter
        claude_prof = resolve_model_profile("claude-3-5-sonnet", provider="anthropic")
        assert claude_prof.get("thinking_tags") == ("<thinking>", "</thinking>")

    def test_resolve_model_profile_with_overrides(self) -> None:
        """Test profile resolution with explicit overrides merged cleanly."""
        overrides: ModelProfile = {"supports_thinking": True, "thinking_always_enabled": True}
        merged = resolve_model_profile("openai:gpt-4o", overrides=overrides)
        assert merged.get("supports_thinking") is True
        assert merged.get("thinking_always_enabled") is True
        assert merged.get("supports_json_schema_output") is True

    def test_resolve_model_profile_fallback(self) -> None:
        """Test profile resolution fallback for None or unrecognized strings."""
        fallback = resolve_model_profile(None)
        assert fallback == DEFAULT_PROFILE

        fallback_unknown = resolve_model_profile("unrecognized-model-12345")
        assert isinstance(fallback_unknown, dict)

    def test_thinking_tag_and_capability_introspection(self) -> None:
        """Test thinking tag retrieval, support check, and always-enabled predicate."""
        assert get_model_thinking_tags("anthropic:claude-3-5-sonnet") == (
            "<thinking>",
            "</thinking>",
        )
        assert get_model_thinking_tags("openai:gpt-4o") == ("<think>", "</think>")
        assert supports_thinking("anthropic:claude-3-5-sonnet") is True
        assert supports_thinking("openai:gpt-4o") is False
        assert thinking_always_enabled("deepseek:deepseek-r1") is True
        assert thinking_always_enabled("openai:gpt-4o") is False

    def test_merge_profile_utility(self) -> None:
        """Test merge_profile correctly overlays dictionary keys."""
        base: ModelProfile = {"supports_tools": True, "supports_thinking": False}
        overlay: ModelProfile = {"supports_thinking": True}
        res = merge_profile(base, overlay)
        assert res.get("supports_tools") is True
        assert res.get("supports_thinking") is True


class TestPydanticAIProviders:
    """Test suite for native Pydantic AI providers subsystem."""

    def test_native_provider_classes_and_subclasses(self) -> None:
        """Verify native Provider ABC and concrete provider classes."""
        assert issubclass(NativeOllamaProvider, Provider)
        assert issubclass(NativeOpenAIProvider, Provider)
        assert issubclass(NativeAnthropicProvider, Provider)
        assert issubclass(NativeGoogleProvider, Provider)
        assert issubclass(NativeDeepSeekProvider, Provider)
        assert issubclass(NativeOpenRouterProvider, Provider)

    def test_infer_provider_and_class(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify infer_provider_class and infer_provider work natively."""
        assert infer_provider_class("ollama") is NativeOllamaProvider
        assert infer_provider_class("openai") is NativeOpenAIProvider
        assert infer_provider_class("anthropic") is NativeAnthropicProvider
        assert infer_provider_class("google") is NativeGoogleProvider
        assert infer_provider_class("deepseek") is NativeDeepSeekProvider

        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ollama_inst = infer_provider("ollama")
        assert isinstance(ollama_inst, NativeOllamaProvider)

    @pytest.mark.usefixtures("public_dns")
    def test_create_pydantic_ai_provider_factory(self) -> None:
        """Test unified create_pydantic_ai_provider factory."""
        ollama_p = create_pydantic_ai_provider("ollama", base_url="http://localhost:11434")
        assert isinstance(ollama_p, NativeOllamaProvider)
        assert ollama_p.base_url == "http://localhost:11434"

        openai_p = create_pydantic_ai_provider(
            "openai", api_key="sk-test-key", base_url="https://api.openai.com/v1"
        )
        assert isinstance(openai_p, NativeOpenAIProvider)
        assert str(openai_p.base_url).rstrip("/") == "https://api.openai.com/v1"

        anthropic_p = create_pydantic_ai_provider("anthropic", api_key="sk-ant-test")
        assert isinstance(anthropic_p, NativeAnthropicProvider)

    def test_legacy_providers_resolution(self) -> None:
        """Verify legacy BaseLLMProvider and get_provider remain operational."""
        config = AIConfig()
        ollama = get_provider("ollama", config)
        assert isinstance(ollama, LegacyOllamaProvider)
        assert isinstance(ollama, BaseLLMProvider)
        assert ollama.name == "ollama"

        openai = get_provider("openai", config)
        assert isinstance(openai, LegacyOpenAIProvider)
        assert openai.name == "openai"

        claude = get_provider("claude", config)
        assert isinstance(claude, LegacyAnthropicProvider)
        assert claude.name == "claude"

        copilot = get_provider("copilot", config)
        assert isinstance(copilot, CopilotProvider)
        assert copilot.name == "copilot"

        register_provider("mock", MockProvider)
        mock = get_provider("mock", config)
        assert isinstance(mock, MockProvider)
        assert mock.name == "mock"


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

    def test_package_reexports(self) -> None:
        """Verify profiles and providers symbols are cleanly re-exported across packages."""
        import devops_cli.ai as ai_pkg
        import devops_cli.ai.agents as agents_pkg
        import devops_cli.ai.agents.pydantic_agent as pa_module

        for mod in (ai_pkg, agents_pkg, pa_module):
            assert hasattr(mod, "ModelProfile")
            assert hasattr(mod, "DEFAULT_PROFILE")
            assert hasattr(mod, "DEFAULT_THINKING_TAGS")
            assert hasattr(mod, "resolve_model_profile")
            assert hasattr(mod, "get_model_thinking_tags")
            assert hasattr(mod, "supports_thinking")
            assert hasattr(mod, "thinking_always_enabled")
            assert hasattr(mod, "Provider")
            assert hasattr(mod, "create_pydantic_ai_provider")
            assert hasattr(mod, "infer_provider")
            assert hasattr(mod, "infer_provider_class")


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


@pytest.mark.parametrize(("provider", "model"), [("mock", "gpt-4o"), ("vllm", "qwen3-coder:30b")])
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


def test_agent_factory_does_not_swallow_a_configuration_error(
    remote_bridge: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the agent factory lets a configuration error through instead of falling back."""
    from devops_cli.exceptions import ConfigurationError

    settings = _remote_settings("openai", api_base_url="localhost:8000/v1")
    monkeypatch.setattr(remote_bridge, "load_settings", lambda: settings)

    with pytest.raises(ConfigurationError, match=r"^ai\.api_base_url cannot serve model"):
        remote_bridge.create_pydantic_ai_agent(model_name="openai:gpt-4o")


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
