"""Kubernetes cluster context inspection, switching, node status, and log commands."""

from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import typer

import devops_cli.commands.k8s as k8s
from devops_cli.config.defaults import DEFAULT_K8S_LOGS_TAIL, DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    format_k8s_contexts_table,
    format_k8s_nodes_table,
    print,
    print_error,
    print_success,
)


def contexts() -> None:
    """List kubeconfig contexts and mark the active one."""
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s contexts",
            action="list_kube_config_contexts",
            details={"contexts": ["minikube"], "active": "minikube"},
        )
        return
    k8s_config, _ = k8s._k8s_clients()
    try:
        ctx_list, active = k8s_config.list_kube_config_contexts()
    except Exception as exc:
        print_error(f"Failed to load kubeconfig: {exc}", prefix=False)
        raise typer.Exit(1)

    active_name = active["name"] if active else ""
    print(format_k8s_contexts_table(ctx_list, active_name=active_name))


def switch_context(
    name: Annotated[str, typer.Argument(help=HELP.k8s.context_target)],
) -> None:
    """Switch active kubeconfig context."""
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s switch-context",
            target=name,
            action="switch_kube_config_context",
            details={"target_context": name},
        )
        return

    k8s._validate_k8s_identifier(name, "context name")
    cmd = ["kubectl", "config", "use-context", name]
    k8s._run_cmd(cmd, check=True)
    msg = MESSAGES.k8s.switched_context.format(context=name)
    print_success(msg, prefix=False)


def status() -> None:
    """Show node and pod summary for the current context."""
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s status",
            action="query_k8s_status",
            details={"nodes": 1, "status": "Ready"},
        )
        return
    k8s_config, k8s_client = k8s._k8s_clients()
    try:
        k8s_config.load_kube_config()
        core_v1_api = k8s_client.CoreV1Api()
        nodes = core_v1_api.list_node()
    except Exception as exc:
        print_error(f"Failed to query cluster: {exc}", prefix=False)
        raise typer.Exit(1)

    print(format_k8s_nodes_table(nodes.items))


def apply(
    path: Annotated[str, typer.Argument(help=HELP.k8s.manifest_path)],
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
) -> None:
    """Apply a Kubernetes manifest (delegates to kubectl)."""
    if "://" in path:
        u = urlparse(path)
        if u.scheme not in ("http", "https"):
            raise KubernetesContextError(f"Unsupported manifest URL scheme: {u.scheme}")
        host = u.hostname or ""
        if not host:
            raise KubernetesContextError(f"Invalid manifest URL: {path}")
        if host.lower() in ("localhost", "127.0.0.1", "169.254.169.254", "::1"):
            raise KubernetesContextError(f"Manifest URL points to forbidden host: {host}")
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise KubernetesContextError(
                    f"Manifest URL points to private or reserved IP: {host}"
                )
        except ValueError:
            pass

        try:
            resolved_addrs = socket.getaddrinfo(host, None)
            for addr in resolved_addrs:
                ip_str = str(addr[4][0])
                resolved_ip = ipaddress.ip_address(ip_str)
                if (
                    resolved_ip.is_private
                    or resolved_ip.is_loopback
                    or resolved_ip.is_link_local
                    or resolved_ip.is_reserved
                ):
                    raise KubernetesContextError(
                        f"Manifest URL resolves to private or reserved IP: {ip_str} for host {host}"
                    )
        except (socket.gaierror, socket.herror) as err:
            raise KubernetesContextError(
                f"Failed to resolve manifest URL host '{host}': {err}"
            ) from err
    else:
        if ".." in Path(path).parts or ".." in path:
            raise KubernetesContextError(f"Path traversal detected in manifest path: {path}")

    if namespace:
        k8s._validate_k8s_identifier(namespace, "namespace", namespace=True)
    cmd = ["kubectl", "apply", "-f", path]
    if dry_run or is_dry_run():
        cmd += ["--dry-run=client"]
    if namespace:
        cmd += ["--namespace", namespace]
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s apply",
            target=path,
            action="kubectl_apply",
            details={"cmd": " ".join(cmd), "namespace": namespace},
        )
        return
    k8s._run_cmd(cmd, check=True)


def logs(
    pod: Annotated[str, typer.Argument(help=HELP.k8s.pod_name)],
    container: Annotated[
        str | None, typer.Option("--container", "-c", help=HELP.options.container)
    ] = None,
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
    follow: Annotated[bool, typer.Option("--follow", "-f", help=HELP.options.follow)] = False,
    tail: Annotated[int, typer.Option("--tail", help=HELP.options.tail)] = DEFAULT_K8S_LOGS_TAIL,
) -> None:
    """Stream pod logs (delegates to kubectl)."""
    k8s._validate_k8s_identifier(pod, "pod name")
    if container:
        k8s._validate_k8s_identifier(container, "container name")
    if namespace:
        k8s._validate_k8s_identifier(namespace, "namespace", namespace=True)
    bounded_tail = max(1, min(tail, 10000))
    cmd = ["kubectl", "logs", pod, f"--tail={bounded_tail}"]
    if container:
        cmd += ["--container", container]
    if namespace:
        cmd += ["--namespace", namespace]
    if follow:
        cmd.append("--follow")
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s logs",
            target=pod,
            action="kubectl_logs",
            details={"cmd": " ".join(cmd), "pod": pod, "tail": bounded_tail},
        )
        return
    if follow:
        k8s.run_subprocess(
            cmd,
            check=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
            capture_output=False,
        )
    else:
        k8s._run_cmd(cmd, check=True)
