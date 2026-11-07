"""Fixtures that several MCP test files share."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    # Imported for the annotation only: pytest loads this conftest before it isolates HOME, and
    # an import of devops-cli here would bind its paths under the real HOME (#1311, #1312).
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
