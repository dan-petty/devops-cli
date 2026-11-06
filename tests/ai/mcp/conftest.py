"""Fixtures that several MCP test files share."""

from __future__ import annotations

import logging

import pytest

from tests.support.fakes.mcp_dispatcher import DispatcherFake


@pytest.fixture
def handler_runner(mcp_dispatcher: DispatcherFake) -> DispatcherFake:
    """Stand in for the CLI, failing loudly if any handler gets far enough to run a command."""
    mcp_dispatcher.fail(AssertionError("a handler ran"))
    return mcp_dispatcher


@pytest.fixture
def fastmcp_log(caplog):
    """Capture every FastMCP logger at DEBUG; FastMCP stops them propagating to the root."""
    fastmcp_logger = logging.getLogger("fastmcp")
    caplog.set_level(logging.DEBUG, logger="fastmcp")
    fastmcp_logger.addHandler(caplog.handler)
    yield caplog
    fastmcp_logger.removeHandler(caplog.handler)
