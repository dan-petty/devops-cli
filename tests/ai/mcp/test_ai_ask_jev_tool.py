"""The MCP tool `ai_ask_jev` asks Jev one question, is read-only and shares the bounds of the
command (#4306)."""

from __future__ import annotations

import asyncio

from devops_cli.ai.mcp.server import mcp
from tests.support.mcp_client import published_schemas

_TOOL = "ai_ask_jev"


def test_the_tool_is_generated_read_only_and_in_the_ai_domain() -> None:
    tool = asyncio.run(mcp.get_tool(_TOOL))

    assert tool is not None
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is True
    assert tool.name.split("_")[0] == "ai"


def test_the_schema_holds_the_question_inputs_and_no_output_option() -> None:
    schema = asyncio.run(published_schemas())[_TOOL]

    assert sorted(schema["properties"]) == [
        "context",
        "dry_run",
        "kind",
        "level",
        "no",
        "option",
        "question",
        "yes",
    ]
    assert sorted(schema["required"]) == ["kind", "question"]
    assert schema["properties"]["kind"]["enum"] == ["choice", "noul", "score"]


def test_an_input_over_the_bound_is_refused_through_the_tool() -> None:
    from devops_cli.config.constants import CONST_AI_JEV_ASK_MAX_INPUT_CHARS
    from tests.support.mcp_client import call_tool

    failed, reply = asyncio.run(
        call_tool(_TOOL, {"kind": "noul", "question": "x" * (CONST_AI_JEV_ASK_MAX_INPUT_CHARS + 1)})
    )

    assert failed or "Jev takes at most" in reply
    assert "Jev takes at most" in reply
