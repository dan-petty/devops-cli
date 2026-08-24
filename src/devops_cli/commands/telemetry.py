"""OpenTelemetry observability, tracing, and metrics management CLI."""

from __future__ import annotations

import time
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import CommandDryRunResult, is_dry_run
from devops_cli.telemetry.tracer import (
    get_tracer,
    record_metric,
    trace_span,
)

app = new_typer(
    help="OpenTelemetry observability, tracing, and metrics management.",
    no_args_is_help=True,
)
console = Console()


@app.command("status")
def telemetry_status_cmd() -> None:
    """Display OpenTelemetry collector endpoint, Jaeger UI URL, and connection health."""
    settings = load_settings()
    tracer = get_tracer()

    telemetry_cfg = getattr(settings, "telemetry", None) or getattr(settings, "otel", None)
    endpoint = (
        telemetry_cfg.endpoint
        if telemetry_cfg and hasattr(telemetry_cfg, "endpoint")
        else tracer.endpoint
    )
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
        res = CommandDryRunResult(
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
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
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

    console.print(table)
    rprint(f"\n[dim]To view traces in Jaeger UI: {jaeger_url}[/dim]")


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
        res = CommandDryRunResult(
            command="devops telemetry test",
            action="emit_test_telemetry",
            target=tracer.endpoint,
            details={"span_name": name, "endpoint": tracer.endpoint},
        )
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
        return

    rprint(
        f"[bold]Emitting test trace span '[cyan]{name}[/cyan]' "
        f"to [cyan]{tracer.endpoint}[/cyan]...[/bold]"
    )
    start = time.perf_counter()

    with trace_span(name, attributes={"test": True, "cli": "devops-cli"}) as span_id:
        record_metric("devops_cli.test_counter", 1.0, unit="1", attributes={"test": True})
        time.sleep(0.02)  # 20ms simulated span duration

    elapsed_ms = (time.perf_counter() - start) * 1000

    rprint(
        f"[bold green]✓ Test span emitted successfully![/bold green] "
        f"(Span ID: [cyan]{span_id}[/cyan], Duration: {elapsed_ms:.1f}ms)"
    )
    settings = load_settings()
    jaeger_cfg = getattr(settings, "jaeger", None)
    jaeger_url = (
        jaeger_cfg.url if jaeger_cfg and hasattr(jaeger_cfg, "url") else "http://localhost:16686"
    )
    rprint(f"[dim]View in Jaeger: {jaeger_url} (Service: {tracer.service_name})[/dim]")


@app.command("open-ui")
def telemetry_open_ui_cmd() -> None:
    """Print and show the Jaeger Query UI endpoint for inspecting traces."""
    settings = load_settings()
    jaeger_cfg = getattr(settings, "jaeger", None)
    jaeger_url = (
        jaeger_cfg.url if jaeger_cfg and hasattr(jaeger_cfg, "url") else "http://localhost:16686"
    )
    rprint(f"[bold]Jaeger Tracing UI:[/bold] [link={jaeger_url}]{jaeger_url}[/link]")
    rprint("[dim]Port-forward if running in cluster: devops k8s port-forward[/dim]")
