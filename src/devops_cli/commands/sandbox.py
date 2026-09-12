"""CLI command group for isolated workload sandbox lifecycle management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.core.cli import new_typer
from devops_cli.dry_run.models import CommandDryRunResult
from devops_cli.dry_run.state import is_dry_run, set_dry_run
from devops_cli.exceptions.sandbox import (
    SandboxError,
    SandboxNotFoundError,
    SandboxValidationError,
)
from devops_cli.lang import HELP
from devops_cli.output import (
    Console,
    Panel,
    Table,
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    render_dry_run_result,
)
from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.models import (
    CgroupV2Metrics,
    PanicIncident,
    ProbeProtocol,
    ProbeStatus,
    PrometheusMetric,
    SandboxDeployConfig,
    SandboxInstance,
    SandboxLogLine,
    SandboxLogsReport,
    SandboxMetricsSnapshot,
    SandboxProbeReport,
    SandboxStatus,
)
from devops_cli.telemetry.tracer import record_metric, trace_span

app = new_typer(help=HELP.sandbox.app, no_args_is_help=True)


def _parse_env_flags(env_list: list[str] | None) -> dict[str, str]:
    """Convert KEY=VALUE list into an environment dictionary."""
    if not env_list:
        return {}
    env_map: dict[str, str] = {}
    for item in env_list:
        if "=" in item:
            k, v = item.split("=", 1)
            env_map[k.strip()] = v.strip()
    return env_map


def _format_ports(inst: SandboxInstance) -> str:
    """Format port bindings for display in tables."""
    if not inst.port_bindings:
        return "-"
    return ", ".join(f"{b.host_port}->{b.container_port}/{b.protocol}" for b in inst.port_bindings)


def _render_instances_table(instances: list[SandboxInstance]) -> None:
    """Display sandbox instances in a Rich table."""
    columns = [
        ("Instance ID", "cyan"),
        ("Name", "bold"),
        ("Image", "white"),
        ("Status", "green"),
        ("Ports", "yellow"),
        ("Created", "dim"),
    ]
    rows = [
        [
            inst.instance_id,
            inst.name,
            inst.image,
            inst.status.value,
            _format_ports(inst),
            inst.created_at[:19].replace("T", " "),
        ]
        for inst in instances
    ]
    print_table("Workload Sandbox Instances", columns, rows)


@app.command("deploy")
def deploy(
    command: Annotated[list[str] | None, typer.Argument(help="Optional container command")] = None,
    image: Annotated[
        str, typer.Option("--image", "-i", help=HELP.sandbox.image)
    ] = "python:3.14-slim",
    name: Annotated[str | None, typer.Option("--name", "-n", help=HELP.sandbox.name)] = None,
    ports: Annotated[list[int] | None, typer.Option("--port", "-p", help=HELP.sandbox.port)] = None,
    workspace: Annotated[
        Path, typer.Option("--workspace", "-w", help=HELP.sandbox.workspace)
    ] = Path("."),
    memory: Annotated[str, typer.Option("--memory", "-m", help=HELP.sandbox.memory)] = "2g",
    cpus: Annotated[float, typer.Option("--cpus", "-c", help=HELP.sandbox.cpus)] = 2.0,
    read_only: Annotated[bool, typer.Option("--read-only", help=HELP.sandbox.read_only)] = True,
    network: Annotated[str, typer.Option("--network", help=HELP.sandbox.network)] = "bridge",
    env: Annotated[list[str] | None, typer.Option("--env", "-e", help=HELP.sandbox.env)] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> CommandDryRunResult | None:
    """Deploy an isolated background container sandbox with security containment."""
    set_dry_run(dry_run)
    engine = WorkloadSandboxEngine()
    env_map = _parse_env_flags(env)
    cmd_list = command or ["sleep", "infinity"]

    cfg = SandboxDeployConfig(
        image=image,
        name=name,
        ports=ports or [],
        command=cmd_list,
        workspace_dir=workspace,
        memory_limit=memory,
        cpu_limit=cpus,
        read_only=read_only,
        network_mode=network,
        env=env_map,
    )

    if is_dry_run():
        simulated = engine.deploy(cfg, dry_run=True)
        render_dry_run_result(
            command="devops sandbox deploy",
            action="deploy_workload_sandbox",
            details={
                "instance_id": simulated.instance_id,
                "name": simulated.name,
                "image": simulated.image,
                "workspace": str(simulated.workspace_dir),
                "ports": [b.model_dump() for b in simulated.port_bindings],
                "security": {
                    "cap_drop": ["ALL"],
                    "security_opt": ["no-new-privileges:true"],
                    "pids_limit": 256,
                    "read_only": read_only,
                },
            },
        )
        return None

    try:
        inst = engine.deploy(cfg)
        print_success(f"Sandbox '{inst.name}' deployed successfully [ID: {inst.instance_id}]")
        _render_instances_table([inst])
        return None
    except (SandboxValidationError, SandboxError) as exc:
        print_error(f"Failed deploying sandbox: {exc}")
        raise typer.Exit(1) from exc


@app.command("status")
def status(
    instance_id: Annotated[str | None, typer.Argument(help=HELP.sandbox.instance_id)] = None,
    all_instances: Annotated[
        bool, typer.Option("--all", "-a", help=HELP.sandbox.all_instances)
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help=HELP.sandbox.json_output)] = False,
) -> None:
    """Inspect status of deployed sandbox containers."""
    engine = WorkloadSandboxEngine()
    try:
        instances = engine.status(identifier=instance_id)
    except SandboxNotFoundError as exc:
        print_error(str(exc))
        raise typer.Exit(1) from exc

    if not all_instances and not instance_id:
        instances = [i for i in instances if i.status == SandboxStatus.RUNNING]

    if json_output:
        typer.echo(json.dumps([i.model_dump() for i in instances], indent=2))
        return

    if not instances:
        print_success("No sandbox instances found.")
        return

    _render_instances_table(instances)


@app.command("stop")
def stop(
    instance_id: Annotated[str | None, typer.Argument(help=HELP.sandbox.instance_id)] = None,
    all_instances: Annotated[
        bool, typer.Option("--all", "-a", help=HELP.sandbox.all_instances)
    ] = False,
    timeout: Annotated[int, typer.Option("--timeout", "-t", help=HELP.sandbox.timeout)] = 10,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> CommandDryRunResult | None:
    """Gracefully stop and tear down a sandbox container."""
    set_dry_run(dry_run)
    engine = WorkloadSandboxEngine()

    if not instance_id and not all_instances:
        print_error("Please specify a sandbox instance ID or use --all to stop all sandboxes.")
        raise typer.Exit(1)

    targets: list[str] = (
        [inst.instance_id for inst in engine.registry.list_instances()]
        if all_instances
        else ([instance_id] if instance_id else [])
    )

    if is_dry_run():
        render_dry_run_result(
            command="devops sandbox stop",
            action="stop_workload_sandbox",
            details={"targets": targets, "timeout": timeout},
        )
        return None

    for target in targets:
        try:
            stopped = engine.stop(target, timeout=timeout)
            print_success(
                f"Sandbox '{stopped.name}' stopped and removed [ID: {stopped.instance_id}]"
            )
        except SandboxNotFoundError as exc:
            print_error(f"Cannot stop '{target}': {exc}")
    return None


@app.command("exec")
def exec_cmd(
    instance_id: Annotated[str, typer.Argument(help=HELP.sandbox.instance_id)],
    command: Annotated[
        list[str], typer.Argument(help="Command and arguments to execute inside sandbox")
    ],
    workdir: Annotated[
        str | None, typer.Option("--workdir", "-w", help=HELP.sandbox.workdir)
    ] = None,
) -> None:
    """Execute a command inside an active sandbox container."""
    engine = WorkloadSandboxEngine()
    try:
        res = engine.exec(instance_id, command=command, workdir=workdir)
        if res.stdout:
            typer.echo(res.stdout, nl=False)
        if res.stderr:
            typer.echo(res.stderr, nl=False, err=True)
        if res.exit_code != 0:
            raise typer.Exit(res.exit_code)
    except (SandboxNotFoundError, SandboxError) as exc:
        print_error(f"Execution failed: {exc}")
        raise typer.Exit(1) from exc


def _parse_protocols(protocols_raw: str | None) -> list[ProbeProtocol]:
    """Parse comma-separated protocol string into typed ProbeProtocol list."""
    if not protocols_raw:
        return [ProbeProtocol.TCP, ProbeProtocol.HTTP]
    parsed: list[ProbeProtocol] = []
    for item in protocols_raw.split(","):
        clean = item.strip().lower()
        if clean:
            try:
                parsed.append(ProbeProtocol(clean))
            except ValueError:
                continue
    return parsed or [ProbeProtocol.TCP, ProbeProtocol.HTTP]


def _parse_expected_statuses(statuses_raw: str | None) -> list[int] | None:
    """Parse comma-separated expected status codes."""
    if not statuses_raw:
        return None
    codes: list[int] = []
    for s in statuses_raw.split(","):
        try:
            codes.append(int(s.strip()))
        except ValueError:
            continue
    return codes or None


def _format_status_badge(status: ProbeStatus) -> str:
    """Return colored Rich markup for probe status."""
    if status == ProbeStatus.PASS:
        return "[green]PASS[/green]"
    if status == ProbeStatus.FAIL:
        return "[red]FAIL[/red]"
    if status == ProbeStatus.TIMEOUT:
        return "[yellow]TIMEOUT[/yellow]"
    return "[dim]SKIPPED[/dim]"


def _render_probe_report(report: SandboxProbeReport) -> None:
    """Render structured probe results in a Rich table."""
    columns = [
        ("Protocol", "cyan"),
        ("Target", "white"),
        ("Status", "bold"),
        ("Latency (ms)", "yellow"),
        ("HTTP Code", "blue"),
        ("Message", "dim"),
    ]
    rows = [
        [
            r.protocol.value.upper(),
            r.target,
            _format_status_badge(r.status),
            f"{r.latency_ms:.1f}",
            str(r.status_code) if r.status_code is not None else "-",
            r.message or "-",
        ]
        for r in report.results
    ]
    print_table(f"Probe Results: {report.target}", columns, rows)

    summary = (
        f"Probes: {report.passed_probes}/{report.total_probes} passed, "
        f"{report.failed_probes} failed ({report.duration_seconds:.2f}s)"
    )
    if report.overall_status == ProbeStatus.PASS:
        print_success(summary)
    else:
        print_error(summary)
    if report.trace_id:
        print_info(
            f"[dim]Trace ID: {report.trace_id} (Visualize with: devops sandbox traces --trace-id {report.trace_id})[/dim]",
            prefix=False,
        )


@app.command("probe")
def probe(
    identifier: Annotated[str, typer.Argument(help=HELP.sandbox.instance_id)],
    protocol: Annotated[
        str | None,
        typer.Option("--protocol", "-p", help=HELP.sandbox.probe_protocol),
    ] = None,
    path: Annotated[
        list[str] | None,
        typer.Option("--path", help=HELP.sandbox.probe_path),
    ] = None,
    expected_status: Annotated[
        str | None,
        typer.Option("--expected-status", help=HELP.sandbox.probe_expected_status),
    ] = None,
    regex: Annotated[
        str | None,
        typer.Option("--regex", "-r", help=HELP.sandbox.probe_regex),
    ] = None,
    latency_sla: Annotated[
        float | None,
        typer.Option("--latency-sla", help=HELP.sandbox.probe_latency_sla),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option("--timeout", "-t", help=HELP.sandbox.timeout),
    ] = 5.0,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.sandbox.json_output),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> CommandDryRunResult | None:
    """Probe endpoint readiness and service health across network protocols."""
    set_dry_run(dry_run)
    protocols = _parse_protocols(protocol)
    statuses = _parse_expected_statuses(expected_status)

    if is_dry_run():
        render_dry_run_result(
            command="devops sandbox probe",
            action="probe_sandbox_endpoint",
            target=identifier,
            details={
                "identifier": identifier,
                "protocols": [p.value for p in protocols],
                "paths": path or ["/healthz"],
                "timeout": timeout,
                "expected_statuses": statuses,
            },
        )
        return None

    engine = WorkloadSandboxEngine()
    report: SandboxProbeReport
    try:
        instances = engine.status(identifier=identifier)
        if instances:
            report = engine.probe(
                identifier=instances[0].instance_id,
                protocols=protocols,
                http_paths=path,
                expected_statuses=statuses,
                regex=regex,
                timeout=timeout,
                latency_budget_ms=latency_sla,
            )
        else:
            raise SandboxNotFoundError(f"Sandbox '{identifier}' not found")
    except SandboxNotFoundError:
        if "://" in identifier or ":" in identifier:
            from devops_cli.sandbox.probe import run_sandbox_probes

            report = run_sandbox_probes(
                target_or_instance=identifier,
                protocols=protocols,
                http_paths=path,
                expected_statuses=statuses,
                regex=regex,
                timeout=timeout,
                latency_budget_ms=latency_sla,
            )
        else:
            print_error(f"Sandbox instance '{identifier}' not found.")
            raise typer.Exit(1)

    if json_output:
        typer.echo(json.dumps(report.model_dump(), indent=2))
        if report.overall_status != ProbeStatus.PASS:
            raise typer.Exit(1)
        return None

    _render_probe_report(report)
    if report.overall_status != ProbeStatus.PASS:
        raise typer.Exit(1)
    return None


def _render_cgroup_table(target: str, cgroup: CgroupV2Metrics) -> None:
    """Render Cgroup v2 resource telemetry table."""
    columns = [
        ("Resource / Metric", "cyan"),
        ("Value", "white"),
        ("Limit / Baseline", "yellow"),
        ("Status", "bold"),
    ]
    cpu_badge = (
        "[red]HIGH[/red]"
        if (cgroup.cpu_percent or 0.0) > 85.0
        else ("[green]HEALTHY[/green]" if cgroup.cpu_percent is not None else "[dim]UNKNOWN[/dim]")
    )
    cpu_str = f"{cgroup.cpu_percent:.1f}%" if cgroup.cpu_percent is not None else "-"
    mem_lim_str = f"{cgroup.memory_limit_mb:.1f} MB" if cgroup.memory_limit_mb else "unbounded"
    mem_pct = (
        f"{cgroup.memory_usage_percent:.1f}%" if cgroup.memory_usage_percent is not None else "-"
    )
    mem_badge = (
        "[red]HIGH[/red]"
        if (cgroup.memory_usage_percent or 0.0) > 80.0
        else "[green]HEALTHY[/green]"
    )

    rows = [
        ["CPU Utilization", cpu_str, "< 85.0%", cpu_badge],
        ["Memory (RSS)", f"{cgroup.memory_current_mb:.1f} MB", mem_lim_str, mem_badge],
        ["Memory Usage %", mem_pct, "< 80.0%", mem_badge],
        ["Active Tasks (PIDs)", str(cgroup.pids_current), "-", "[dim]ACTIVE[/dim]"],
        ["Page Faults Total", str(cgroup.page_faults_total), "-", "[dim]NORMAL[/dim]"],
    ]
    if cgroup.open_fds_count is not None:
        rows.append(["Open File Descriptors", str(cgroup.open_fds_count), "-", "[dim]ACTIVE[/dim]"])
    rows.extend(
        [
            [
                "Block I/O (R/W)",
                f"{cgroup.io_read_bytes / (1024 * 1024):.1f} MB / {cgroup.io_write_bytes / (1024 * 1024):.1f} MB",
                "-",
                "[dim]I/O[/dim]",
            ],
            [
                "Network I/O (Rx/Tx)",
                f"{cgroup.network_rx_bytes / (1024 * 1024):.1f} MB / {cgroup.network_tx_bytes / (1024 * 1024):.1f} MB",
                "-",
                "[dim]NET[/dim]",
            ],
        ]
    )
    print_table(f"Cgroup v2 Resource Telemetry: {target}", columns, rows)


def _render_prom_table(target: str, metrics: list[PrometheusMetric]) -> None:
    """Render Prometheus application metrics table."""
    columns = [
        ("Metric Name", "cyan"),
        ("Type", "magenta"),
        ("Labels", "dim"),
        ("Value", "green"),
    ]
    rows = []
    for m in metrics[:15]:
        lbl_str = ", ".join(f"{k}={v}" for k, v in m.labels.items()) if m.labels else "-"
        lbl_truncated = lbl_str if len(lbl_str) <= 40 else lbl_str[:37] + "..."
        rows.append([m.name, m.metric_type.upper(), lbl_truncated, f"{m.value:.2f}"])
    print_table(f"Prometheus Application Metrics: {target}", columns, rows)


def _render_metrics_snapshot(snapshot: SandboxMetricsSnapshot) -> None:
    """Render structured container telemetry and Prometheus metrics in Rich tables."""
    if snapshot.cgroup:
        _render_cgroup_table(snapshot.target, snapshot.cgroup)

    if snapshot.prometheus_metrics:
        _render_prom_table(snapshot.target, snapshot.prometheus_metrics)

    if snapshot.scrape_error:
        print_warning(f"SCRAPE WARNING: {snapshot.scrape_error}")

    for warning in snapshot.warnings:
        print_warning(f"THRESHOLD ALERT: {warning}")

    if snapshot.is_healthy:
        print_success(f"Workload '{snapshot.target}' operating within normal performance bounds.")
    elif snapshot.scrape_error and not snapshot.warnings:
        print_error(
            f"Workload '{snapshot.target}' encountered telemetry collection error: {snapshot.scrape_error}"
        )
    else:
        print_error(
            f"Workload '{snapshot.target}' exceeded {len(snapshot.warnings)} operating threshold(s)."
        )


@app.command("metrics")
def metrics(
    identifier: Annotated[str, typer.Argument(help=HELP.sandbox.instance_id)],
    prom_endpoint: Annotated[
        str,
        typer.Option(
            "--prom-endpoint",
            "-p",
            "--path",
            help=HELP.sandbox.metrics_endpoint,
        ),
    ] = "/metrics",
    timeout: Annotated[
        float, typer.Option("--timeout", "-t", help=HELP.sandbox.metrics_timeout)
    ] = 5.0,
    warn_memory_pct: Annotated[
        float,
        typer.Option(
            "--warn-memory-pct",
            help=HELP.sandbox.warn_memory_pct,
        ),
    ] = 80.0,
    warn_cpu_pct: Annotated[
        float,
        typer.Option(
            "--warn-cpu-pct",
            help=HELP.sandbox.warn_cpu_pct,
        ),
    ] = 85.0,
    latency_sla_ms: Annotated[
        float | None,
        typer.Option(
            "--latency-sla-ms",
            help=HELP.sandbox.latency_sla_ms,
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help=HELP.sandbox.json_output)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Capture real-time cgroup v2 metrics and scrape Prometheus application metrics."""
    set_dry_run(dry_run)

    with trace_span(
        "sandbox.metrics",
        attributes={
            "sandbox.identifier": identifier,
            "sandbox.prom_endpoint": prom_endpoint,
            "sandbox.dry_run": is_dry_run(),
        },
    ):
        record_metric(
            "devops_cli.sandbox.metrics_invoked",
            1.0,
            unit="1",
            attributes={"dry_run": is_dry_run()},
        )
        if is_dry_run():
            render_dry_run_result(
                command="devops sandbox metrics",
                action="collect_sandbox_metrics",
                details={
                    "identifier": identifier,
                    "prom_endpoint": prom_endpoint,
                    "timeout": timeout,
                    "warn_memory_pct": warn_memory_pct,
                    "warn_cpu_pct": warn_cpu_pct,
                    "latency_sla_ms": latency_sla_ms,
                },
            )
            return None

        engine = WorkloadSandboxEngine()
        try:
            snapshot = engine.metrics(
                identifier=identifier,
                prom_endpoint=prom_endpoint,
                timeout=timeout,
                memory_threshold_pct=warn_memory_pct,
                cpu_threshold_pct=warn_cpu_pct,
                latency_sla_ms=latency_sla_ms,
            )
        except SandboxNotFoundError:
            if "://" in identifier or ":" in identifier:
                from devops_cli.sandbox.metrics import collect_sandbox_metrics

                snapshot = collect_sandbox_metrics(
                    instance_or_target=identifier,
                    prom_endpoint=prom_endpoint,
                    timeout=timeout,
                    memory_threshold_pct=warn_memory_pct,
                    cpu_threshold_pct=warn_cpu_pct,
                    latency_sla_ms=latency_sla_ms,
                )
            else:
                print_error(f"Sandbox instance '{identifier}' not found.")
                raise typer.Exit(1)

        if json_output:
            typer.echo(json.dumps(snapshot.model_dump(), indent=2))
            return None

        _render_metrics_snapshot(snapshot)
        return None


