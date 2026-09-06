"""Unit tests for FastMCP server integration (devops_cli.mcp and devops_cli.commands.mcp)."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.mcp import list_mcp_tools, mcp, run_mcp_server
from devops_cli.ai.mcp.server import (
    _run_mcp_cmd,
    _validate_mcp_arg,
    review_branch,
    review_findings,
    review_path,
    review_pr,
    review_stats,
    verify_finding,
)
from devops_cli.commands.mcp import app
from devops_cli.exceptions import ValidationError

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
            "review_export_feedback",
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
            "k8s_jaeger_info",
            "argo_list",
            "argo_status",
            "grafana_dashboards",
            "prometheus_query",
            "docker_stats",
            "workspace_list",
            "config_show",
            "config_output",
            "ci_run",
            "release_status",
            "tf_plan",
            "tf_apply",
            "tf_output",
            "rag_search",
            "rag_index",
            "security_intel_package",
            "security_intel_network",
            "tls_generate_ca",
            "tls_generate_cert",
            "tls_inspect_cert",
            "k8s_create_tls_secret",
            "k8s_enable_tls",
            "telemetry_status",
            "telemetry_test_span",
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

    def test_export_schemas_command(self, runner: CliRunner, tmp_path: Path) -> None:
        """devops mcp export-schemas must write JSON files and instructions."""
        out_dir = tmp_path / "mcp_schemas"
        result = runner.invoke(app, ["export-schemas", "--output-dir", str(out_dir)])
        assert result.exit_code == 0
        assert (out_dir / "instructions.md").exists()
        assert (out_dir / "scan_trivy.json").exists()
        assert (out_dir / "vault_set.json").exists()
        assert "Exported" in result.output


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


class TestAllMcpToolsDirectly:
    """Direct execution tests for all MCP server tool endpoints."""

    def test_mcp_tool_delegations(self) -> None:
        from devops_cli.ai.mcp.server import (
            argo_list,
            argo_status,
            ci_run,
            config_output,
            config_show,
            docker_stats,
            grafana_dashboards,
            k8s_bootstrap,
            k8s_create_tls_secret,
            k8s_deploy_stack,
            k8s_enable_tls,
            k8s_jaeger_info,
            k8s_pods,
            k8s_status,
            k8s_teardown_stack,
            prometheus_query,
            rag_index,
            rag_search,
            release_status,
            repos_list,
            repos_status,
            repos_sync,
            scan_uv_audit,
            security_intel_network,
            security_intel_package,
            ssh_audit,
            ssh_status,
            telemetry_status,
            telemetry_test_span,
            tf_apply,
            tf_output,
            tf_plan,
            tls_generate_ca,
            tls_generate_cert,
            tls_inspect_cert,
            workspace_list,
        )

        with (
            patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="mock_output"),
            patch("devops_cli.ai.tools.builtin_tools.scan_osv", return_value="mock_output"),
            patch(
                "devops_cli.ai.tools.builtin_tools.check_threat_intel", return_value="mock_output"
            ),
            patch("devops_cli.ai.tools.builtin_tools.scan_uv_audit", return_value="mock_output"),
        ):
            assert repos_list() == "mock_output"
            assert repos_status() == "mock_output"
            assert repos_sync(all_repos=True) == "mock_output"
            assert ssh_status() == "mock_output"
            assert ssh_audit() == "mock_output"
            assert k8s_pods(namespace="default") == "mock_output"
            assert k8s_status() == "mock_output"
            assert k8s_bootstrap(auto_start=True) == "mock_output"
            assert k8s_deploy_stack(stack="monitoring") == "mock_output"
            assert k8s_teardown_stack(stack="monitoring") == "mock_output"
            assert "Jaeger Tracing Endpoints" in k8s_jaeger_info()
            assert argo_list() == "mock_output"
            assert argo_status(app="argocd") == "mock_output"
            assert grafana_dashboards() == "mock_output"
            assert prometheus_query("up") == "mock_output"
            assert docker_stats() == "mock_output"
            assert workspace_list() == "mock_output"
            assert config_show() == "mock_output"
            assert config_output() == "mock_output"
            assert ci_run(check="all") == "mock_output"
            assert release_status() == "mock_output"
            assert tf_plan("tf/aws") == "mock_output"
            assert tf_apply("tf/aws") == "mock_output"
            assert tf_output("tf/aws") == "mock_output"
            assert rag_search("test query") == "mock_output"
            assert rag_index(force=True) == "mock_output"
            assert security_intel_package("requests") == "mock_output"
            assert security_intel_network("api.github.com") == "mock_output"
            assert scan_uv_audit(".") == "mock_output"
            assert tls_generate_ca(output_dir="/tmp/ca") == "mock_output"
            assert (
                tls_generate_cert(
                    common_name="example.com", sans="example.com", output_dir="/tmp/ca"
                )
                == "mock_output"
            )
            assert tls_inspect_cert("/tmp/cert.pem") == "mock_output"
            assert k8s_create_tls_secret("my-sec", "/tmp/cert.pem", "/tmp/key.pem") == "mock_output"
            assert k8s_enable_tls(stack="all", secret_name="web-tls") == "mock_output"
            assert telemetry_status() == "mock_output"
            assert telemetry_test_span(name="test") == "mock_output"


def test_expanded_mcp_tools_and_prompts_execution() -> None:
    """Verify execution of newly added security, k8s, vault, benchmark, and git governance MCP tools."""
    from devops_cli.ai.mcp.server import (
        ai_architecture,
        benchmark_embeddings,
        branches_list,
        code_review_prompt,
        k8s_audit,
        k8s_chaos,
        k8s_diff_helm,
        k8s_lint,
        k8s_validate,
        pr_checks,
        pr_list,
        scan_aibom,
        scan_checkov,
        scan_complexity,
        scan_gitleaks,
        scan_sbom,
        scan_semgrep,
        scan_trivy,
        security_audit_prompt,
        vault_set,
        vault_sync,
    )

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="mock_output"):
        # Security scanners
        assert scan_trivy(".") == "mock_output"
        assert scan_gitleaks(".") == "mock_output"
        assert scan_semgrep(".") == "mock_output"
        assert scan_checkov(".") == "mock_output"
        assert scan_complexity("src") == "mock_output"
        assert scan_aibom(".") == "mock_output"
        assert scan_sbom(".") == "mock_output"

        # Kubernetes operations
        assert k8s_chaos("validate", "pod-failure") == "mock_output"
        assert k8s_audit("default") == "mock_output"
        assert k8s_lint(".") == "mock_output"
        assert k8s_validate(".") == "mock_output"
        assert k8s_diff_helm("argocd", "argo/argo-cd") == "mock_output"

        # HashiCorp Vault
        assert vault_set("secret/data/app", ["FOO=bar"]) == "mock_output"
        assert vault_sync("secret/data/app") == "mock_output"

        # AI & Benchmark
        assert benchmark_embeddings(provider="ollama", model="bge-m3") == "mock_output"
        assert ai_architecture(target="src") == "mock_output"

        # Git & PR governance
        assert branches_list() == "mock_output"
        assert pr_list(limit=5) == "mock_output"
        assert pr_checks(32) == "mock_output"

    # Prompts return formatted strings
    review_p = code_review_prompt(persona="architect", target="src/devops_cli")
    assert "architect" in review_p
    assert "src/devops_cli" in review_p

    sec_p = security_audit_prompt(target="src")
    assert "security audit" in sec_p.lower()
    assert "src" in sec_p


def test_mcp_helpers_and_error_branches() -> None:
    """Verify _run_mcp_cmd timeout, error exit code, _validate_mcp_arg, and review tool calls."""
    # 1. _validate_mcp_arg
    with pytest.raises(ValidationError, match="must not start with a hyphen"):
        _validate_mcp_arg("target", "--malicious-flag")

    _validate_mcp_arg("target", "src/main.py")

    # 2. _run_mcp_cmd timeout
    with patch(
        "devops_cli.ai.mcp.server.run_subprocess",
        side_effect=subprocess.TimeoutExpired(cmd=["uv"], timeout=5.0),
    ):
        res_to = _run_mcp_cmd(["uv", "run", "devops"], timeout=5.0)
        assert "timed out after 5.0 seconds" in res_to

    # 3. _run_mcp_cmd OSError
    with patch("devops_cli.ai.mcp.server.run_subprocess", side_effect=OSError("binary not found")):
        res_os = _run_mcp_cmd(["uv"])
        assert "Execution failed" in res_os

    # 4. _run_mcp_cmd non-zero exit code
    mock_fail = subprocess.CompletedProcess(
        args=["uv"], returncode=2, stdout="bad input", stderr="error details"
    )
    with patch("devops_cli.ai.mcp.server.run_subprocess", return_value=mock_fail):
        res_fail = _run_mcp_cmd(["uv"])
        assert "Command exited with status 2" in res_fail
        assert "error details" in res_fail

    # 5. Review tools
    with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="Review Output"):
        assert review_path("src", "*.py", "architect") == "Review Output"
        assert review_branch("feat/new", "main", "devsecops") == "Review Output"
        assert review_pr(42, post=True, persona="qa") == "Review Output"
        assert review_findings("20260826-session", status="verified") == "Review Output"
        assert verify_finding("20260826-session", 1, "VALIDATED", "Fixed in PR") == "Review Output"
        assert review_stats() == "Review Output"
