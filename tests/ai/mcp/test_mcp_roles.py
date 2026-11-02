"""The tool set of each MCP role, and that a connection holds the tools of its role only (#3219)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from devops_cli.ai.mcp.remote import build_role_server
from devops_cli.ai.mcp.roles import (
    JOB_ROLES,
    ROLE_IMPLEMENTATION,
    ROLE_OPS,
    ROLE_PLANNING,
    ROLE_REVIEW,
    named_job_tools,
    tools_for_role,
)
from devops_cli.ai.mcp.server import mcp

_MUTATING_TOOLS = ("gh_issues_create", "k8s_deploy_stack", "k8s_teardown_stack", "docker_sign")


def _names(role: str) -> set[str]:
    server = build_role_server(role)

    async def listing() -> set[str]:
        async with Client(server) as client:
            return {tool.name for tool in await client.list_tools()}

    return asyncio.run(listing())


def _catalogue() -> list[Any]:
    return asyncio.run(mcp._list_tools())


def _fake_tool(name: str, *, read_only: bool | None) -> Any:
    annotations = None if read_only is None else SimpleNamespace(read_only_hint=read_only)
    return SimpleNamespace(name=name, annotations=annotations)


def test_two_connections_with_different_roles_see_different_tool_lists() -> None:
    planning, implementation, review = (_names(role) for role in JOB_ROLES)
    assert (len(planning), len(implementation), len(review)) == (28, 17, 16)
    assert (review < implementation, review < planning, implementation - planning) == (
        True,
        True,
        {"pr_describe"},
    )
    assert (planning & {"k8s_pods"}, implementation & {"k8s_pods"}) == ({"k8s_pods"}, set())


def test_ops_holds_every_tool_but_the_hydrate_tool() -> None:
    catalogue = {tool.name for tool in _catalogue()}
    assert _names(ROLE_OPS) == catalogue - {"hydrate_tool_domain"}


@pytest.mark.parametrize("role", JOB_ROLES)
def test_a_job_role_holds_read_only_tools_only(role: str) -> None:
    held = {tool.name for tool in tools_for_role(role, _catalogue())}
    mutating = {
        tool.name
        for tool in _catalogue()
        if getattr(tool.annotations, "read_only_hint", None) is not True
    }
    assert (held & mutating, held & set(_MUTATING_TOOLS)) == (set(), set())


@pytest.mark.parametrize("role", JOB_ROLES)
@pytest.mark.parametrize("tool", _MUTATING_TOOLS)
def test_a_job_role_cannot_call_a_mutating_tool_by_name(role: str, tool: str) -> None:
    server = build_role_server(role)

    async def call() -> None:
        async with Client(server) as client:
            await client.call_tool(tool, {})

    with pytest.raises(ToolError, match=f"Unknown tool: '{tool}'"):
        asyncio.run(call())


def test_a_read_only_tool_outside_the_role_cannot_be_called() -> None:
    server = build_role_server(ROLE_REVIEW)

    async def call() -> None:
        async with Client(server) as client:
            await client.call_tool("k8s_pods", {})

    with pytest.raises(ToolError, match="Unknown tool: 'k8s_pods'"):
        asyncio.run(call())


def test_a_hydrated_domain_does_not_change_the_tools_of_a_role() -> None:
    async def hydrate() -> None:
        async with Client(mcp) as client:
            await client.call_tool("hydrate_tool_domain", {"domain": "docker"})

    before = _names(ROLE_REVIEW)
    asyncio.run(hydrate())
    assert (_names(ROLE_REVIEW), "hydrate_tool_domain" in _names(ROLE_PLANNING)) == (before, False)


def test_a_role_server_offers_no_resource_and_no_prompt() -> None:
    server = build_role_server(ROLE_PLANNING)

    async def listing() -> tuple[list[Any], list[Any]]:
        async with Client(server) as client:
            return await client.list_resources(), await client.list_prompts()

    assert asyncio.run(listing()) == ([], [])


def test_every_tool_that_a_job_table_names_exists() -> None:
    assert named_job_tools() <= {tool.name for tool in _catalogue()}


def test_a_tool_that_is_not_read_only_leaves_every_job_role() -> None:
    tools = [_fake_tool(name, read_only=True) for name in named_job_tools()]
    flagged = [_fake_tool(t.name, read_only=t.name != "pr_diff") for t in tools]
    assert "pr_diff" in {t.name for t in tools_for_role(ROLE_IMPLEMENTATION, tools)}
    assert "pr_diff" not in {t.name for t in tools_for_role(ROLE_IMPLEMENTATION, flagged)}


def test_a_tool_without_a_read_only_flag_is_in_no_job_role() -> None:
    tools = [_fake_tool(name, read_only=None) for name in named_job_tools()]
    assert [tools_for_role(role, tools) for role in JOB_ROLES] == [[], [], []]


def test_a_table_name_that_no_tool_carries_is_refused() -> None:
    tools = [_fake_tool(name, read_only=True) for name in named_job_tools() - {"pr_diff"}]
    with pytest.raises(ValueError, match="names tools that do not exist: \\['pr_diff'\\]"):
        tools_for_role(ROLE_REVIEW, tools)


def test_an_unknown_role_is_refused() -> None:
    with pytest.raises(ValueError, match="Unknown MCP role 'admin'"):
        tools_for_role("admin", [])
