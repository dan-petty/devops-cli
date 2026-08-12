"""MCP tool bridge exposing FastMCP tools to PydanticAgent."""

from __future__ import annotations

from typing import Any


def get_mcp_agent_tools() -> list[Any]:
    """Expose FastMCP server tools directly to PydanticAgents."""
    from devops_cli.ai.mcp import server as mcp_module

    return [
        mcp_module.repos_list,
        mcp_module.repos_status,
        mcp_module.repos_sync,
        mcp_module.ssh_status,
        mcp_module.ssh_audit,
        mcp_module.k8s_status,
        mcp_module.argo_list,
        mcp_module.argo_status,
        mcp_module.grafana_dashboards,
        mcp_module.prometheus_query,
        mcp_module.docker_stats,
        mcp_module.workspace_list,
        mcp_module.config_show,
        mcp_module.ci_run,
    ]
