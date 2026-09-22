"""Regression suite verifying schema contracts, parameters, and docstrings across all FastMCP tools."""

from __future__ import annotations

from devops_cli.ai.mcp.server import list_mcp_tools


def test_fastmcp_tools_registration() -> None:
    """Verify that all expected FastMCP tools are registered on the server."""
    tools = list_mcp_tools()
    assert len(tools) >= 70, f"Expected at least 70 registered FastMCP tools, got {len(tools)}"

    tool_names = {t.name for t in tools}
    expected_core_tools = {
        # Code Review
        "review_path",
        "review_branch",
        "review_pr",
        "review_findings",
        "verify_finding",
        "review_stats",
        "review_export_feedback",
        # Repositories & Workspace
        "repos_list",
        "repos_status",
        "repos_sync",
        "workspace_list",
        "branches_list",
        "pr_list",
        "pr_checks",
        # SSH & Keyring
        "ssh_status",
        "ssh_audit",
        "config_audit_keys",
        "config_show",
        "config_output",
        # Kubernetes & GitOps
        "k8s_pods",
        "k8s_status",
        "k8s_bootstrap",
        "k8s_deploy_stack",
        "k8s_teardown_stack",
        "k8s_jaeger_info",
        "k8s_create_tls_secret",
        "k8s_enable_tls",
        "k8s_chaos",
        "k8s_audit",
        "k8s_lint",
        "k8s_validate",
        "k8s_diff_helm",
        "argo_list",
        "argo_status",
        # Monitoring & Tracing
        "grafana_dashboards",
        "prometheus_query",
        "telemetry_status",
        "telemetry_test_span",
        "telemetry_profile",
        "telemetry_logfire_status",
        # Docker & Isolation
        "docker_stats",
        "docker_sandbox",
        "docker_sign",
        "docker_verify",
        # CI, Release & Quality
        "ci_run",
        "release_status",
        "docs_compact",
        # Terraform / OpenTofu
        "tf_plan",
        "tf_apply",
        "tf_output",
        "tf_notify_plan",
        # RAG & Embeddings
        "rag_search",
        "rag_index",
        "rag_drift",
        "benchmark_embeddings",
        "benchmark_suite",
        # Security Intel & Scanners
        "security_intel_package",
        "security_intel_network",
        "scan_uv_audit",
        "scan_fix",
        "scan_trivy",
        "scan_gitleaks",
        "scan_semgrep",
        "scan_checkov",
        "scan_complexity",
        "scan_aibom",
        "scan_sbom",
        # TLS & Certificates
        "tls_generate_ca",
        "tls_generate_cert",
        "tls_inspect_cert",
        # AI Architecture & AST
        "ai_repomap",
        "ai_diagram",
        "ai_test_gen",
        "ai_architecture",
        "ai_harness_status",
        "ai_subagent_offload",
        "ai_chaos_model",
        "ai_quiesce",
        "ai_failover",
        "ai_resume",
        "ai_constellation_status",
        "ai_ingest_library",
        "ai_query_library",
        "ai_inspect_symbol",
        "ai_ast_parse",
        "ai_ast_graph",
        "ai_pack_context",
        "ai_read",
        "ai_spend_report",
        # HashiCorp Vault
        "vault_status",
        "vault_get",
        "vault_set",
        "vault_sync",
        # GitHub Projects, Pages, Issues & Views
        "gh_views_sync",
        "gh_pages_status",
        "gh_pages_build",
        "gh_pages_verify",
        "gh_issue_list",
        "gh_issue_create",
        "gh_issue_triage",
        "gh_issue_status",
        "gh_issue_edit",
        "gh_project_list",
        "gh_project_audit",
        "gh_views_audit",
        "gh_rate_limit",
        "gh_runs_list",
        "gh_run_view",
        "gh_sync_roadmap",
        "pr_ready",
        "pr_diff",
        "pr_close",
        "pr_edit",
        "pr_check_readiness",
    }

    for expected in expected_core_tools:
        assert expected in tool_names, (
            f"Expected tool '{expected}' to be registered on FastMCP server"
        )


