"""Planned request builders for Kubernetes cluster read and access commands.

A dry run makes zero external requests and returns the ordered PlannedRequest items.
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence

from devops_cli.config.commands import (
    BIN_KUBECTL,
    BIN_STERN,
    build_kubectl_cmd,
    build_popeye_cmd,
    build_stern_cmd,
)
from devops_cli.config.defaults import DEFAULT_LOKI_URL
from devops_cli.dry_run.requests import PlannedRequest


def plan_k8s_audit(
    context: str | None = None,
    namespace: str | None = None,
) -> list[PlannedRequest]:
    """Plan external Popeye execution for Kubernetes cluster resource audit."""
    argv = tuple(build_popeye_cmd(context=context, namespace=namespace))
    return [
        PlannedRequest(
            method="popeye",
            target="cluster",
            argv=argv,
        )
    ]


def plan_k8s_contexts() -> list[PlannedRequest]:
    """Plan kubeconfig context listing."""
    return [
        PlannedRequest(
            method="kubernetes.config",
            target="list_kube_config_contexts",
        )
    ]


def plan_k8s_status() -> list[PlannedRequest]:
    """Plan cluster node query via Kubernetes API."""
    return [
        PlannedRequest(
            method="kubernetes.client.CoreV1Api",
            target="list_node",
        )
    ]


def plan_k8s_switch_context(name: str, should_autostart: bool = False) -> list[PlannedRequest]:
    """Plan switching active context and optional minikube autostart."""
    requests: list[PlannedRequest] = []
    if should_autostart:
        requests.append(
            PlannedRequest(
                method="minikube",
                target="start",
                argv=("minikube", "start"),
                condition="minikube not running",
            )
        )
    requests.append(
        PlannedRequest(
            method="kubectl",
            target="config use-context",
            argv=("kubectl", "config", "use-context", name),
        )
    )
    return requests


def plan_k8s_pods(
    namespace: str | None = None,
    label: str | None = None,
    all_namespaces: bool = False,
) -> list[PlannedRequest]:
    """Plan pod listing via Kubernetes API."""
    if all_namespaces:
        target = "list_pod_for_all_namespaces"
        if label:
            target += f" [label={label}]"
    else:
        target = f"list_namespaced_pod(namespace={namespace or 'default'})"
        if label:
            target += f" [label={label}]"
    return [
        PlannedRequest(
            method="kubernetes.client.CoreV1Api",
            target=target,
        )
    ]


def plan_k8s_logs(
    pod: str,
    container: str | None = None,
    namespace: str | None = None,
    tail: int = 100,
    follow: bool = False,
    query: str | None = None,
    loki_url: str | None = None,
) -> list[PlannedRequest]:
    """Plan pod log retrieval either via Loki HTTP query or kubectl logs."""
    if query:
        url = loki_url or DEFAULT_LOKI_URL
        return [
            PlannedRequest(
                method="GET",
                target=f"{url.rstrip('/')}/loki/api/v1/query_range?query={query}",
            )
        ]

    bounded_tail = max(1, min(tail, 10000))
    cmd = ["kubectl", "logs", pod, f"--tail={bounded_tail}"]
    if container:
        cmd.extend(["-c", container])
    if namespace:
        cmd.extend(["-n", namespace])
    if follow:
        cmd.append("-f")
    return [
        PlannedRequest(
            method="kubectl",
            target="logs",
            argv=tuple(cmd),
        )
    ]


def plan_k8s_stream_logs(
    pod_query: str,
    namespace: str | None = None,
    container: str | None = None,
    tail: int = 100,
    follow: bool = False,
) -> list[PlannedRequest]:
    """Plan parallel pod log streaming via Stern or kubectl."""
    if shutil.which(BIN_STERN):
        cmd = build_stern_cmd(
            pod_query=pod_query,
            namespace=namespace,
            container=container,
            tail_lines=tail,
            follow=follow,
        )
        return [
            PlannedRequest(
                method="stern",
                target="logs",
                argv=tuple(cmd),
            )
        ]
    k_args = ["logs", "-l", f"app={pod_query}", f"--tail={tail}"]
    if namespace:
        k_args.extend(["-n", namespace])
    if container:
        k_args.extend(["-c", container])
    if follow:
        k_args.append("-f")
    cmd = build_kubectl_cmd(k_args)
    return [
        PlannedRequest(
            method="kubectl",
            target="logs",
            argv=tuple(cmd),
        )
    ]


def plan_k8s_security_stream(
    namespace: str,
    label: str,
    tail: int = 100,
    follow: bool = False,
) -> list[PlannedRequest]:
    """Plan Falco probe security event streaming via kubectl."""
    cmd = ["kubectl", "logs", "-n", namespace, "-l", label, "--tail", str(tail)]
    if follow:
        cmd.append("-f")
    return [
        PlannedRequest(
            method="kubectl",
            target="logs",
            argv=tuple(cmd),
        )
    ]


def plan_k8s_rbac_audit(namespace: str | None = None) -> list[PlannedRequest]:
    """Plan RBAC role and binding retrieval via kubectl."""
    scope = ["-n", namespace] if namespace else ["--all-namespaces"]
    cmd_bindings = [BIN_KUBECTL, "get", "clusterrolebindings,rolebindings", "-o", "json", *scope]
    cmd_roles = [BIN_KUBECTL, "get", "clusterroles,roles", "-o", "json", *scope]
    return [
        PlannedRequest(
            method="kubectl",
            target="get rbac bindings",
            argv=tuple(cmd_bindings),
        ),
        PlannedRequest(
            method="kubectl",
            target="get rbac roles",
            argv=tuple(cmd_roles),
        ),
    ]


def plan_k8s_port_forward(
    services: Sequence[tuple[str, str, int, int]],
    effective_context: str | None = None,
    address: str = "127.0.0.1",
) -> list[PlannedRequest]:
    """Plan kubectl port-forward daemon processes for services."""
    ctx_args = ["--context", effective_context] if effective_context else []
    requests: list[PlannedRequest] = []
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
            *ctx_args,
        ]
        requests.append(
            PlannedRequest(
                method="kubectl",
                target=f"port-forward {svc}",
                argv=tuple(cmd),
            )
        )
    return requests


def plan_k8s_service_url(
    address_desc: str,
    proxy_url: str | None = None,
    fetch: bool = False,
) -> list[PlannedRequest]:
    """Plan cluster service URL resolution or proxy fetch."""
    if fetch:
        target = proxy_url or address_desc
        return [
            PlannedRequest(
                method="GET",
                target=target,
            )
        ]
    return [
        PlannedRequest(
            method="resolve",
            target=address_desc,
        )
    ]
