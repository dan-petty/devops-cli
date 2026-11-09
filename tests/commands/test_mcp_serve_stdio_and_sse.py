"""`devops mcp serve` starts the stdio and SSE transports, and its dry run lists the bind and the start (#2260)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.mcp import app


def _plan_lines(output: str) -> list[str]:
    """The numbered lines of a request plan, without their numbers."""
    import re

    return [line.split(". ", 1)[1] for line in output.splitlines() if re.match(r"^\s*\d+\. ", line)]


def test_serve_invalid_transport(runner: CliRunner) -> None:
    """devops mcp serve with invalid transport must exit with code 1."""
    result = runner.invoke(app, ["serve", "--transport", "grpc"])
    assert result.exit_code == 1
    assert "Invalid transport" in result.output


def test_serve_stdio_calls_run_mcp_server(runner: CliRunner) -> None:
    """devops mcp serve --transport stdio must delegate to run_mcp_server."""
    with patch("fastmcp.FastMCP.run") as mock_run:
        result = runner.invoke(app, ["serve", "--transport", "stdio"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(transport="stdio", show_banner=False)


def test_serve_sse_calls_run_mcp_server(runner: CliRunner) -> None:
    """devops mcp serve --transport sse must pass host and port to run_mcp_server."""
    with patch("fastmcp.FastMCP.run") as mock_run:
        result = runner.invoke(
            app, ["serve", "--transport", "sse", "--host", "::1", "--port", "9090"]
        )
        assert result.exit_code == 0
        mock_run.assert_called_once_with(transport="sse", host="::1", port=9090)


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--transport", "stdio"], ["START mcp server (stdio)"]),
        (
            ["--transport", "sse", "--host", "::1", "--port", "9090"],
            ["BIND tcp ::1:9090", "START mcp server (sse)"],
        ),
    ],
)
@pytest.mark.parametrize("flag_first", [True, False])
def test_mcp_serve_dry_run_lists_the_bind_and_the_start(
    cli: Any, argv: list[str], expected: list[str], flag_first: bool
) -> None:
    """A dry run starts no server and lists what the start would bind and start."""
    full = ["mcp", "serve", *argv]
    with patch("fastmcp.FastMCP.run", side_effect=AssertionError("no server")):
        result = cli(["--dry-run", *full] if flag_first else [*full, "--dry-run"])

    assert result.exit_code == 0, result.output
    assert _plan_lines(result.output) == expected


def test_mcp_serve_dry_run_refuses_what_the_start_refuses(cli: Any) -> None:
    """A bad transport and a remote `sse` host end the dry run as they end the start."""
    with patch("fastmcp.FastMCP.run", side_effect=AssertionError("no server")):
        bad = cli(["mcp", "serve", "--transport", "grpc", "--dry-run"])
        remote = cli(["mcp", "serve", "--transport", "sse", "--host", "192.0.2.10", "--dry-run"])

    assert (bad.exit_code, remote.exit_code) == (1, 1)
    assert _plan_lines(remote.output) == []


def test_mcp_serve_starts_what_its_plan_lists(cli: Any) -> None:
    """The start receives the host, the port and the transport of the plan."""
    argv = ["mcp", "serve", "--transport", "sse", "--host", "::1", "--port", "9090"]
    planned = _plan_lines(cli([*argv, "--dry-run"]).output)
    with patch("fastmcp.FastMCP.run") as start:
        result = cli(argv)

    assert result.exit_code == 0, result.output
    kwargs = start.call_args.kwargs
    assert planned == [
        f"BIND tcp {kwargs['host']}:{kwargs['port']}",
        f"START mcp server ({kwargs['transport']})",
    ]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
