"""Kubernetes diagnostics, stern/kubectl multi-pod log streaming, Helm 3-way diffing, and chaos experiments."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_K8S_NAMESPACE,
)
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import HELP
from devops_cli.output import (
    format_json,
    write_stdout,
)

# =============================================================================
# Helper: parse kubectl pods output
# =============================================================================


def _parse_pod_age(created_at: str) -> str:
    """Convert an ISO-8601 creation timestamp to a concise age string."""
    try:
        created = datetime.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.UTC)
        delta = now - created
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        if delta.days > 0:
            return f"{delta.days}d{hours}h"
        if hours > 0:
            return f"{hours}h{minutes}m"
        if minutes > 0:
            return f"{minutes}m{seconds}s"
        return f"{seconds}s"
    except Exception:
        return "—"


def _build_pods_table(
    namespace: str | None,
    label_selector: str | None,
    all_namespaces: bool,
) -> Any:
    """Build a Rich Table of Kubernetes pod status using the kubernetes SDK."""
    from rich.table import Table

    table = Table(title="Kubernetes Pods", show_header=True, header_style="bold cyan")
    table.add_column("Namespace", style="dim")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Status")
    table.add_column("Ready", justify="center")
    table.add_column("Restarts", justify="right")
    table.add_column("Age", justify="right")

    try:
        from kubernetes import client as k8s_client  # type: ignore[import-untyped]
        from kubernetes import config as k8s_config

        try:
            k8s_config.load_incluster_config()
        except Exception:
            k8s_config.load_kube_config()

        v1 = k8s_client.CoreV1Api()
        kwargs: dict[str, Any] = {}
        if label_selector:
            kwargs["label_selector"] = label_selector

        if all_namespaces:
            pod_list = v1.list_pod_for_all_namespaces(**kwargs)
        else:
            ns = namespace or "default"
            pod_list = v1.list_namespaced_pod(namespace=ns, **kwargs)

        for pod in pod_list.items:
            pod_ns = pod.metadata.namespace or "default"
            pod_name = pod.metadata.name or "—"
            phase = pod.status.phase or "Unknown"
            created_at = (
                pod.metadata.creation_timestamp.isoformat()
                if pod.metadata.creation_timestamp
                else ""
            )
            containers = pod.spec.containers or []
            ready_containers = sum(1 for cs in (pod.status.container_statuses or []) if cs.ready)
            restarts = sum(cs.restart_count for cs in (pod.status.container_statuses or []))
            status_color = (
                "green" if phase == "Running" else ("yellow" if phase == "Pending" else "red")
            )
            table.add_row(
                pod_ns,
                pod_name,
                f"[{status_color}]{phase}[/{status_color}]",
                f"{ready_containers}/{len(containers)}",
                str(restarts),
                _parse_pod_age(created_at),
            )
    except Exception as exc:
        table.add_row("—", f"[red]Error: {exc}[/red]", "—", "—", "—", "—")

    return table


# =============================================================================
# Command: devops k8s pods
# =============================================================================


def pods_cmd(
    namespace: Annotated[
        str | None,
        typer.Option("--namespace", "-n", help=HELP.options.namespace),
    ] = None,
    label: Annotated[
        str | None,
        typer.Option("--label", "-l", help=HELP.k8s.label_selector),
    ] = None,
    all_namespaces: Annotated[
        bool,
        typer.Option("--all-namespaces", "-A", help=HELP.k8s.all_namespaces),
    ] = False,
    watch: Annotated[
        bool,
        typer.Option("--watch", "-w", help=HELP.k8s.watch),
    ] = False,
    interval: Annotated[
        float,
        typer.Option("--interval", "-i", help=HELP.k8s.interval),
    ] = 3.0,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """List running pods with health status, restart counts, and age."""
    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops k8s pods",
            action="list_k8s_pods",
            details={
                "namespace": namespace,
                "label": label,
                "all_namespaces": all_namespaces,
                "watch": watch,
                "interval": interval,
            },
        )
        return

    if watch:
        from devops_cli.watchers.live_resource import LiveResourceWatcher

        watcher = LiveResourceWatcher(
            lambda: _build_pods_table(namespace, label, all_namespaces),
            interval_seconds=interval,
            name="k8s_pods",
        )
        watcher.watch()
    else:
        from rich import get_console

        get_console().print(_build_pods_table(namespace, label, all_namespaces))


def stream_logs_cmd(
    pod_query: Annotated[
        str,
        typer.Argument(help=HELP.k8s.pod_query),
    ],
    namespace: Annotated[
        str | None,
        typer.Option("--namespace", "-n", help=HELP.options.namespace),
    ] = None,
    container: Annotated[
        str | None,
        typer.Option("--container", "-c", help=HELP.options.container),
    ] = None,
    tail: Annotated[
        int,
        typer.Option("--tail", "-t", help=HELP.k8s.tail_lines),
    ] = 100,
    follow: Annotated[
        bool,
        typer.Option("--follow/--no-follow", "-f", help=HELP.k8s.follow_logs),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Stream logs across multiple pods in parallel using Stern or kubectl."""
    from devops_cli.k8s.logs import stream_multi_pod_logs

    rc = stream_multi_pod_logs(
        pod_query=pod_query,
        namespace=namespace,
        container=container,
        tail_lines=tail,
        follow=follow,
        dry_run=dry_run,
    )
    if rc != 0 and not (dry_run or is_dry_run()):
        raise typer.Exit(rc)


def diff_helm_cmd(
    release_name: Annotated[
        str,
        typer.Argument(help=HELP.k8s.helm_release),
    ],
    chart_path: Annotated[
        Path,
        typer.Argument(help=HELP.k8s.helm_chart),
    ] = DEFAULT_CURRENT_PATH,
    namespace: Annotated[
        str | None,
        typer.Option("--namespace", "-n", help=HELP.options.namespace),
    ] = None,
    values: Annotated[
        list[Path] | None,
        typer.Option("--values", "-f", help=HELP.k8s.helm_values),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Preview Kubernetes manifest diffs before executing a Helm upgrade."""
    from devops_cli.k8s.diff import diff_helm_release

    rc, diff_output = diff_helm_release(
        release_name=release_name,
        chart_path=chart_path.resolve(),
        namespace=namespace,
        values_files=[v.resolve() for v in values] if values else None,
        dry_run=dry_run,
    )
    if dry_run or is_dry_run():
        return

    if diff_output.strip():
        write_stdout(diff_output + "\n")
    if rc not in (0, 2):
        raise typer.Exit(rc)


def chaos_cmd(
    experiment: Annotated[
        str,
        typer.Argument(help=HELP.k8s.chaos_experiment),
    ] = "pod-kill",
    deployment: Annotated[
        str,
        typer.Option("--deployment", "-d", help=HELP.k8s.chaos_deployment),
    ] = "sample-app",
    namespace: Annotated[
        str,
        typer.Option("--namespace", "-n", help=HELP.options.namespace),
    ] = DEFAULT_K8S_NAMESPACE,
    duration: Annotated[
        int,
        typer.Option("--duration", help=HELP.k8s.chaos_duration),
    ] = 30,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> None:
    """Run resilience and chaos experiments against Kubernetes workloads."""
    from devops_cli.k8s.chaos import execute_chaos_experiment

    result = execute_chaos_experiment(
        experiment_name=experiment,
        target_deployment=deployment,
        namespace=namespace,
        duration_seconds=duration,
        dry_run=dry_run,
    )
    if dry_run or is_dry_run():
        return

    if json_output:
        write_stdout(format_json(result.model_dump()) + "\n")
        return

    if not result.recovered_successfully:
        raise typer.Exit(1)
