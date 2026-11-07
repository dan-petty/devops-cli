"""The MCP tool `ai_fetch_page` reads a page and takes no secret, service address or path (#3892)."""

from __future__ import annotations

import asyncio

from devops_cli.ai.mcp.roles import JOB_ROLES, named_job_tools
from devops_cli.ai.mcp.server import mcp
from tests.support.mcp_client import published_schemas

_TOOL = "ai_fetch_page"


def test_the_tool_is_generated_read_only_and_in_the_ai_domain() -> None:
    tool = asyncio.run(mcp.get_tool(_TOOL))

    assert tool is not None
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is True
    assert tool.name.split("_")[0] == "ai"


def test_the_schema_holds_the_page_url_and_the_dry_run_flag_only() -> None:
    schema = asyncio.run(published_schemas())[_TOOL]

    assert sorted(schema["properties"]) == ["dry_run", "url"]
    assert schema["required"] == ["url"]


def test_no_job_role_holds_the_tool_until_a_person_approves_the_egress() -> None:
    from devops_cli.ai.mcp.roles import tools_for_role

    catalogue = asyncio.run(mcp._list_tools())

    assert _TOOL in {tool.name for tool in catalogue}
    assert _TOOL not in named_job_tools()
    for role in JOB_ROLES:
        assert _TOOL not in {tool.name for tool in tools_for_role(role, catalogue)}
