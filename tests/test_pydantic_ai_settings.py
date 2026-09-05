"""Unit tests for the native Pydantic AI settings subsystem in devops-cli."""

from __future__ import annotations

from devops_cli.ai.settings import (
    AgentModelSettings,
    ModelSettings,
    ToolOrOutput,
    create_model_settings,
    create_tool_or_output,
    merge_model_settings,
    normalize_service_tier,
    normalize_thinking_level,
    normalize_tool_choice,
    resolve_runtime_model_settings,
)


class TestPydanticAISettingsSubsystem:
    """Test suite verifying native Pydantic AI settings integration."""

    def test_core_classes_and_type_exports(self) -> None:
        """Verify that core settings types and functions are exported."""
        assert ModelSettings is not None
        assert ToolOrOutput is not None
        assert callable(merge_model_settings)
        assert callable(create_model_settings)
        assert callable(create_tool_or_output)
        assert callable(normalize_thinking_level)
        assert callable(normalize_service_tier)
        assert callable(normalize_tool_choice)
        assert callable(resolve_runtime_model_settings)
        assert AgentModelSettings is not None

    def test_create_model_settings(self) -> None:
        """Verify create_model_settings constructs clean ModelSettings without None entries."""
        settings = create_model_settings(
            temperature=0.7,
            max_tokens=2048,
            thinking="high",
            service_tier="priority",
            parallel_tool_calls=True,
            custom_extra="custom_value",
        )
        assert settings["temperature"] == 0.7
        assert settings["max_tokens"] == 2048
        assert settings["thinking"] == "high"
        assert settings["service_tier"] == "priority"
        assert settings["parallel_tool_calls"] is True
        assert settings.get("custom_extra") == "custom_value"
        # Keys not provided should not be present
        assert "seed" not in settings
        assert "presence_penalty" not in settings

    def test_create_tool_or_output(self) -> None:
        """Verify create_tool_or_output constructs a valid ToolOrOutput instance."""
        tool_or_output = create_tool_or_output("web_search", "fetch_url")
        assert isinstance(tool_or_output, ToolOrOutput)
        assert tool_or_output.function_tools == ["web_search", "fetch_url"]

    def test_merge_model_settings(self) -> None:
        """Verify merge_model_settings correctly merges base and override dictionaries."""
        base: ModelSettings = {"temperature": 0.2, "max_tokens": 1000}
        overrides: ModelSettings = {"temperature": 0.8, "thinking": True}

        merged = merge_model_settings(base, overrides)
        assert merged is not None
        assert merged["temperature"] == 0.8  # overrides take precedence
        assert merged["max_tokens"] == 1000  # base preserved
        assert merged["thinking"] is True

        assert merge_model_settings(base, None) == base
        assert merge_model_settings(None, overrides) == overrides
        assert merge_model_settings(None, None) is None

    def test_normalize_thinking_level(self) -> None:
        """Verify normalize_thinking_level parses booleans and valid effort levels."""
        assert normalize_thinking_level(True) is True
        assert normalize_thinking_level(False) is False
        assert normalize_thinking_level("true") is True
        assert normalize_thinking_level("FALSE") is False

        for level in ("minimal", "low", "medium", "high", "xhigh"):
            assert normalize_thinking_level(level) == level
            assert normalize_thinking_level(level.upper()) == level

        assert normalize_thinking_level("invalid_level") is None
        assert normalize_thinking_level(123) is None
        assert normalize_thinking_level(None) is None

    def test_normalize_service_tier(self) -> None:
        """Verify normalize_service_tier parses valid service tiers."""
        for tier in ("auto", "default", "flex", "priority"):
            assert normalize_service_tier(tier) == tier
            assert normalize_service_tier(tier.upper()) == tier

        assert normalize_service_tier("unsupported_tier") is None
        assert normalize_service_tier(None) is None

    def test_normalize_tool_choice(self) -> None:
        """Verify normalize_tool_choice handles scalars, lists, and ToolOrOutput."""
        assert normalize_tool_choice("auto") == "auto"
        assert normalize_tool_choice("NONE") == "none"
        assert normalize_tool_choice("required") == "required"

        tools_list = ["code_search", "run_bash"]
        assert normalize_tool_choice(tools_list) == tools_list

        tool_or_output = ToolOrOutput(function_tools=["lint_fix"])
        assert normalize_tool_choice(tool_or_output) is tool_or_output

        assert normalize_tool_choice("invalid_scalar") is None
        assert normalize_tool_choice(None) is None

    def test_resolve_runtime_model_settings(self) -> None:
        """Verify resolve_runtime_model_settings layer merging behavior."""
        base: ModelSettings = {"temperature": 0.3, "max_tokens": 500}
        overrides: ModelSettings = {"temperature": 0.9}

        resolved = resolve_runtime_model_settings(
            base,
            overrides,
            max_tokens=2000,
            thinking="low",
        )
        assert resolved["temperature"] == 0.9
        assert resolved["max_tokens"] == 2000
        assert resolved["thinking"] == "low"

    def test_package_reexports(self) -> None:
        """Verify all settings symbols are cleanly exposed across public package tiers."""
        import devops_cli.ai as ai
        import devops_cli.ai.agents as agents
        import devops_cli.ai.agents.pydantic_agent as pa

        for target in (ai, agents, pa):
            assert hasattr(target, "ModelSettings")
            assert hasattr(target, "merge_model_settings")
            assert hasattr(target, "create_model_settings")
            assert hasattr(target, "ToolOrOutput")
            assert hasattr(target, "create_tool_or_output")
            assert hasattr(target, "normalize_thinking_level")
            assert hasattr(target, "normalize_service_tier")
            assert hasattr(target, "normalize_tool_choice")
            assert hasattr(target, "resolve_runtime_model_settings")
