"""Kubernetes command group."""

from __future__ import annotations

import subprocess
from typing import Annotated, Any

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.cli import new_typer

app = new_typer(help="Kubernetes resource management.", no_args_is_help=True)
console = Console()


def _k8s_clients() -> tuple[Any, Any]:
    try:
        from kubernetes import client as k8s_client  # type: ignore[import-untyped]
        from kubernetes import config as k8s_config

        return k8s_config, k8s_client
    except Exception as exc:
        rprint(f"[red]kubernetes SDK unavailable: {exc}[/red]")
        raise typer.Exit(1)


@app.command()
def contexts() -> None:
    """List kubeconfig contexts and mark the active one."""
    k8s_config, _ = _k8s_clients()
    try:
        ctx_list, active = k8s_config.list_kube_config_contexts()
    except Exception as exc:
        rprint(f"[red]Failed to load kubeconfig: {exc}[/red]")
        raise typer.Exit(1)

    active_name = active["name"] if active else ""
    table = Table(title="Kubernetes Contexts")
    table.add_column("", width=2)
    table.add_column("Context", style="cyan")
    table.add_column("Cluster")
    table.add_column("User")

    for ctx in ctx_list:
        indicator = "[green]●[/green]" if ctx["name"] == active_name else ""
        table.add_row(
            indicator,
            ctx["name"],
            ctx["context"].get("cluster", ""),
            ctx["context"].get("user", ""),
        )
    console.print(table)


@app.command()
def status() -> None:
    """Show node and pod summary for the current context."""
    k8s_config, k8s_client = _k8s_clients()
    try:
        k8s_config.load_kube_config()
        v1 = k8s_client.CoreV1Api()
        nodes = v1.list_node()
    except Exception as exc:
        rprint(f"[red]Failed to query cluster: {exc}[/red]")
        raise typer.Exit(1)

    table = Table(title="Nodes")
    table.add_column("Name", style="cyan")
    table.add_column("Status")
    table.add_column("Roles")
    table.add_column("Version")

    for node in nodes.items:
        ready = next(
            (c.status for c in node.status.conditions if c.type == "Ready"),
            "Unknown",
        )
        roles = (
            ", ".join(
                k.replace("node-role.kubernetes.io/", "")
                for k in (node.metadata.labels or {})
                if k.startswith("node-role.kubernetes.io/")
            )
            or "worker"
        )
        table.add_row(
            node.metadata.name,
            "[green]Ready[/green]" if ready == "True" else "[red]NotReady[/red]",
            roles,
            node.status.node_info.kubelet_version,
        )
    console.print(table)


@app.command()
def apply(
    path: Annotated[str, typer.Argument(help="Manifest file or directory path")],
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
) -> None:
    """Apply a Kubernetes manifest (delegates to kubectl)."""
    cmd = ["kubectl", "apply", "-f", path]
    if dry_run:
        cmd += ["--dry-run=client"]
    if namespace:
        cmd += ["--namespace", namespace]
    subprocess.run(cmd, check=True)


@app.command()
def logs(
    pod: Annotated[str, typer.Argument(help="Pod name")],
    container: Annotated[str | None, typer.Option("--container", "-c")] = None,
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
    follow: Annotated[bool, typer.Option("--follow", "-f")] = False,
    tail: Annotated[int, typer.Option("--tail")] = 100,
) -> None:
    """Stream pod logs (delegates to kubectl)."""
    cmd = ["kubectl", "logs", pod, f"--tail={tail}"]
    if container:
        cmd += ["--container", container]
    if namespace:
        cmd += ["--namespace", namespace]
    if follow:
        cmd.append("--follow")
    subprocess.run(cmd, check=True)
