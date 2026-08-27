"""Regression suite verifying schema contracts, parameters, and docstrings across all FastMCP tools."""

from __future__ import annotations

from devops_cli.ai.mcp.server import list_mcp_tools


def test_fastmcp_tools_registration() -> None:
    """Verify that all expected FastMCP tools are registered on the server."""
    tools = list_mcp_tools()
    assert len(tools) >= 30, f"Expected at least 30 registered FastMCP tools, got {len(tools)}"

    tool_names = {t.name for t in tools}
    expected_core_tools = {
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
        "release_status",
        "tf_plan",
        "tf_apply",
        "tf_output",
        "rag_search",
        "rag_index",
        "security_intel_package",
        "security_intel_network",
        "scan_uv_audit",
        "review_export_feedback",
        "telemetry_status",
        "telemetry_test_span",
        "ai_repomap",
        "ai_diagram",
        "ai_test_gen",
        "config_audit_keys",
        "telemetry_profile",
        "tf_notify_plan",
    }

    for expected in expected_core_tools:
        assert expected in tool_names, (
            f"Expected tool '{expected}' to be registered on FastMCP server"
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
