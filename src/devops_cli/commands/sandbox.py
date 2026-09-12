"""CLI command group for isolated workload sandbox lifecycle management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

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
    print_error,
    print_success,
    print_table,
    print_warning,
    render_dry_run_result,
)
from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.models import (
    CgroupV2Metrics,
    ProbeProtocol,
    ProbeStatus,
    PrometheusMetric,
    SandboxDeployConfig,
    SandboxInstance,
    SandboxMetricsSnapshot,
    SandboxProbeReport,
    SandboxStatus,
)

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
    cpu_badge = "[red]HIGH[/red]" if cgroup.cpu_percent > 85.0 else "[green]HEALTHY[/green]"
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
        ["CPU Utilization", f"{cgroup.cpu_percent:.1f}%", "< 85.0%", cpu_badge],
        ["Memory (RSS)", f"{cgroup.memory_current_mb:.1f} MB", mem_lim_str, mem_badge],
        ["Memory Usage %", mem_pct, "< 80.0%", mem_badge],
        ["Active Tasks (PIDs)", str(cgroup.pids_current), "-", "[dim]ACTIVE[/dim]"],
        ["Page Faults Total", str(cgroup.page_faults_total), "-", "[dim]NORMAL[/dim]"],
        [
            "Block I/O (R/W)",
            f"{cgroup.io_read_bytes / (1024 * 1024):.1f} MB / {cgroup.io_write_bytes / (1024 * 1024):.1f} MB",
            "-",
            "[dim]I/O[/dim]",
        ],
    ]
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

    for warning in snapshot.warnings:
        print_warning(f"THRESHOLD ALERT: {warning}")

    if snapshot.is_healthy:
        print_success(f"Workload '{snapshot.target}' operating within normal performance bounds.")
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
    timeout: Annotated[float, typer.Option("--timeout", "-t", help=HELP.sandbox.timeout)] = 5.0,
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
    json_output: Annotated[bool, typer.Option("--json", help=HELP.sandbox.json_output)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Capture real-time cgroup v2 metrics and scrape Prometheus application metrics."""
    set_dry_run(dry_run)

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
            )
        else:
            print_error(f"Sandbox instance '{identifier}' not found.")
            raise typer.Exit(1)

    if json_output:
        typer.echo(json.dumps(snapshot.model_dump(), indent=2))
        return None

    _render_metrics_snapshot(snapshot)
    return None


__all__ = ["app"]
