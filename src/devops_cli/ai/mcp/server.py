"""FastMCP server implementation for devops-cli."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.exceptions import ValidationError as FastMCPValidationError
from fastmcp.server.middleware import Middleware
from pydantic import ValidationError as PydanticValidationError

from devops_cli.ai.mcp.argument_contract import (
    ArgumentValueLogFilter,
    argument_refusal,
    pydantic_violations,
    schema_violations,
)
from devops_cli.ai.mcp.generator import generate_mcp_tools
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_FASTMCP_OPERATIONS_LOGGER,
    CONST_MCP_EAGER_DOMAINS,
    CONST_MCP_LAZY_DOMAINS,
    CONST_MCP_MAX_COMMAND_OUTPUT_CHARS,
)
from devops_cli.config.defaults import (
    DEFAULT_MCP_SERVER_PORT,
    DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
    DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
    DEFAULT_TRUNCATION_SUFFIX,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import SecurityError, ValidationError
from devops_cli.lang import ERRORS, MESSAGES
from devops_cli.models.ai import MCPToolInfo

mcp = FastMCP(
    name="devops-cli",
    instructions=(
        "DevOps CLI Model Context Protocol Server. Provides tools for AI code reviews, "
        "repository automation, SSH key management, Kubernetes, ArgoCD, Grafana, "
        "Prometheus monitoring, Docker cleanup, and quality gates."
    ),
)


def _bound_output(text: str, max_chars: int = CONST_MCP_MAX_COMMAND_OUTPUT_CHARS) -> str:
    """Bound tool output length while appending truncation suffix if exceeded."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + DEFAULT_TRUNCATION_SUFFIX


