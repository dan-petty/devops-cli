"""Tests for native Pydantic AI output subsystem integration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai.output import NativeOutput, PromptedOutput, StructuredDict, ToolOutput

from devops_cli.ai.output import TextOutput, extract_output_json_schema, unwrap_output_spec


class SampleOutputModel(BaseModel):
    summary: str = Field(description="Summary text")
    score: int = Field(default=10, description="Numerical score")


def sample_text_processor(text: str) -> list[str]:
    return [word.strip() for word in text.split() if word.strip()]


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
