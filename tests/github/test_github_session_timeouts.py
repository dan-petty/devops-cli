"""The read bound of the GitHub session and the chain of bounds around a GitHub read (#4626)."""

from __future__ import annotations

import math
import socket
from collections.abc import Awaitable, Iterator
from itertools import pairwise
from typing import Final

import httpx2
import pytest

from devops_cli.config import defaults
from devops_cli.config.constants import (
    CONST_MCP_EXPOSURE_TABLE,
    CONST_MCP_GITHUB_TOOL_TIMEOUT_SECONDS,
)
from devops_cli.exceptions.git import GitHubUnreadError
from devops_cli.github import session_transport
from devops_cli.github.session import get_github_session
from tests.support.fakes.dns import DnsFake
from tests.support.fakes.github import GitHubApiDouble, serve_github_api

# The read bound of the test of a silent host, so that the test ends at once.
_SHORT_READ_SECONDS: Final = 0.05

# The chains of bounds around a GitHub session read, each one the innermost first. A call holds
# the call of the bound before it: the Valkey cache tier in front of a read stops before the read,
# and the session's read stops before the call that holds it. The MCP server reads each
# `resource://gh/` resource with `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS`, and `devops gh issue status`
# reads the issues through the session (#4678). A new call around a GitHub read adds its bound to
# its chain, or adds its own chain.
_CHAINS: Final = (
    (
        "DEFAULT_VALKEY_TIMEOUT_SECONDS",
        "DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS",
        "DEFAULT_MCP_TOOL_TIMEOUT_SECONDS",
    ),
)

# Each pair of a bound and the bound around it, once, in the order of the chains.
_PAIRS: Final = list(dict.fromkeys(pair for chain in _CHAINS for pair in pairwise(chain)))


class _SilentGitHub(GitHubApiDouble):
    """GitHub as a host that takes each request and sends no answer.

    httpx2's own transport sends each request over plain HTTP to a loopback listener that accepts
    no connection. The kernel completes the connect, so only the read bound of the session's
    client ends the wait. The request that the session's hook sees keeps GitHub's origin.
    """

    def __init__(self, port: int) -> None:
        super().__init__()
        self._port = port

    def _handle(self, request: httpx2.Request) -> httpx2.Response | Awaitable[httpx2.Response]:
        self.sent.append(request)
        self.timeouts.append(request.extensions["timeout"])
        return self._send(request)

    async def _send(self, request: httpx2.Request) -> httpx2.Response:
        wire = httpx2.Request(
            request.method,
            request.url.copy_with(scheme="http", host="127.0.0.1", port=self._port),
            headers=request.headers,
            extensions=request.extensions,
        )
        async with httpx2.AsyncHTTPTransport() as transport:
            response = await transport.handle_async_request(wire)
            await response.aread()
            return response


@pytest.fixture
def silent_github(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, dns: DnsFake
) -> Iterator[_SilentGitHub]:
    """A silent GitHub for every GitHub session of the test, on a listener that the test binds."""
    dns.answer_every_name()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        api = _SilentGitHub(listener.getsockname()[1])
        serve_github_api(request, monkeypatch, api)
        yield api


def test_a_host_that_does_not_answer_fails_the_read_at_the_sessions_read_bound(
    silent_github: _SilentGitHub, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read that gets no answer stops at the session's read bound, here made short, with
    `ReadTimeout`. The session does not send it again: a read timeout is not a lost connection."""
    monkeypatch.setattr(
        session_transport, "DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS", _SHORT_READ_SECONDS
    )
    with pytest.raises(GitHubUnreadError) as raised:
        get_github_session().rest("GET", "/user")
    reads = [timeout["read"] for timeout in silent_github.timeouts]
    assert ("ReadTimeout" in raised.value.message, reads, silent_github.waits) == (
        True,
        [_SHORT_READ_SECONDS],
        [],
    )


@pytest.mark.parametrize(("inner", "outer"), _PAIRS)
def test_each_bound_of_the_chain_is_shorter_than_the_bound_around_it(
    inner: str, outer: str
) -> None:
    """Each inner timeout is shorter than the call around it (owner rule of 2026-11-11), so the
    inner call fails first and the call around it gets that error, not its own deadline. A bound
    that is not defined is endless."""
    assert getattr(defaults, inner, math.inf) < getattr(defaults, outer, math.inf)


# The MCP tool groups whose every command reads GitHub: `gh` and `pr`. A write command reads before
# it writes, so the read bound of the session applies to each one (#4784).
_GITHUB_TOOL_GROUPS: Final = frozenset({"gh", "pr"})


def test_each_github_mcp_tool_outlasts_the_github_read_bound() -> None:
    """Every `gh` and `pr` tool of the exposure table reads GitHub through the session, so its
    dispatch bound is the named GitHub MCP bound, above `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS`.
    A row at or below the read bound fails and is named (#4784)."""
    short = [
        f"{' '.join(path)}: {timeout}"
        for path, timeout, *_ in CONST_MCP_EXPOSURE_TABLE
        if path[0] in _GITHUB_TOOL_GROUPS
        and (
            timeout != CONST_MCP_GITHUB_TOOL_TIMEOUT_SECONDS
            or timeout <= defaults.DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS
        )
    ]

    assert short == []
