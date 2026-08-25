"""FastMCP server implementation for devops-cli."""

from __future__ import annotations

import asyncio
import subprocess
from typing import Literal

from fastmcp import FastMCP

from devops_cli.config.defaults import (
    DEFAULT_MCP_SERVER_PORT,
    DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
    DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.models.ai import MCPToolInfo

mcp = FastMCP(
    name="devops-cli",
    instructions=(
        "DevOps CLI Model Context Protocol Server. Provides tools for AI code reviews, "
        "repository automation, SSH key management, Kubernetes, ArgoCD, Grafana, "
        "Prometheus monitoring, Docker cleanup, and quality gates."
    ),
)


def _run_mcp_cmd(
    cmd: list[str],
    timeout: float = DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
) -> str:
    """Run a subprocess command for an MCP tool and return combined output or error status."""
    try:
        res = run_subprocess(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds: {' '.join(cmd)}"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"Execution failed: {exc}"

    output = (res.stdout + ("\n" + res.stderr if res.stderr else "")).strip()
    if res.returncode != 0:
        return f"Command exited with status {res.returncode}:\n{output}"
    return output or "Success"


def _validate_mcp_arg(name: str, value: str) -> None:
    """Reject MCP tool arguments that start with a hyphen to prevent flag injection."""
    if value.startswith("-"):
        raise ValueError(
            f"Invalid value for '{name}': must not start with a hyphen. "
            "Hyphen-prefixed values could be interpreted as flags by the underlying command."
        )


@mcp.tool()
def review_path(target: str = ".", pattern: str = "*", persona: str = "devsecops") -> str:
    """Run an AI code review on local files matching pattern using specified persona."""
    _validate_mcp_arg("target", target)
    _validate_mcp_arg("pattern", pattern)
    _validate_mcp_arg("persona", persona)
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
        timeout=DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
    )


@mcp.tool()
def review_branch(branch: str = "", base: str = "main", persona: str = "devsecops") -> str:
    """Run an AI code review on git branch diff against base branch."""
    if branch:
        _validate_mcp_arg("branch", branch)
    _validate_mcp_arg("base", base)
    _validate_mcp_arg("persona", persona)
    cmd = ["uv", "run", "devops", "review", "branch"]
    if branch:
        cmd.append(branch)
    cmd.extend(["--base", base, "--persona", persona])
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_TIMEOUT_SECONDS)


@mcp.tool()
def review_pr(number: int, post: bool = False, persona: str = "devsecops") -> str:
    """Fetch GitHub PR diff and review using specified persona; optionally post comment."""
    cmd = ["uv", "run", "devops", "review", "pr", str(number), "--persona", persona]
    if post:
        cmd.append("--post")
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_TIMEOUT_SECONDS)


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
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS)


@mcp.tool()
def verify_finding(session_id: str, index: int, status: str, reason: str = "") -> str:
    """Validate or invalidate a finding and record human feedback."""
    _validate_mcp_arg("session_id", session_id)
    _validate_mcp_arg("status", status)
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
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS)


@mcp.tool()
def review_stats() -> str:
    """View accuracy metrics and false-positive rates per reviewer persona."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "review", "stats"],
        timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
    )


@mcp.tool()
def repos_list() -> str:
    """List local workspace repositories and active git branches."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "repos", "list"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.tool()
def repos_status() -> str:
    """Display uncommitted changes and branch drift across workspace repositories."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "branches", "list"],
        timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
    )


@mcp.tool()
def repos_sync(all_repos: bool = False) -> str:
    """Fetch and pull tracking branches across workspace repositories."""
    cmd = ["uv", "run", "devops", "repos", "sync"]
    if all_repos:
        cmd.append("--all")
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS * 2)


@mcp.tool()
def ssh_status() -> str:
    """Inspect age and rotation status of managed SSH keys in ~/.ssh."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "ssh", "status"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.tool()
def ssh_audit() -> str:
    """Audit SSH key expiration dates and key file permissions."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "ssh", "audit"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.tool()
def k8s_pods(namespace: str = "default") -> str:
    """List Kubernetes pod status for the specified namespace."""
    if namespace:
        _validate_mcp_arg("namespace", namespace)
    return _run_mcp_cmd(
        ["uv", "run", "devops", "k8s", "status"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.tool()
def k8s_status() -> str:
    """Display pod status across infrastructure namespaces."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "k8s", "status"],
        timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
    )


