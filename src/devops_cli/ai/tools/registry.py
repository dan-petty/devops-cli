"""Central tool registry combining native and MCP tools for PydanticAgent."""

from __future__ import annotations

from typing import Any

from devops_cli.ai.personas import Persona
from devops_cli.ai.tools.mcp_bridge import get_mcp_agent_tools
from devops_cli.ai.tools.native import (
    argo_apps,
    check_threat_intel,
    git_diff,
    git_status,
    k8s_jaeger_status,
    k8s_pods,
    list_files,
    rag_search,
    read_file,
    run_security_scan,
    scan_bandit,
    scan_kubelinter,
    scan_osv,
    scan_pluto,
    scan_popeye,
    scan_trivy,
    search_code,
)


def get_default_tools() -> list[Any]:
    """Return unified standard set of native and MCP agent tools."""
    native = [
        list_files,
        read_file,
        git_status,
        git_diff,
        search_code,
        rag_search,
        k8s_pods,
        k8s_jaeger_status,
        argo_apps,
        scan_trivy,
        scan_kubelinter,
        scan_pluto,
        scan_bandit,
        scan_popeye,
        scan_osv,
        check_threat_intel,
        run_security_scan,
    ]
    return native + get_mcp_agent_tools()


def get_persona_tools(persona: str | Persona) -> list[Any]:
    """Return curated tool selection tailored to a specific reviewer persona."""
    from devops_cli.ai.mcp import server as mcp_module

    p_str = persona.value if isinstance(persona, Persona) else str(persona).lower()

    if p_str == "devsecops":
        return [
            read_file,
            list_files,
            git_diff,
            rag_search,
            scan_trivy,
            scan_kubelinter,
            scan_pluto,
            scan_bandit,
            scan_popeye,
            scan_osv,
            check_threat_intel,
            mcp_module.ssh_audit,
            mcp_module.security_intel_package,
            mcp_module.security_intel_network,
            mcp_module.review_findings,
            mcp_module.verify_finding,
        ]
    elif p_str == "architect":
        return [
            read_file,
            list_files,
            search_code,
            git_diff,
            rag_search,
            k8s_pods,
            k8s_jaeger_status,
            argo_apps,
            mcp_module.k8s_status,
            mcp_module.k8s_jaeger_info,
            mcp_module.argo_status,
            mcp_module.prometheus_query,
            mcp_module.grafana_dashboards,
            mcp_module.tf_plan,
            mcp_module.tf_output,
            mcp_module.tofu_plan,
            mcp_module.tofu_output,
            mcp_module.docker_stats,
        ]
    elif p_str == "qa":
        return [
            read_file,
            list_files,
            search_code,
            git_diff,
            git_status,
            rag_search,
            mcp_module.ci_run,
            mcp_module.review_stats,
            mcp_module.review_findings,
            mcp_module.verify_finding,
        ]
    elif p_str == "auditor":
        return [
            read_file,
            list_files,
            git_diff,
            rag_search,
            scan_trivy,
            scan_kubelinter,
            scan_pluto,
            mcp_module.ssh_audit,
            mcp_module.ssh_status,
            mcp_module.config_show,
            mcp_module.release_status,
            mcp_module.review_export_feedback,
        ]
    elif p_str == "pm":
        return [
            read_file,
            list_files,
            git_status,
            git_diff,
            rag_search,
            mcp_module.repos_list,
            mcp_module.repos_status,
            mcp_module.release_status,
            mcp_module.workspace_list,
        ]

    return get_default_tools()
