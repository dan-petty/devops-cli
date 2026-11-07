"""Call the devops-cli MCP server the way an MCP client does, over FastMCP's in-memory transport."""

from __future__ import annotations

from fastmcp import Client

from devops_cli.ai.mcp import server as mcp_server
from devops_cli.config.constants import CONST_MCP_LAZY_DOMAINS


async def call_tool(tool: str, arguments: dict[str, object]) -> tuple[bool, str]:
    """Call a tool the way an MCP client does, returning whether it failed and its reply."""
    async with Client(mcp_server.mcp) as client:
        result = await client.call_tool(tool, arguments, raise_on_error=False)
    return result.is_error, "\n".join(getattr(block, "text", "") for block in result.content)


async def published_schemas() -> dict[str, dict]:
    """Every registered tool's input schema as a client receives it, with all domains hydrated."""
    for domain in CONST_MCP_LAZY_DOMAINS:
        mcp_server.hydrate_tool_domain(domain)
    async with Client(mcp_server.mcp) as client:
        tools = await client.list_tools()
    return {
        tool.name: (getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None))
        for tool in tools
    }