def _run_mcp_cmd(
    cmd: list[str],
    timeout: float = DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
    env: dict[str, str] | None = None,
) -> str:
    """Run a command for an MCP tool in-process or via subprocess and return masked output."""
    from devops_cli.ai.mcp.dispatcher import _extract_devops_sub_args, get_mcp_dispatcher
    from devops_cli.security.sanitizer import mask_secrets

    sub_args = _extract_devops_sub_args(cmd)
    if sub_args is not None:
        dispatcher = get_mcp_dispatcher()
        exit_code, output = dispatcher.dispatch(cmd, timeout=timeout, env=env)
        clean = mask_secrets(output.strip())
        clean = _bound_output(clean)
        if exit_code != 0:
            raise ToolError(f"Command exited with status {exit_code}:\n{clean}")
        return clean or "Success"

    try:
        res = run_subprocess(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        safe_cmd = mask_secrets(" ".join(cmd))
        return f"Command timed out after {timeout} seconds: {safe_cmd}"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"Execution failed: {mask_secrets(str(exc))}"

    output = (res.stdout + ("\n" + res.stderr if res.stderr else "")).strip()
    output = mask_secrets(output)
    output = _bound_output(output)
    if res.returncode != 0:
        raise ToolError(f"Command exited with status {res.returncode}:\n{output}")
    return output or "Success"


def _validate_mcp_arg(name: str, value: str) -> None:
    """Reject MCP tool arguments that start with a hyphen to prevent flag injection."""
    if value.startswith("-"):
        raise ValidationError(
            ERRORS.mcp.hyphen_prefixed_argument.format(name=name),
            field=name,
        )


# ── Hand-Written Native Tools ───────────────────────────────────────────────────


@mcp.tool(annotations={"readOnlyHint": True})
def k8s_tempo_info() -> str:
    """Retrieve Tempo distributed tracing HTTP API URL and OTLP trace endpoints."""
    return (
        "Tempo Tracing Endpoints:\n"
        "- HTTP API: http://localhost:3200\n"
        "- OTLP gRPC: localhost:4317\n"
        "- OTLP HTTP: http://localhost:4318/v1/traces"
    )


@mcp.tool(annotations={"readOnlyHint": True})
def security_intel_package(package_name: str, version: str = "", ecosystem: str = "PyPI") -> str:
    """Query the OSV.dev vulnerability database for package CVE intelligence."""
    _validate_mcp_arg("package_name", package_name)
    if version:
        _validate_mcp_arg("version", version)
    if ecosystem:
        _validate_mcp_arg("ecosystem", ecosystem)
    from devops_cli.ai.tools.builtin_tools import scan_osv

    return scan_osv(package_name=package_name, version=version, ecosystem=ecosystem)


@mcp.tool(annotations={"readOnlyHint": True})
def security_intel_network(target: str) -> str:
    """Check IP or domain threat intelligence via Shodan and Cloudflare Radar."""
    _validate_mcp_arg("target", target)
    from devops_cli.ai.tools.builtin_tools import check_threat_intel

    return check_threat_intel(target=target)


@mcp.tool(annotations={"readOnlyHint": True})
def scan_uv_audit(directory: str = ".") -> str:
    """Audit the packages that the uv.lock of a project pins, as it is, for known vulnerabilities and adverse project statuses, with uv audit."""
    _validate_mcp_arg("directory", directory)
    from devops_cli.ai.tools.builtin_tools import scan_uv_audit as _native_uv_audit

    return _native_uv_audit(directory=directory)


# ── FastMCP Dynamic System State Resources ─────────────────────────────────────


def _run_mcp_resource(
    resource_uri: str,
    cmd: list[str],
    timeout: float = DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
) -> str:
    """Execute resource query in-process and stream state update to subscribers."""
    output = _run_mcp_cmd(cmd, timeout=timeout)
    from devops_cli.ai.mcp.dispatcher import get_mcp_dispatcher

    get_mcp_dispatcher().subscriptions.notify(resource_uri, output)
    return output


@mcp.resource("resource://workspace/status")
def get_workspace_resource() -> str:
    """Return live workspace inventory and repository statuses."""
    return _run_mcp_resource(
        "resource://workspace/status",
        ["uv", "run", "devops", "repos", "list"],
        timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://config/active")
def get_config_resource() -> str:
    """Return active configuration settings."""
    return _run_mcp_resource(
        "resource://config/active",
        ["uv", "run", "devops", "config", "show"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://telemetry/status")
def get_telemetry_resource() -> str:
    """Return OpenTelemetry distributed tracing and Prometheus metrics status."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "telemetry", "status"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://telemetry/logfire")
def get_logfire_resource() -> str:
    """Return Logfire structured AI observability status and token metrics."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "telemetry", "logfire", "--json"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://gh/pages/status")
def get_gh_pages_resource() -> str:
    """Return live GitHub Pages publishing status, custom domain, and build health."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "gh", "pages", "status"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://gh/issues/status")
def get_gh_issues_resource() -> str:
    """Return aggregated open GitHub issues counts grouped by priority, type, and milestone."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "gh", "issues", "status"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://gh/project/status")
def get_gh_project_resource() -> str:
    """Return live GitHub Projects v2 board configuration and field mappings."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "gh", "project", "status"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://gh/views/status")
def get_gh_views_resource() -> str:
    """Return remote GitHub Projects views synchronization and audit status."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "gh", "views", "audit"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://argo/fleet/status")
def get_argo_fleet_status_resource() -> str:
    """Return live ArgoCD multi-cluster fleet synchronization status across all managed clusters."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "argo", "cd", "apps", "list"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://tf/cost/latest")
def get_tf_cost_latest_resource() -> str:
    """Return latest Terraform cloud infrastructure cost breakdown and FinOps metrics."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "tf", "cost", "breakdown", ".", "--mock", "--json"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://k8s/logs/recent")
def get_k8s_logs_recent_resource() -> str:
    """Provide structured summary of recent cluster logs across active namespaces and error events."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "k8s", "logs", "{}", "--limit", "30", "--format", "json"],
        timeout=DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://ai/gateway")
def get_ai_gateway_resource() -> str:
    """Return live LLM Gateway health and active virtual model routing table."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "ai", "gateway", "status", "--format", "json"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://ai/spend")
def get_ai_spend_resource() -> str:
    """Return lifetime AI spend report aggregated by backend server in JSON format."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "ai", "cost", "report", "--by", "server", "--format", "json"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://libraries/indexed")
def get_indexed_libraries_resource() -> str:
    """Return JSON metadata of all indexed library contracts, module counts, and symbol counts."""
    from devops_cli.ai.rag.library_store import library_contracts_dir, load_local_contracts

    contracts = load_local_contracts(library_contracts_dir())
    payload = [
        {
            "package_name": c.package_name,
            "version": c.version,
            "timestamp": c.timestamp,
            "total_modules": c.total_modules,
            "total_functions": c.total_functions,
            "total_classes": c.total_classes,
        }
        for c in contracts
    ]
    return json.dumps(payload, indent=2)


@mcp.resource("resource://ai/constellation")
def get_ai_constellation_resource() -> str:
    """Return the constellation flag: state, reason and recorded fallback route."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "ai", "constellation", "--format", "json"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://vault/status")
def get_vault_resource() -> str:
    """Return live HashiCorp Vault cluster health, sealing, and initialization status."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "vault", "status"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://valkey/status")
def get_valkey_resource() -> str:
    """Return live Valkey caching server status, memory usage, and health."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "valkey", "stats"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://sandbox/instances")
