"""MCP submodule for devops-cli FastMCP server integration."""

from __future__ import annotations

from typing import Any

from devops_cli.ai.mcp.dispatcher import (
    DomainSchemaHydrator,
    InProcessDispatcher,
    ResourceSubscriptionManager,
    get_mcp_dispatcher,
    resolve_tool_domain,
)
from devops_cli.ai.mcp.toolset import (
    CallToolFunc,
    ContentBlock,
    EmbeddedResource,
    Icon,
    MCPError,
    MCPToolset,
    MCPToolsetClient,
    ProcessToolCallback,
    Prompt,
    PromptArgument,
    PromptMessage,
    PromptResult,
    PromptRole,
    Resource,
    ResourceAnnotations,
    ResourceLink,
    ResourceTemplate,
    ServerCapabilities,
    ToolResult,
    create_devops_mcp_toolset,
    create_mcp_toolset,
    load_devops_mcp_toolsets,
    load_mcp_toolsets,
)

__all__ = [
    "CallToolFunc",
    "ContentBlock",
    "DomainSchemaHydrator",
    "EmbeddedResource",
    "Icon",
    "InProcessDispatcher",
    "MCPError",
    "MCPToolset",
    "MCPToolsetClient",
    "ProcessToolCallback",
    "Prompt",
    "PromptArgument",
    "PromptMessage",
    "PromptResult",
    "PromptRole",
    "Resource",
    "ResourceAnnotations",
    "ResourceLink",
    "ResourceSubscriptionManager",
    "ResourceTemplate",
    "ServerCapabilities",
    "ToolResult",
    "create_devops_mcp_toolset",
    "create_mcp_toolset",
    "get_mcp_dispatcher",
    "list_mcp_tools",
    "load_devops_mcp_toolsets",
    "load_mcp_toolsets",
    "mcp",
    "resolve_tool_domain",
    "run_mcp_server",
    "server",
]


def __getattr__(name: str) -> Any:
    """Lazy attribute lookup for server exports avoiding circular imports."""
    if name in {"list_mcp_tools", "mcp", "run_mcp_server", "server"}:
        import importlib

        server_mod = importlib.import_module("devops_cli.ai.mcp.server")
        if name == "server":
            return server_mod
        return getattr(server_mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
