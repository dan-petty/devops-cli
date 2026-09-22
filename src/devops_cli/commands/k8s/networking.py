"""Kubernetes service discovery, URL auto-configuration, and port-forwarding."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Sequence
from typing import Annotated, Any

import typer

import devops_cli.commands.k8s.cluster_runtime as runtime
from devops_cli.config.constants import (
    CONST_ADDRESSING_MODES,
    CONST_ADDRESSING_NODEPORT,
    CONST_ADDRESSING_PROXY,
)
from devops_cli.config.defaults import (
    DEFAULT_ARGOCD_PORT,
    DEFAULT_GRAFANA_PORT,
    DEFAULT_HTTP_PROBE_TIMEOUT_SECONDS,
    DEFAULT_JAEGER_PORT,
    DEFAULT_K8S_STACK,
    DEFAULT_OLLAMA_PORT,
    DEFAULT_OPEN_WEBUI_PORT,
    DEFAULT_OTEL_PORT,
    DEFAULT_PROMETHEUS_PORT,
    DEFAULT_QDRANT_PORT,
    DEFAULT_REST_HOST,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    DEFAULT_VALKEY_PORT,
)
from devops_cli.config.settings import load_settings, save_settings
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    format_json,
    format_k8s_service_targets_table,
    print,
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    write_stdout,
)

logger = logging.getLogger(__name__)

VALID_STACKS: tuple[str, ...] = ("infra", "llm", "logging", "all")


def _resolve_stacks(stack: str) -> list[str]:
    s = stack.strip().lower()
    if s == "all":
        return ["infra", "llm", "logging"]
    if s in ("infra", "llm", "logging"):
        return [s]
    print_error(
        f"Invalid stack: {stack!r}. Supported stacks: {', '.join(VALID_STACKS)}",
        prefix=False,
    )
    raise typer.Exit(1)


def _parse_minikube_service_url(stdout: str) -> str | None:
    """Extract HTTP/HTTPS URL from minikube service command output."""
    for line in stdout.splitlines():
        line_str = line.strip()
        if line_str.startswith(("http://", "https://")):
            return line_str
    return None


def _extract_first_node_ip(item: dict[str, Any]) -> str | None:
    """Extract first external/internal IP or hostname from a Kubernetes node item."""
    for addr in item.get("status", {}).get("addresses", []):
        if addr.get("type") in ("ExternalIP", "InternalIP", "Hostname"):
            ip = addr.get("address")
            if ip:
                return str(ip)
    return None


def _resolve_k8s_node_port_url(ctx_args: list[str], node_port: int) -> str | None:
    """Query Kubernetes nodes to find node IP and construct nodePort URL."""
    try:
        nodes_res = runtime.run_subprocess(
            ["kubectl", "get", "nodes", "-o", "json"] + ctx_args,
            capture_output=True,
            text=True,
            check=False,
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
        if nodes_res.returncode == 0 and nodes_res.stdout.strip():
            import json

            nodes_data = json.loads(nodes_res.stdout)
            for item in nodes_data.get("items", []):
                node_ip = _extract_first_node_ip(item)
                if node_ip:
                    return f"http://{node_ip}:{node_port}"
    except Exception as exc:
        logger.debug("Failed to resolve k8s node port URL: %s", exc)
    return None


def _detect_minikube_service_url(
    service: str, namespace: str, effective_ctx: str | None
) -> str | None:
    """Query Minikube service URL via minikube service CLI."""
    if not (effective_ctx and effective_ctx.strip().lower() == "minikube"):
        return None
    try:
        res = runtime.run_subprocess(
            ["minikube", "service", service, "-n", namespace, "--url"],
            capture_output=True,
            text=True,
            check=False,
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
        if res.returncode == 0 and res.stdout.strip():
            return _parse_minikube_service_url(res.stdout)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("minikube service url query failed for %s: %s", service, exc)
    return None


def _extract_service_ingress_or_nodeport(
    svc_data: dict[str, Any], ctx_args: list[str]
) -> str | None:
    """Extract LoadBalancer ingress URL or NodePort URL from Kubernetes service spec."""
    spec = svc_data.get("spec", {})
    ports = spec.get("ports", [])
    if not ports:
        return None
    node_port = ports[0].get("nodePort")
    port_num = ports[0].get("port")

    ingress = svc_data.get("status", {}).get("loadBalancer", {}).get("ingress", [])
    if ingress:
        lb_host = ingress[0].get("ip") or ingress[0].get("hostname")
        if lb_host and port_num:
            return f"http://{lb_host}:{port_num}"

    if node_port:
        return _resolve_k8s_node_port_url(ctx_args, int(node_port))
    return None


def _detect_kubectl_service_url(
    service: str, namespace: str, effective_ctx: str | None
) -> str | None:
    """Query generic Kubernetes service URL via kubectl JSON output."""
    ctx_args = ["--context", effective_ctx] if effective_ctx else []
    try:
        svc_res = runtime.run_subprocess(
            ["kubectl", "get", "svc", service, "-n", namespace, "-o", "json"] + ctx_args,
            capture_output=True,
            text=True,
            check=False,
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
        if svc_res.returncode == 0 and svc_res.stdout.strip():
            import json

            svc_data = json.loads(svc_res.stdout)
            return _extract_service_ingress_or_nodeport(svc_data, ctx_args)
    except Exception as exc:
        logger.debug("Failed to detect kubectl service URL for %s: %s", service, exc)
    return None


def _detect_service_url(service: str, namespace: str, context: str | None = None) -> str | None:
    """Query service URL via native KubernetesService, minikube service, or kubectl fallback."""
    effective_ctx = runtime.resolve_effective_context(context)
    try:
        from devops_cli.k8s.service import KubernetesService

        native_url = KubernetesService.get_instance().resolve_service_endpoint(
            service=service, namespace=namespace, context=effective_ctx
        )
        if native_url:
            return native_url
    except Exception as exc:
        logger.debug("Native service endpoint resolution failed: %s", exc)

    return _detect_minikube_service_url(
        service, namespace, effective_ctx
    ) or _detect_kubectl_service_url(service, namespace, effective_ctx)


def _verify_url_reachability(url: str, timeout: float = DEFAULT_HTTP_PROBE_TIMEOUT_SECONDS) -> bool:
    """Check if target HTTP URL host and port can accept socket connections."""
    import socket
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not host:
            return False
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception as exc:
        logger.debug("URL %s reachability check failed: %s", url, exc)
        return False


def _check_preferred_ports(scheme: str, ports: list[int] | None) -> str | None:
    """Return first reachable preferred localhost endpoint candidate."""
    if not ports:
        return None
    for port in ports:
        candidate = f"{scheme}://localhost:{port}"
        if _verify_url_reachability(candidate):
            return candidate
    return None


def _resolve_loopback_fallback(scheme: str, port: int) -> str:
    """Resolve and test localhost/loopback fallbacks for unreachable NodePort."""
    localhost_url = f"{scheme}://localhost:{port}"
    if _verify_url_reachability(localhost_url):
        return localhost_url
    loopback_url = f"{scheme}://127.0.0.1:{port}"
    if _verify_url_reachability(loopback_url):
        return loopback_url
    return localhost_url


def _resolve_accessible_url(
    detected_url: str | None,
    preferred_localhost_ports: list[int] | None = None,
    default_scheme: str = "http",
) -> str | None:
    """Resolve service URL to ensure it is accessible from devcontainer / host OS environment."""
    from urllib.parse import urlparse

    scheme = default_scheme
    if detected_url:
        parsed_orig = urlparse(detected_url)
        scheme = parsed_orig.scheme or default_scheme

    preferred = _check_preferred_ports(scheme, preferred_localhost_ports)
    if preferred:
        return preferred

    if not detected_url or _verify_url_reachability(detected_url):
        return detected_url

    parsed = urlparse(detected_url)
    if parsed.port:
        return _resolve_loopback_fallback(parsed.scheme or scheme, parsed.port)

    return detected_url


def _configure_infra_stack_urls(
    effective_context: str | None,
    settings: Any,
    configured: dict[str, str],
) -> None:
    """Detect and configure accessible URLs for infrastructure stack services."""
    from devops_cli.config.settings import dotted_set

    raw_argocd = _detect_service_url("argocd-server", "argocd", context=effective_context)
    raw_grafana = _detect_service_url(
        "kube-prometheus-grafana", "monitoring", context=effective_context
    )
    raw_prom = _detect_service_url(
        "kube-prometheus-kube-prome-prometheus", "monitoring", context=effective_context
    )
    raw_jaeger = _detect_service_url("jaeger", "otel", context=effective_context)

    argocd_url = _resolve_accessible_url(raw_argocd, preferred_localhost_ports=[8080])
    grafana_url = _resolve_accessible_url(raw_grafana, preferred_localhost_ports=[8030, 8000, 3000])
    prom_url = _resolve_accessible_url(raw_prom, preferred_localhost_ports=[8090, 9090])
    jaeger_url = _resolve_accessible_url(raw_jaeger, preferred_localhost_ports=[16686])

    if argocd_url:
        dotted_set(settings, "argocd.url", argocd_url)
        configured["argocd.url"] = argocd_url
    if grafana_url:
        dotted_set(settings, "grafana.url", grafana_url)
        configured["grafana.url"] = grafana_url
    if prom_url:
        dotted_set(settings, "prometheus.url", prom_url)
        configured["prometheus.url"] = prom_url
    if jaeger_url:
        dotted_set(settings, "jaeger.url", jaeger_url)
        configured["jaeger.url"] = jaeger_url
        dotted_set(settings, "otel.endpoint", "http://localhost:4318")
        configured["otel.endpoint"] = "http://localhost:4318"


def _configure_llm_stack_urls(
    effective_context: str | None,
    settings: Any,
    configured: dict[str, str],
) -> None:
    """Detect and configure accessible URLs for LLM stack services."""
    from urllib.parse import urlparse

    from devops_cli.config.settings import dotted_set

    raw_ollama = _detect_service_url("ollama", "llm", context=effective_context)
    raw_webui = _detect_service_url("open-webui", "llm", context=effective_context)
    raw_qdrant = _detect_service_url("qdrant", "llm", context=effective_context)
    raw_valkey = _detect_service_url("valkey", "llm", context=effective_context)

    ollama_url = _resolve_accessible_url(raw_ollama, preferred_localhost_ports=[11434])
    webui_url = _resolve_accessible_url(raw_webui, preferred_localhost_ports=[3000, 8080])
    qdrant_url = _resolve_accessible_url(raw_qdrant, preferred_localhost_ports=[6333])
    valkey_url = _resolve_accessible_url(
        raw_valkey, preferred_localhost_ports=[6379], default_scheme="tcp"
    )

    if ollama_url:
        settings.ai.ollama_urls = [ollama_url]
        configured["ai.ollama_urls"] = ollama_url
    if webui_url:
        dotted_set(settings, "open_webui.url", webui_url)
        configured["open_webui.url"] = webui_url
    if qdrant_url:
        dotted_set(settings, "qdrant.url", qdrant_url)
        configured["qdrant.url"] = qdrant_url
    if valkey_url:
        dotted_set(settings, "valkey.url", valkey_url)
        p_valkey = urlparse(valkey_url)
        if p_valkey.port:
            h = p_valkey.hostname or "localhost"
            dotted_set(settings, "valkey.host", f"{h}:{p_valkey.port}")
            dotted_set(settings, "valkey.port", str(p_valkey.port))
        configured["valkey.url"] = valkey_url


# Which Service backs each configured endpoint. Names are matched as substrings, most
# specific first, because chart releases rename services: Prometheus ships as
# `kube-prometheus-kube-prome-prometheus` rather than `prometheus`.
_PROXY_TARGETS_INFRA: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("argocd.url", "argocd", ("argocd-server",), ("80", "http", "server")),
    ("grafana.url", "monitoring", ("grafana",), ("80", "http", "service")),
    ("prometheus.url", "monitoring", ("prome-prometheus", "prometheus"), ("9090", "web")),
    ("jaeger.url", "otel", ("jaeger",), ("16686", "query", "http-query")),
)
_PROXY_TARGETS_LLM: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("open_webui.url", "llm", ("open-webui",), ("80", "http")),
    ("qdrant.url", "llm", ("qdrant",), ("6333", "http")),
)


def _configure_proxy_urls(
    effective_context: str | None,
    settings: Any,
    configured: dict[str, str],
    stacks: Sequence[str],
) -> None:
    """Record cluster-native addresses for each detected service.

    These addresses carry no host and no local port, so the same configuration resolves on
    whichever cluster is active and survives a cluster being rebuilt.
    """
    from devops_cli.config.settings import dotted_set
    from devops_cli.k8s.service_proxy import discover_service

    targets: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = []
    if "infra" in stacks:
        targets.extend(_PROXY_TARGETS_INFRA)
    if "llm" in stacks:
        targets.extend(_PROXY_TARGETS_LLM)

    for key, namespace, patterns, port_hints in targets:
        ref = discover_service(namespace, patterns, port_hints, context=effective_context)
        if ref is None:
            logger.debug("No service matching %s in namespace '%s'", patterns, namespace)
            continue
        address = ref.describe()
        dotted_set(settings, key, address)
        configured[key] = address


def configure_urls(
    stack: Annotated[str, typer.Option("--stack", "-s", help=HELP.k8s.stack)] = DEFAULT_K8S_STACK,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
    addressing: Annotated[
        str, typer.Option("--addressing", "-a", help=HELP.k8s.addressing)
    ] = CONST_ADDRESSING_NODEPORT,
) -> None:
    """Auto-detect Kubernetes stack URLs and update CLI config."""
    if addressing not in CONST_ADDRESSING_MODES:
        print_error(
            f"Unknown addressing mode '{addressing}'. Choose one of: "
            f"{', '.join(sorted(CONST_ADDRESSING_MODES))}."
        )
        raise typer.Exit(2)
    effective_context = runtime.resolve_effective_context(context)
    if effective_context:
        runtime._validate_kubeconfig_context_name(effective_context, "context")

    selected_stacks = _resolve_stacks(stack)

    dry_run_details: dict[str, str] = {}
    if "infra" in selected_stacks:
        dry_run_details.update(
            {
                "argocd.url": "http://192.168.49.2:30080",
                "grafana.url": "http://192.168.49.2:32047",
                "prometheus.url": "http://192.168.49.2:30090",
                "jaeger.url": "http://192.168.49.2:30686",
            }
        )
    if "llm" in selected_stacks:
        dry_run_details.update(
            {
                "ai.ollama_urls": "http://192.168.49.2:31434",
                "open_webui.url": "http://192.168.49.2:30080",
                "qdrant.url": "http://192.168.49.2:30633",
                "valkey.url": "tcp://192.168.49.2:30379",
            }
        )

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s configure-urls",
            action="configure_monitoring_urls",
            details=dry_run_details,
        )
        return

    if not runtime._cluster_reachable(context=effective_context):
        print_error(MESSAGES.k8s.cluster_not_reachable, prefix=False)
        raise typer.Exit(1)

    print_info(
        f"[bold]Detecting {stack} service URLs (context: {effective_context or 'active'})...[/bold]",
        prefix=False,
    )

    settings = load_settings()
    configured: dict[str, str] = {}

    if addressing == CONST_ADDRESSING_PROXY:
        _configure_proxy_urls(effective_context, settings, configured, selected_stacks)
    else:
        if "infra" in selected_stacks:
            _configure_infra_stack_urls(effective_context, settings, configured)

        if "llm" in selected_stacks:
            _configure_llm_stack_urls(effective_context, settings, configured)

    if configured:
        save_settings(settings)

    print(format_k8s_service_targets_table(configured, stack))


def port_forward(
    stack: Annotated[str, typer.Option("--stack", "-s", help=HELP.k8s.stack)] = DEFAULT_K8S_STACK,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
    argocd_port: Annotated[
        int, typer.Option("--argocd-port", help=HELP.k8s.argocd_port)
    ] = DEFAULT_ARGOCD_PORT,
    grafana_port: Annotated[
        int, typer.Option("--grafana-port", help=HELP.k8s.grafana_port)
    ] = DEFAULT_GRAFANA_PORT,
    prometheus_port: Annotated[
        int, typer.Option("--prometheus-port", help=HELP.k8s.prometheus_port)
    ] = DEFAULT_PROMETHEUS_PORT,
    jaeger_port: Annotated[
        int, typer.Option("--jaeger-port", help=HELP.k8s.jaeger_port)
    ] = DEFAULT_JAEGER_PORT,
    otel_port: Annotated[
        int, typer.Option("--otel-port", help=HELP.k8s.otel_port)
    ] = DEFAULT_OTEL_PORT,
    ollama_port: Annotated[
        int, typer.Option("--ollama-port", help=HELP.k8s.ollama_port)
    ] = DEFAULT_OLLAMA_PORT,
    open_webui_port: Annotated[
        int, typer.Option("--open-webui-port", help=HELP.k8s.open_webui_port)
    ] = DEFAULT_OPEN_WEBUI_PORT,
    qdrant_port: Annotated[
        int, typer.Option("--qdrant-port", help=HELP.k8s.qdrant_port)
    ] = DEFAULT_QDRANT_PORT,
    valkey_port: Annotated[
        int, typer.Option("--valkey-port", help=HELP.k8s.valkey_port)
    ] = DEFAULT_VALKEY_PORT,
    address: Annotated[
        str, typer.Option("--address", help=HELP.k8s.bind_address)
    ] = DEFAULT_REST_HOST,
) -> None:
    """Port-forward k8s monitoring / LLM stack services to localhost ports and update CLI config."""
    import time

    effective_context = runtime.resolve_effective_context(context)
    if effective_context:
        runtime._validate_kubeconfig_context_name(effective_context, "context")

    selected_stacks = _resolve_stacks(stack)

    details: dict[str, str] = {}
    if "infra" in selected_stacks:
        details.update(
            {
                "argocd.url": f"http://localhost:{argocd_port}",
                "grafana.url": f"http://localhost:{grafana_port}",
                "prometheus.url": f"http://localhost:{prometheus_port}",
                "jaeger.url": f"http://localhost:{jaeger_port}",
                "otel.endpoint": f"http://localhost:{otel_port}",
            }
        )
    if "llm" in selected_stacks:
        details.update(
            {
                "ollama.url": f"http://localhost:{ollama_port}",
                "open_webui.url": f"http://localhost:{open_webui_port}",
                "qdrant.url": f"http://localhost:{qdrant_port}",
                "valkey.url": f"tcp://localhost:{valkey_port}",
            }
        )

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s port-forward",
            action="k8s_port_forward",
            details=details,
        )
        return

    if not runtime._cluster_reachable(context=effective_context):
        print_error(MESSAGES.k8s.cluster_not_reachable, prefix=False)
        raise typer.Exit(1)

    print_info(
        f"[bold cyan]Port-forwarding k8s {stack} services to localhost ports...[/bold cyan]",
        prefix=False,
    )

    services: list[tuple[str, str, int, int]] = []
    if "infra" in selected_stacks:
        services.extend(
            [
                ("argocd", "svc/argocd-server", argocd_port, 80),
                ("monitoring", "svc/kube-prometheus-grafana", grafana_port, 80),
                ("monitoring", "svc/kube-prometheus-kube-prome-prometheus", prometheus_port, 9090),
                ("otel", "svc/jaeger", jaeger_port, 16686),
                ("otel", "svc/jaeger", otel_port, 4318),
            ]
        )
    if "llm" in selected_stacks:
        services.extend(
            [
                ("llm", "svc/ollama", ollama_port, 11434),
                ("llm", "svc/open-webui", open_webui_port, 8080),
                ("llm", "svc/qdrant", qdrant_port, 6333),
                ("llm", "svc/valkey", valkey_port, 6379),
            ]
        )

    from devops_cli.k8s.port_forward_daemon import PortForwardInfo, get_daemon_manager

    daemon_mgr = get_daemon_manager()
    active_forwards: list[PortForwardInfo] = daemon_mgr.list_forwards()

    ctx_args = ["--context", effective_context] if effective_context else []
    for ns, svc, lport, rport in services:
        cmd = [
            "kubectl",
            "port-forward",
            "--address",
            address,
            "-n",
            ns,
            svc,
            f"{lport}:{rport}",
        ] + ctx_args
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        active_forwards.append(
            PortForwardInfo(
                pid=proc.pid,
                service=svc,
                namespace=ns,
                local_port=lport,
                remote_port=rport,
                address=address,
                stack=stack,
            )
        )
        print_success(f"Forwarding {svc} ({ns}) to http://{address}:{lport} (pid {proc.pid})")

    daemon_mgr.save_forwards(active_forwards)
    time.sleep(1.0)
    configure_urls(stack=stack, context=effective_context)


def port_forward_status() -> None:
    """List active background Kubernetes port-forward daemons."""
    from devops_cli.k8s.port_forward_daemon import get_daemon_manager

    mgr = get_daemon_manager()
    forwards = mgr.list_forwards()
    if not forwards:
        print_info("No active Kubernetes port-forward daemons running.")
        return

    columns: list[str | tuple[str, str]] = [
        ("PID", "bold"),
        "Service",
        "Namespace",
        "Local Port",
        "Remote Port",
        "Stack",
        "Started",
    ]
    rows: list[list[str]] = [
        [
            str(f.pid),
            f.service,
            f.namespace,
            f"{f.address}:{f.local_port}",
            str(f.remote_port),
            f.stack,
            f.started_at[:19],
        ]
        for f in forwards
    ]
    print_table("Active Kubernetes Port-Forward Daemons", columns=columns, rows=rows)


def port_forward_stop(
    service: Annotated[
        str | None, typer.Option("--service", "-s", help="Specific service to stop")
    ] = None,
) -> None:
    """Terminate active background Kubernetes port-forward daemons."""
    from devops_cli.k8s.port_forward_daemon import get_daemon_manager

    mgr = get_daemon_manager()
    stopped = mgr.stop_forwards(service_filter=service)
    print_success(f"✓ Terminated {stopped} active port-forward daemon(s)")


def service_url(
    service: Annotated[str, typer.Argument(help=HELP.k8s.proxy_service)],
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = "default",
    port: Annotated[str, typer.Option("--port", "-p", help=HELP.k8s.proxy_port)] = "http",
    path: Annotated[str, typer.Option("--path", help=HELP.k8s.proxy_path)] = "",
    tls: Annotated[bool, typer.Option("--tls", help=HELP.k8s.proxy_tls)] = False,
    fetch: Annotated[bool, typer.Option("--fetch", help=HELP.k8s.proxy_fetch)] = False,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.k8s.context_target)
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help=HELP.options.json_output)] = False,
) -> None:
    """Show, or fetch from, a cluster service address that needs no port-forward."""
    from devops_cli.k8s.service_http import get_json
    from devops_cli.k8s.service_proxy import (
        ServiceAddressError,
        ServiceRef,
        resolve_proxy_target,
    )

    request_path, _, request_query = path.partition("?")
    ref = ServiceRef(
        namespace=namespace,
        service=service,
        port=port,
        tls=tls,
        path=request_path,
        query=request_query,
    )

    if not fetch:
        try:
            target = resolve_proxy_target(ref, context=context)
            resolved = target.url
        except ServiceAddressError as exc:
            # The portable address is still worth printing: it is valid configuration even
            # when no cluster is reachable right now.
            print_warning(str(exc))
            resolved = ""
        if json_output:
            write_stdout(
                format_json({"address": ref.describe(), "proxy_url": resolved, "path": ref.path})
            )
            return
        print_table(
            "Cluster Service Address",
            ["Field", "Value"],
            [
                ["Configuration address", ref.describe()],
                ["API server proxy URL", resolved or "unresolved"],
            ],
        )
        return

    try:
        payload = get_json(ref.describe(), context=context)
    except ServiceAddressError as exc:
        print_error(str(exc))
        raise typer.Exit(1) from exc
    except Exception as exc:
        print_error(f"Request to {ref.describe()} failed: {exc}")
        raise typer.Exit(1) from exc

    write_stdout(format_json(payload))