def _render_sandbox_trace_waterfall(
    trace_id: str,
    target: str | None,
    spans: list[dict[str, Any]],
    jaeger_url: str | None = None,
) -> None:
    """Render terminal waterfall Gantt table for OpenTelemetry trace spans."""
    from devops_cli.output import format_latency
    from devops_cli.telemetry.tracer import build_span_waterfall_tree
    from devops_cli.telemetry.waterfall import flatten_waterfall_tree, render_waterfall_bar

    tree = build_span_waterfall_tree(spans)
    if not tree:
        return

    flattened = flatten_waterfall_tree(tree)
    columns = [
        ("Span / Operation", "cyan"),
        ("Duration", "yellow"),
        ("Offset", "dim"),
        ("Execution Waterfall", "white"),
        ("Status", "bold"),
    ]
    rows: list[list[str]] = []
    for node, prefix in flattened:
        name_display = f"{prefix}[bold]{node.name}[/bold]"
        dur_display = format_latency(node.duration_ms)
        is_err = "ERROR" in getattr(node, "status_code", "").upper()
        bar_display = render_waterfall_bar(
            node.relative_offset_pct, node.relative_duration_pct, is_error=is_err
        )
        status_badge = "[red]ERROR[/red]" if is_err else "[green]OK[/green]"
        rows.append(
            [
                name_display,
                dur_display,
                f"{node.relative_offset_pct:.0f}%",
                bar_display,
                status_badge,
            ]
        )

    target_title = f" [{target}]" if target else ""
    print_table(f"Trace Waterfall{target_title}: {trace_id}", columns, rows)

    min_start = min((int(s.get("startTimeUnixNano", 0)) for s in spans), default=0)
    max_end = max((int(s.get("endTimeUnixNano", 0)) for s in spans), default=0)
    total_dur_ms = max(0.0, (max_end - min_start) / 1e6)
    j_url = (jaeger_url or "http://localhost:16686").rstrip("/")

    print_info(
        f"[bold]Trace Summary:[/bold] {len(spans)} span(s), total duration {format_latency(total_dur_ms)} | "
        f"[dim]Jaeger: {j_url}/trace/{trace_id}[/dim]",
        prefix=False,
    )


