"""Unit tests for FastMCP server integration (devops_cli.mcp and devops_cli.commands.mcp)."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import PropertyMock, patch

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
            "valkey_ping",
            "valkey_info",
            "valkey_stats",
            "valkey_get",
            "valkey_set",
            "valkey_flush",
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
        assert "instructions" in result.output

    def test_export_schemas_without_instructions(self, runner: CliRunner, tmp_path: Path) -> None:
        """devops mcp export-schemas without instructions writes empty file and adjusts message."""
        from devops_cli.ai.mcp.server import mcp

        out_dir = tmp_path / "mcp_schemas_no_inst"
        with patch.object(type(mcp), "instructions", new_callable=PropertyMock, return_value=""):
            result = runner.invoke(app, ["export-schemas", "--output-dir", str(out_dir)])
            assert result.exit_code == 0
            assert (out_dir / "instructions.md").exists()
            assert (out_dir / "instructions.md").read_text(encoding="utf-8") == ""
            assert "Exported" in result.output
            assert "instructions" not in result.output


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
        ai_harness_status,
        ai_subagent_offload,
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
        assert ai_harness_status() == "mock_output"
        assert ai_subagent_offload(repo="src", symbol="Foo") == "mock_output"
        with pytest.raises(ValidationError, match="Cannot specify both 'symbol' and 'pattern'"):
            ai_subagent_offload(repo="src", symbol="Foo", pattern="*.py")

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


def test_mcp_integer_bounds_validation() -> None:
    """Verify integer bounds validation rejecting non-positive or negative values."""
    from devops_cli.ai.mcp.server import (
        _validate_mcp_int_bound,
        ai_architecture,
        pr_checks,
        pr_list,
        review_pr,
        verify_finding,
    )

    # Helper directly
    _validate_mcp_int_bound("valid_field", 1, min_val=1)
    _validate_mcp_int_bound("valid_field", 0, min_val=0)
    with pytest.raises(ValidationError, match="Must be >= 1"):
        _validate_mcp_int_bound("bad_field", 0, min_val=1)
    with pytest.raises(ValidationError, match="Must be >= 1"):
        _validate_mcp_int_bound("bad_field", -1, min_val=1)

    # Tools bounds
    with pytest.raises(ValidationError, match="pr_number"):
        pr_checks(0)
    with pytest.raises(ValidationError, match="pr_number"):
        pr_checks(-5)

    with pytest.raises(ValidationError, match="number"):
        review_pr(0)
    with pytest.raises(ValidationError, match="number"):
        review_pr(-1)

    with pytest.raises(ValidationError, match="index"):
        verify_finding("session-1", -1, "verified")

    with pytest.raises(ValidationError, match="limit"):
        pr_list(limit=0)

    with pytest.raises(ValidationError, match="max_depth"):
        ai_architecture(target="src", max_depth=0)


class TestValkeyMcpTools:
    """Tests for Valkey FastMCP tools and system resource."""

    def test_valkey_ping(self) -> None:
        from devops_cli.ai.mcp.server import valkey_ping

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="PONG") as mock:
            res = valkey_ping()
            assert res == "PONG"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "valkey" in args
            assert "ping" in args

    def test_valkey_info(self) -> None:
        from devops_cli.ai.mcp.server import valkey_info

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="info table") as mock:
            res = valkey_info(section="memory")
            assert res == "info table"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "info" in args
            assert "--section" in args
            assert "memory" in args

    def test_valkey_stats(self) -> None:
        from devops_cli.ai.mcp.server import valkey_stats

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="stats table") as mock:
            res = valkey_stats()
            assert res == "stats table"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "stats" in args

    def test_valkey_get(self) -> None:
        from devops_cli.ai.mcp.server import valkey_get

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="my-value") as mock:
            res = valkey_get(key="user:100")
            assert res == "my-value"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "get" in args
            assert "user:100" in args

    def test_valkey_set(self) -> None:
        from devops_cli.ai.mcp.server import valkey_set

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="Success") as mock:
            res = valkey_set(key="token", value="xyz", ex=300)
            assert res == "Success"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "set" in args
            assert "token" in args
            assert "xyz" in args
            assert "--ex" in args
            assert "300" in args

    def test_valkey_flush(self) -> None:
        from devops_cli.ai.mcp.server import valkey_flush

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="Flushed") as mock:
            res = valkey_flush(all_databases=True)
            assert res == "Flushed"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "flush" in args
            assert "--all" in args

    def test_valkey_resource(self) -> None:
        from devops_cli.ai.mcp.server import get_valkey_resource

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="live status") as mock:
            res = get_valkey_resource()
            assert res == "live status"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "valkey" in args
            assert "stats" in args


class TestGitHubMcpTools:
    """Tests for GitHub Pages, Issues, Project, and Views FastMCP tools and system resources."""

    def test_gh_pages_tools(self) -> None:
        from devops_cli.ai.mcp.server import (
            get_gh_pages_resource,
            gh_pages_build,
            gh_pages_status,
            gh_pages_verify,
        )

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="pages status") as mock:
            res = gh_pages_status(repo="owner/repo")
            assert res == "pages status"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert ["gh", "pages", "status", "--repo", "owner/repo"] == args[3:]

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="build queued") as mock:
            res = gh_pages_build()
            assert res == "build queued"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert ["gh", "pages", "build"] == args[3:]

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="verified") as mock:
            res = gh_pages_verify()
            assert res == "verified"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert ["gh", "pages", "verify"] == args[3:]

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="res status") as mock:
            res = get_gh_pages_resource()
            assert res == "res status"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert ["gh", "pages", "status"] == args[3:]

    def test_gh_issues_tools(self) -> None:
        from devops_cli.ai.mcp.server import (
            get_gh_issues_resource,
            gh_issue_create,
            gh_issue_list,
            gh_issue_status,
            gh_issue_triage,
        )

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="issue list") as mock:
            res = gh_issue_list(
                repo="owner/repo", state="open", milestone="v0.2.14", label="type/feat", limit=10
            )
            assert res == "issue list"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "issues" in args
            assert "--milestone" in args
            assert "--label" in args

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="issue created") as mock:
            res = gh_issue_create(
                title="feat(gh): new feature",
                body="Issue body description",
                milestone="v0.2.14",
                labels="type/feat, priority/p1-high",
                repo="owner/repo",
            )
            assert res == "issue created"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "create" in args
            assert "--title" in args
            assert "--milestone" in args
            assert "--label" in args

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="triage report") as mock:
            res = gh_issue_triage(repo="owner/repo")
            assert res == "triage report"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "triage" in args

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="status summary") as mock:
            res = gh_issue_status(repo="owner/repo")
            assert res == "status summary"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert "status" in args

        with patch(
            "devops_cli.ai.mcp.server._run_mcp_cmd", return_value="res issue status"
        ) as mock:
            res = get_gh_issues_resource()
            assert res == "res issue status"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert ["gh", "issues", "status"] == args[3:]

    def test_gh_project_and_views_tools(self) -> None:
        from devops_cli.ai.mcp.server import (
            get_gh_project_resource,
            get_gh_views_resource,
            gh_project_audit,
            gh_project_list,
            gh_views_audit,
        )

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="project list") as mock:
            res = gh_project_list(owner="my-org")
            assert res == "project list"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert ["gh", "project", "list", "--owner", "my-org"] == args[3:]

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="project audit") as mock:
            res = gh_project_audit(repo="owner/repo")
            assert res == "project audit"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert ["gh", "project", "audit", "--repo", "owner/repo"] == args[3:]

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="views audit") as mock:
            res = gh_views_audit(repo="owner/repo")
            assert res == "views audit"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert ["gh", "views", "audit", "--repo", "owner/repo"] == args[3:]

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="proj status") as mock:
            res = get_gh_project_resource()
            assert res == "proj status"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert ["gh", "project", "status"] == args[3:]

        with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="views status") as mock:
            res = get_gh_views_resource()
            assert res == "views status"
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert ["gh", "views", "audit"] == args[3:]
