"""Tests for native Pydantic AI output subsystem integration."""

from __future__ import annotations

from typing import Any

import pydantic_ai.output as pai_output
from pydantic import BaseModel, Field

from devops_cli.ai.output import (
    REVIEW_RESULT_NATIVE,
    REVIEW_RESULT_PROMPTED,
    REVIEW_RESULT_TOOL,
    NativeOutput,
    OutputContext,
    OutputObjectDefinition,
    PromptedOutput,
    StructuredDict,
    TextOutput,
    ToolOutput,
    build_output_spec,
    extract_output_json_schema,
    get_review_output_spec,
    resolve_output_mode,
    unwrap_output_spec,
)
from devops_cli.ai.review_schema import ReviewResult


class SampleOutputModel(BaseModel):
    summary: str = Field(description="Summary text")
    score: int = Field(default=10, description="Numerical score")


def sample_text_processor(text: str) -> list[str]:
    return [word.strip() for word in text.split() if word.strip()]


def test_native_output_symbols_reexported() -> None:
    """Verify devops_cli.ai.output re-exports exact native Pydantic AI output constructs."""
    assert ToolOutput is pai_output.ToolOutput
    assert NativeOutput is pai_output.NativeOutput
    assert PromptedOutput is pai_output.PromptedOutput
    assert TextOutput is pai_output.TextOutput
    assert StructuredDict is pai_output.StructuredDict
    assert OutputObjectDefinition is pai_output.OutputObjectDefinition
    assert OutputContext is pai_output.OutputContext


def test_unwrap_output_spec_varieties() -> None:
    """Verify unwrap_output_spec extracts types from bare models and all output markers."""
    # 1. Bare model
    unwrapped_bare = unwrap_output_spec(SampleOutputModel)
    assert unwrapped_bare == (SampleOutputModel,)

    # 2. NativeOutput
    native = NativeOutput(SampleOutputModel, name="sample_native", description="Native schema")
    assert unwrap_output_spec(native) == (SampleOutputModel,)

    # 3. ToolOutput
    tool = ToolOutput(SampleOutputModel, name="sample_tool", description="Tool schema", strict=True)
    assert unwrap_output_spec(tool) == (SampleOutputModel,)

    # 4. PromptedOutput
    prompted = PromptedOutput(SampleOutputModel, name="sample_prompted")
    assert unwrap_output_spec(prompted) == (SampleOutputModel,)

    # 5. TextOutput
    text_out = TextOutput(sample_text_processor)
    assert unwrap_output_spec(text_out) == (sample_text_processor,)

    # 6. StructuredDict
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {"status": {"type": "string"}},
        "required": ["status"],
    }
    sd = StructuredDict(schema, name="StatusDict")
    unwrapped_sd = unwrap_output_spec(sd)
    assert len(unwrapped_sd) == 1
    assert hasattr(unwrapped_sd[0], "__get_pydantic_json_schema__")


def test_extract_output_json_schema() -> None:
    """Verify extract_output_json_schema retrieves valid JSON schema dictionaries across all specs."""
    # Bare model
    schema1 = extract_output_json_schema(SampleOutputModel)
    assert isinstance(schema1, dict)
    assert "properties" in schema1
    assert "summary" in schema1["properties"]

    # NativeOutput
    schema2 = extract_output_json_schema(NativeOutput(SampleOutputModel, name="CustomNative"))
    assert isinstance(schema2, dict)
    assert "properties" in schema2
    assert "summary" in schema2["properties"]

    # ToolOutput
    schema3 = extract_output_json_schema(ToolOutput(SampleOutputModel, name="CustomTool"))
    assert isinstance(schema3, dict)
    assert "properties" in schema3

    # StructuredDict
    raw_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"metric": {"type": "number"}},
        "required": ["metric"],
    }
    sd = StructuredDict(raw_schema, name="MetricReport")
    schema4 = extract_output_json_schema(sd)
    assert isinstance(schema4, dict)
    assert "properties" in schema4
    assert "metric" in schema4["properties"]

    # TextOutput produces string schema
    text_out = TextOutput(sample_text_processor)
    schema5 = extract_output_json_schema(text_out)
    assert isinstance(schema5, dict)
    assert schema5.get("type") == "string"