@mcp.tool()
def k8s_bootstrap(auto_start: bool = True) -> str:
    """Bootstrap minikube Kubernetes cluster and deploy infrastructure stack."""
    cmd = ["uv", "run", "devops", "k8s", "bootstrap"]
    if not auto_start:
        cmd.append("--no-auto-start")
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_TIMEOUT_SECONDS + 60)


@mcp.tool()
def k8s_deploy_stack(stack: str = "infra", context: str | None = None) -> str:
    """Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to Kubernetes cluster."""
    _validate_mcp_arg("stack", stack)
    cmd = ["uv", "run", "devops", "k8s", "deploy-stack", "--stack", stack]
    if context:
        _validate_mcp_arg("context", context)
        cmd.extend(["--context", context])
    return _run_mcp_cmd(
        cmd,
        timeout=DEFAULT_MCP_TOOL_TIMEOUT_SECONDS + 60,
    )


@mcp.tool()
def k8s_teardown_stack(stack: str = "infra", context: str | None = None) -> str:
    """Uninstall Kubernetes infrastructure or LLM stack and delete namespaces."""
    _validate_mcp_arg("stack", stack)
    cmd = ["uv", "run", "devops", "k8s", "teardown-stack", "--stack", stack]
    if context:
        _validate_mcp_arg("context", context)
        cmd.extend(["--context", context])
    return _run_mcp_cmd(
        cmd,
        timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS * 3,
    )


@mcp.tool()
def argo_list() -> str:
    """List ArgoCD applications."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "argo", "cd", "apps", "list"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.tool()
def argo_status(app: str = "argocd") -> str:
    """Check ArgoCD application health and sync status."""
    _validate_mcp_arg("app", app)
    return _run_mcp_cmd(
        ["uv", "run", "devops", "argo", "cd", "apps", "status", app],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.tool()
def grafana_dashboards(query: str = "") -> str:
    """List Grafana dashboards, optionally filtered by search query."""
    if query:
        _validate_mcp_arg("query", query)
        return _run_mcp_cmd(
            ["uv", "run", "devops", "grafana", "search", "--query", query],
            timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
        )
    return _run_mcp_cmd(
        ["uv", "run", "devops", "grafana", "dashboards", "list"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.tool()
def prometheus_query(promql: str = "up") -> str:
    """Execute PromQL instant query against Prometheus endpoint."""
    _validate_mcp_arg("promql", promql)
    return _run_mcp_cmd(
        ["uv", "run", "devops", "prometheus", "query", promql],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.tool()
def docker_stats() -> str:
    """List local Docker images and display container information."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "docker", "images"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.tool()
def workspace_list() -> str:
    """Show the active VS Code workspace file and configured repository directories."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "repos", "list"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.tool()
def config_show() -> str:
    """Display configuration settings with masked secret tokens."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "config", "show"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.tool()
def config_output(output_format: str = "json") -> str:
    """Output environment variables available for configuration (text or json)."""
    flag = "--json" if output_format == "json" else "--export"
    return _run_mcp_cmd(
        ["uv", "run", "devops", "config", "output", flag],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.tool()
def ci_run(check: Literal["all", "test", "lint", "format", "typecheck"] = "all") -> str:
    """Run devops-cli complete quality gate (pytest, ruff check, ruff format, mypy)."""
    cmd = ["uv", "run", "devops", "ci"]
    if check != "all":
        cmd.append(check)
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS * 3)


