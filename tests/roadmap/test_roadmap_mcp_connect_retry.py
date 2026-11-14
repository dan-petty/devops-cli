"""Tests for the first-connection retry of the roadmap MCP client (#4372)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic_ai.mcp import MCPToolset

from devops_cli.config import constants
from devops_cli.exceptions.roadmap import RoadmapMcpUnavailableError
from devops_cli.roadmap.mcp import RoadmapMcpToolset


def _budget(monkeypatch: pytest.MonkeyPatch, seconds: float = 0.05) -> None:
    monkeypatch.setattr(constants, "ROADMAP_MCP_CONNECT_RETRY_SECONDS", seconds)
    monkeypatch.setattr(constants, "ROADMAP_MCP_CONNECT_RETRY_INITIAL_SECONDS", 0.001)
    monkeypatch.setattr(constants, "ROADMAP_MCP_CONNECT_RETRY_MAX_SECONDS", 0.001)


@pytest.mark.asyncio
async def test_a_refused_first_connection_is_retried_until_it_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[int] = []

    async def flaky(self: Any) -> str:
        attempts.append(len(attempts) + 1)
        if len(attempts) < 3:
            raise ConnectionRefusedError("Connection refused")
        return "entered"

    monkeypatch.setattr(MCPToolset, "__aenter__", flaky)
    _budget(monkeypatch)

    toolset = RoadmapMcpToolset("http://mcp.example.com")

    assert await toolset.__aenter__() == "entered"
    assert len(attempts) == 3


@pytest.mark.asyncio
async def test_an_exhausted_budget_raises_the_existing_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def refused(self: Any) -> str:
        raise ConnectionRefusedError("Connection refused")

    monkeypatch.setattr(MCPToolset, "__aenter__", refused)
    _budget(monkeypatch, 0.02)

    toolset = RoadmapMcpToolset("http://mcp.example.com", target_url="http://mcp.example.com")

    with pytest.raises(RoadmapMcpUnavailableError) as found:
        await toolset.__aenter__()

    assert found.value.url == "http://mcp.example.com"
    assert isinstance(found.value.__cause__, ConnectionRefusedError)


@pytest.mark.asyncio
async def test_an_authentication_failure_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    class Unauthenticated(Exception):
        pass

    async def unauthenticated(self: Any) -> str:
        calls.append(1)
        raise Unauthenticated("HTTP 401")

    monkeypatch.setattr(MCPToolset, "__aenter__", unauthenticated)
    _budget(monkeypatch, 10.0)

    toolset = RoadmapMcpToolset("http://mcp.example.com")

    with pytest.raises(RoadmapMcpUnavailableError, match="HTTP 401"):
        await toolset.__aenter__()

    assert len(calls) == 1


def test_the_retry_budget_comes_from_the_constants_module() -> None:
    assert constants.ROADMAP_MCP_CONNECT_RETRY_SECONDS == 30.0
    assert constants.ROADMAP_MCP_CONNECT_RETRY_INITIAL_SECONDS == 1.0
    assert constants.ROADMAP_MCP_CONNECT_RETRY_MAX_SECONDS == 8.0