def get_sandbox_instances_resource() -> str:
    """Return live inventory of registered and active sandbox container instances."""
    return _run_mcp_cmd(
        ["uv", "run", "devops", "sandbox", "status", "--all", "--json"],
        timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    )


@mcp.resource("resource://mcp/tools")
def get_mcp_catalog_resource() -> str:
    """Return live catalog of registered FastMCP tools and descriptions."""
    tools = list_mcp_tools()
    return "\n".join(f"- {t.name}: {t.description}" for t in tools)


# ── FastMCP Prompts ─────────────────────────────────────────────────────────────

_SECURITY_AUDIT_PROMPT_TEMPLATE = load_task_prompt("security_audit_prompt.md")
_K8S_DIAGNOSTICS_PROMPT_TEMPLATE = load_task_prompt("k8s_diagnostics_prompt.md")
_ARCHITECTURE_ANALYSIS_PROMPT_TEMPLATE = load_task_prompt("architecture_analysis_prompt.md")


@mcp.prompt()
def security_audit_prompt(target: str = ".") -> str:
    """Prompt template for running a multi-layer security audit across dependencies and code."""
    return _SECURITY_AUDIT_PROMPT_TEMPLATE.format(target=target)


@mcp.prompt()
def k8s_diagnostics_prompt(namespace: str = "default") -> str:
    """Prompt template for diagnosing Kubernetes cluster, workload, and pod health."""
    return _K8S_DIAGNOSTICS_PROMPT_TEMPLATE.format(namespace=namespace)


@mcp.prompt()
def architecture_analysis_prompt(target: str = "src") -> str:
    """Prompt template for analyzing software architecture, modularity, and dependencies."""
    return _ARCHITECTURE_ANALYSIS_PROMPT_TEMPLATE.format(target=target)


def _tool_read_only_hint(tool: Any) -> bool | None:
    """Extract the read_only_hint boolean from a FastMCP tool's annotations."""
    annotations = getattr(tool, "annotations", None)
    raw = getattr(annotations, "read_only_hint", None) if annotations is not None else None
    return raw if isinstance(raw, bool) else None


def list_mcp_tools() -> list[MCPToolInfo]:
    """Return every tool registered on the FastMCP server, gated or not.

    This documents the catalogue -- it drives `devops ai mcp export-schemas` and
    `docs/MCP_TOOLS.md` -- so it reads the registry rather than the client-facing listing.
    `mcp.list_tools()` runs the domain gate and would report only what a client is offered
    before hydrating, which would silently shrink the published reference to a quarter.
    """
    tools = asyncio.run(mcp._list_tools())
    return [
        MCPToolInfo(
            name=t.name,
            description=t.description or MESSAGES.mcp.no_description_provided,
            read_only_hint=_tool_read_only_hint(t),
        )
        for t in tools
    ]


def check_sse_bind(transport: str, host: str, *, allow_remote: bool = False) -> None:
    """Refuse an `sse` bind to a host that is not loopback, unless `allow_remote` is set. The
    server start and its dry run both call it."""
    from devops_cli.core.validation import is_loopback_host

    if transport == "sse" and not allow_remote and not is_loopback_host(host):
        raise SecurityError(ERRORS.mcp.security_sse_non_loopback.format(host=host))


def run_mcp_server(
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = DEFAULT_MCP_SERVER_PORT,
    allow_remote: bool = False,
) -> None:
    """Launch FastMCP server using stdio or sse transport."""
    check_sse_bind(transport, host, allow_remote=allow_remote)
    if transport == "sse":
        mcp.run(transport="sse", host=host, port=port)
    else:
        mcp.run(transport="stdio", show_banner=False)


# =============================================================================
# Lazy domain-gated tool hydration
# =============================================================================

# Domains a caller has asked for, beyond the eager set. This filters what is advertised;
# it never removes a tool from the server. An earlier version did remove them, which
# mutated a process-wide object every consumer shares -- the schema exporter, the
# in-process bridge and every later test saw whatever the last caller left behind, and a
# launch rejected for binding a non-loopback address had already withheld its tools before
# the security check ran.
_HYDRATED_DOMAINS: set[str] = set()


def _tool_domain(name: str) -> str:
    """Return the domain prefix a tool name belongs to."""
    return name.split("_", 1)[0]


def _is_advertised(name: str) -> bool:
    """Report whether a tool belongs to the set currently offered to a client."""
    domain = _tool_domain(name)
    return (
        name == "hydrate_tool_domain"
        or domain in CONST_MCP_EAGER_DOMAINS
        or domain in _HYDRATED_DOMAINS
    )


