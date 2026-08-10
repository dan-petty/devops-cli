"""Unit tests for FastMCP server integration (devops_cli.mcp and devops_cli.commands.mcp)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.mcp import app
from devops_cli.mcp import list_mcp_tools, mcp, run_mcp_server

if TYPE_CHECKING:
    pass


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ── FastMCP server ───────────────────────────────────────────────────────────


class TestMcpServer:
    """Tests for the FastMCP server instance and tool registrations."""

    def test_server_name(self) -> None:
        """FastMCP server must be named 'devops-cli'."""
        assert mcp.name == "devops-cli"

    def test_tools_registered(self) -> None:
        """All expected MCP tools must be registered on the server."""
        tools = asyncio.run(mcp.list_tools())
        tool_names = {t.name for t in tools}

        expected = {
            "review_path",
            "review_branch",
            "review_pr",
            "review_findings",
            "verify_finding",
            "review_stats",
            "repos_list",
            "repos_status",
            "repos_sync",
            "ssh_status",
            "ssh_audit",
            "k8s_pods",
            "k8s_status",
            "argo_list",
            "argo_status",
            "grafana_dashboards",
            "prometheus_query",
            "docker_stats",
            "workspace_list",
            "config_show",
            "config_output",
            "ci_run",
        }
        assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"

    def test_list_mcp_tools_returns_list_of_dicts(self) -> None:
        """list_mcp_tools() must return a list of dicts with name and description keys."""
        tools = list_mcp_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0
        for t in tools:
            assert "name" in t
            assert "description" in t

    def test_all_tools_have_descriptions(self) -> None:
        """All registered tools must have non-empty docstrings used as descriptions."""
        tools = asyncio.run(mcp.list_tools())
        missing_desc = [t.name for t in tools if not t.description]
        assert missing_desc == [], f"Tools missing descriptions: {missing_desc}"


# ── run_mcp_server ───────────────────────────────────────────────────────────


class TestRunMcpServer:
    """Tests for run_mcp_server launch helper."""

    def test_run_stdio(self) -> None:
        """run_mcp_server stdio must call mcp.run(transport='stdio')."""
        with patch("devops_cli.mcp.mcp") as mock_mcp:
            run_mcp_server(transport="stdio")
            mock_mcp.run.assert_called_once_with(transport="stdio")

    def test_run_sse(self) -> None:
        """run_mcp_server sse must call mcp.run with host and port."""
        with patch("devops_cli.mcp.mcp") as mock_mcp:
            run_mcp_server(transport="sse", host="0.0.0.0", port=9000)
            mock_mcp.run.assert_called_once_with(transport="sse", host="0.0.0.0", port=9000)


# ── commands/mcp.py CLI ──────────────────────────────────────────────────────


class TestMcpCli:
    """Tests for `devops mcp` CLI subcommands."""

    def test_tools_command_outputs_table(self, runner: CliRunner) -> None:
        """devops mcp tools must print a table with tool names."""
        result = runner.invoke(app, ["tools"])
        assert result.exit_code == 0
        assert "review_path" in result.output

    def test_serve_invalid_transport(self, runner: CliRunner) -> None:
        """devops mcp serve with invalid transport must exit with code 1."""
        result = runner.invoke(app, ["serve", "--transport", "grpc"])
        assert result.exit_code == 1
        assert "Invalid transport" in result.output

    def test_serve_stdio_calls_run_mcp_server(self, runner: CliRunner) -> None:
        """devops mcp serve --transport stdio must delegate to run_mcp_server."""
        with patch("devops_cli.commands.mcp.run_mcp_server") as mock_run:
            result = runner.invoke(app, ["serve", "--transport", "stdio"])
            assert result.exit_code == 0
            mock_run.assert_called_once_with(transport="stdio", host="127.0.0.1", port=8000)

    def test_serve_sse_calls_run_mcp_server(self, runner: CliRunner) -> None:
        """devops mcp serve --transport sse must pass host and port to run_mcp_server."""
        with patch("devops_cli.commands.mcp.run_mcp_server") as mock_run:
            result = runner.invoke(
                app, ["serve", "--transport", "sse", "--host", "0.0.0.0", "--port", "9090"]
            )
            assert result.exit_code == 0
            mock_run.assert_called_once_with(transport="sse", host="0.0.0.0", port=9090)
