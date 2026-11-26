"""The optional code search provider on an MCP server (#4672): it finds the search tool of the
server, reads the links to files on GitHub in its answer as code hits, and raises the unavailable
error for a server that is down at the start or that fails a call.

A FastMCP server in the process is the MCP server, so no test opens a socket. The refused
connection is answered at the HTTP edge by `web`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastmcp import FastMCP

from devops_cli.config.settings import Settings
from devops_cli.exceptions.roadmap import RoadmapMcpUnavailableError
from devops_cli.roadmap.mcp import RoadmapMcpToolset
from devops_cli.roadmap.references.mcp_provider import (
    McpCodeSearch,
    configured_optional_providers,
    hits_of,
)
from devops_cli.roadmap.references.providers import Hit, HitKind, SearchKind, open_providers
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

if TYPE_CHECKING:
    from tests.support.fakes.http import WebFake

pytestmark = pytest.mark.usefixtures("keyring_store")

SERVER_URL = "https://mcp.example.com/mcp"
ANSWER = """Repository: example/agent
Path: src/agent.py
URL: https://github.com/example/agent/blob/main/src/agent.py
License: MIT

Snippets:
--- Snippet 1 (Line 3) ---
import pydantic_ai

Repository: example/app
Path: app/my run.py
URL: https://github.com/example/app/blob/main/app/my%20run.py
License: Unknown
"""


def _hit(repository: str, path: str, query: str = "pydantic_ai") -> Hit:
    return Hit("mcp-code", HitKind.CODE, query, repository=repository, path=path)


def _server(*, fails: bool = False) -> FastMCP:
    server = FastMCP("code-search")

    @server.tool
    def status() -> str:
        """The state of the index."""
        return "ready"

    @server.tool
    def search_code(query: str) -> str:
        """Search the code of public repositories."""
        if fails:
            raise RuntimeError("The index is down.")
        return ANSWER if query == "pydantic_ai" else "No results found."

    return server


def _provider(server: FastMCP) -> McpCodeSearch:
    toolset = RoadmapMcpToolset(server, optional=True, target_url=SERVER_URL)
    return McpCodeSearch(SERVER_URL, timeout=5.0, toolset=toolset)


def test_the_provider_asks_the_search_tool_and_reads_each_file_link_as_a_code_hit() -> None:
    provider = _provider(_server())

    provider.connect()
    try:
        found = (provider.search("pydantic_ai"), provider.search("another query"))
    finally:
        provider.close()

    assert (provider.name, provider.kind, found) == (
        "mcp-code",
        SearchKind.CODE,
        ([_hit("example/agent", "src/agent.py"), _hit("example/app", "app/my run.py")], []),
    )


def test_an_answer_gives_one_hit_for_each_file_link_and_none_for_another_url() -> None:
    answer = [
        "https://github.com/example/agent/blob/main/src/agent.py",
        "https://github.com/example/agent/blob/main/src/agent.py#L3",
        "https://github.com/example/agent",
        "https://github.com/example/agent/tree/main/src",
        "https://example.com/example/agent/blob/main/src/agent.py",
    ]

    assert hits_of("mcp-code", "q", answer) == [_hit("example/agent", "src/agent.py", "q")]


def test_a_failed_call_raises_the_unavailable_error_of_the_server() -> None:
    provider = _provider(_server(fails=True))

    provider.connect()
    try:
        with pytest.raises(
            RoadmapMcpUnavailableError, match="code search of the MCP server failed"
        ):
            provider.search("pydantic_ai")
    finally:
        provider.close()


def test_a_server_with_no_search_tool_and_a_provider_that_is_not_connected_are_unavailable() -> (
    None
):
    bare = FastMCP("bare")

    @bare.tool
    def status() -> str:
        """The state of the index."""
        return "ready"

    with pytest.raises(RoadmapMcpUnavailableError, match="no tool with a query argument"):
        _provider(bare).connect()
    with pytest.raises(RoadmapMcpUnavailableError, match="not connected"):
        _provider(_server()).search("pydantic_ai")


def test_no_server_url_gives_no_optional_provider() -> None:
    assert configured_optional_providers(Settings()) == []


def test_a_configured_server_that_refuses_the_connection_at_the_start_leaves_the_run(
    web: WebFake,
) -> None:
    web.refuse(SERVER_URL)
    settings = Settings(roadmap={"alternatives": {"references_mcp_url": SERVER_URL}})
    store = InMemoryRoadmapStore(repo="example/roadmap")

    optional = configured_optional_providers(settings)
    with open_providers(store, private=False, optional=optional) as providers:
        names = [provider.name for provider in providers]

    assert ([provider.name for provider in optional], names, web.requested) == (
        ["mcp-code"],
        ["github-code", "github-repository"],
        [SERVER_URL],
    )
