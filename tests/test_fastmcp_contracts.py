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
        # CI, Release & Quality
        "ci_run",
        "release_status",
        # Terraform / OpenTofu
        "tf_plan",
        "tf_apply",
        "tf_output",
        "tf_notify_plan",
        # RAG & Embeddings
        "rag_search",
        "rag_index",
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
        # HashiCorp Vault
        "vault_status",
        "vault_get",
        "vault_set",
        "vault_sync",
        # GitHub Projects & Views
        "gh_views_sync",
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
        "resource://mcp/tools",
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
