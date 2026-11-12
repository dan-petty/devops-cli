"""Central tool registry combining native and MCP tools for agents."""

from __future__ import annotations

from typing import Any

from devops_cli.ai.personas import Persona
from devops_cli.ai.tools.builtin_tools import (
    argo_apps,
    check_threat_intel,
    git_diff,
    git_status,
    k8s_pods,
    k8s_tempo_status,
    k8s_validate_manifests,
    list_files,
    rag_search,
    read_file,
    scan_bandit,
    scan_gitleaks,
    scan_iac,
    scan_kubelinter,
    scan_osv,
    scan_pluto,
    scan_popeye,
    scan_semgrep,
    scan_trivy,
    scan_uv_audit,
    search_code,
    tf_lint,
)
from devops_cli.ai.tools.mcp_bridge import get_mcp_agent_tools


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
        k8s_tempo_status,
        k8s_validate_manifests,
        argo_apps,
        scan_trivy,
        scan_uv_audit,
        scan_kubelinter,
        scan_pluto,
        scan_bandit,
        scan_gitleaks,
        scan_semgrep,
        scan_iac,
        scan_popeye,
        scan_osv,
        check_threat_intel,
        tf_lint,
    ]
    return native + get_mcp_agent_tools()


def _build_persona_tool_map(mcp_module: Any) -> dict[Persona, list[Any]]:
    """Build the mapping of each persona to its own tool set."""
    return {
        Persona.DEVSECOPS: [
            read_file,
            list_files,
            git_diff,
            rag_search,
            scan_uv_audit,
            scan_trivy,
            scan_gitleaks,
            scan_semgrep,
            scan_iac,
            scan_kubelinter,
            scan_pluto,
            scan_bandit,
            scan_popeye,
            scan_osv,
            check_threat_intel,
            tf_lint,
            k8s_validate_manifests,
            mcp_module.ssh_audit,
            mcp_module.security_intel_package,
            mcp_module.security_intel_network,
            mcp_module.review_findings,
        ],
        Persona.ARCHITECT: [
            read_file,
            list_files,
            search_code,
            git_diff,
            rag_search,
            k8s_pods,
            k8s_tempo_status,
            k8s_validate_manifests,
            argo_apps,
            tf_lint,
            mcp_module.k8s_status,
            mcp_module.k8s_tempo_info,
            mcp_module.argo_cd_apps_status,
            mcp_module.prometheus_query,
            mcp_module.grafana_dashboards_list,
            mcp_module.tf_plan,
            mcp_module.tf_output,
            mcp_module.docker_images,
        ],
        Persona.QA: [
            read_file,
            list_files,
            search_code,
            git_diff,
            git_status,
            rag_search,
            scan_semgrep,
            k8s_validate_manifests,
            mcp_module.ci,
            mcp_module.review_stats,
            mcp_module.review_findings,
        ],
        Persona.AUDITOR: [
            read_file,
            list_files,
            git_diff,
            rag_search,
            scan_trivy,
            scan_iac,
            scan_kubelinter,
            scan_pluto,
            tf_lint,
            mcp_module.ssh_audit,
            mcp_module.ssh_status,
            mcp_module.config_show,
            mcp_module.review_export_feedback,
        ],
        Persona.PM: [
            read_file,
            list_files,
            git_status,
            git_diff,
            rag_search,
            mcp_module.repos_list,
            mcp_module.branches_list,
        ],
        # Challenger argues against a claim and names the evidence that settles it: it reads and
        # searches, and runs no scanner, cluster or MCP tool.
        Persona.CHALLENGER: [
            read_file,
            list_files,
            search_code,
            git_diff,
            git_status,
            rag_search,
        ],
    }


def get_persona_tools(persona: str | Persona) -> list[Any]:
    """Return the tool set of a persona. A name that is not a `Persona` raises `ValueError`."""
    from devops_cli.ai.mcp import server as mcp_module

    return _build_persona_tool_map(mcp_module)[Persona(persona)]
