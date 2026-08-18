"""Unit tests for FastMCP server integration (devops_cli.mcp and devops_cli.commands.mcp)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.mcp import list_mcp_tools, mcp, run_mcp_server
from devops_cli.commands.mcp import app

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
            "k8s_bootstrap",
            "k8s_deploy_stack",
            "k8s_teardown_stack",
            "argo_list",
            "argo_status",
            "grafana_dashboards",
            "prometheus_query",
            "workspace_list",
            "config_show",
            "config_output",
            "ci_run",
            "ci_remote_status",
            "ci_remote_logs",
            "pr_list",
            "pr_view",
            "pr_checks",
            "branches_create",
            "branches_status",
            "repos_exec",
            "release_prepare",
            "release_notes",
            "tf_plan",
            "tf_apply",
            "tf_output",
            "tofu_plan",
            "tofu_apply",
            "tofu_output",
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
        """run_mcp_server stdio must call mcp.run(transport='stdio', show_banner=False)."""
        with patch("devops_cli.ai.mcp.server.mcp") as mock_mcp:
            run_mcp_server(transport="stdio")
            mock_mcp.run.assert_called_once_with(transport="stdio", show_banner=False)

    def test_run_sse(self) -> None:
        """run_mcp_server sse must call mcp.run with host and port when allowed."""
        with patch("devops_cli.ai.mcp.server.mcp") as mock_mcp:
            run_mcp_server(transport="sse", host="0.0.0.0", port=9000, allow_remote=True)
            mock_mcp.run.assert_called_once_with(transport="sse", host="0.0.0.0", port=9000)

    def test_run_sse_rejects_non_loopback_by_default(self) -> None:
        """run_mcp_server sse must reject non-loopback host unless allow_remote=True."""
        import pytest

        with pytest.raises(ValueError, match="Refusing to bind SSE transport"):
            run_mcp_server(transport="sse", host="0.0.0.0", port=9000)


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
            mock_run.assert_called_once_with(
                transport="stdio", host="127.0.0.1", port=8000, allow_remote=False
            )

    def test_serve_sse_calls_run_mcp_server(self, runner: CliRunner) -> None:
        """devops mcp serve --transport sse must pass host and port to run_mcp_server."""
        with patch("devops_cli.commands.mcp.run_mcp_server") as mock_run:
            result = runner.invoke(
                app, ["serve", "--transport", "sse", "--host", "0.0.0.0", "--port", "9090"]
            )
            assert result.exit_code == 0
            mock_run.assert_called_once_with(
                transport="sse", host="0.0.0.0", port=9090, allow_remote=False
            )


# ── OpenTofu / Terraform MCP Tools ───────────────────────────────────────────


class TestTfMcpTools:
    """Tests for OpenTofu / Terraform FastMCP tools."""

    def test_tf_plan_tool(self) -> None:
        from devops_cli.ai.mcp.server import tf_plan

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="Plan: 2 to add") as mock:
            res = tf_plan(directory="tf/aws", var_file="tf/environments/aws.tfvars.example")
            assert res == "Plan: 2 to add"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "tf" in args
            assert "plan" in args
            assert "tf/aws" in args

    def test_tf_apply_tool(self) -> None:
        from devops_cli.ai.mcp.server import tf_apply

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="Apply complete!") as mock:
            res = tf_apply(directory="tf/aws", auto_approve=True)
            assert res == "Apply complete!"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "apply" in args
            assert "--auto-approve" in args

    def test_tf_output_tool(self) -> None:
        from devops_cli.ai.mcp.server import tf_output

        with patch(
            "devops_cli.ai.mcp.server._run_mcp_cmd", return_value='{"cluster": "eks"}'
        ) as mock:
            res = tf_output(directory="tf/aws", json_format=True)
            assert res == '{"cluster": "eks"}'
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "output" in args
            assert "--json" in args

    def test_tofu_aliases(self) -> None:
        from devops_cli.ai.mcp.server import tofu_apply, tofu_output, tofu_plan

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="ok"):
            assert tofu_plan("tf/aws") == "ok"
            assert tofu_apply("tf/aws") == "ok"
            assert tofu_output("tf/aws") == "ok"


# ── SDLC & PR MCP Tools ───────────────────────────────────────────────────────


class TestSdlcMcpTools:
    """Tests for Remote CI, PR, Branches, Repos Exec, and Release FastMCP tools."""

    def test_ci_remote_status_tool(self) -> None:
        from devops_cli.ai.mcp.server import ci_remote_status

        with patch(
            "devops_cli.ai.mcp.server._run_mcp_cmd", return_value="all checks passed"
        ) as mock:
            res = ci_remote_status(branch="feat/test", pr_number=14)
            assert res == "all checks passed"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "ci" in args
            assert "remote" in args
            assert "status" in args
            assert "--pr" in args
            assert "14" in args

    def test_ci_remote_logs_tool(self) -> None:
        from devops_cli.ai.mcp.server import ci_remote_logs

        with patch(
            "devops_cli.ai.mcp.server._run_mcp_cmd", return_value="error log snippet"
        ) as mock:
            res = ci_remote_logs(run_id="12345", failed_only=True)
            assert res == "error log snippet"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "logs" in args
            assert "--run-id" in args
            assert "12345" in args
            assert "--failed" in args

    def test_pr_tools(self) -> None:
        from devops_cli.ai.mcp.server import pr_checks, pr_list, pr_view

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="pr result") as mock:
            assert pr_list(state="open", repo="owner/repo") == "pr result"
            assert pr_view(number=13, repo="owner/repo") == "pr result"
            assert pr_checks(number=13, repo="owner/repo") == "pr result"
            assert mock.call_count == 3

    def test_branches_tools(self) -> None:
        from devops_cli.ai.mcp.server import branches_create, branches_status

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="branch created") as mock:
            res = branches_create("new-feature", base="release/v0.1.12", branch_type="feat")
            assert res == "branch created"
            assert branches_status(".") == "branch created"
            assert mock.call_count == 2

    def test_repos_exec_tool(self) -> None:
        from devops_cli.ai.mcp.server import repos_exec

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="exec result") as mock:
            res = repos_exec("git status -s", base_dir="repos")
            assert res == "exec result"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "repos" in args
            assert "exec" in args
            assert "git status -s" in args

    def test_release_tools(self) -> None:
        from devops_cli.ai.mcp.server import release_notes, release_prepare

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="release result") as mock:
            assert release_prepare("0.1.12", create_pr=True) == "release result"
            assert release_notes("0.1.12", raw=True) == "release result"
            assert mock.call_count == 2
