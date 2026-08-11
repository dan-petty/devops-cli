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


def _run_mcp_cmd(cmd: list[str], timeout: int = 60) -> str:
    """Run a subprocess command for an MCP tool and return combined output or error status."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds: {' '.join(cmd)}"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"Execution failed: {exc}"

    output = (res.stdout + ("\n" + res.stderr if res.stderr else "")).strip()
    if res.returncode != 0:
        return f"Command exited with status {res.returncode}:\n{output}"
    return output or "Success"


@mcp.tool()
def review_path(target: str = ".", pattern: str = "*", persona: str = "devsecops") -> str:
    """Run an AI code review on local files matching pattern using specified persona."""
    return _run_mcp_cmd(
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
        timeout=300,
    )


@mcp.tool()
def review_branch(branch: str = "", base: str = "main", persona: str = "devsecops") -> str:
    """Run an AI code review on git branch diff against base branch."""
    cmd = ["uv", "run", "devops", "review", "branch"]
    if branch:
        cmd.append(branch)
    cmd.extend(["--base", base, "--persona", persona])
    return _run_mcp_cmd(cmd, timeout=300)


@mcp.tool()
def review_pr(number: int, post: bool = False, persona: str = "devsecops") -> str:
    """Fetch GitHub PR diff and review using specified persona; optionally post comment."""
    cmd = ["uv", "run", "devops", "review", "pr", str(number), "--persona", persona]
    if post:
        cmd.append("--post")
    return _run_mcp_cmd(cmd, timeout=300)


@mcp.tool()
def review_findings(session_id: str = "", status: str = "") -> str:
    """Inspect structured review findings for a session by verification status."""
    cmd = ["uv", "run", "devops", "review", "findings"]
    if session_id:
        cmd.append(session_id)
    if status:
        st_clean = status.lower().strip("-")
        if st_clean in {"verified", "unverified", "mitigated"}:
            cmd.append(f"--{st_clean}")
    return _run_mcp_cmd(cmd, timeout=60)


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
    return _run_mcp_cmd(cmd, timeout=60)


@mcp.tool()
def review_stats() -> str:
    """View accuracy metrics and false-positive rates per reviewer persona."""
    return _run_mcp_cmd(["uv", "run", "devops", "review", "stats"], timeout=60)


@mcp.tool()
def repos_list() -> str:
    """List local workspace repositories and active git branches."""
    return _run_mcp_cmd(["uv", "run", "devops", "repos", "list"], timeout=30)


@mcp.tool()
def repos_status() -> str:
    """Display uncommitted changes and branch drift across workspace repositories."""
    return _run_mcp_cmd(["uv", "run", "devops", "repos", "status"], timeout=60)


@mcp.tool()
def repos_sync(all_repos: bool = False) -> str:
    """Fetch and pull tracking branches across workspace repositories."""
    cmd = ["uv", "run", "devops", "repos", "sync"]
    if all_repos:
        cmd.append("--all")
    return _run_mcp_cmd(cmd, timeout=120)


@mcp.tool()
def ssh_status() -> str:
    """Inspect age and rotation status of managed SSH keys in ~/.ssh."""
    return _run_mcp_cmd(["uv", "run", "devops", "ssh", "status"], timeout=30)


@mcp.tool()
def ssh_audit() -> str:
    """Audit SSH key expiration dates and key file permissions."""
    return _run_mcp_cmd(["uv", "run", "devops", "ssh", "audit"], timeout=30)


@mcp.tool()
def k8s_pods(namespace: str = "default") -> str:
    """List Kubernetes pod status for the specified namespace."""
    cmd = ["uv", "run", "devops", "k8s", "pods"]
    if namespace:
        cmd.extend(["--namespace", namespace])
    return _run_mcp_cmd(cmd, timeout=30)


@mcp.tool()
def k8s_status() -> str:
    """Display pod status across infrastructure namespaces."""
    return _run_mcp_cmd(["uv", "run", "devops", "k8s", "status"], timeout=60)


@mcp.tool()
def k8s_bootstrap(auto_start: bool = True) -> str:
    """Bootstrap minikube Kubernetes cluster and deploy infrastructure stack."""
    cmd = ["uv", "run", "devops", "k8s", "bootstrap"]
    if not auto_start:
        cmd.append("--no-auto-start")
    return _run_mcp_cmd(cmd, timeout=360)


@mcp.tool()
def k8s_deploy_stack() -> str:
    """Deploy ArgoCD, Prometheus, Grafana, and OTEL Collector to minikube."""
    return _run_mcp_cmd(["uv", "run", "devops", "k8s", "deploy-stack"], timeout=360)


@mcp.tool()
def k8s_teardown_stack() -> str:
    """Uninstall minikube infrastructure stack and delete namespaces."""
    return _run_mcp_cmd(["uv", "run", "devops", "k8s", "teardown-stack"], timeout=180)


@mcp.tool()
def argo_list() -> str:
    """List ArgoCD applications."""
    return _run_mcp_cmd(["uv", "run", "devops", "argo", "list"], timeout=30)


@mcp.tool()
def argo_status(app: str) -> str:
    """Check ArgoCD application health and sync status."""
    return _run_mcp_cmd(["uv", "run", "devops", "argo", "status", "--app", app], timeout=30)


@mcp.tool()
def grafana_dashboards(query: str = "") -> str:
    """List Grafana dashboards, optionally filtered by search query."""
    cmd = ["uv", "run", "devops", "grafana", "dashboards"]
    if query:
        cmd.extend(["--query", query])
    return _run_mcp_cmd(cmd, timeout=30)


@mcp.tool()
def prometheus_query(promql: str) -> str:
    """Execute PromQL instant query against Prometheus endpoint."""
    return _run_mcp_cmd(["uv", "run", "devops", "prometheus", "query", promql], timeout=30)


@mcp.tool()
def docker_stats() -> str:
    """List local Docker images and display container information."""
    return _run_mcp_cmd(["uv", "run", "devops", "docker", "stats"], timeout=30)


@mcp.tool()
def workspace_list() -> str:
    """Show the active VS Code workspace file and configured repository directories."""
    return _run_mcp_cmd(["uv", "run", "devops", "workspace", "list"], timeout=30)


@mcp.tool()
def config_show() -> str:
    """Display configuration settings with masked secret tokens."""
    return _run_mcp_cmd(["uv", "run", "devops", "config", "show"], timeout=30)


@mcp.tool()
def config_output(output_format: str = "json") -> str:
    """Output environment variables available for configuration (text or json)."""
    flag = "--json" if output_format == "json" else "--export"
    return _run_mcp_cmd(["uv", "run", "devops", "config", "output", flag], timeout=30)


@mcp.tool()
def ci_run(check: Literal["all", "test", "lint", "format", "typecheck"] = "all") -> str:
    """Run devops-cli complete quality gate (pytest, ruff check, ruff format, mypy)."""
    cmd = ["uv", "run", "devops", "ci"]
    if check != "all":
        cmd.append(check)
    return _run_mcp_cmd(cmd, timeout=180)


def list_mcp_tools() -> list[dict[str, str]]:
    """Return a list of tool names and descriptions registered on the FastMCP server."""
    tools = asyncio.run(mcp.list_tools())
    return [
        {"name": t.name, "description": t.description or "No description provided."} for t in tools
    ]


def run_mcp_server(
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8000,
    allow_remote: bool = False,
) -> None:
    """Launch FastMCP server using stdio or sse transport."""
    if transport == "sse":
        allowed_hosts = {"127.0.0.1", "::1", "localhost"}
        if not allow_remote and host not in allowed_hosts:
            raise ValueError(
                f"Refusing to bind SSE transport to non-loopback host '{host}' by default. "
                "Use allow_remote=True to permit external host binding."
            )
        mcp.run(transport="sse", host=host, port=port)
    else:
        # show_banner=False prevents the ASCII banner from writing to stdout,
        # which would corrupt the JSON-RPC stream for stdio MCP clients.
        mcp.run(transport="stdio", show_banner=False)