def _render_sandbox_trace_json(
    trace_id: str,
    target: str | None,
    spans: list[dict[str, Any]],
) -> None:
    """Render trace waterfall as structured JSON payload."""
    from devops_cli.telemetry.tracer import build_span_waterfall_tree

    tree = build_span_waterfall_tree(spans)
    min_start = min((int(s.get("startTimeUnixNano", 0)) for s in spans), default=0)
    max_end = max((int(s.get("endTimeUnixNano", 0)) for s in spans), default=0)
    total_dur_ms = max(0.0, (max_end - min_start) / 1e6)
    payload = {
        "trace_id": trace_id,
        "target": target,
        "total_duration_ms": round(total_dur_ms, 2),
        "span_count": len(spans),
        "waterfall": [n.to_dict() for n in tree],
    }
    typer.echo(json.dumps(payload, indent=2))


def _execute_sandbox_probe_before_trace(identifier: str) -> tuple[str, str | None]:
    """Execute dynamic probe against target or sandbox instance and return (target, trace_id)."""
    from devops_cli.sandbox.probe import run_sandbox_probes

    engine = WorkloadSandboxEngine()
    target_obj: SandboxInstance | str = identifier
    try:
        instances = engine.status(identifier=identifier)
        if instances:
            target_obj = instances[0]
    except SandboxError, OSError:
        pass

    report = run_sandbox_probes(target_obj)
    return report.target, report.trace_id