class DomainGateMiddleware(Middleware):
    """Advertise only the eager domains until a caller hydrates the rest.

    The server registers 151 tools. Their names and summaries alone cost roughly 2,700
    tokens in every request, before the per-parameter JSON Schema the protocol adds on top,
    and a model choosing among 151 tools chooses worse than one choosing among a few dozen.

    Calling a withheld tool still works; only the listing is filtered. A client that
    already knows a tool's name is not forced through a hydration round trip to use it.
    """

    async def on_list_tools(self, context: Any, call_next: Any) -> Any:
        tools = await call_next(context)
        return [tool for tool in tools if _is_advertised(tool.name)]


class ArgumentContractMiddleware(Middleware):
    """Refuse a call its tool's published schema does not allow, before the handler runs.

    FastMCP validates arguments with pydantic in lax mode, so `{"number": true, "post": true}`
    ran `review_pr` against PR 1 and commented on it. The SDK's strict check is no substitute:
    it sees only listed tools, so withheld ones kept coercing, and it quotes the value. This
    resolves the registered tool, listed or withheld, and refuses `1.0` for any integer,
    though JSON Schema counts it as one. Pydantic still runs afterwards, and its refusal is
    answered with the same envelope.
    """

    async def on_call_tool(self, context: Any, call_next: Any) -> Any:
        tool = await mcp.get_tool(context.message.name)
        if tool is None:
            return await call_next(context)
        violations = schema_violations(tool.parameters, context.message.arguments or {})
        if violations:
            raise ToolError(argument_refusal(tool.name, tool.parameters, violations))
        try:
            return await call_next(context)
        except FastMCPValidationError as exc:
            if not isinstance(exc.__cause__, PydanticValidationError):
                raise
            violations = pydantic_violations(tool.parameters, exc.__cause__)
            raise ToolError(argument_refusal(tool.name, tool.parameters, violations)) from None


def reset_hydrated_domains() -> None:
    """Forget every hydrated domain, restoring the eager-only listing."""
    _HYDRATED_DOMAINS.clear()
    _BACKGROUND_TASKS.clear()


_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()


def _notify_tool_list_changed(ctx: Context | None) -> None:
    """Send tool list changed notification to client if session is active."""
    if ctx and getattr(ctx, "session", None):
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(ctx.session.send_tool_list_changed())
            _BACKGROUND_TASKS.add(task)
            task.add_done_callback(_BACKGROUND_TASKS.discard)
        except RuntimeError:
            try:
                asyncio.run(ctx.session.send_tool_list_changed())
            except Exception:
                pass


@mcp.tool(annotations={"readOnlyHint": True})
def hydrate_tool_domain(domain: str, ctx: Context | None = None) -> dict[str, Any]:
    """Advertise the tools for one domain, which are withheld from the listing by default.

    Call this before browsing a domain's tools. Available lazy domains include `argo`,
    `benchmark`, `branches`, `ci`, `docker`, `docs`, `gh`, `grafana`, `k8s`, `pr`,
    `prometheus`, `rag`, `repos`, `roadmap`, `sandbox`, `scan`, `security`, `ssh`, `telemetry`,
    `tf`, `tls`, `valkey`, `vault` and `verify`.
    Pass the domain name alone, for example `k8s`.
    """
    key = domain.strip().lower().removesuffix("_")
    if not key or not re.fullmatch(r"^[a-z0-9_-]{1,64}$", key):
        return {
            "domain": key[:64] if key else "",
            "hydrated": False,
            "detail": "invalid domain name",
        }
    if key in CONST_MCP_EAGER_DOMAINS:
        return {"domain": key, "hydrated": False, "detail": "always advertised"}
    if key not in CONST_MCP_LAZY_DOMAINS:
        return {"domain": key, "hydrated": False, "detail": f"unknown domain: {key}"}
    _HYDRATED_DOMAINS.add(key)
    _notify_tool_list_changed(ctx)
    return {"domain": key, "hydrated": True, "advertised_domains": sorted(_HYDRATED_DOMAINS)}


mcp.add_middleware(DomainGateMiddleware())
mcp.add_middleware(ArgumentContractMiddleware())
logging.getLogger(CONST_FASTMCP_OPERATIONS_LOGGER).addFilter(ArgumentValueLogFilter())

# ── Dynamic Tool Generation From Typer App ─────────────────────────────────────

_GENERATED_TOOLS = generate_mcp_tools(mcp)
globals().update(_GENERATED_TOOLS)
