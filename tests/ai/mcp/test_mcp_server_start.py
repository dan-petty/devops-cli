"""`run_mcp_server` starts a transport and refuses a remote bind unless the caller allows it."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from devops_cli.ai.mcp.server import (
    run_mcp_server,
)


def test_run_stdio() -> None:
    """run_mcp_server stdio must call mcp.run(transport='stdio', show_banner=False)."""
    with patch("devops_cli.ai.mcp.server.mcp") as mock_mcp:
        run_mcp_server(transport="stdio")
        mock_mcp.run.assert_called_once_with(transport="stdio", show_banner=False)


def test_run_sse() -> None:
    """run_mcp_server sse must call mcp.run with host and port when allowed."""
    bind_all = "0.0.0.0"  # nosec B104  # the remote bind allow_remote permits, under test
    with patch("devops_cli.ai.mcp.server.mcp") as mock_mcp:
        run_mcp_server(transport="sse", host=bind_all, port=9000, allow_remote=True)
        mock_mcp.run.assert_called_once_with(transport="sse", host=bind_all, port=9000)


def test_run_sse_rejects_non_loopback_by_default() -> None:
    """run_mcp_server sse must reject non-loopback host unless allow_remote=True."""
    bind_all = "0.0.0.0"  # nosec B104  # the remote bind refused by default, under test
    with pytest.raises(ValueError, match="Refusing to bind SSE transport"):
        run_mcp_server(transport="sse", host=bind_all, port=9000)


@pytest.mark.parametrize(
    "loopback_host",
    ["127.0.0.2", "::ffff:127.0.0.1", "LOCALHOST."],
)
def test_run_sse_permits_loopback_variants(loopback_host: str) -> None:
    """run_mcp_server sse permits loopback addresses without allow_remote."""
    with patch("devops_cli.ai.mcp.server.mcp") as mock_mcp:
        run_mcp_server(transport="sse", host=loopback_host, port=9000)
        mock_mcp.run.assert_called_once_with(transport="sse", host=loopback_host, port=9000)
