"""OpenTelemetry observability, tracing, and metrics management CLI."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.constants import CONST_OTEL_COLLECTOR_NAMESPACE, CONST_OTEL_COLLECTOR_SERVICE
from devops_cli.config.defaults import (
    DEFAULT_TELEMETRY_PROFILE_POLL_INTERVAL_SECONDS,
    DEFAULT_TELEMETRY_PROFILE_POLL_SECONDS,
    DEFAULT_TELEMETRY_TEST_NAME,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    format_code_span,
    format_latency,
    format_link,
    format_status_badge,
    print_error,
    print_info,
    print_success,
    print_table,
    render_dry_run_result,
)
from devops_cli.telemetry.tracer import (
    OTelTelemetryClient,
    get_tracer,
    record_metric,
    trace_span,
)
from devops_cli.telemetry.waterfall import (
    flatten_waterfall_tree as _flatten_tree_for_display,
)
from devops_cli.telemetry.waterfall import query_jaeger_trace
from devops_cli.telemetry.waterfall import (
    render_waterfall_bar as _render_waterfall_bar,
)

app = new_typer(
    help=HELP.telemetry.app,
    no_args_is_help=True,
)
semconv_app = new_typer(help=HELP.telemetry.semconv, no_args_is_help=True)
app.add_typer(semconv_app, name="semconv", help=HELP.telemetry.semconv)


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

    from devops_cli.telemetry.logfire import get_logfire_bridge

    logfire_bridge = get_logfire_bridge()
    lf_status = logfire_bridge.get_status()

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
            [
                "Logfire Observability",
                format_status_badge(
                    lf_status.enabled, label="Active" if lf_status.enabled else "Inactive"
                ),
            ],
            [
                "Logfire Token",
                format_status_badge(
                    lf_status.token_configured,
                    label="Configured (Keyring/Env)"
                    if lf_status.token_configured
                    else "Not Configured",
                ),
            ],
        ],
    )
    print_info(f"\n[dim]To view traces in Jaeger UI: {format_link(jaeger_url)}[/dim]", prefix=False)


# =============================================================================
# Command: devops telemetry logfire
# =============================================================================


@app.command("connect")
def telemetry_connect_cmd(
    context: Annotated[
        str | None, typer.Option("--context", help=HELP.telemetry.connect_context)
    ] = None,
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help=HELP.telemetry.connect_namespace)
    ] = CONST_OTEL_COLLECTOR_NAMESPACE,
    service: Annotated[
        str, typer.Option("--service", help=HELP.telemetry.connect_service)
    ] = CONST_OTEL_COLLECTOR_SERVICE,
    save: Annotated[
        bool, typer.Option("--save/--no-save", help=HELP.telemetry.connect_save)
    ] = True,
) -> None:
    """Find the cluster's OpenTelemetry collector, check it answers, and send telemetry there."""
    from devops_cli.config.settings import load_settings, save_settings
    from devops_cli.k8s.node_port import ServiceNotReachableError
    from devops_cli.telemetry.collector import collector_endpoint

    try:
        endpoint = collector_endpoint(context, namespace, service)
    except ServiceNotReachableError as exc:
        print_error(f"Cannot find the collector: {exc}", prefix=False)
        raise typer.Exit(1) from exc
    reachable, health, latency_ms = OTelTelemetryClient(endpoint=endpoint).test_connection(
        timeout=3.0
    )
    if not reachable:
        print_error(f"The collector at {endpoint} does not answer: {health}", prefix=False)
        raise typer.Exit(1)
    if not save:
        print_success(f"Collector at {endpoint} answers ({format_latency(latency_ms)})")
        return
    settings = load_settings()
    settings.telemetry.endpoint = endpoint
    settings.telemetry.enabled = True
    save_settings(settings)
    print_success(f"Telemetry now goes to {endpoint} ({format_latency(latency_ms)})")


