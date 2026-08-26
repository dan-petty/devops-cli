"""OpenTelemetry observability, tracing, and metrics management CLI."""

from __future__ import annotations

import time
from typing import Annotated

import typer

from devops_cli.config.defaults import DEFAULT_TELEMETRY_TEST_NAME
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    format_code_span,
    format_latency,
    format_link,
    format_status_badge,
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
    help=HELP.telemetry.app,
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

    print_table(
        title="OpenTelemetry Observability Status",
        columns=[("Property", "cyan"), ("Value", "white")],
        rows=[
            [
                "Telemetry Enabled",
                format_status_badge(enabled, label="Yes (Active)" if enabled else "Disabled"),
            ],
            ["OTLP Endpoint", endpoint],
            ["Service Name", tracer.service_name],
            ["Jaeger UI", format_link(jaeger_url)],
            [
                "Collector Health",
                format_status_badge(True, label=f"✓ Connected ({format_latency(latency_ms)})")
                if is_reachable
                else format_status_badge(False, label=f"✗ Unreachable: {health_msg}"),
            ],
        ],
    )
    print_info(f"\n[dim]To view traces in Jaeger UI: {format_link(jaeger_url)}[/dim]", prefix=False)


# =============================================================================
# Command: devops telemetry test
# =============================================================================


@app.command("test")
def telemetry_test_cmd(
    name: Annotated[
        str,
        typer.Option("--name", "-n", help=HELP.telemetry.span_name),
    ] = DEFAULT_TELEMETRY_TEST_NAME,
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
        f"[bold]Emitting test trace span '{format_code_span(name)}' "
        f"to {format_code_span(tracer.endpoint)}...[/bold]",
        prefix=False,
    )
    start = time.perf_counter()

    with trace_span(name, attributes={"test": True, "cli": "devops-cli"}) as span_id:
        record_metric("devops_cli.test_counter", 1.0, unit="1", attributes={"test": True})
        time.sleep(0.02)  # 20ms simulated span duration

    elapsed_ms = (time.perf_counter() - start) * 1000

    print_success(
        f"Test span emitted successfully! "
        f"(Span ID: {format_code_span(str(span_id))}, Duration: {format_latency(elapsed_ms)})"
    )
    settings = load_settings()
    jaeger_cfg = getattr(settings, "jaeger", None)
    jaeger_url = (
        jaeger_cfg.url if jaeger_cfg and hasattr(jaeger_cfg, "url") else "http://localhost:16686"
    )
    print_info(
        f"[dim]View in Jaeger: {format_link(jaeger_url)} (Service: {tracer.service_name})[/dim]",
        prefix=False,
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
    print_info(f"[bold]Jaeger Tracing UI:[/bold] {format_link(jaeger_url)}", prefix=False)
    print_info(MESSAGES.telemetry.port_forward_tip, prefix=False)