def _resolve_spans_for_traces(
    trace_id: str | None, last: bool, jaeger_url: str | None
) -> tuple[str, list[dict[str, Any]]]:
    """Retrieve trace spans matching trace_id or fallback to most recent buffer spans."""
    from devops_cli.telemetry.tracer import get_trace_spans
    from devops_cli.telemetry.waterfall import resolve_trace_spans

    active_id, spans = resolve_trace_spans(trace_id=trace_id, jaeger_url=jaeger_url)
    if not spans and (last or not trace_id):
        buffered = get_trace_spans(None)
        if buffered:
            return str(buffered[0].get("traceId", "unknown")), buffered

    return active_id, spans


@app.command("traces")
def traces(
    identifier: Annotated[
        str | None,
        typer.Argument(help=HELP.sandbox.instance_id),
    ] = None,
    trace_id: Annotated[
        str | None,
        typer.Option("--trace-id", "-t", help=HELP.sandbox.trace_id),
    ] = None,
    last: Annotated[
        bool,
        typer.Option("--last", "-l", help=HELP.sandbox.last_trace),
    ] = False,
    probe: Annotated[
        bool,
        typer.Option("--probe", help=HELP.sandbox.probe_before_trace),
    ] = False,
    jaeger_url: Annotated[
        str | None,
        typer.Option("--jaeger-url", help=HELP.sandbox.jaeger_url),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Visualize distributed trace waterfall and cross-service latency for sandbox workloads."""
    set_dry_run(dry_run)
    if is_dry_run():
        render_dry_run_result(
            command="devops sandbox traces",
            action="visualize_sandbox_traces",
            details={
                "identifier": identifier,
                "trace_id": trace_id or "latest",
                "probe": probe,
                "jaeger_url": jaeger_url,
            },
        )
        return None

    resolved_trace_id = trace_id
    target_display = identifier
    if probe and identifier:
        target_display, resolved_trace_id = _execute_sandbox_probe_before_trace(identifier)

    active_id, spans = _resolve_spans_for_traces(resolved_trace_id, last, jaeger_url)
    if not spans:
        print_warning(f"No telemetry spans recorded for trace '{resolved_trace_id or active_id}'.")
        return None

    if json_output:
        _render_sandbox_trace_json(active_id, target_display, spans)
        return None

    _render_sandbox_trace_waterfall(active_id, target_display, spans, jaeger_url=jaeger_url)
    return None


def _resolve_sandbox_identifier(
    engine: WorkloadSandboxEngine, identifier: str | None
) -> str | None:
    """Resolve single instance identifier or prompt error if ambiguous."""
    if identifier:
        return identifier
    instances = engine.status()
    if not instances:
        print_error("No running or deployed sandbox instances found.")
        return None
    if len(instances) == 1:
        return instances[0].instance_id
    print_error("Multiple sandboxes running. Specify an instance identifier.")
    return None


def _render_incident_alert_panel(incident: PanicIncident) -> None:
    """Display rich alert panel when a runtime panic is detected."""
    table = Table.grid(padding=(0, 2))
    table.add_column("Key", style="bold red")
    table.add_column("Value", style="yellow")

    table.add_row("Panic Type:", incident.panic_type.value)
    table.add_row("Instance:", incident.instance_id)
    table.add_row("Message:", incident.message)
    table.add_row("Incident ID:", incident.incident_id)
    if incident.archived_path:
        table.add_row("Archived Record:", incident.archived_path)

    console = Console()
    console.print(
        Panel(
            table,
            title="[bold red]🚨 CRITICAL PANIC DETECTED[/bold red]",
            border_style="red",
            expand=False,
        )
    )


def _render_single_log_line(line: SandboxLogLine, incident: PanicIncident | None) -> None:
    """Print formatted log line and alert panel if panic triggered."""
    console = Console()
    prefix = f"[dim cyan]{line.timestamp}[/dim cyan] " if line.timestamp else ""
    if line.is_panic:
        console.print(f"{prefix}[bold red]{line.content}[/bold red]")
    elif line.stream == "stderr":
        console.print(f"{prefix}[yellow]{line.content}[/yellow]")
    else:
        console.print(f"{prefix}{line.content}")

    if incident:
        _render_incident_alert_panel(incident)


def _render_logs_json(report: SandboxLogsReport) -> None:
    """Output structured JSON log report."""
    print(json.dumps(report.model_dump(), indent=2))


def _render_logs_output(report: SandboxLogsReport) -> None:
    """Display collected log lines and any detected panic incident alert panels."""
    for line in report.lines:
        _render_single_log_line(line, incident=None)
    for incident in report.incidents:
        _render_incident_alert_panel(incident)


@app.command("logs")
def logs(
    identifier: Annotated[str | None, typer.Argument(help=HELP.sandbox.instance_id)] = None,
    follow: Annotated[bool, typer.Option("--follow", "-f", help=HELP.sandbox.follow)] = False,
    tail: Annotated[int, typer.Option("--tail", "-n", help=HELP.sandbox.tail)] = 100,
    timestamps: Annotated[
        bool, typer.Option("--timestamps", "-t", help=HELP.sandbox.timestamps)
    ] = True,
    detect_panics: Annotated[
        bool, typer.Option("--detect-panics/--no-detect-panics", help=HELP.sandbox.detect_panics)
    ] = True,
    archive_incidents: Annotated[
        bool,
        typer.Option(
            "--archive-incidents/--no-archive-incidents",
            help="Archive incident records to JSON files",
        ),
    ] = True,
    incident_dir: Annotated[
        Path | None, typer.Option("--incident-dir", help=HELP.sandbox.incident_dir)
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help=HELP.options.json_output)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Stream stdout/stderr container logs with automated panic and crash detection."""
    set_dry_run(dry_run)
    if is_dry_run():
        render_dry_run_result(
            command="devops sandbox logs",
            action="stream_sandbox_logs",
            details={
                "identifier": identifier or "auto",
                "follow": follow,
                "tail": tail,
                "timestamps": timestamps,
                "detect_panics": detect_panics,
            },
        )
        return None

    engine = WorkloadSandboxEngine()
    target_id = _resolve_sandbox_identifier(engine, identifier)
    if not target_id:
        return None

    callback = _render_single_log_line if follow and not json_output else None
    report = engine.logs(
        identifier=target_id,
        follow=follow,
        tail=tail,
        timestamps=timestamps,
        detect_panics_flag=detect_panics,
        archive_incidents=archive_incidents,
        incident_dir=incident_dir,
        line_callback=callback,
    )

    if json_output:
        _render_logs_json(report)
        return None

    if not follow:
        _render_logs_output(report)

    if report.panics_detected > 0:
        print_warning(f"Detected {report.panics_detected} critical panic incidents in log stream.")
    else:
        print_success(f"Stream closed ({report.total_lines} lines).")
    return None


__all__ = ["app"]
