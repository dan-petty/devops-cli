"""OpenTelemetry observability, tracing, and metrics management CLI."""

from __future__ import annotations

import time
from typing import Annotated, Any

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
        title=MESSAGES.telemetry.status_title,
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
# Command: devops telemetry profile
# =============================================================================


def _render_waterfall_bar(
    offset_pct: float, dur_pct: float, total_slots: int = 24, is_error: bool = False
) -> str:
    start_slot = min(total_slots - 1, int(offset_pct / 100.0 * total_slots))
    span_len = max(1, min(total_slots - start_slot, int(dur_pct / 100.0 * total_slots)))

    lead = " " * start_slot
    bar = "█" * span_len
    trail = " " * (total_slots - start_slot - span_len)

    color = (
        "red"
        if is_error
        else ("green" if dur_pct < 25 else ("yellow" if dur_pct < 65 else "magenta"))
    )
    return f"[{color}]{lead}{bar}{trail}[/{color}]"


def _flatten_tree_for_display(
    nodes: list[Any],
) -> list[tuple[Any, str]]:
    rows: list[tuple[Any, str]] = []

    def _walk(node: Any, prefix: str = "", is_last: bool = True) -> None:
        marker = "└─ " if is_last else "├─ "
        display_prefix = prefix + marker if node.depth > 0 else ""
        rows.append((node, display_prefix))
        child_prefix = prefix + ("   " if is_last else "│  ") if node.depth > 0 else ""
        for i, child in enumerate(node.children):
            _walk(child, child_prefix, i == len(node.children) - 1)

    for i, root in enumerate(nodes):
        _walk(root, "", i == len(nodes) - 1)
    return rows


@app.command("profile")
def telemetry_profile_cmd(
    command: Annotated[
        str | None,
        typer.Argument(help=HELP.telemetry.command_to_profile),
    ] = None,
    trace_id: Annotated[
        str | None,
        typer.Option("--trace-id", "-t", help=HELP.telemetry.trace_id),
    ] = None,
    last: Annotated[
        bool,
        typer.Option("--last", "-l", help=HELP.telemetry.last),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Display terminal-rendered waterfall breakdown and latency heatmap of OpenTelemetry spans."""
    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops telemetry profile",
            action="profile_trace_waterfall",
            details={
                "command": command,
                "trace_id": trace_id or "latest",
                "profile_mode": "dry_run",
                "status": "PROFILED_DRY_RUN",
            },
        )
        return

    import json
    import os
    import secrets
    import shlex

    from devops_cli.core.process import run_subprocess
    from devops_cli.output import print_warning, write_stdout
    from devops_cli.telemetry.tracer import (
        build_span_waterfall_tree,
        get_trace_spans,
    )

    executed_trace_id = trace_id

    if command:
        executed_trace_id = secrets.token_hex(16)
        print_info(
            f"Profiling command: [bold]{command}[/bold] (Trace: {executed_trace_id[:8]}...)",
            prefix=False,
        )
        cmd_args = shlex.split(command)
        sub_env = dict(os.environ)
        sub_env["DEVOPS_CLI_TRACE_ID"] = executed_trace_id
        sub_env["TRACEPARENT"] = f"00-{executed_trace_id}-{secrets.token_hex(8)}-01"

        with trace_span(
            f"cli.{cmd_args[0] if cmd_args else 'command'}",
            attributes={"command.line": command},
        ) as span_h:
            t0 = time.perf_counter()
            proc = run_subprocess(cmd_args, env=sub_env, capture_output=False, quiet=True)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            span_h.set_attribute("cli.exit_code", proc.returncode)
            span_h.set_attribute("cli.elapsed_ms", elapsed_ms)

    spans = get_trace_spans(executed_trace_id)
    if not spans and not command and not trace_id:
        with trace_span("telemetry.sample_profile", attributes={"service.name": "devops-cli"}):
            time.sleep(0.015)
            with trace_span("sample.database_lookup", attributes={"db.system": "sqlite"}):
                time.sleep(0.008)
            with trace_span("sample.ai_inference", attributes={"ai.model": "qwen2.5-coder"}):
                time.sleep(0.022)
        spans = get_trace_spans(None)

    tree = build_span_waterfall_tree(spans)
    if not tree:
        print_warning("No telemetry spans recorded for the specified trace.", prefix=False)
        return

    total_trace_id = spans[0].get("traceId", "unknown") if spans else "unknown"
    min_start = min(int(s.get("startTimeUnixNano", 0)) for s in spans)
    max_end = max(int(s.get("endTimeUnixNano", 0)) for s in spans)
    total_dur_ms = max(0.0, (max_end - min_start) / 1e6)

    if json_output:
        payload = {
            "trace_id": total_trace_id,
            "total_duration_ms": round(total_dur_ms, 2),
            "span_count": len(spans),
            "waterfall": [n.to_dict() for n in tree],
        }
        write_stdout(json.dumps(payload, indent=2) + "\n")
        return

    flattened = _flatten_tree_for_display(tree)
    table_rows: list[list[str]] = []

    for node, prefix in flattened:
        name_display = f"{prefix}[bold]{node.name}[/bold]"
        dur_display = format_latency(node.duration_ms)
        is_err = "ERROR" in getattr(node, "status_code", "").upper()
        bar_display = _render_waterfall_bar(
            node.relative_offset_pct, node.relative_duration_pct, is_error=is_err
        )
        status_badge = "[red]ERROR[/red]" if is_err else "[green]OK[/green]"

        table_rows.append(
            [
                name_display,
                dur_display,
                f"{node.relative_offset_pct:.0f}%",
                bar_display,
                status_badge,
            ]
        )

    print_info(
        f"[bold]Trace Waterfall Profile[/bold] (Trace ID: [cyan]{total_trace_id}[/cyan], "
        f"Total Latency: [green]{format_latency(total_dur_ms)}[/green], Spans: {len(spans)})",
        prefix=False,
    )
    print_table(
        columns=["Span / Subsystem", "Duration", "Offset", "Latency Waterfall Heatmap", "Status"],
        rows=table_rows,
        border_style="cyan",
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