def test_resolve_output_mode() -> None:
    """Verify resolve_output_mode recommends native vs tool outputs based on endpoints."""
    # Local self-hosted Ollama endpoint -> native
    assert resolve_output_mode("llama3:8b", base_url="http://localhost:11434/v1") == "native"

    # Ollama Cloud domain -> tool
    assert resolve_output_mode("llama3:8b", base_url="https://ollama.com/v1") == "tool"

    # Cloud model suffix -> tool
    assert resolve_output_mode("deepseek-r1:7b-cloud") == "tool"

    # Standard model default -> native
    assert resolve_output_mode("gpt-4o") == "native"


def test_build_output_spec_factory() -> None:
    """Verify build_output_spec wraps schemas into appropriate output marker instances."""
    # Native
    spec_native = build_output_spec(SampleOutputModel, mode="native", name="test_native")
    assert isinstance(spec_native, NativeOutput)
    assert spec_native.name == "test_native"

    # Tool
    spec_tool = build_output_spec(SampleOutputModel, mode="tool", name="test_tool", strict=True)
    assert isinstance(spec_tool, ToolOutput)
    assert spec_tool.name == "test_tool"
    assert spec_tool.strict is True

    # Prompted
    spec_prompted = build_output_spec(
        SampleOutputModel, mode="prompted", template="Format: {schema}"
    )
    assert isinstance(spec_prompted, PromptedOutput)
    assert spec_prompted.template == "Format: {schema}"

    # Text
    spec_text = build_output_spec(sample_text_processor, mode="text")
    assert isinstance(spec_text, TextOutput)
    assert spec_text.output_function is sample_text_processor

    # Pre-wrapped instance identity preservation
    assert build_output_spec(spec_tool, mode="native") is spec_tool


def test_predefined_review_output_specs() -> None:
    """Verify predefined review output markers and factory for ReviewResult."""
    assert isinstance(REVIEW_RESULT_NATIVE, NativeOutput)
    assert REVIEW_RESULT_NATIVE.outputs is ReviewResult

    assert isinstance(REVIEW_RESULT_TOOL, ToolOutput)
    assert REVIEW_RESULT_TOOL.output is ReviewResult
    assert REVIEW_RESULT_TOOL.name == "submit_review"

    assert isinstance(REVIEW_RESULT_PROMPTED, PromptedOutput)
    assert REVIEW_RESULT_PROMPTED.outputs is ReviewResult

    # Factory selection
    spec1 = get_review_output_spec(mode="native")
    assert isinstance(spec1, NativeOutput)

    spec2 = get_review_output_spec(mode="tool")
    assert isinstance(spec2, ToolOutput)

    spec3 = get_review_output_spec(mode="auto", model_name="deepseek-r1-cloud")
    assert isinstance(spec3, ToolOutput)


def test_create_pydantic_ai_agent_with_output_spec() -> None:
    """Verify create_pydantic_ai_agent accepts OutputSpec markers and output_mode."""
    from devops_cli.ai.pydantic_ai_bridge import create_pydantic_ai_agent

    # 1. Direct NativeOutput
    agent_native = create_pydantic_ai_agent(
        model_name="test",
        output_type=NativeOutput(ReviewResult, name="review_native"),
    )
    assert agent_native is not None

    # 2. Output mode auto-wrapping
    agent_tool = create_pydantic_ai_agent(
        model_name="test",
        output_type=ReviewResult,
        output_mode="tool",
    )
    assert agent_tool is not None