def test_fastmcp_prompts_and_resources_registration() -> None:
    """Verify FastMCP prompt templates and dynamic system resources are registered."""
    import asyncio

    from devops_cli.ai.mcp.server import mcp

    # Check prompts
    prompts = asyncio.run(mcp.list_prompts())
    prompt_names = {p.name for p in prompts}
    expected_prompts = {
        "code_review_prompt",
        "security_audit_prompt",
        "k8s_diagnostics_prompt",
        "architecture_analysis_prompt",
    }
    assert expected_prompts.issubset(prompt_names), (
        f"Missing FastMCP prompts: {expected_prompts - prompt_names}"
    )

    # Check resources
    resources = asyncio.run(mcp.list_resources())
    resource_uris = {str(r.uri) for r in resources}
    expected_resources = {
        "resource://workspace/status",
        "resource://config/active",
        "resource://telemetry/status",
        "resource://telemetry/logfire",
        "resource://release/status",
        "resource://vault/status",
        "resource://ai/constellation",
        "resource://ai/spend",
        "resource://mcp/tools",
        "resource://gh/pages/status",
        "resource://gh/issues/status",
        "resource://gh/project/status",
        "resource://gh/views/status",
        "resource://libraries/indexed",
    }
    assert expected_resources.issubset(resource_uris), (
        f"Missing FastMCP resources: {expected_resources - resource_uris}"
    )


def test_fastmcp_tool_docstrings_and_parameters() -> None:
    """Verify that every FastMCP tool has a non-empty docstring and typed parameter signatures."""
    tools = list_mcp_tools()
    for tool_info in tools:
        assert tool_info.description, (
            f"FastMCP tool '{tool_info.name}' is missing a docstring description"
        )
        assert len(tool_info.description.strip()) > 10, (
            f"FastMCP tool '{tool_info.name}' has too short description"
        )


def test_fastmcp_arg_validation() -> None:
    """Verify that _validate_mcp_arg catches flag injection attempts."""
    import pytest

    from devops_cli.ai.mcp.server import _validate_mcp_arg
    from devops_cli.exceptions import ValidationError

    # Clean arguments pass
    _validate_mcp_arg("branch", "main")
    _validate_mcp_arg("path", "src/devops_cli")

    # Hyphen flags raise ValidationError
    with pytest.raises(ValidationError, match="must not start with a hyphen"):
        _validate_mcp_arg("branch", "--all")


def test_fastmcp_prompts_rendering() -> None:
    """Verify that FastMCP prompt templates correctly interpolate parameters from task markdown files."""
    from devops_cli.ai.mcp.server import (
        architecture_analysis_prompt,
        code_review_prompt,
        k8s_diagnostics_prompt,
        security_audit_prompt,
    )

    cr = code_review_prompt(persona="architect", target="src/core")
    assert "architect" in cr
    assert "src/core" in cr
    assert "OWASP" in cr

    sa = security_audit_prompt(target="src/security")
    assert "src/security" in sa
    assert "CVEs" in sa

    k8s = k8s_diagnostics_prompt(namespace="kube-system")
    assert "kube-system" in k8s
    assert "pod status" in k8s

    arch = architecture_analysis_prompt(target="src/devops_cli")
    assert "src/devops_cli" in arch
    assert "cyclic imports" in arch


def test_fastmcp_messages_and_errors_localization() -> None:
    """Verify localized error and message catalog integration for FastMCP."""
    from unittest.mock import AsyncMock, patch

    import pytest

    from devops_cli.ai.mcp.server import _validate_mcp_arg, list_mcp_tools, run_mcp_server
    from devops_cli.exceptions import SecurityError, ValidationError
    from devops_cli.lang import ERRORS, MESSAGES

    # 1. Fallback tool description uses localized catalog string
    dummy_tool = AsyncMock()
    dummy_tool.name = "sample_tool"
    dummy_tool.description = None
    with patch("devops_cli.ai.mcp.server.mcp.list_tools", return_value=[dummy_tool]):
        tools = list_mcp_tools()
        assert tools[0].description == MESSAGES.mcp.no_description_provided

    # 2. Argument validation error uses localized catalog template
    with pytest.raises(ValidationError) as exc_info:
        _validate_mcp_arg("bad_field", "--flag")
    assert ERRORS.mcp.hyphen_prefixed_argument.format(name="bad_field") in str(exc_info.value)

    # 3. Security error for non-loopback host uses localized catalog template
    with pytest.raises(SecurityError) as sec_info:
        run_mcp_server(transport="sse", host="192.168.1.50")
    assert ERRORS.mcp.security_sse_non_loopback.format(host="192.168.1.50") in str(sec_info.value)


