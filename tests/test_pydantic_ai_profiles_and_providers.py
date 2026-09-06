"""Unit tests for native Pydantic AI profiles and providers integration."""

from __future__ import annotations

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
    MockProvider,
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

    def test_all_14_family_builders(self) -> None:
        """Verify all 14 family model profile builders execute and return valid ModelProfiles."""
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

    def test_legacy_providers_backward_compatibility(self) -> None:
        """Verify legacy BaseLLMProvider and get_provider remain 100% operational."""
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
            processor.process_token(chunk)
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
