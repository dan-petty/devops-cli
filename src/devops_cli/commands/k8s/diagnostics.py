"""Kubernetes diagnostics, stern/kubectl multi-pod log streaming, Helm 3-way diffing, and chaos experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.constants import (
    CONST_FALCO_SEVERITY_LEVELS,
    CONST_MAX_SECURITY_STREAM_DURATION,
    CONST_MAX_SECURITY_STREAM_TAIL_LINES,
    CONST_MIN_SECURITY_STREAM_DURATION,
    CONST_MIN_SECURITY_STREAM_TAIL_LINES,
)
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_FALCO_LABEL_SELECTOR,
    DEFAULT_FALCO_NAMESPACE,
    DEFAULT_K8S_DOCTOR_LOG_TAIL_LINES,
    DEFAULT_K8S_NAMESPACE,
    DEFAULT_SECURITY_STREAM_DURATION_SECONDS,
    DEFAULT_SECURITY_STREAM_TAIL_LINES,
)
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import HELP
from devops_cli.output import (
    TablePayload,
    format_json,
    format_k8s_pods_table,
    print_error,
    write_stdout,
)


def _build_pods_table(
    namespace: str | None,
    label_selector: str | None,
    all_namespaces: bool,
) -> TablePayload:
    """Build a TablePayload of Kubernetes pod status using the kubernetes SDK."""
    try:
        from devops_cli.k8s.service import KubernetesService

        pods = KubernetesService.get_instance().list_pods(
            namespace=namespace,
            label_selector=label_selector,
            all_namespaces=all_namespaces,
        )
        return format_k8s_pods_table(pods)
    except Exception as exc:
        from devops_cli.security.sanitizer import mask_secrets

        safe_err = mask_secrets(str(exc))
        return format_k8s_pods_table([["—", f"[red]Error: {safe_err}[/red]", "—", "—", "—", "—"]])


def _stream_pods_watch(namespace: str | None, label: str | None, all_namespaces: bool) -> None:
    """Stream pod lifecycle events using ResourceInformer."""
    from devops_cli.k8s.informer import ResourceInformer
    from devops_cli.output import print

    informer = ResourceInformer(
        resource_kind="Pod",
        namespace="" if all_namespaces else (namespace or "default"),
        label_selector=label,
    )
    try:
        ns_label = "all namespaces" if all_namespaces else f"namespace '{namespace or 'default'}'"
        print(f"[cyan]Streaming Pod events from {ns_label} (press Ctrl+C to exit)...[/cyan]")
        for event in informer.stream_events():
            print(
                f"[{event.timestamp}] [bold]{event.event_type:<8}[/bold] {event.namespace}/{event.name} ({event.status})"
            )
    except KeyboardInterrupt, SystemExit:
        informer.stop()


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
        _stream_pods_watch(namespace, label, all_namespaces)
    else:
        from devops_cli.output import print

        print(_build_pods_table(namespace, label, all_namespaces))


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


def _handle_security_stream_export(result: Any, output: Path | None, json_output: bool) -> None:
    """Handle export and JSON output of security stream result."""
    from devops_cli.output.file_writer import write_serialized_file

    dumped = result.model_dump()
    if output:
        write_serialized_file(output, dumped, format_type="json")
    if json_output:
        write_stdout(format_json(dumped) + "\n")


def _validate_severity_callback(value: str | None) -> str | None:
    """Validate severity option against CONST_FALCO_SEVERITY_LEVELS."""
    if value is None:
        return None
    cleaned = value.strip().upper()
    if cleaned not in CONST_FALCO_SEVERITY_LEVELS:
        valid = ", ".join(sorted(CONST_FALCO_SEVERITY_LEVELS.keys()))
        raise typer.BadParameter(f"Invalid severity '{value}'. Must be one of: {valid}")
    return cleaned


def security_stream_cmd(
    namespace: Annotated[
        str,
        typer.Option("--namespace", "-n", help=HELP.options.namespace),
    ] = DEFAULT_FALCO_NAMESPACE,
    label: Annotated[
        str,
        typer.Option("--label", "-l", help=HELP.k8s.label_selector),
    ] = DEFAULT_FALCO_LABEL_SELECTOR,
    severity: Annotated[
        str | None,
        typer.Option(
            "--severity",
            "-s",
            help=HELP.k8s.security_severity,
            callback=_validate_severity_callback,
        ),
    ] = None,
    duration: Annotated[
        int,
        typer.Option(
            "--duration",
            "-d",
            min=CONST_MIN_SECURITY_STREAM_DURATION,
            max=CONST_MAX_SECURITY_STREAM_DURATION,
            help=HELP.k8s.security_duration,
        ),
    ] = DEFAULT_SECURITY_STREAM_DURATION_SECONDS,
    tail: Annotated[
        int,
        typer.Option(
            "--tail",
            "-t",
            min=CONST_MIN_SECURITY_STREAM_TAIL_LINES,
            max=CONST_MAX_SECURITY_STREAM_TAIL_LINES,
            help=HELP.k8s.tail_lines,
        ),
    ] = DEFAULT_SECURITY_STREAM_TAIL_LINES,
    follow: Annotated[
        bool,
        typer.Option("--follow/--no-follow", "-f", help=HELP.k8s.follow_logs),
    ] = False,
    simulate: Annotated[
        bool,
        typer.Option("--simulate", help=HELP.k8s.security_simulate),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Export discovered alerts to JSON file"),
    ] = None,
) -> None:
    """Stream runtime security anomaly events from Kubernetes Falco eBPF probes."""
    from devops_cli.exceptions.k8s import KubernetesLoggingError
    from devops_cli.k8s.security_stream import render_security_alerts, stream_security_events
    from devops_cli.models.k8s import SecurityStreamRequest

    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops k8s security-stream",
            action="stream_security_events",
            details={
                "namespace": namespace,
                "label": label,
                "severity": severity,
                "duration": duration,
                "simulate": simulate,
            },
        )
        return

    req = SecurityStreamRequest(
        namespace=namespace,
        label_selector=label,
        severity=severity,
        duration_seconds=duration,
        tail_lines=tail,
        follow=follow,
        simulate=simulate,
    )
    try:
        result = stream_security_events(req, dry_run=False)
    except KubernetesLoggingError as err:
        print_error(str(err))
        raise typer.Exit(1) from err

    _handle_security_stream_export(result, output, json_output)

    if not json_output and not output:
        render_security_alerts(result)


def _render_doctor_table(report: Any) -> None:
    """Render and print doctor findings in a formatted console table."""
    from devops_cli.output import TablePayload, print_table

    columns = ["Severity", "Class", "Rule", "Resource", "Cause", "Remediation"]
    rows = []
    for f in report.findings:
        sev_color = "red" if f.severity == "critical" else "yellow"
        sev_text = f"[{sev_color}]{f.severity}[/{sev_color}]"
        rows.append(
            [
                sev_text,
                f.class_,
                f.rule,
                f.resource,
                f.cause,
                f.remediation,
            ]
        )
    payload = TablePayload(
        title=f"Kubernetes Doctor Findings ({report.context or 'current'})",
        columns=columns,
        rows=rows,
    )
    print_table(payload)


def _handle_doctor_dry_run(
    namespace: str | None, tail: int, context: str | None, resolved_fmt: str
) -> None:
    """Handle dry run request plan output."""
    from devops_cli.config.constants import CONST_OUTPUT_FORMAT_TABLE
    from devops_cli.dry_run.requests import render_request_plan
    from devops_cli.k8s.doctor import plan_doctor_requests
    from devops_cli.models.k8s import DoctorReport
    from devops_cli.output.serialization import emit_serialized

    requests = plan_doctor_requests(namespace=namespace, tail=tail)
    report = DoctorReport(
        context=context or "",
        counts={},
        findings=[],
        errors=[],
        requests=requests,
    )
    if resolved_fmt != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(report.model_dump(), resolved_fmt)
    else:
        render_request_plan("Planned Kubernetes Doctor API Requests:", requests)


def _handle_doctor_output(report: Any, resolved_fmt: str) -> None:
    """Handle doctor report output formatting."""
    from devops_cli.config.constants import CONST_OUTPUT_FORMAT_TABLE
    from devops_cli.output.serialization import emit_serialized

    if resolved_fmt != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(report.model_dump(), resolved_fmt)
    elif not report.findings:
        write_stdout("No problems were found.\n")
    else:
        _render_doctor_table(report)


def doctor_cmd(
    namespace: Annotated[
        str | None,
        typer.Option("--namespace", "-n", help=HELP.k8s.doctor_namespace),
    ] = None,
    context: Annotated[
        str | None,
        typer.Option("--context", help=HELP.k8s.doctor_context),
    ] = None,
    tail: Annotated[
        int,
        typer.Option("--tail", "-t", help=HELP.k8s.doctor_tail),
    ] = DEFAULT_K8S_DOCTOR_LOG_TAIL_LINES,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.k8s.doctor_format),
    ] = "table",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Diagnose Kubernetes cluster deployment health, correlate failures, and recommend remediations."""
    from devops_cli.k8s.doctor import get_k8s_client
    from devops_cli.output.serialization import normalize_format

    resolved_fmt = normalize_format(output_format)

    if dry_run or is_dry_run():
        _handle_doctor_dry_run(namespace, tail, context, resolved_fmt)
        return

    try:
        from devops_cli.k8s.context import resolve_context
        from devops_cli.k8s.doctor import collect, diagnose

        target_context = resolve_context(context) or ""
        core = get_k8s_client(context)
        snapshot = collect(core, namespace=namespace, tail=tail, context=target_context)
        report = diagnose(snapshot)
    except Exception as exc:
        from devops_cli.security.sanitizer import mask_secrets

        safe_err = mask_secrets(str(exc))
        print_error(safe_err)
        raise typer.Exit(1) from exc

    _handle_doctor_output(report, resolved_fmt)

    if report.findings:
        raise typer.Exit(2)
