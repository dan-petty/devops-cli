"""The default agent tools follow the tools of the devops-cli MCP server."""

from __future__ import annotations

import pytest

from devops_cli.ai.tools import get_mcp_agent_tools

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_mcp_bridge_dynamic_discovery() -> None:
    """Verify get_mcp_agent_tools returns dynamic tools from FastMCP rather than a static list."""
    tools = get_mcp_agent_tools()
    assert len(tools) >= 10
    tool_names = {getattr(t, "__name__", getattr(t, "name", str(t))) for t in tools}
    assert "review_path" in tool_names
    assert "k8s_pods" in tool_names


async def test_mcp_derived_default_tools_match_published_fastmcp_schemas() -> None:
    """Every MCP-derived tool in get_default_tools() matches FastMCP's published schema and runs without session."""
    import warnings

    from pydantic.json_schema import PydanticJsonSchemaWarning

    from devops_cli.ai.mcp.server import mcp as devops_server
    from devops_cli.ai.mcp.server import reset_hydrated_domains
    from devops_cli.ai.tools import Tool, get_default_tools

    mcp_fns = [
        fn
        for fn in get_default_tools()
        if getattr(fn, "__module__", "").startswith("devops_cli.ai.mcp.")
    ]
    published_tools = {
        fn.__name__: (fn, mcp_tool)
        for fn in mcp_fns
        if (mcp_tool := await devops_server.get_tool(fn.__name__)) is not None
    }
    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always", PydanticJsonSchemaWarning)
        mismatched_schemas = {
            name: (Tool.from_function(fn).function_schema.json_schema, mcp_tool.parameters)
            for name, (fn, mcp_tool) in published_tools.items()
            if Tool.from_function(fn).function_schema.json_schema != mcp_tool.parameters
        }
        hydrate_fn, _ = published_tools["hydrate_tool_domain"]
        hydrate_agent_tool = Tool.from_function(hydrate_fn)

    schema_warnings = [
        str(item.message)
        for item in recorded_warnings
        if issubclass(item.category, PydanticJsonSchemaWarning)
    ]
    try:
        hydrate_result = hydrate_agent_tool.execute(domain="k8s")
    finally:
        reset_hydrated_domains()

    assert (
        len(published_tools) >= 145,
        mismatched_schemas,
        schema_warnings,
        hydrate_result,
    ) == (
        True,
        {},
        [],
        {"domain": "k8s", "hydrated": True, "advertised_domains": ["k8s"]},
    )
