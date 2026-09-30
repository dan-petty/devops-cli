"""Kubernetes service discovery, URL auto-configuration, and port-forwarding."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Iterable, Sequence
from typing import Annotated, Any

import typer

import devops_cli.commands.k8s.cluster_runtime as runtime
from devops_cli.config.constants import (
    CONST_ADDRESSING_FQDN,
    CONST_ADDRESSING_INGRESS,
    CONST_ADDRESSING_MODES,
    CONST_ADDRESSING_NODEPORT,
    CONST_ADDRESSING_PROXY,
    CONST_AI_GATEWAY_PROVIDER,
    CONST_K8S_URL_SCHEME,
    CONST_LOCAL_DOMAIN_SUFFIXES,
    CONST_LOCAL_HOSTNAMES,
    CONST_PLACEHOLDER_NODE,
    CONST_PLACEHOLDER_PORT,
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


def _is_node_ready(item: dict[str, Any]) -> bool:
    """Return True if node Ready condition is True or conditions are omitted."""
    conditions = item.get("status", {}).get("conditions")
    if not conditions:
        return True
    return any(cond.get("type") == "Ready" and cond.get("status") == "True" for cond in conditions)


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
                if _is_node_ready(item):
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


def _is_fqdn_url(url: str | None) -> bool:
    """Check whether a URL points to a non-loopback, non-IP fully-qualified domain name."""
    if not url:
        return False
    try:
        import ipaddress
        from urllib.parse import urlparse

        host = urlparse(url).hostname
        if not host or "." not in host:
            return False
        host_lower = host.lower()
        if host_lower in CONST_LOCAL_HOSTNAMES or any(
            host_lower.endswith(suffix) for suffix in CONST_LOCAL_DOMAIN_SUFFIXES
        ):
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            return True
    except Exception:
        return False


def _should_update_url(
    existing_url: str | None,
    new_url: str | None,
    default_url: str | None = None,
) -> bool:
    """Determine whether a detected service URL should update existing configuration."""
    from urllib.parse import urlparse

    if not new_url:
        return False
    if not existing_url or existing_url == default_url or existing_url == new_url:
        return True
    if _is_fqdn_url(existing_url) and not _is_fqdn_url(new_url):
        return False
    existing_host = urlparse(existing_url).hostname or ""
    new_host = urlparse(new_url).hostname or ""
    return not (existing_host not in CONST_LOCAL_HOSTNAMES and new_host in CONST_LOCAL_HOSTNAMES)


def _apply_service_url(
    settings: Any,
    configured: dict[str, str],
    key: str,
    new_url: str | None,
    existing_url: str | None,
    default_url: str | None = None,
) -> None:
    """Set configured service URL on settings if update criteria are satisfied."""
    from devops_cli.config.settings import dotted_set

    if new_url and _should_update_url(existing_url, new_url, default_url=default_url):
        dotted_set(settings, key, new_url)
        configured[key] = new_url


def _update_ollama_urls(
    settings: Any,
    configured: dict[str, str],
    ollama_url: str | None,
) -> None:
    """Update settings.ai.ollama_urls preserving existing custom non-loopback endpoints."""
    from urllib.parse import urlparse

    from devops_cli.config.defaults import DEFAULT_OLLAMA_URLS

    if not ollama_url:
        return
    existing = list(settings.ai.ollama_urls or [])
    is_loopback = (urlparse(ollama_url).hostname or "") in ("localhost", "127.0.0.1", "::1")
    if not existing or existing == list(DEFAULT_OLLAMA_URLS):
        settings.ai.ollama_urls = [ollama_url]
        configured["ai.ollama_urls"] = ollama_url
    elif ollama_url in existing:
        configured["ai.ollama_urls"] = ", ".join(existing)
    elif not is_loopback:
        settings.ai.ollama_urls.append(ollama_url)
        configured["ai.ollama_urls"] = ", ".join(settings.ai.ollama_urls)


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
        if _verify_url_reachability(detected_url):
            return detected_url

    preferred = _check_preferred_ports(scheme, preferred_localhost_ports)
    if preferred:
        return preferred

    if detected_url:
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
    from urllib.parse import urlparse

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

    _apply_service_url(
        settings, configured, "argocd.url", argocd_url, getattr(settings.argocd, "url", None)
    )
    _apply_service_url(
        settings, configured, "grafana.url", grafana_url, getattr(settings.grafana, "url", None)
    )
    _apply_service_url(
        settings, configured, "prometheus.url", prom_url, getattr(settings.prometheus, "url", None)
    )
    if jaeger_url and _should_update_url(getattr(settings.jaeger, "url", None), jaeger_url):
        dotted_set(settings, "jaeger.url", jaeger_url)
        configured["jaeger.url"] = jaeger_url
        j_host = urlparse(jaeger_url).hostname or "localhost"
        otel_url = f"http://{j_host}:4318"
        telemetry_endpoint = getattr(getattr(settings, "telemetry", None), "endpoint", None)
        if _should_update_url(telemetry_endpoint, otel_url):
            dotted_set(settings, "otel.endpoint", otel_url)
            configured["otel.endpoint"] = otel_url


def _should_update_valkey(settings: Any, valkey_url: str | None) -> bool:
    """Determine whether detected valkey_url should update valkey host/port configuration."""
    from urllib.parse import urlparse

    from devops_cli.config.constants import CONST_LOCAL_HOSTNAMES

    if not valkey_url:
        return False
    valkey_cfg = getattr(settings, "valkey", None)
    if valkey_cfg is None:
        return True

    existing_url = getattr(valkey_cfg, "url", None)
    if existing_url and not _should_update_url(existing_url, valkey_url):
        return False

    existing_host_raw = getattr(valkey_cfg, "host", "") or ""
    existing_host = existing_host_raw.split(":")[0].strip().lower()
    new_host = (urlparse(valkey_url).hostname or "").strip().lower()
    if (
        existing_host
        and existing_host not in CONST_LOCAL_HOSTNAMES
        and new_host in CONST_LOCAL_HOSTNAMES
    ):
        return False
    return True


def _configure_llm_stack_urls(
    effective_context: str | None,
    settings: Any,
    configured: dict[str, str],
) -> None:
    """Detect and configure accessible URLs for LLM stack services."""
    from urllib.parse import urlparse

    from devops_cli.config.defaults import DEFAULT_QDRANT_URL
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

    _update_ollama_urls(settings, configured, ollama_url)
    _apply_service_url(
        settings, configured, "open_webui.url", webui_url, getattr(settings.open_webui, "url", None)
    )
    _apply_service_url(
        settings,
        configured,
        "qdrant.url",
        qdrant_url,
        getattr(settings.qdrant, "url", None),
        default_url=DEFAULT_QDRANT_URL,
    )
    if valkey_url and _should_update_valkey(settings, valkey_url):
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


# The endpoints nodeport addressing writes, per stack. Proxy addressing derives its own
# from `_PROXY_TARGETS_*`, which is why the two previews differ: proxy mode configures only
# the services it can address through the API server.
_NODEPORT_KEYS_INFRA: tuple[str, ...] = (
    "argocd.url",
    "grafana.url",
    "prometheus.url",
    "jaeger.url",
    "otel.endpoint",
)
_NODEPORT_KEYS_LLM: tuple[str, ...] = (
    "ai.ollama_urls",
    "open_webui.url",
    "qdrant.url",
    "valkey.url",
)


def _preview_proxy_addresses(stacks: Sequence[str]) -> dict[str, str]:
    """Render the cluster-native address each key will receive."""
    targets: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = []
    if "infra" in stacks:
        targets.extend(_PROXY_TARGETS_INFRA)
    if "llm" in stacks:
        targets.extend(_PROXY_TARGETS_LLM)

    preview: dict[str, str] = {}
    for key, namespace, patterns, port_hints in targets:
        port = next((hint for hint in port_hints if hint.isdigit()), CONST_PLACEHOLDER_PORT)
        preview[key] = f"{CONST_K8S_URL_SCHEME}://{namespace}/{patterns[0]}:{port}"
    return preview


def _preview_nodeport_addresses(stacks: Sequence[str]) -> dict[str, str]:
    """Render the shape of a node address, which is only known after discovery.

    A fixed address was written here -- a minikube node IP with assigned port numbers --
    so the preview described a cluster the command was not going to configure, and did so
    identically whichever addressing mode was asked for.
    """
    keys: list[str] = []
    if "infra" in stacks:
        keys.extend(_NODEPORT_KEYS_INFRA)
    if "llm" in stacks:
        keys.extend(_NODEPORT_KEYS_LLM)

    preview: dict[str, str] = {}
    for key in keys:
        scheme = "tcp" if key.startswith("valkey") else "http"
        preview[key] = f"{scheme}://{CONST_PLACEHOLDER_NODE}:{CONST_PLACEHOLDER_PORT}"
    return preview


def _record_host_for_service(
    svc_hosts: dict[str, list[str]],
    svc_name: str,
    host: str,
    namespace: str | None = None,
) -> None:
    """Append host to service entry and optional namespace-qualified entry."""
    hosts = svc_hosts.setdefault(svc_name, [])
    if host not in hosts:
        hosts.append(host)
    if namespace:
        ns_hosts = svc_hosts.setdefault(f"{namespace}:{svc_name}", [])
        if host not in ns_hosts:
            ns_hosts.append(host)


def _extract_rule_hosts(
    rules: list[dict[str, Any]],
    svc_hosts: dict[str, list[str]],
    namespace: str | None = None,
) -> None:
    """Extract backend service host mappings from ingress rules."""
    for rule in rules:
        host = rule.get("host")
        if not host:
            continue
        for path_entry in rule.get("http", {}).get("paths", []):
            svc_name = path_entry.get("backend", {}).get("service", {}).get("name")
            if svc_name:
                _record_host_for_service(svc_hosts, svc_name, host, namespace)


def _discover_ingress_hosts(effective_ctx: str | None = None) -> dict[str, list[str]]:
    """Discover service-to-hostname mappings from Kubernetes Ingress resources."""
    import json

    ctx_args = ["--context", effective_ctx] if effective_ctx else []
    try:
        res = runtime.run_subprocess(
            ["kubectl", "get", "ingress", "-A", "-o", "json"] + ctx_args,
            capture_output=True,
            text=True,
            check=False,
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
        if res.returncode != 0 or not res.stdout.strip():
            return {}
        svc_hosts: dict[str, list[str]] = {}
        for item in json.loads(res.stdout).get("items", []):
            ns = item.get("metadata", {}).get("namespace")
            _extract_rule_hosts(item.get("spec", {}).get("rules", []), svc_hosts, namespace=ns)
        return svc_hosts
    except Exception as exc:
        logger.debug("Failed discovering Ingress hosts: %s", exc)
        return {}


def _select_best_ingress_host(hosts: list[str], preferred_domain: str | None = None) -> str | None:
    """Select the best Ingress hostname matching preferred domain or the first available."""
    if not hosts:
        return None
    if preferred_domain:
        norm = preferred_domain.strip().lower().lstrip(".")
        for h in hosts:
            if h.lower().endswith(norm):
                return h
    return hosts[0]


def _ingress_matches(key: str, hosts: list[str], service_pattern: str) -> bool:
    """Check if service pattern matches ingress key or any of its hostnames."""
    return service_pattern in key or any(service_pattern in h for h in hosts)


def _search_ingress_hosts(
    items: Iterable[tuple[str, list[str]]],
    service_pattern: str,
    preferred_domain: str | None,
) -> str | None:
    """Search ingress items for matching service pattern and return https URL if found."""
    for key, hosts in items:
        if _ingress_matches(key, hosts, service_pattern):
            chosen = _select_best_ingress_host(hosts, preferred_domain=preferred_domain)
            if chosen:
                return f"https://{chosen}"
    return None


def _find_service_ingress_url(
    service_pattern: str,
    ingress_map: dict[str, list[str]],
    preferred_domain: str | None = None,
    namespace: str | None = None,
) -> str | None:
    """Find and construct HTTPS endpoint for a service pattern from discovered ingress hosts."""
    if namespace:
        prefix = f"{namespace}:"
        ns_items = ((k, v) for k, v in ingress_map.items() if k.startswith(prefix))
        found = _search_ingress_hosts(ns_items, service_pattern, preferred_domain)
        if found:
            return found
    return _search_ingress_hosts(ingress_map.items(), service_pattern, preferred_domain)


_FQDN_TARGETS_INFRA: tuple[tuple[str, str], ...] = (
    ("argocd.url", "argocd"),
    ("grafana.url", "grafana"),
    ("prometheus.url", "prome-prometheus"),
)
_FQDN_TARGETS_LLM: tuple[tuple[str, str], ...] = (
    ("open_webui.url", "open-webui"),
    ("qdrant.url", "qdrant"),
)


def _apply_fqdn_targets(
    settings: Any,
    configured: dict[str, str],
    ingress_map: dict[str, list[str]],
    domain: str | None,
    targets: Sequence[tuple[str, str]],
) -> None:
    """Apply resolved FQDN ingress URLs for specified service targets."""
    for key, pattern in targets:
        url = _find_service_ingress_url(pattern, ingress_map, preferred_domain=domain)
        if url:
            _apply_service_url(
                settings,
                configured,
                key,
                url,
                getattr(getattr(settings, key.split(".")[0], None), "url", None),
            )


def _update_task_gateway_urls(settings: Any, full_gw: str) -> None:
    """Update gateway URL for tasks explicitly configured with the gateway provider."""
    from devops_cli.config.settings import dotted_set

    tasks_cfg = getattr(getattr(settings, "ai", None), "tasks", None)
    if not tasks_cfg:
        return
    for task_name in ("analysis", "chat"):
        task_cfg = getattr(tasks_cfg, task_name, None)
        if task_cfg and getattr(task_cfg, "provider", None) == CONST_AI_GATEWAY_PROVIDER:
            if _should_update_url(getattr(task_cfg, "api_base_url", None), full_gw):
                dotted_set(settings, f"ai.tasks.{task_name}.api_base_url", full_gw)


def _configure_fqdn_gateway(
    settings: Any,
    configured: dict[str, str],
    ingress_map: dict[str, list[str]],
    domain: str | None,
) -> None:
    """Configure AI gateway URL from discovered ingress endpoints."""
    from devops_cli.config.settings import dotted_set

    gw_url = _find_service_ingress_url(
        "ai", ingress_map, preferred_domain=domain, namespace="llm"
    ) or _find_service_ingress_url(
        "llm-gateway", ingress_map, preferred_domain=domain, namespace="llm"
    )
    if gw_url:
        full_gw = f"{gw_url}/v1"
        existing_gw = getattr(getattr(settings, "ai", None), "gateway_url", None)
        if _should_update_url(existing_gw, full_gw):
            dotted_set(settings, "ai.gateway_url", full_gw)
            configured["ai.gateway_url"] = full_gw
        _update_task_gateway_urls(settings, full_gw)


def _configure_fqdn_urls(
    effective_context: str | None,
    settings: Any,
    configured: dict[str, str],
    stacks: Sequence[str],
) -> None:
    """Detect Ingress hosts and configure domain-based FQDN service URLs."""
    ingress_map = _discover_ingress_hosts(effective_context)
    if not ingress_map:
        return

    domain = getattr(getattr(settings, "k8s", None), "domain", None) or getattr(
        getattr(settings, "cloudflare", None), "domain", None
    )

    if "infra" in stacks:
        _apply_fqdn_targets(settings, configured, ingress_map, domain, _FQDN_TARGETS_INFRA)
    if "llm" in stacks:
        _apply_fqdn_targets(settings, configured, ingress_map, domain, _FQDN_TARGETS_LLM)
        _configure_fqdn_gateway(settings, configured, ingress_map, domain)


def _preview_fqdn_addresses(stacks: Sequence[str]) -> dict[str, str]:
    """Render the domain-based FQDN address each key will receive in dry-run mode."""
    preview: dict[str, str] = {}
    if "infra" in stacks:
        preview.update(
            {
                "argocd.url": "https://argocd.example.com",
                "grafana.url": "https://grafana.example.com",
                "prometheus.url": "https://prometheus.example.com",
            }
        )
    if "llm" in stacks:
        preview.update(
            {
                "open_webui.url": "https://chat.example.com",
                "qdrant.url": "https://qdrant.example.com",
                "ai.gateway_url": "https://ai.example.com/v1",
            }
        )
    return preview


def _dry_run_preview(stacks: Sequence[str], addressing: str) -> dict[str, str]:
    """Describe what `configure-urls` would write under the requested addressing mode."""
    if addressing in (CONST_ADDRESSING_FQDN, CONST_ADDRESSING_INGRESS):
        return _preview_fqdn_addresses(stacks)
    if addressing == CONST_ADDRESSING_PROXY:
        return _preview_proxy_addresses(stacks)
    return _preview_nodeport_addresses(stacks)


def _dispatch_nodeport_urls(
    effective_ctx: str | None,
    settings: Any,
    configured: dict[str, str],
    stacks: Sequence[str],
) -> None:
    """Configure URLs in nodeport mode."""
    if "infra" in stacks:
        _configure_infra_stack_urls(effective_ctx, settings, configured)
    if "llm" in stacks:
        _configure_llm_stack_urls(effective_ctx, settings, configured)


def _dispatch_addressing_configuration(
    effective_ctx: str | None,
    settings: Any,
    configured: dict[str, str],
    stacks: Sequence[str],
    addressing: str,
) -> None:
    """Route service URL configuration to the appropriate addressing handler."""
    if addressing in (CONST_ADDRESSING_FQDN, CONST_ADDRESSING_INGRESS):
        _configure_fqdn_urls(effective_ctx, settings, configured, stacks)
    elif addressing == CONST_ADDRESSING_PROXY:
        _configure_proxy_urls(effective_ctx, settings, configured, stacks)
    else:
        _dispatch_nodeport_urls(effective_ctx, settings, configured, stacks)


def _resolve_effective_addressing(addressing: str | None, settings: Any) -> str:
    """Determine effective addressing mode from CLI argument or settings defaults."""
    if addressing is not None:
        return addressing
    configured_mode = getattr(getattr(settings, "k8s", None), "addressing", None)
    if configured_mode in CONST_ADDRESSING_MODES:
        return str(configured_mode)
    if getattr(getattr(settings, "k8s", None), "domain", None):
        return CONST_ADDRESSING_FQDN
    return CONST_ADDRESSING_NODEPORT


def configure_urls(
    stack: Annotated[str, typer.Option("--stack", "-s", help=HELP.k8s.stack)] = DEFAULT_K8S_STACK,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
    addressing: Annotated[
        str | None, typer.Option("--addressing", "-a", help=HELP.k8s.addressing)
    ] = None,
) -> None:
    """Auto-detect Kubernetes stack URLs and update CLI config."""
    settings = load_settings()
    effective_addressing = _resolve_effective_addressing(addressing, settings)
    if effective_addressing not in CONST_ADDRESSING_MODES:
        print_error(
            f"Unknown addressing mode '{effective_addressing}'. Choose one of: "
            f"{', '.join(sorted(CONST_ADDRESSING_MODES))}."
        )
        raise typer.Exit(2)
    effective_context = runtime.resolve_effective_context(context)
    if effective_context:
        runtime._validate_kubeconfig_context_name(effective_context, "context")

    selected_stacks = _resolve_stacks(stack)

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s configure-urls",
            action="configure_monitoring_urls",
            details=_dry_run_preview(selected_stacks, effective_addressing),
        )
        return

    if not runtime._cluster_reachable(context=effective_context):
        print_error(MESSAGES.k8s.cluster_not_reachable, prefix=False)
        raise typer.Exit(1)

    print_info(
        f"[bold]Detecting {stack} service URLs (context: {effective_context or 'active'})...[/bold]",
        prefix=False,
    )

    configured: dict[str, str] = {}
    _dispatch_addressing_configuration(
        effective_context, settings, configured, selected_stacks, effective_addressing
    )

    if configured:
        save_settings(settings)

    print(format_k8s_service_targets_table(configured, stack))


def _build_port_forward_details(
    selected_stacks: Sequence[str],
    ports: dict[str, int],
) -> dict[str, str]:
    """Build key-to-URL mappings for port-forward dry run output."""
    details: dict[str, str] = {}
    if "infra" in selected_stacks:
        details.update(
            {
                "argocd.url": f"http://localhost:{ports['argocd']}",
                "grafana.url": f"http://localhost:{ports['grafana']}",
                "prometheus.url": f"http://localhost:{ports['prometheus']}",
                "jaeger.url": f"http://localhost:{ports['jaeger']}",
                "otel.endpoint": f"http://localhost:{ports['otel']}",
            }
        )
    if "llm" in selected_stacks:
        details.update(
            {
                "ollama.url": f"http://localhost:{ports['ollama']}",
                "open_webui.url": f"http://localhost:{ports['open_webui']}",
                "qdrant.url": f"http://localhost:{ports['qdrant']}",
                "valkey.url": f"tcp://localhost:{ports['valkey']}",
            }
        )
    return details


def _collect_port_forward_services(
    selected_stacks: Sequence[str],
    ports: dict[str, int],
) -> list[tuple[str, str, int, int]]:
    """Build list of (namespace, service, local_port, remote_port) for port forwarding."""
    services: list[tuple[str, str, int, int]] = []
    if "infra" in selected_stacks:
        services.extend(
            [
                ("argocd", "svc/argocd-server", ports["argocd"], 80),
                ("monitoring", "svc/kube-prometheus-grafana", ports["grafana"], 80),
                (
                    "monitoring",
                    "svc/kube-prometheus-kube-prome-prometheus",
                    ports["prometheus"],
                    9090,
                ),
                ("otel", "svc/jaeger", ports["jaeger"], 16686),
                ("otel", "svc/jaeger", ports["otel"], 4318),
            ]
        )
    if "llm" in selected_stacks:
        services.extend(
            [
                ("llm", "svc/ollama", ports["ollama"], 11434),
                ("llm", "svc/open-webui", ports["open_webui"], 8080),
                ("llm", "svc/qdrant", ports["qdrant"], 6333),
                ("llm", "svc/valkey", ports["valkey"], 6379),
            ]
        )
    return services


def _launch_port_forwards(
    services: list[tuple[str, str, int, int]],
    effective_context: str | None,
    address: str,
    stack: str,
) -> None:
    """Launch detached kubectl port-forward processes and record active daemons."""
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
        # Its own session, so the forward outlives the command that started it and does
        # not take a terminal's SIGINT along with the CLI. `devops k8s port-forward status`
        # lists these as background daemons, which is only true if they are detached.
        proc = subprocess.Popen(  # nosec B603
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
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
    update_config: Annotated[
        bool,
        typer.Option(
            "--update-config/--no-update-config",
            help=HELP.k8s.update_config_flag,
        ),
    ] = False,
) -> None:
    """Port-forward k8s monitoring / LLM stack services to localhost ports."""
    import time

    effective_context = runtime.resolve_effective_context(context)
    if effective_context:
        runtime._validate_kubeconfig_context_name(effective_context, "context")

    selected_stacks = _resolve_stacks(stack)
    ports = {
        "argocd": argocd_port,
        "grafana": grafana_port,
        "prometheus": prometheus_port,
        "jaeger": jaeger_port,
        "otel": otel_port,
        "ollama": ollama_port,
        "open_webui": open_webui_port,
        "qdrant": qdrant_port,
        "valkey": valkey_port,
    }

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s port-forward",
            action="k8s_port_forward",
            details=_build_port_forward_details(selected_stacks, ports),
        )
        return

    if not runtime._cluster_reachable(context=effective_context):
        print_error(MESSAGES.k8s.cluster_not_reachable, prefix=False)
        raise typer.Exit(1)

    print_info(
        f"[bold cyan]Port-forwarding k8s {stack} services to localhost ports...[/bold cyan]",
        prefix=False,
    )
    services = _collect_port_forward_services(selected_stacks, ports)
    _launch_port_forwards(services, effective_context, address, stack)
    time.sleep(1.0)
    if update_config:
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
