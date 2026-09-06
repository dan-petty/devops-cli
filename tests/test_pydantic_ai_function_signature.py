"""Unit test suite for native Pydantic AI function_signature integration and tool introspection."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pydantic_ai.function_signature as p_fs
import pytest
from pydantic import BaseModel, Field
from pydantic_ai.tools import RunContext, Tool

from devops_cli.ai.agents import PydanticAgent
from devops_cli.ai.agents.tools import AgentTool
from devops_cli.ai.function_signature import (
    FunctionParam,
    FunctionSignature,
    GenericTypeExpr,
    LiteralTypeExpr,
    SimpleTypeExpr,
    SimpleTypeName,
    TypeExpr,
    TypeFieldSignature,
    TypeSignature,
    UnionTypeExpr,
    get_tool_signatures,
    render_signatures,
    render_tool_interface,
    signature_from_callable,
    signature_from_schema,
    signature_from_tool,
)


class VulnerabilityReport(BaseModel):
    """Vulnerability report data structure."""

    cve_id: str = Field(description="CVE identifier")
    severity: str = Field(default="HIGH", description="Severity rating")


def sample_scan(target: str, max_depth: int = 3) -> list[str]:
    """Scan directory tree for security vulnerabilities."""
    return [f"{target}:depth_{max_depth}"]


async def sample_async_remediate(
    ctx: RunContext[None], finding_id: str, auto_apply: bool = False
) -> bool:
    """Remediate a detected security vulnerability."""
    return True


def test_native_function_signature_reexports() -> None:
    """Verify all native classes and expressions are re-exported from pydantic_ai.function_signature."""
    assert FunctionSignature is p_fs.FunctionSignature
    assert FunctionParam is p_fs.FunctionParam
    assert TypeSignature is p_fs.TypeSignature
    assert TypeFieldSignature is p_fs.TypeFieldSignature
    assert TypeExpr is p_fs.TypeExpr
    assert SimpleTypeName is p_fs.SimpleTypeName
    assert SimpleTypeExpr is p_fs.SimpleTypeExpr
    assert LiteralTypeExpr is p_fs.LiteralTypeExpr
    assert GenericTypeExpr is p_fs.GenericTypeExpr
    assert UnionTypeExpr is p_fs.UnionTypeExpr


def test_signature_from_schema_simple() -> None:
    """Verify building a FunctionSignature from a JSON schema."""
    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "default": 10},
        },
        "required": ["query"],
    }
    sig = signature_from_schema(
        name="search_kb",
        parameters_schema=schema,
        description="Search documentation knowledge base",
    )
    assert sig.name == "search_kb"
    assert "query" in sig.params
    assert "limit" in sig.params
    assert sig.params["query"].description == "Search query"
    assert sig.params["limit"].default == "10"

    rendered = sig.render("return ...", description=sig.description)
    assert "def search_kb(*, query: str, limit: int = 10) -> Any:" in rendered
    assert "Search documentation knowledge base" in rendered


def test_signature_from_callable_sync() -> None:
    """Verify building a FunctionSignature from a synchronous Python callable."""
    sig = signature_from_callable(sample_scan)
    assert sig.name == "sample_scan"
    assert "target" in sig.params
    assert "max_depth" in sig.params
    assert sig.params["max_depth"].default == "3"
    assert sig.is_async is False

    rendered = sig.render("return []", description=sig.description)
    assert "def sample_scan(*, target: str, max_depth: int = 3) -> list[str]:" in rendered
    assert "Scan directory tree for security vulnerabilities." in rendered


def test_signature_from_callable_async_with_ctx() -> None:
    """Verify building a FunctionSignature from an async callable taking RunContext."""
    sig = signature_from_callable(sample_async_remediate, takes_ctx=True)
    assert sig.name == "sample_async_remediate"
    assert "ctx" not in sig.params
    assert "finding_id" in sig.params
    assert "auto_apply" in sig.params
    assert sig.params["auto_apply"].default == "False"
    assert sig.is_async is True

    rendered = sig.render("return True", description=sig.description, is_async=True)
    assert (
        "async def sample_async_remediate(*, finding_id: str, auto_apply: bool = False) -> bool:"
        in rendered
    )
    assert "Remediate a detected security vulnerability." in rendered


def test_signature_from_tool_pydantic_ai_tool() -> None:
    """Verify building a FunctionSignature from a native Pydantic AI Tool instance."""
    tool = Tool(sample_scan)
    sig = signature_from_tool(tool)
    assert sig.name == "sample_scan"
    assert "target" in sig.params
    assert "max_depth" in sig.params


def test_signature_from_tool_agent_tool() -> None:
    """Verify building a FunctionSignature from an AgentTool instance."""
    agent_tool = AgentTool(
        name="scan_repo",
        description="Run security scan across repository",
        func=sample_scan,
        parameters={"target": "str", "max_depth": "int"},
    )
    sig = signature_from_tool(agent_tool)
    assert sig.name == "scan_repo"
    assert "target" in sig.params

    # Verify method on AgentTool directly
    direct_sig = agent_tool.to_function_signature()
    assert direct_sig.name == "scan_repo"


def test_render_signatures_with_type_definitions() -> None:
    """Verify render_signatures renders referenced TypedDict schemas alongside signatures."""

    def submit_report(report: VulnerabilityReport, tag: str = "latest") -> bool:
        """Submit a vulnerability report."""
        return True

    sig = signature_from_callable(submit_report)
    rendered = render_signatures([sig])
    assert "class VulnerabilityReport(TypedDict):" in rendered
    assert "cve_id: str" in rendered
    assert "def submit_report(*, report: VulnerabilityReport, tag: str = 'latest') -> bool:" in (
        rendered
    )


def test_render_tool_interface_formats() -> None:
    """Verify render_tool_interface renders both raw python and markdown fenced blocks."""
    tools = [Tool(sample_scan)]

    py_out = render_tool_interface(tools, format="python")
    assert "def sample_scan(" in py_out
    assert "```" not in py_out

    md_out = render_tool_interface(tools, format="markdown")
    assert "```python\n" in md_out
    assert "def sample_scan(" in md_out
    assert md_out.endswith("```")


def test_pydantic_agent_tool_signatures() -> None:
    """Verify PydanticAgent exposes get_tool_signatures and render_tool_interface."""
    agent: PydanticAgent[Any, Any] = PydanticAgent(
        name="SecOpsAgent",
        system_prompt="You are a security assistant.",
    )
    agent.add_tool(sample_scan)

    sigs = agent.get_tool_signatures()
    assert len(sigs) == 1
    assert sigs[0].name == "sample_scan"

    interface = agent.render_tool_interface()
    assert "def sample_scan(*, target: str, max_depth: int = 3) -> list[str]:" in interface


def test_get_tool_signatures_batch() -> None:
    """Verify get_tool_signatures extracts signatures from multiple tool instances."""
    tools = [sample_scan, Tool(sample_async_remediate, takes_ctx=True)]
    sigs = get_tool_signatures(tools)
    assert len(sigs) == 2
    assert sigs[0].name == "sample_scan"
    assert sigs[1].name == "sample_async_remediate"


def test_public_package_reexports() -> None:
    """Verify function_signature types and helpers are re-exported across package tiers."""
    import devops_cli.ai as ai
    import devops_cli.ai.agents as agents
    import devops_cli.ai.agents.pydantic_agent as pydantic_agent

    assert hasattr(ai, "FunctionSignature")
    assert hasattr(ai, "FunctionParam")
    assert hasattr(ai, "TypeSignature")
    assert hasattr(ai, "signature_from_tool")
    assert hasattr(ai, "signature_from_callable")
    assert hasattr(ai, "render_signatures")
    assert hasattr(ai, "render_tool_interface")

    assert hasattr(agents, "FunctionSignature")
    assert hasattr(agents, "FunctionParam")
    assert hasattr(pydantic_agent, "FunctionSignature")


def test_signature_from_schema_async() -> None:
    """Verify signature_from_schema correctly flags asynchronous routines."""
    sig = signature_from_schema(
        name="async_task",
        parameters_schema={"type": "object", "properties": {"msg": {"type": "string"}}},
        is_async=True,
    )
    assert sig.is_async is True


def test_signature_from_tool_variations() -> None:
    """Verify signature_from_tool handles existing signatures, duck typing, and errors."""
    # Existing FunctionSignature
    sig_orig = signature_from_schema(name="noop", parameters_schema={"type": "object"})
    assert signature_from_tool(sig_orig) is sig_orig

    # Duck-typed object with func
    class CustomDuckTool:
        func = sample_scan
        name = "duck_scan"
        description = "Duck tool"
        takes_ctx = False

    sig_duck = signature_from_tool(CustomDuckTool())
    assert sig_duck.name == "duck_scan"

    # Duck-typed object with func and dictionary schema parameters fallback
    class CustomDuckDictTool:
        name = "duck_dict"
        description = "Duck dict tool"
        parameters = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]}

        def func(self, **kwargs: Any) -> Any:
            pass

    with patch(
        "devops_cli.ai.function_signature.signature_from_callable",
        side_effect=ValueError("Cannot inspect"),
    ):
        sig_duck_dict = signature_from_tool(CustomDuckDictTool())
        assert sig_duck_dict.name == "duck_dict"
        assert "x" in sig_duck_dict.params

    # Duck-typed object with simple parameters mapping
    class CustomSimpleTool:
        name = "simple_tool"
        description = "Simple tool"
        parameters = {"arg1": "str"}

        def func(self, **kwargs: Any) -> Any:
            pass

    with patch(
        "devops_cli.ai.function_signature.signature_from_callable",
        side_effect=ValueError("Cannot inspect"),
    ):
        sig_simple = signature_from_tool(CustomSimpleTool())
        assert sig_simple.name == "simple_tool"
        assert "arg1" in sig_simple.params

    # Invalid tool type
    with pytest.raises(TypeError, match="Unsupported tool type"):
        signature_from_tool(12345)


def test_render_signatures_edge_cases() -> None:
    """Verify edge case behaviors of render_signatures."""
    # Empty list
    assert render_signatures([]) == ""

    # include_type_defs=False
    sig = signature_from_callable(sample_scan)
    rendered = render_signatures([sig], include_type_defs=False)
    assert "def sample_scan(" in rendered
    assert "TypedDict" not in rendered


def test_agent_tool_fallback_signature() -> None:
    """Verify AgentTool fallback when func cannot be inspected directly."""
    tool = AgentTool(
        name="custom_raw",
        description="Raw tool",
        func=sample_scan,
        parameters={"properties": {"foo": {"type": "string"}}, "type": "object"},
    )
    with patch(
        "devops_cli.ai.function_signature.signature_from_callable",
        side_effect=ValueError("Cannot inspect"),
    ):
        sig = tool.to_function_signature()
        assert sig.name == "custom_raw"
        assert "foo" in sig.params