def test_pydantic_agent_callable_and_dict_output_json_schema() -> None:
    """Verify PydanticAgent supports both property and callable access to output_json_schema."""
    from unittest.mock import MagicMock

    from devops_cli.ai.agents.agent import PydanticAgent

    agent: PydanticAgent[Any] = PydanticAgent(
        client=MagicMock(),
        name="test-agent",
        output_type=NativeOutput(SampleOutputModel),
    )

    # Property access (dict)
    schema_dict = agent.output_json_schema
    assert isinstance(schema_dict, dict)
    assert "properties" in schema_dict
    assert "summary" in schema_dict["properties"]

    # Callable access (method style)
    callable_schema = agent.output_json_schema()
    assert isinstance(callable_schema, dict)
    assert callable_schema == schema_dict


def test_pydantic_agent_text_output_execution() -> None:
    """Verify PydanticAgent applies TextOutput function to raw string model outputs."""
    from unittest.mock import MagicMock

    from devops_cli.ai.agents.agent import PydanticAgent

    mock_client = MagicMock()
    mock_client.chat_messages.return_value = "alpha beta gamma delta"
    mock_client.chat_messages_stream.return_value = iter(["alpha beta ", "gamma delta"])
    agent: PydanticAgent[Any] = PydanticAgent(
        client=mock_client,
        name="text-output-agent",
        output_type=TextOutput(sample_text_processor),
    )

    result = agent.run("Split words")
    assert result.data == ["alpha", "beta", "gamma", "delta"]


def test_pydantic_agent_structured_dict_execution() -> None:
    """Verify PydanticAgent validates structured outputs with StructuredDict."""
    from unittest.mock import MagicMock

    from devops_cli.ai.agents.agent import PydanticAgent

    raw_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"status": {"type": "string"}, "code": {"type": "integer"}},
        "required": ["status", "code"],
    }
    sd = StructuredDict(raw_schema, name="StatusPayload")

    mock_client = MagicMock()
    mock_client.chat_messages.return_value = '{"status": "ok", "code": 200}'
    mock_client.chat_messages_stream.return_value = iter(['{"status": "ok", ', '"code": 200}'])
    agent: PydanticAgent[Any] = PydanticAgent(
        client=mock_client,
        name="dict-agent",
        output_type=sd,
    )

    result = agent.run("Get status")
    assert isinstance(result.data, dict)
    assert result.data.get("status") == "ok"
    assert result.data.get("code") == 200


def test_public_reexports_in_ai_and_agents() -> None:
    """Verify output symbols are re-exported in devops_cli.ai and devops_cli.ai.agents."""
    import devops_cli.ai as ai
    import devops_cli.ai.agents as agents
    import devops_cli.ai.agents.pydantic_agent as pydantic_agent

    # devops_cli.ai
    assert hasattr(ai, "ToolOutput")
    assert hasattr(ai, "NativeOutput")
    assert hasattr(ai, "PromptedOutput")
    assert hasattr(ai, "TextOutput")
    assert hasattr(ai, "StructuredDict")
    assert hasattr(ai, "build_output_spec")
    assert hasattr(ai, "unwrap_output_spec")
    assert hasattr(ai, "extract_output_json_schema")
    assert hasattr(ai, "get_review_output_spec")

    # devops_cli.ai.agents
    assert hasattr(agents, "ToolOutput")
    assert hasattr(agents, "NativeOutput")
    assert hasattr(agents, "PromptedOutput")
    assert hasattr(agents, "TextOutput")
    assert hasattr(agents, "StructuredDict")
    assert hasattr(agents, "build_output_spec")

    # devops_cli.ai.agents.pydantic_agent
    assert hasattr(pydantic_agent, "ToolOutput")
    assert hasattr(pydantic_agent, "NativeOutput")
    assert hasattr(pydantic_agent, "PromptedOutput")
    assert hasattr(pydantic_agent, "TextOutput")
    assert hasattr(pydantic_agent, "StructuredDict")
