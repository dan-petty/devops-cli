"""Kubernetes diagnostics, stern/kubectl multi-pod log streaming, Helm 3-way diffing, and chaos experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_K8S_NAMESPACE,
)
from devops_cli.dry_run import is_dry_run
from devops_cli.output import (
    format_json,
    write_stdout,
)


def stream_logs_cmd(
    pod_query: Annotated[
        str,
        typer.Argument(help="Regex pattern or query to match pod names"),
    ],
    namespace: Annotated[
        str | None,
        typer.Option("--namespace", "-n", help="Target Kubernetes namespace"),
    ] = None,
    container: Annotated[
        str | None,
        typer.Option("--container", "-c", help="Target container name within matched pods"),
    ] = None,
    tail: Annotated[
        int,
        typer.Option("--tail", "-t", help="Number of historical log lines to stream"),
    ] = 100,
    follow: Annotated[
        bool,
        typer.Option("--follow/--no-follow", "-f", help="Continuously stream live log output"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate multi-pod log streaming"),
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
        typer.Argument(help="Name of deployed Helm release"),
    ],
    chart_path: Annotated[
        Path,
        typer.Argument(help="Path to local Helm chart directory or packaged archive"),
    ] = DEFAULT_CURRENT_PATH,
    namespace: Annotated[
        str | None,
        typer.Option("--namespace", "-n", help="Target Kubernetes namespace"),
    ] = None,
    values: Annotated[
        list[Path] | None,
        typer.Option("--values", "-f", help="Values YAML files to override release defaults"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate Helm diff preview"),
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
        typer.Argument(help="Resilience experiment name (e.g., pod-kill, latency-inject)"),
    ] = "pod-kill",
    deployment: Annotated[
        str,
        typer.Option("--deployment", "-d", help="Target deployment to disrupt"),
    ] = "sample-app",
    namespace: Annotated[
        str,
        typer.Option("--namespace", "-n", help="Target Kubernetes namespace"),
    ] = DEFAULT_K8S_NAMESPACE,
    duration: Annotated[
        int,
        typer.Option("--duration", help="Reconciliation monitoring window in seconds"),
    ] = 30,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate chaos experiment execution"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output experiment result as JSON"),
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
