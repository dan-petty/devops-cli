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
from devops_cli.lang import HELP
from devops_cli.output import (
    format_json,
    write_stdout,
)


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