def test_fastmcp_library_tools_and_resource() -> None:
    """Verify library intelligence FastMCP tools and system resource execution."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import (
        ai_ingest_library,
        ai_inspect_symbol,
        ai_query_library,
        get_indexed_libraries_resource,
    )
    from devops_cli.config.defaults import (
        DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
    )

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = '{"status": "ok"}'

        res = ai_ingest_library(package="typer", max_depth=2)
        assert res == '{"status": "ok"}'
        mock_cmd.assert_called_with(
            [
                "uv",
                "run",
                "devops",
                "ai",
                "ingest",
                "library",
                "typer",
                "--max-depth",
                "2",
                "--format",
                "json",
            ],
            timeout=DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
        )

        res = ai_query_library(query="command", package="typer", exact=True, top_k=3)
        assert res == '{"status": "ok"}'
        mock_cmd.assert_called_with(
            [
                "uv",
                "run",
                "devops",
                "ai",
                "ingest",
                "query-library",
                "command",
                "--top-k",
                "3",
                "--format",
                "json",
                "--package",
                "typer",
                "--exact",
            ],
            timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )

        res = ai_inspect_symbol(symbol="Typer", package="typer")
        assert res == '{"status": "ok"}'
        mock_cmd.assert_called_with(
            [
                "uv",
                "run",
                "devops",
                "ai",
                "ingest",
                "query-library",
                "Typer",
                "--exact",
                "--format",
                "json",
                "--package",
                "typer",
            ],
            timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )

    # Test resource returns valid JSON
    resource_data = get_indexed_libraries_resource()
    assert isinstance(resource_data, str)
    assert resource_data.startswith("[")


def test_fastmcp_ast_tools() -> None:
    """Verify ai_ast_parse and ai_ast_graph FastMCP execution contracts."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import ai_ast_graph, ai_ast_parse
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = '{"status": "ok"}'

        res = ai_ast_parse(file_path="src/main.py", query="(function_definition) @fn")
        assert res == '{"status": "ok"}'
        mock_cmd.assert_called_with(
            [
                "uv",
                "run",
                "devops",
                "ai",
                "ast",
                "parse",
                "src/main.py",
                "--json",
                "--query",
                "(function_definition) @fn",
            ],
            timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )

        res = ai_ast_graph(target_dir="src", max_files=20)
        assert res == '{"status": "ok"}'
        mock_cmd.assert_called_with(
            ["uv", "run", "devops", "ai", "ast", "graph", "--dir", "src", "--max-files", "20"],
            timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )


def test_fastmcp_context_packing_tool() -> None:
    """Verify ai_pack_context FastMCP execution contract."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import ai_pack_context
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = '{"content": "..."}'

        res = ai_pack_context(
            file_path="src/main.py",
            referenced="main,app",
            max_tokens=500,
            strip_private=True,
            skeletonize=False,
        )
        assert res == '{"content": "..."}'
        mock_cmd.assert_called_with(
            [
                "uv",
                "run",
                "devops",
                "ai",
                "pack-context",
                "src/main.py",
                "--max-tokens",
                "500",
                "--json",
                "--referenced",
                "main,app",
                "--no-skeletonize",
            ],
            timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )


def test_fastmcp_ai_read_tool() -> None:
    """Verify ai_read FastMCP execution contract."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import ai_read
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = "# Outline content"

        res = ai_read(
            target_path="src/main.py",
            inspect=True,
            level=0,
            lines="10:50",
            symbol="App",
            format="markdown",
        )
        assert (res, mock_cmd.call_args[0][0]) == (
            "# Outline content",
            [
                "uv",
                "run",
                "devops",
                "ai",
                "read",
                "src/main.py",
                "--inspect",
                "--level",
                "0",
                "--lines",
                "10:50",
                "--symbol",
                "App",
                "--format",
                "markdown",
            ],
        )
        assert mock_cmd.call_args[1]["timeout"] == DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS


def test_fastmcp_rag_drift_tool() -> None:
    """Verify rag_drift FastMCP execution contract."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import rag_drift
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = '{"drift_score": 0.0}'

        res = rag_drift(path="src", auto_sync=True)
        assert res == '{"drift_score": 0.0}'
        mock_cmd.assert_called_with(
            [
                "uv",
                "run",
                "devops",
                "ai",
                "rag",
                "drift",
                "src",
                "--json",
                "--auto-sync",
            ],
            timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )


def test_fastmcp_pr_check_readiness_tool() -> None:
    """Verify pr_check_readiness FastMCP execution contract."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import pr_check_readiness
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = "PR #187 satisfies merge readiness"

        res = pr_check_readiness(
            pr_number=187,
            require_ready=True,
            allow_blocked_state=True,
            repo="owner/repo",
        )
        assert "satisfies merge readiness" in res
        mock_cmd.assert_called_with(
            [
                "uv",
                "run",
                "devops",
                "pr",
                "check-readiness",
                "187",
                "--require-ready",
                "--allow-blocked-state",
                "--repo",
                "owner/repo",
            ],
            timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )


