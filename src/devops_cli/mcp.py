"""FastMCP server integration for devops-cli."""

from __future__ import annotations

import asyncio
import subprocess
from typing import Literal

from fastmcp import FastMCP

mcp = FastMCP(
    name="devops-cli",
    instructions=(
        "DevOps CLI Model Context Protocol Server. Provides tools for AI code reviews, "
        "repository automation, SSH key management, Kubernetes, ArgoCD, Grafana, "
        "Prometheus monitoring, Docker cleanup, and quality gates."
    ),
)


@mcp.tool()
def review_path(target: str = ".", pattern: str = "*", persona: str = "devsecops") -> str:
    """Run an AI code review on local files matching pattern using specified persona."""
    res = subprocess.run(
        [
            "uv",
            "run",
            "devops",
            "review",
            "path",
            target,
            "--pattern",
            pattern,
            "--persona",
            persona,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    return res.stdout or res.stderr


@mcp.tool()
def review_branch(branch: str = "", base: str = "main", persona: str = "devsecops") -> str:
    """Run an AI code review on git branch diff against base branch."""
    cmd = ["uv", "run", "devops", "review", "branch"]
    if branch:
        cmd.append(branch)
    cmd.extend(["--base", base, "--persona", persona])
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return res.stdout or res.stderr


@mcp.tool()
def review_pr(number: int, post: bool = False, persona: str = "devsecops") -> str:
    """Fetch GitHub PR diff and review using specified persona; optionally post comment."""
    cmd = ["uv", "run", "devops", "review", "pr", str(number), "--persona", persona]
    if post:
        cmd.append("--post")
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return res.stdout or res.stderr


@mcp.tool()
def review_findings(session_id: str = "", status: str = "") -> str:
    """Inspect structured review findings for a session by verification status."""
    cmd = ["uv", "run", "devops", "review", "findings"]
    if session_id:
        cmd.append(session_id)
    if status:
        cmd.extend(["--" + status.lower().strip("-")])
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return res.stdout or res.stderr


@mcp.tool()
def verify_finding(session_id: str, index: int, status: str, reason: str = "") -> str:
    """Validate or invalidate a finding and record human feedback."""
    cmd = [
        "uv",
        "run",
        "devops",
        "review",
        "verify",
        session_id,
        "--index",
        str(index),
        "--status",
        status,
    ]
    if reason:
        cmd.extend(["--reason", reason])
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return res.stdout or res.stderr


@mcp.tool()
def review_stats() -> str:
    """View accuracy metrics and false-positive rates per reviewer persona."""
    res = subprocess.run(
        ["uv", "run", "devops", "review", "stats"], capture_output=True, text=True, timeout=60
    )
    return res.stdout or res.stderr


@mcp.tool()
def repos_list() -> str:
    """List local workspace repositories and active git branches."""
    res = subprocess.run(
        ["uv", "run", "devops", "repos", "list"], capture_output=True, text=True, timeout=30
    )
    return res.stdout or res.stderr


@mcp.tool()
def repos_status() -> str:
    """Display uncommitted changes and branch drift across workspace repositories."""
    res = subprocess.run(
        ["uv", "run", "devops", "repos", "status"], capture_output=True, text=True, timeout=60
    )
    return res.stdout or res.stderr


@mcp.tool()
def repos_sync(all_repos: bool = False) -> str:
    """Fetch and pull tracking branches across workspace repositories."""
    cmd = ["uv", "run", "devops", "repos", "sync"]
    if all_repos:
        cmd.append("--all")
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return res.stdout or res.stderr


@mcp.tool()
def ssh_status() -> str:
    """Inspect age and rotation status of managed SSH keys in ~/.ssh."""
    res = subprocess.run(
        ["uv", "run", "devops", "ssh", "status"], capture_output=True, text=True, timeout=30
    )
    return res.stdout or res.stderr


@mcp.tool()
def ssh_audit() -> str:
    """Audit SSH key expiration dates and key file permissions."""
    res = subprocess.run(
        ["uv", "run", "devops", "ssh", "audit"], capture_output=True, text=True, timeout=30
    )
    return res.stdout or res.stderr


@mcp.tool()
def k8s_pods(namespace: str = "default") -> str:
    """List Kubernetes pod status with RFC 1123 label filtering."""
    res = subprocess.run(
        ["uv", "run", "devops", "k8s", "pods", "--namespace", namespace],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return res.stdout or res.stderr


@mcp.tool()
def k8s_status() -> str:
    """Display pod status across infrastructure namespaces."""
    res = subprocess.run(
        ["uv", "run", "devops", "k8s", "status"], capture_output=True, text=True, timeout=60
    )
    return res.stdout or res.stderr


@mcp.tool()
def argo_list() -> str:
    """List ArgoCD applications."""
    res = subprocess.run(
        ["uv", "run", "devops", "argo", "list"], capture_output=True, text=True, timeout=30
    )
    return res.stdout or res.stderr


@mcp.tool()
def argo_status(app: str) -> str:
    """Check ArgoCD application health and sync status."""
    res = subprocess.run(
        ["uv", "run", "devops", "argo", "status", "--app", app],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return res.stdout or res.stderr


@mcp.tool()
def grafana_dashboards(query: str = "") -> str:
    """Search and list Grafana dashboards by tag or query."""
    cmd = ["uv", "run", "devops", "grafana", "dashboards"]
    if query:
        cmd.extend(["--query", query])
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return res.stdout or res.stderr


@mcp.tool()
def prometheus_query(promql: str) -> str:
    """Execute PromQL instant query against Prometheus endpoint."""
    res = subprocess.run(
        ["uv", "run", "devops", "prometheus", "query", promql],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return res.stdout or res.stderr


@mcp.tool()
def docker_stats() -> str:
    """Display resource usage metrics for running Docker containers."""
    res = subprocess.run(
        ["uv", "run", "devops", "docker", "stats"], capture_output=True, text=True, timeout=30
    )
    return res.stdout or res.stderr


@mcp.tool()
def workspace_list() -> str:
    """List configured directories in active multi-root workspace file."""
    res = subprocess.run(
        ["uv", "run", "devops", "workspace", "list"], capture_output=True, text=True, timeout=30
    )
    return res.stdout or res.stderr


@mcp.tool()
def config_show() -> str:
    """Display configuration settings with masked secret tokens."""
    res = subprocess.run(
        ["uv", "run", "devops", "config", "show"], capture_output=True, text=True, timeout=30
    )
    return res.stdout or res.stderr


@mcp.tool()
def config_output(output_format: str = "json") -> str:
    """Output environment variables available for configuration (text or json)."""
    flag = "--json" if output_format == "json" else "--export"
    res = subprocess.run(
        ["uv", "run", "devops", "config", "output", flag],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return res.stdout or res.stderr


@mcp.tool()
def ci_run(check: Literal["all", "test", "lint", "format", "typecheck"] = "all") -> str:
    """Run devops-cli complete quality gate (pytest, ruff check, ruff format, mypy)."""
    cmd = ["uv", "run", "devops", "ci"]
    if check != "all":
        cmd.append(check)
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    return res.stdout or res.stderr


def list_mcp_tools() -> list[dict[str, str]]:
    """Return a list of tool names and descriptions registered on the FastMCP server."""
    tools = asyncio.run(mcp.list_tools())
    return [
        {"name": t.name, "description": t.description or "No description provided."} for t in tools
    ]


def run_mcp_server(transport: str = "stdio", host: str = "127.0.0.1", port: int = 8000) -> None:
    """Launch FastMCP server using stdio or sse transport."""
    if transport == "sse":
        mcp.run(transport="sse", host=host, port=port)
    else:
        # show_banner=False prevents the ASCII banner from writing to stdout,
        # which would corrupt the JSON-RPC stream for stdio MCP clients.
        mcp.run(transport="stdio", show_banner=False)
