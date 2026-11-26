"""The optional code search provider of the reference step on an MCP server (#4672).

`roadmap.alternatives.references_mcp_url` names the server, such as the grep.app server, which
searches the code of public repositories. The provider is not specific to one server. It takes the
first tool of the server that has a `query` argument, sends it one query of an item, and reads
each link to a file on GitHub (`https://github.com/<owner>/<repo>/blob/<ref>/<path>`) in the
answer as a code hit. The step verifies each hit itself at the head commit, so the provider trusts
no ref and no line of the answer.

The connection is a `RoadmapMcpToolset` in its optional mode: `connect` makes one attempt and
raises `RoadmapMcpUnavailableError` when the server is down, and the run then leaves the provider
out. The HTTP client of the connection comes from `devops_cli.http.entry` at the public egress
level. The toolset runs on an event loop of its own, which a blocking portal keeps open from
`connect` to `close`.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import ExitStack
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import unquote, urlsplit

from anyio.from_thread import BlockingPortal, start_blocking_portal
from pydantic_ai.exceptions import AgentRunError, ModelRetry, ToolFailedError, UserError

from devops_cli.exceptions.roadmap import RoadmapMcpUnavailableError
from devops_cli.github.repo_ref import is_repository_name
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import async_http_client
from devops_cli.roadmap.mcp import RoadmapMcpToolset
from devops_cli.roadmap.page_fetch import urls_in_order
from devops_cli.roadmap.references.providers import Hit, HitKind, OptionalProvider, SearchKind

if TYPE_CHECKING:
    from devops_cli.config.settings import Settings

MCP_CODE: Final[str] = "mcp-code"
# The argument that a code search tool takes its query in.
_QUERY: Final[str] = "query"
_GITHUB_HOST: Final[str] = "github.com"
# The path segment of a link to a file on GitHub, after the owner and the repository.
_BLOB: Final[str] = "blob"
# The errors of a remote tool call that the provider gives as an unavailable server, the ones that
# `RoadmapMcpToolset.call_tool` turns into a tool error.
_CALL_ERRORS: Final = (
    ModelRetry,
    ToolFailedError,
    UserError,
    AgentRunError,
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    ExceptionGroup,
)


def _text_of(answer: Any) -> str:
    """The answer of a tool as one text: its text, or its JSON form."""
    return answer if isinstance(answer, str) else json.dumps(answer, default=str)


def _blob_hit(provider: str, query: str, url: str) -> Hit | None:
    """The code hit that the link `url` to a file on GitHub names, or None for another URL."""
    parts = urlsplit(url)
    segments = [unquote(segment) for segment in parts.path.split("/") if segment]
    if (parts.hostname or "").lower() != _GITHUB_HOST or len(segments) < 5:
        return None
    repository = f"{segments[0]}/{segments[1]}"
    if segments[2] != _BLOB or not is_repository_name(repository):
        return None
    return Hit(provider, HitKind.CODE, query, repository=repository, path="/".join(segments[4:]))


def hits_of(provider: str, query: str, answer: Any) -> list[Hit]:
    """The code hits of the answer of a code search tool: one for each link to a file on GitHub,
    in the order of the answer, each file once."""
    found = (_blob_hit(provider, query, url) for url in urls_in_order(_text_of(answer)))
    return list(dict.fromkeys(hit for hit in found if hit is not None))


class McpCodeSearch:
    """A code search tool of the MCP server at `url` as an optional provider. `timeout` bounds
    one call of the tool, in seconds. `connect` builds the toolset of the connection and its HTTP
    client, so a provider that never connects opens nothing. `toolset` replaces that toolset, for
    a server in the process."""

    name: str = MCP_CODE
    kind: SearchKind = SearchKind.CODE

    def __init__(
        self, url: str, *, timeout: float, toolset: RoadmapMcpToolset | None = None
    ) -> None:
        self._url = url
        self._timeout = timeout
        self._given = toolset
        self._toolset: RoadmapMcpToolset | None = None
        self._portal: BlockingPortal | None = None
        self._tool = ""
        self._open = ExitStack()

    def connect(self) -> None:
        """Connect to the server and find its search tool. Raises `RoadmapMcpUnavailableError`
        when the server is down or offers no tool with a `query` argument: nothing stays open."""
        with ExitStack() as opening:
            portal = opening.enter_context(start_blocking_portal())
            toolset = self._given
            if toolset is None:
                client = async_http_client(EgressLevel.PUBLIC)
                opening.callback(portal.call, client.aclose)
                toolset = RoadmapMcpToolset(
                    self._url,
                    optional=True,
                    timeout_seconds=self._timeout,
                    target_url=self._url,
                    http_client=client,
                )
            opening.enter_context(portal.wrap_async_context_manager(toolset))
            self._tool = portal.call(self._search_tool, toolset)
            self._toolset, self._portal = toolset, portal
            self._open = opening.pop_all()

    async def _search_tool(self, toolset: RoadmapMcpToolset) -> str:
        """The name of the first tool of the server that takes a `query`."""
        for tool in await toolset.list_tools():
            if _QUERY in (tool.input_schema.get("properties") or {}):
                return tool.name
        raise RoadmapMcpUnavailableError(
            self._url, message="The MCP server offers no tool with a query argument."
        )

    async def _call(self, toolset: RoadmapMcpToolset, query: str) -> Any:
        async with asyncio.timeout(self._timeout):
            return await toolset.direct_call_tool(self._tool, {_QUERY: query})

    def search(self, query: str) -> list[Hit]:
        """The code hits that the search tool of the server gives for `query`. A call that fails
        or passes the bound of a remote tool call raises `RoadmapMcpUnavailableError`."""
        if self._portal is None or self._toolset is None:
            raise RoadmapMcpUnavailableError(self._url, message="The MCP server is not connected.")
        try:
            answer = self._portal.call(self._call, self._toolset, query)
        except (TimeoutError, *_CALL_ERRORS) as exc:
            raise RoadmapMcpUnavailableError(
                self._url,
                message=f"The code search of the MCP server failed ({type(exc).__name__}).",
            ) from exc
        return hits_of(self.name, query, answer)

    def close(self) -> None:
        """End the connection and its event loop."""
        self._portal = self._toolset = None
        self._open.close()


def configured_optional_providers(settings: Settings) -> list[OptionalProvider]:
    """The optional providers that `settings` name: the MCP code search of
    `roadmap.alternatives.references_mcp_url`, or none."""
    url = settings.roadmap.alternatives.references_mcp_url
    if not url:
        return []
    return [McpCodeSearch(url, timeout=settings.roadmap.mcp.timeout_seconds)]


__all__ = ["MCP_CODE", "McpCodeSearch", "configured_optional_providers", "hits_of"]
