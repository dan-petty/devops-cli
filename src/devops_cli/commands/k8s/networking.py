"""Kubernetes service discovery, URL auto-configuration, and port-forwarding."""

from __future__ import annotations

import subprocess
from typing import Annotated, Any

import typer

import devops_cli.commands.k8s as k8s
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
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    format_k8s_service_targets_table,
    print,
    print_error,
    print_info,
    print_success,
    print_table,
)

VALID_STACKS: tuple[str, ...] = ("infra", "llm", "all")


def _resolve_stacks(stack: str) -> list[str]:
    s = stack.strip().lower()
    if s == "all":
        return ["infra", "llm"]
    if s in ("infra", "llm"):
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
        nodes_res = k8s.run_subprocess(
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
    except Exception:
        pass
    return None


def _detect_service_url(service: str, namespace: str, context: str | None = None) -> str | None:
    """Query service URL via minikube service or kubectl nodePort/cluster info."""
    # 1. Try minikube service if context is not explicit non-minikube
    if not context or context == "minikube":
        try:
            res = k8s.run_subprocess(
                ["minikube", "service", service, "-n", namespace, "--url"],
                capture_output=True,
                text=True,
                check=False,
                quiet=True,
                timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
            )
            if res.returncode == 0 and res.stdout.strip():
                url = _parse_minikube_service_url(res.stdout)
                if url:
                    return url
        except OSError, subprocess.SubprocessError:
            pass

    # 2. Generic K8s nodePort or loadBalancer detection via kubectl
    try:
        ctx_args = ["--context", context] if context else []
        svc_res = k8s.run_subprocess(
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
            spec = svc_data.get("spec", {})
            ports = spec.get("ports", [])
            node_port = ports[0].get("nodePort") if ports else None
            port_num = ports[0].get("port") if ports else None

            # Check LoadBalancer ingress IP
            ingress = svc_data.get("status", {}).get("loadBalancer", {}).get("ingress", [])
            if ingress:
                lb_host = ingress[0].get("ip") or ingress[0].get("hostname")
                if lb_host and port_num:
                    return f"http://{lb_host}:{port_num}"

            # Check NodePort
            if node_port:
                node_url = _resolve_k8s_node_port_url(ctx_args, int(node_port))
                if node_url:
                    return node_url
    except Exception:
        pass

    return None


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
    except Exception:
        return False


def _resolve_accessible_url(
    detected_url: str | None, preferred_localhost_ports: list[int] | None = None
) -> str | None:
    """Resolve service URL to ensure it is accessible from devcontainer / host OS environment."""
    if preferred_localhost_ports:
        for port in preferred_localhost_ports:
            candidate = f"http://localhost:{port}"
            if k8s._verify_url_reachability(candidate):
                return candidate

    if not detected_url:
        return None

    from urllib.parse import urlparse

    if k8s._verify_url_reachability(detected_url):
        return detected_url

    parsed = urlparse(detected_url)
    if parsed.port:
        localhost_url = f"{parsed.scheme}://localhost:{parsed.port}"
        if k8s._verify_url_reachability(localhost_url):
            return localhost_url

        loopback_url = f"{parsed.scheme}://127.0.0.1:{parsed.port}"
        if k8s._verify_url_reachability(loopback_url):
            return loopback_url

        return localhost_url

    return detected_url


def configure_urls(
    stack: Annotated[str, typer.Option("--stack", "-s", help=HELP.k8s.stack)] = DEFAULT_K8S_STACK,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
) -> None:
    """Auto-detect Kubernetes stack URLs and update CLI config."""
    if context:
        k8s._validate_k8s_identifier(context, "context")

    selected_stacks = k8s._resolve_stacks(stack)

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

    if not k8s._cluster_reachable(context=context):
        print_error(MESSAGES.k8s.cluster_not_reachable, prefix=False)
        raise typer.Exit(1)

    print_info(
        f"[bold]Detecting {stack} service URLs (context: {context or 'active'})...[/bold]",
        prefix=False,
    )

    from devops_cli.config.settings import dotted_set, load_settings, save_settings

    settings = load_settings()
    configured: dict[str, str] = {}

    if "infra" in selected_stacks:
        raw_argocd = k8s._detect_service_url("argocd-server", "argocd", context=context)
        raw_grafana = k8s._detect_service_url(
            "kube-prometheus-grafana", "monitoring", context=context
        )
        raw_prom = k8s._detect_service_url(
            "kube-prometheus-kube-prome-prometheus", "monitoring", context=context
        )
        raw_jaeger = k8s._detect_service_url("jaeger", "otel", context=context)

        argocd_url = k8s._resolve_accessible_url(raw_argocd, preferred_localhost_ports=[8080])
        grafana_url = k8s._resolve_accessible_url(
            raw_grafana, preferred_localhost_ports=[8030, 8000, 3000]
        )
        prom_url = k8s._resolve_accessible_url(raw_prom, preferred_localhost_ports=[8090, 9090])
        jaeger_url = k8s._resolve_accessible_url(raw_jaeger, preferred_localhost_ports=[16686])

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

    if "llm" in selected_stacks:
        raw_ollama = k8s._detect_service_url("ollama", "llm", context=context)
        raw_webui = k8s._detect_service_url("open-webui", "llm", context=context)
        raw_qdrant = k8s._detect_service_url("qdrant", "llm", context=context)
        raw_valkey = k8s._detect_service_url("valkey", "llm", context=context)

        ollama_url = k8s._resolve_accessible_url(raw_ollama, preferred_localhost_ports=[11434])
        webui_url = k8s._resolve_accessible_url(raw_webui, preferred_localhost_ports=[3000, 8080])
        qdrant_url = k8s._resolve_accessible_url(raw_qdrant, preferred_localhost_ports=[6333])
        valkey_url = k8s._resolve_accessible_url(raw_valkey, preferred_localhost_ports=[6379])

        if ollama_url:
            settings.ai.ollama_urls = [ollama_url]
            configured["ai.ollama_urls"] = ollama_url
        if webui_url:
            configured["open_webui.url"] = webui_url
        if qdrant_url:
            configured["qdrant.url"] = qdrant_url
        if valkey_url:
            configured["valkey.url"] = valkey_url

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

    if context:
        k8s._validate_k8s_identifier(context, "context")

    selected_stacks = k8s._resolve_stacks(stack)

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

    if not k8s._cluster_reachable(context=context):
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

    ctx_args = ["--context", context] if context else []
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
    k8s.configure_urls(stack=stack, context=context)


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