@app.command("logfire")
def telemetry_logfire_cmd(
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> None:
    """Display Logfire structured observability bridge status and token metrics."""
    import json

    from devops_cli.output import write_stdout
    from devops_cli.telemetry.logfire import get_logfire_bridge

    bridge = get_logfire_bridge()
    status = bridge.get_status()

    if json_output:
        write_stdout(json.dumps(status.model_dump(), indent=2) + "\n")
        return

    print_table(
        title="Logfire Structured AI Observability Status",
        columns=[("Property", "cyan"), ("Value", "white")],
        rows=[
            [
                "Logfire Active",
                format_status_badge(
                    status.enabled, label="Active" if status.enabled else "Inactive"
                ),
            ],
            [
                "Token Configured",
                format_status_badge(
                    status.token_configured,
                    label="Configured (Keyring/Env)"
                    if status.token_configured
                    else "Not Configured",
                ),
            ],
            ["Send to Logfire", str(status.send_to_logfire)],
            ["Recorded Agent Turns", str(status.turns_count)],
            ["Input Tokens", str(status.token_metrics.get("input_tokens", 0))],
            ["Output Tokens", str(status.token_metrics.get("output_tokens", 0))],
            ["Total Tokens", str(status.token_metrics.get("total_tokens", 0))],
        ],
    )


# =============================================================================
# Command: devops telemetry test
# =============================================================================


@app.command("test")
def telemetry_test_cmd(
    name: Annotated[
        str,
        typer.Option("--name", "-n", help=HELP.telemetry.span_name),
    ] = DEFAULT_TELEMETRY_TEST_NAME,
    logfire: Annotated[
        bool,
        typer.Option("--logfire", help=HELP.telemetry.test_logfire),
    ] = False,
) -> None:
    """Emit a test OpenTelemetry trace span and metric to the configured collector."""
    tracer = get_tracer()

    if is_dry_run():
        render_dry_run_result(
            command="devops telemetry test",
            action="emit_test_telemetry",
            target=tracer.endpoint,
            details={"span_name": name, "endpoint": tracer.endpoint, "logfire": logfire},
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
        if logfire:
            from devops_cli.telemetry.logfire import logfire_agent_turn

            with logfire_agent_turn("test_agent", turn_index=1, prompt=name) as turn:
                turn.record_tokens(input_tokens=10, output_tokens=5)
                turn.set_response("Logfire test response")
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


def _jaeger_url() -> str:
    """Return the configured Jaeger Query URL."""
    jaeger_cfg = getattr(load_settings(), "jaeger", None)
    return str(getattr(jaeger_cfg, "url", "") or "http://localhost:16686")


def _run_profiled_command(command: str, tracer: OTelTelemetryClient) -> str:
    """Run a command inside a profile span and return the trace it ran under.

    `run_subprocess` hands the child that trace through TRACEPARENT. The child gets the
    caller's full environment, as if run directly, so its own telemetry settings reach it.
    """
    import shlex

    from devops_cli.core.process import run_subprocess

    cmd_args = shlex.split(command)
    with trace_span("telemetry.profile", attributes={"command.line": command}) as span_h:
        trace_id = tracer.current_trace_id or ""
        print_info(f"Profiling command: [bold]{command}[/bold] (Trace: {trace_id})", prefix=False)
        start_time = time.perf_counter()
        proc = run_subprocess(cmd_args, capture_output=False, quiet=True, isolate_env=False)
        span_h.set_attribute("cli.exit_code", proc.returncode)
        span_h.set_attribute("cli.elapsed_ms", (time.perf_counter() - start_time) * 1000)
    tracer.flush()
    return trace_id


def _read_trace_from_jaeger(trace_id: str, jaeger_url: str) -> list[dict[str, Any]]:
    """Poll Jaeger until the trace stops growing, within a fixed bound.

    Spans reach the collector asynchronously, so one read can catch a trace half-exported.
    """
    deadline = time.monotonic() + DEFAULT_TELEMETRY_PROFILE_POLL_SECONDS
    spans: list[dict[str, Any]] = []
    while True:
        fetched = query_jaeger_trace(trace_id, jaeger_url=jaeger_url)
        if fetched and len(fetched) == len(spans):
            return fetched
        spans = fetched or spans
        if time.monotonic() >= deadline:
            return spans
        time.sleep(DEFAULT_TELEMETRY_PROFILE_POLL_INTERVAL_SECONDS)


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
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run a command, or name a trace, and show its span waterfall as Jaeger recorded it."""
    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops telemetry profile",
            action="profile_trace_waterfall",
            details={
                "command": command,
                "trace_id": trace_id,
                "profile_mode": "dry_run",
                "status": "PROFILED_DRY_RUN",
            },
        )
        return

    import json

    from devops_cli.output import write_stdout
    from devops_cli.telemetry.tracer import build_span_waterfall_tree

    if not command and not trace_id:
        print_error("Pass a command to profile, or --trace-id to show a trace already in Jaeger.")
        raise typer.Exit(2)

    tracer = get_tracer()
    if command:
        if not tracer.enabled:
            print_error(
                "Telemetry export is off, so the command's spans would never reach a collector. "
                "Enable it (DEVOPS_TELEMETRY_ENABLED=true) and run the collector."
            )
            raise typer.Exit(1)
        trace_id = _run_profiled_command(command, tracer)

    jaeger_url = _jaeger_url()
    spans = _read_trace_from_jaeger(str(trace_id), jaeger_url)
    if not spans:
        print_error(
            f"No spans for trace {trace_id} reached Jaeger at {jaeger_url} within "
            f"{DEFAULT_TELEMETRY_PROFILE_POLL_SECONDS:.0f}s; check the collector and Jaeger "
            "are running."
        )
        raise typer.Exit(1)

    tree = build_span_waterfall_tree(spans)
    total_trace_id = str(trace_id)
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
    print_info(f"[bold]Jaeger Tracing UI:[/bold] {format_link(_jaeger_url())}", prefix=False)
    print_info(MESSAGES.telemetry.port_forward_tip, prefix=False)


# =============================================================================
# Command: devops telemetry semconv refresh
# =============================================================================


@semconv_app.command("refresh")
def telemetry_semconv_refresh_cmd(
    commit: Annotated[str, typer.Option("--commit", help=HELP.telemetry.semconv_commit)],
) -> None:
    """Resolve the GenAI semantic conventions at a commit with weaver and rewrite the snapshot."""
    from devops_cli.exceptions import DevOpsCLIError
    from devops_cli.telemetry.semconv import (
        GENAI_SNAPSHOT_PATH,
        refresh_genai_snapshot,
        weaver_package_argv,
    )

    if is_dry_run():
        render_dry_run_result(
            command="devops telemetry semconv refresh",
            action="refresh_semconv_snapshot",
            target=str(GENAI_SNAPSHOT_PATH),
            details={"argv": weaver_package_argv("weaver", commit, Path("<tmp>/package"))},
        )
        return
    try:
        snapshot = refresh_genai_snapshot(commit, snapshot_path=GENAI_SNAPSHOT_PATH)
    except DevOpsCLIError as exc:
        print_error(exc.message, prefix=False)
        raise typer.Exit(exc.exit_code) from exc
    print_success(
        MESSAGES.telemetry.semconv_refreshed.format(
            path=GENAI_SNAPSHOT_PATH,
            attributes=len(snapshot["attributes"]),
            metrics=len(snapshot["metrics"]),
            spans=len(snapshot["spans"]),
            **snapshot["source"],
        )
    )
