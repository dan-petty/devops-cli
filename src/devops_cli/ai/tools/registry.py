"""Central tool registry combining native and MCP tools for PydanticAgent."""

from __future__ import annotations

from typing import Any

from devops_cli.ai.tools.mcp_bridge import get_mcp_agent_tools
from devops_cli.ai.tools.native import (
    argo_apps,
    git_diff,
    git_status,
    k8s_pods,
    list_files,
    read_file,
    run_security_scan,
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
        k8s_pods,
        argo_apps,
        run_security_scan,
    ]
    return native + get_mcp_agent_tools()
