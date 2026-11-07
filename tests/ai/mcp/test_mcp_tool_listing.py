"""The tool listing that MCP clients receive changes only through a reviewed snapshot diff."""

from __future__ import annotations

from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.json import JSONSnapshotExtension

from devops_cli.ai.mcp.server import mcp


async def test_the_tool_listing_matches_the_snapshot(snapshot: SnapshotAssertion) -> None:
    """A change to a tool name, description or input schema shows as a diff of the snapshot.

    Update it with `uv run pytest tests/ai/mcp/test_mcp_tool_listing.py --snapshot-update` and
    review the diff.
    """
    tools = await mcp.list_tools(run_middleware=False)

    listing = {
        tool.name: {"description": tool.description, "input_schema": tool.parameters}
        for tool in tools
    }

    assert listing == snapshot(extension_class=JSONSnapshotExtension)