def test_fastmcp_pr_ready_tool() -> None:
    """Verify pr_ready FastMCP execution contract."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import pr_ready
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = "PR #212 is ready for review"

        res = pr_ready(
            pr_number=212,
            monitor=False,
            force=True,
            repo="owner/repo",
        )
        assert "is ready for review" in res
        mock_cmd.assert_called_with(
            [
                "uv",
                "run",
                "devops",
                "pr",
                "ready",
                "212",
                "--force",
                "--repo",
                "owner/repo",
            ],
            timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )


def test_fastmcp_docker_sign_tool() -> None:
    """Verify docker_sign FastMCP execution contract."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import docker_sign
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = "Image signed successfully"

        res = docker_sign(
            image="example.com/app:1.0.0",
            key="/path/to/key.key",
            keyless=False,
            oidc_token="token123",
            annotations=["env=prod"],
            upload=False,
            dry_run=True,
        )
        assert "Image signed successfully" in res
        mock_cmd.assert_called_with(
            [
                "uv",
                "run",
                "devops",
                "docker",
                "sign",
                "example.com/app:1.0.0",
                "--key",
                "/path/to/key.key",
                "--keyed",
                "--annotation",
                "env=prod",
                "--no-upload",
                "--dry-run",
            ],
            timeout=DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
            env={"COSIGN_IDENTITY_TOKEN": "token123"},
        )


def test_fastmcp_docker_verify_tool() -> None:
    """Verify docker_verify FastMCP execution contract."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import docker_verify
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = "Image verified successfully"

        res = docker_verify(
            image="example.com/app:1.0.0",
            key="/path/to/key.pub",
            certificate_identity="https://example.com/build.yml",
            certificate_oidc_issuer="https://example.com/oidc",
            attestation=True,
            predicate_type="slsaprovenance",
            insecure_ignore_tlog=True,
            dry_run=True,
        )
        assert "Image verified successfully" in res
        mock_cmd.assert_called_with(
            [
                "uv",
                "run",
                "devops",
                "docker",
                "verify",
                "example.com/app:1.0.0",
                "--key",
                "/path/to/key.pub",
                "--certificate-identity",
                "https://example.com/build.yml",
                "--certificate-oidc-issuer",
                "https://example.com/oidc",
                "--attestation",
                "--type",
                "slsaprovenance",
                "--insecure-ignore-tlog",
                "--dry-run",
            ],
            timeout=DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
        )


# =============================================================================
# Credential hygiene in dispatcher logs
# =============================================================================


def test_no_dispatch_argument_reaches_a_log_record(caplog) -> None:
    """The dispatcher runs arbitrary `devops` command lines, and some carry a credential.

    `logger.debug("In-process dispatch %s ...", sub_args)` wrote the argument list
    verbatim, so `gh secrets set NAME <token>` put that token in the log in clear text.
    CodeQL reported it as three high-severity `py/clear-text-logging-sensitive-data`
    alerts and they blocked the v0.2.22 release. Masking the values first made it worse --
    the sanitizer is not a barrier CodeQL recognises, so three alerts became six -- so
    nothing derived from the command reaches a record at all.
    """
    import logging

    from devops_cli.ai.mcp.dispatcher import InProcessDispatcher

    secret = "ghp_A1b2C3d4E5f6G7h8I9j0"
    with caplog.at_level(logging.DEBUG):
        InProcessDispatcher().dispatch(["devops", "workspace", "-h", "--token", secret])
    assert secret not in caplog.text


def test_the_dispatch_record_still_reports_its_duration(caplog) -> None:
    """A record stripped of everything is not hygiene; the timing is why it exists."""
    import logging

    from devops_cli.ai.mcp.dispatcher import InProcessDispatcher

    with caplog.at_level(logging.DEBUG):
        InProcessDispatcher().dispatch(["devops", "workspace", "-h"])
    assert "In-process dispatch finished in" in caplog.text


def test_a_handler_failure_reports_its_exception_type(caplog) -> None:
    """Which kind of failure occurred is the diagnostic that survives dropping the data."""
    import logging

    from devops_cli.ai.mcp.dispatcher import InProcessDispatcher

    dispatcher = InProcessDispatcher()

    def explode(*_: str) -> tuple[int, str]:
        raise RuntimeError("holding ghp_A1b2C3d4E5f6G7h8I9j0")

    dispatcher.register_handler(("boom",), explode)
    with caplog.at_level(logging.DEBUG):
        dispatcher._check_functional_handlers(["boom"])
    assert "RuntimeError" in caplog.text and "ghp_A1b2C3d4E5f6G7h8I9j0" not in caplog.text
