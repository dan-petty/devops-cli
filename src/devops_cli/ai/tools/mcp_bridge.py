"""MCP tool bridge exposing FastMCP tools to agents."""

from __future__ import annotations

from typing import Any


def get_mcp_agent_tools() -> list[Any]:
    """Expose FastMCP server tools dynamically to agents."""
    from fastmcp.server.dependencies import without_injected_parameters

    from devops_cli.ai.mcp.server import mcp as devops_server

    provider = getattr(devops_server, "local_provider", None)
    if provider is not None and hasattr(provider, "_components"):
        return [
            without_injected_parameters(getattr(c, "fn", c))
            for c in provider._components.values()
            if hasattr(c, "fn") and callable(getattr(c, "fn"))
        ]

    from devops_cli.ai.mcp import server as mcp_module

    return [
        without_injected_parameters(getattr(mcp_module, name))
        for name in dir(mcp_module)
        if not name.startswith("_") and callable(getattr(mcp_module, name))
    ]
