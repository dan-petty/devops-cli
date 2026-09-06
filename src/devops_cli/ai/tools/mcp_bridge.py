"""MCP tool bridge exposing FastMCP tools to PydanticAgent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_ai.mcp import MCPToolset
    from pydantic_ai.toolsets import PrefixedToolset


def get_mcp_agent_tools() -> list[Any]:
    """Expose FastMCP server tools dynamically to PydanticAgents."""
    from devops_cli.ai.mcp.server import mcp as devops_server

    provider = getattr(devops_server, "local_provider", None)
    if provider is not None and hasattr(provider, "_components"):
        return [
            getattr(c, "fn", c)
            for c in provider._components.values()
            if hasattr(c, "fn") and callable(getattr(c, "fn"))
        ]

    from devops_cli.ai.mcp import server as mcp_module

    return [
        getattr(mcp_module, name)
        for name in dir(mcp_module)
        if not name.startswith("_") and callable(getattr(mcp_module, name))
    ]


def get_devops_mcp_toolset(*, tool_prefix: str | None = None) -> MCPToolset | PrefixedToolset:
    """Return native Pydantic AI MCPToolset connected to the in-process FastMCP server."""
    from devops_cli.ai.mcp.toolset import create_devops_mcp_toolset

    return create_devops_mcp_toolset(tool_prefix=tool_prefix)