@mcp.tool()
def release_status() -> str:
    """Check devops-cli release status, version consistency, tags, and docs state."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "release", "status"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.tool()
def tf_plan(directory: str = ".", var_file: str = "") -> str:
    """Generate and inspect an OpenTofu / Terraform execution plan."""
    _validate_mcp_arg("directory", directory)
    cmd = ["uv", "run", "devops", "tf", "plan", directory]
    if var_file:
        _validate_mcp_arg("var_file", var_file)
        cmd.extend(["--var-file", var_file])
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_TIMEOUT_SECONDS)


@mcp.tool()
def tf_apply(directory: str = ".", var_file: str = "", auto_approve: bool = True) -> str:
    """Apply OpenTofu / Terraform Infrastructure-as-Code changes."""
    _validate_mcp_arg("directory", directory)
    cmd = ["uv", "run", "devops", "tf", "apply", directory]
    if var_file:
        _validate_mcp_arg("var_file", var_file)
        cmd.extend(["--var-file", var_file])
    if auto_approve:
        cmd.append("--auto-approve")
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_TIMEOUT_SECONDS * 2)


@mcp.tool()
def tf_output(directory: str = ".", json_format: bool = True) -> str:
    """Retrieve OpenTofu / Terraform outputs from state."""
    _validate_mcp_arg("directory", directory)
    cmd = ["uv", "run", "devops", "tf", "output", directory]
    if json_format:
        cmd.append("--json")
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS)


@mcp.tool()
def tofu_plan(directory: str = ".", var_file: str = "") -> str:
    """Generate and inspect an OpenTofu execution plan (alias for tf_plan)."""
    return tf_plan(directory=directory, var_file=var_file)


@mcp.tool()
def tofu_apply(directory: str = ".", var_file: str = "", auto_approve: bool = True) -> str:
    """Apply OpenTofu Infrastructure-as-Code changes (alias for tf_apply)."""
    return tf_apply(directory=directory, var_file=var_file, auto_approve=auto_approve)


@mcp.tool()
def tofu_output(directory: str = ".", json_format: bool = True) -> str:
    """Retrieve OpenTofu outputs from state (alias for tf_output)."""
    return tf_output(directory=directory, json_format=json_format)


@mcp.tool()
def rag_search(
    query: str,
    top_k: int = 5,
    min_score: float = 0.35,
    project: str | None = None,
    language: str | None = None,
    category: str | None = None,
) -> str:
    """Perform semantic vector search across indexed workspace codebase and architecture docs."""
    _validate_mcp_arg("query", query)
    cmd = [
        "uv",
        "run",
        "devops",
        "ai",
        "rag",
        "query",
        query,
        "--top-k",
        str(top_k),
        "--min-score",
        str(min_score),
    ]
    if project:
        cmd.extend(["--project", project])
    if language:
        cmd.extend(["--language", language])
    if category:
        cmd.extend(["--category", category])
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS)


@mcp.tool()
def rag_index(path: str = ".", project: str | None = None, force: bool = False) -> str:
    """Index workspace files into Qdrant vector database for semantic retrieval."""
    _validate_mcp_arg("path", path)
    cmd = ["uv", "run", "devops", "ai", "rag", "index", path]
    if project:
        cmd.extend(["--project", project])
    if force:
        cmd.append("--force")
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_TIMEOUT_SECONDS)


@mcp.tool()
def k8s_jaeger_info() -> str:
    """Retrieve Jaeger distributed tracing Query UI URL and OTLP trace endpoints."""
    return (
        "Jaeger Tracing Endpoints:\n"
        "- Query UI: http://localhost:16686\n"
        "- OTLP gRPC: localhost:4317\n"
        "- OTLP HTTP: http://localhost:4318/v1/traces"
    )


@mcp.tool()
def security_intel_package(package_name: str, version: str = "", ecosystem: str = "PyPI") -> str:
    """Query OSV.dev and NVD vulnerability databases for package CVE intelligence."""
    _validate_mcp_arg("package_name", package_name)
    if version:
        _validate_mcp_arg("version", version)
    if ecosystem:
        _validate_mcp_arg("ecosystem", ecosystem)
    from devops_cli.ai.tools.builtin_tools import scan_osv

    return scan_osv(package_name=package_name, version=version, ecosystem=ecosystem)


@mcp.tool()
def security_intel_network(target: str) -> str:
    """Check IP or domain threat intelligence via Shodan and Cloudflare Radar."""
    _validate_mcp_arg("target", target)
    from devops_cli.ai.tools.builtin_tools import check_threat_intel

    return check_threat_intel(target=target)


@mcp.tool()
def scan_uv_audit(directory: str = ".", requirements_file: str = "") -> str:
    """Run uv dependency audit / pip-audit to check workspace Python dependencies for known CVEs."""
    _validate_mcp_arg("directory", directory)
    if requirements_file:
        _validate_mcp_arg("requirements_file", requirements_file)
    from devops_cli.ai.tools.builtin_tools import scan_uv_audit as _native_uv_audit

    return _native_uv_audit(directory=directory, requirements_file=requirements_file)


@mcp.tool()
def review_export_feedback(status: str = "ALL", output_path: str = "") -> str:
    """Export review findings into JSONL feedback dataset for LLM alignment."""
    cmd = ["uv", "run", "devops", "review", "export-feedback", "--status", status]
    if output_path:
        _validate_mcp_arg("output_path", output_path)
        cmd.extend(["--output", output_path])
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS)


@mcp.tool()
def tls_generate_ca(
    output_dir: str = "",
    common_name: str = "Homelab Root CA",
    validity_days: int = 3650,
) -> str:
    """Generate an X.509 Root CA key pair for local or homelab infrastructure."""
    cmd = [
        "uv",
        "run",
        "devops",
        "tls",
        "ca",
        "--common-name",
        common_name,
        "--validity-days",
        str(validity_days),
    ]
    if output_dir:
        _validate_mcp_arg("output_dir", output_dir)
        cmd.extend(["--output-dir", output_dir])
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS)


@mcp.tool()
def tls_generate_cert(
    common_name: str = "localhost",
    sans: str = "localhost,127.0.0.1,*.homelab.local",
    output_dir: str = "",
    validity_days: int = 365,
) -> str:
    """Generate an X.509 TLS certificate with Subject Alternative Names signed by local CA."""
    _validate_mcp_arg("common_name", common_name)
    cmd = [
        "uv",
        "run",
        "devops",
        "tls",
        "cert",
        "--common-name",
        common_name,
        "--validity-days",
        str(validity_days),
    ]
    if output_dir:
        _validate_mcp_arg("output_dir", output_dir)
        cmd.extend(["--output-dir", output_dir])
    for s in sans.split(","):
        cleaned = s.strip()
        if cleaned:
            _validate_mcp_arg("san", cleaned)
            cmd.extend(["--san", cleaned])
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS)


@mcp.tool()
def tls_inspect_cert(cert_path: str) -> str:
    """Inspect and display metadata, validity, SANs, and expiration of a TLS certificate."""
    _validate_mcp_arg("cert_path", cert_path)
    return _run_mcp_cmd(
        ["uv", "run", "devops", "tls", "inspect", cert_path],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.tool()
def k8s_create_tls_secret(
    secret_name: str,
    namespace: str = "default",
    cert_path: str = "",
    key_path: str = "",
) -> str:
    """Create or update a kubernetes.io/tls secret in a target namespace."""
    _validate_mcp_arg("secret_name", secret_name)
    _validate_mcp_arg("namespace", namespace)
    cmd = [
        "uv",
        "run",
        "devops",
        "k8s",
        "create-tls-secret",
        secret_name,
        "--namespace",
        namespace,
    ]
    if cert_path:
        _validate_mcp_arg("cert_path", cert_path)
        cmd.extend(["--cert", cert_path])
    if key_path:
        _validate_mcp_arg("key_path", key_path)
        cmd.extend(["--key", key_path])
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS)


@mcp.tool()
def k8s_enable_tls(
    stack: str = "all",
    secret_name: str = "homelab-tls",
    context: str = "",
) -> str:
    """Apply TLS secrets across Kubernetes cluster namespaces (argocd, monitoring, llm, otel)."""
    _validate_mcp_arg("stack", stack)
    _validate_mcp_arg("secret_name", secret_name)
    cmd = [
        "uv",
        "run",
        "devops",
        "k8s",
        "enable-tls",
        "--stack",
        stack,
        "--secret-name",
        secret_name,
    ]
    if context:
        _validate_mcp_arg("context", context)
        cmd.extend(["--context", context])
    return _run_mcp_cmd(cmd, timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS)


@mcp.tool()
def telemetry_status() -> str:
    """Check OpenTelemetry collector connectivity, Jaeger UI URL, and active telemetry settings."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "telemetry", "status"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.tool()
def telemetry_test_span(name: str = "mcp_test_span") -> str:
    """Emit a test OpenTelemetry trace span and metric to verify collector pipeline health."""
    _validate_mcp_arg("name", name)
    return _run_mcp_cmd(
        ["uv", "run", "devops", "telemetry", "test", "--name", name],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


def list_mcp_tools() -> list[MCPToolInfo]:
    """Return a list of tool names and descriptions registered on the FastMCP server."""
    tools = asyncio.run(mcp.list_tools())
    return [
        MCPToolInfo(name=t.name, description=t.description or "No description provided.")
        for t in tools
    ]


def run_mcp_server(
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = DEFAULT_MCP_SERVER_PORT,
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
        mcp.run(transport="stdio", show_banner=False)
