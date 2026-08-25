"""OpenTelemetry observability, tracing, and metrics management CLI."""

from __future__ import annotations

import time
from typing import Annotated

import typer
from rich.table import Table

from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run
from devops_cli.lang.en import MESSAGES
from devops_cli.output import (
    print_info,
    print_success,
    print_table,
    render_dry_run_result,
)
from devops_cli.telemetry.tracer import (
    get_tracer,
    record_metric,
    trace_span,
)

app = new_typer(
    help="OpenTelemetry observability, tracing, and metrics management.",
    no_args_is_help=True,
)


# =============================================================================
# Command: devops telemetry status
# =============================================================================


@app.command("status")
def telemetry_status_cmd() -> None:
    """Check OpenTelemetry collector health, Jaeger endpoint, and trace propagation status."""
    tracer = get_tracer()
    endpoint = tracer.endpoint
    settings = load_settings()
    telemetry_cfg = getattr(settings, "telemetry", None)
    enabled = (
        telemetry_cfg.enabled
        if telemetry_cfg and hasattr(telemetry_cfg, "enabled")
        else tracer.enabled
    )

    jaeger_cfg = getattr(settings, "jaeger", None)
    jaeger_url = (
        jaeger_cfg.url if jaeger_cfg and hasattr(jaeger_cfg, "url") else "http://localhost:16686"
    )

    if is_dry_run():
        render_dry_run_result(
            command="devops telemetry status",
            action="check_telemetry_status",
            target=endpoint,
            details={
                "enabled": enabled,
                "endpoint": endpoint,
                "jaeger_url": jaeger_url,
                "service_name": tracer.service_name,
            },
        )
        return

    # Probe OTel collector
    is_reachable, health_msg, latency_ms = tracer.test_connection(timeout=1.5)

    table = Table(title="OpenTelemetry Observability Status", title_style="bold cyan")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row(
        "Telemetry Enabled",
        "[green]Yes (Active)[/green]" if enabled else "[yellow]Disabled[/yellow]",
    )
    table.add_row("OTLP Endpoint", endpoint)
    table.add_row("Service Name", tracer.service_name)
    table.add_row("Jaeger UI", jaeger_url)
    table.add_row(
        "Collector Health",
        f"[green]✓ Connected ({latency_ms:.1f}ms)[/green]"
        if is_reachable
        else f"[red]✗ Unreachable: {health_msg}[/red]",
    )

    print_table(table)
    print_info(f"\n[dim]To view traces in Jaeger UI: {jaeger_url}[/dim]", prefix=False)


# =============================================================================
# Command: devops telemetry test
# =============================================================================


@app.command("test")
def telemetry_test_cmd(
    name: Annotated[
        str,
        typer.Option("--name", "-n", help="Name for test span"),
    ] = "devops-cli.manual_test",
) -> None:
    """Emit a test OpenTelemetry trace span and metric to the configured collector."""
    tracer = get_tracer()

    if is_dry_run():
        render_dry_run_result(
            command="devops telemetry test",
            action="emit_test_telemetry",
            target=tracer.endpoint,
            details={"span_name": name, "endpoint": tracer.endpoint},
        )
        return

    print_info(
        f"[bold]Emitting test trace span '[cyan]{name}[/cyan]' "
        f"to [cyan]{tracer.endpoint}[/cyan]...[/bold]",
        prefix=False,
    )
    start = time.perf_counter()

    with trace_span(name, attributes={"test": True, "cli": "devops-cli"}) as span_id:
        record_metric("devops_cli.test_counter", 1.0, unit="1", attributes={"test": True})
        time.sleep(0.02)  # 20ms simulated span duration

    elapsed_ms = (time.perf_counter() - start) * 1000

    print_success(
        f"Test span emitted successfully! "
        f"(Span ID: [cyan]{span_id}[/cyan], Duration: {elapsed_ms:.1f}ms)"
    )
    settings = load_settings()
    jaeger_cfg = getattr(settings, "jaeger", None)
    jaeger_url = (
        jaeger_cfg.url if jaeger_cfg and hasattr(jaeger_cfg, "url") else "http://localhost:16686"
    )
    print_info(
        f"[dim]View in Jaeger: {jaeger_url} (Service: {tracer.service_name})[/dim]", prefix=False
    )


# =============================================================================
# Command: devops telemetry open-ui
# =============================================================================


@app.command("open-ui")
def telemetry_open_ui_cmd() -> None:
    """Print and show the Jaeger Query UI endpoint for inspecting traces."""
    settings = load_settings()
    jaeger_cfg = getattr(settings, "jaeger", None)
    jaeger_url = (
        jaeger_cfg.url if jaeger_cfg and hasattr(jaeger_cfg, "url") else "http://localhost:16686"
    )
    print_info(
        f"[bold]Jaeger Tracing UI:[/bold] [link={jaeger_url}]{jaeger_url}[/link]", prefix=False
    )
    print_info(MESSAGES.telemetry.port_forward_tip, prefix=False)
