"""The optional code search provider on an MCP server (#4672): it finds the search tool of the
server, reads the links to files on GitHub in its answer as code hits, and raises the unavailable
error for a server that is down at the start or that fails a call.

A FastMCP server in the process is the MCP server, so no test opens a socket. The refused
connection is answered at the HTTP edge by `web`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import anyio
import pytest
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware

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


def _provider(server: FastMCP, *, timeout: float = 5.0) -> McpCodeSearch:
    toolset = RoadmapMcpToolset(server, optional=True, target_url=SERVER_URL)
    return McpCodeSearch(SERVER_URL, timeout=timeout, toolset=toolset)


class _BrokenListing(Middleware):
    """A server whose tool listing answers with an error."""

    async def on_list_tools(self, context: Any, call_next: Any) -> Any:
        raise RuntimeError("The index is broken.")


class _SilentListing(Middleware):
    """A server whose tool listing never answers."""

    async def on_list_tools(self, context: Any, call_next: Any) -> Any:
        await anyio.sleep_forever()


class _BrokenClose(RoadmapMcpToolset):
    """A connection whose stream is lost before its close, once the test says so. The toolset
    also leaves itself after each of its own requests, and those leaves stay as they are."""

    lost = False

    async def __aexit__(self, *args: Any) -> bool | None:
        result = await super().__aexit__(*args)
        if self.lost and not self.is_running:
            raise anyio.BrokenResourceError
        return result


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


def test_a_failed_call_ends_the_connection_and_the_provider_leaves_the_run() -> None:
    provider = _provider(_server(fails=True))
    provider.connect()

    with pytest.raises(RoadmapMcpUnavailableError, match="failed at the code search"):
        provider.search("pydantic_ai")
    connected = provider.connected
    with pytest.raises(RoadmapMcpUnavailableError, match="not connected"):
        provider.search("pydantic_ai")

    assert connected is False


def test_a_server_whose_tool_listing_answers_with_an_error_leaves_the_run(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The MCP library raises its own error for an error answer of `tools/list`. The provider
    gives it as the unavailable error, so the run leaves the provider out and goes on."""
    server = _server()
    server.add_middleware(_BrokenListing())
    store = InMemoryRoadmapStore(repo="example/roadmap")

    with open_providers(store, private=False, optional=[_provider(server)]) as providers:
        names = [provider.name for provider in providers]

    assert names == ["github-code", "github-repository"]
    assert "mcp-code is down at the start" in caplog.text


def test_a_tool_listing_that_does_not_answer_in_the_bound_of_a_tool_call_is_unavailable() -> None:
    server = _server()
    server.add_middleware(_SilentListing())
    provider = _provider(server, timeout=0.05)

    with pytest.raises(RoadmapMcpUnavailableError, match="TimeoutError"):
        provider.connect()

    assert provider.connected is False


def test_a_connection_that_fails_at_its_close_does_not_stop_the_run(
    caplog: pytest.LogCaptureFixture,
) -> None:
    toolset = _BrokenClose(_server(), optional=True, target_url=SERVER_URL)
    provider = McpCodeSearch(SERVER_URL, timeout=5.0, toolset=toolset)
    store = InMemoryRoadmapStore(repo="example/roadmap")

    with open_providers(store, private=False, optional=[provider]) as providers:
        names = [found.name for found in providers]
        hits = provider.search("pydantic_ai")
        toolset.lost = True

    assert (names, len(hits), provider.connected) == (
        ["github-code", "github-repository", "mcp-code"],
        2,
        False,
    )
    assert "mcp-code did not close its connection" in caplog.text


def test_an_answer_with_a_url_that_the_url_parser_refuses_gives_its_other_file_links() -> None:
    answer = (
        "URL: https://[index]/example/agent/blob/main/a.py\n"
        "URL: https://github.com/example/agent/blob/main/src/agent.py\n"
    )

    assert hits_of("mcp-code", "q", answer) == [_hit("example/agent", "src/agent.py", "q")]


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
