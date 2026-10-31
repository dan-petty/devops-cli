"""OpenTelemetry observability, tracing, and metrics management CLI."""

from __future__ import annotations

import time
from typing import Annotated, Any

import typer

from devops_cli.config.constants import (
    CONST_DEVOPS_CLI_COMMAND,
    CONST_DEVOPS_CLI_ENTRY_MODULE,
    CONST_OTEL_COLLECTOR_NAMESPACE,
    CONST_OTEL_COLLECTOR_SERVICE,
    CONST_OUTPUT_FORMAT_TABLE,
)
from devops_cli.config.defaults import (
    DEFAULT_TABLE_FORMAT,
    DEFAULT_TELEMETRY_PROFILE_POLL_INTERVAL_SECONDS,
    DEFAULT_TELEMETRY_PROFILE_POLL_SECONDS,
    DEFAULT_TELEMETRY_TEST_NAME,
)
from devops_cli.config.env import env_var_for_option
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.dry_run.requests import render_request_plan
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
)
from devops_cli.output.serialization import emit_serialized, resolve_format
from devops_cli.telemetry.instruments import TELEMETRY_TESTS_TOTAL, emit
from devops_cli.telemetry.telemetry_plans import (
    plan_telemetry_connect,
    plan_telemetry_profile,
    plan_telemetry_semconv_refresh,
    plan_telemetry_status,
    plan_telemetry_test,
)
from devops_cli.telemetry.tracer import (
    OTelTelemetryClient,
    get_tracer,
    trace_span,
)
from devops_cli.telemetry.waterfall import (
    flatten_waterfall_tree as _flatten_tree_for_display,
)
from devops_cli.telemetry.waterfall import query_tempo_trace
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
@dry_run_class("request-plan")
def telemetry_status_cmd(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Check OpenTelemetry collector health, Tempo endpoint, and trace propagation status."""
    tracer = get_tracer()
    endpoint = tracer.endpoint

    if dry_run or is_dry_run():
        render_request_plan("devops telemetry status", plan_telemetry_status(endpoint))
        return

    settings = load_settings()
    telemetry_cfg = getattr(settings, "telemetry", None)
    enabled = (
        telemetry_cfg.enabled
        if telemetry_cfg and hasattr(telemetry_cfg, "enabled")
        else tracer.enabled
    )

    tempo_cfg = getattr(settings, "tempo", None)
    tempo_url = tempo_cfg.url if tempo_cfg and hasattr(tempo_cfg, "url") else None

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
            ["Tempo API", format_link(tempo_url) if tempo_url else "Unconfigured"],
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
    if tempo_url:
        print_info(
            f"\n[dim]To query traces via Tempo API: {format_link(tempo_url)}[/dim]", prefix=False
        )


# =============================================================================
# Command: devops telemetry logfire
# =============================================================================


@app.command("connect")
@dry_run_class("request-plan")
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
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Find the cluster's OpenTelemetry collector, check it answers, and send telemetry there."""
    if dry_run or is_dry_run():
        render_request_plan(
            "devops telemetry connect",
            plan_telemetry_connect(context, namespace, service, save),
        )
        return

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
@dry_run_class("no-external-request")
def telemetry_logfire_cmd(
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> None:
    """Display Logfire structured observability bridge status and token metrics."""
    from devops_cli.telemetry.logfire import get_logfire_bridge

    bridge = get_logfire_bridge()
    status = bridge.get_status()

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(status.model_dump(), resolved)
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
@dry_run_class("request-plan")
def telemetry_test_cmd(
    name: Annotated[
        str,
        typer.Option("--name", "-n", help=HELP.telemetry.span_name),
    ] = DEFAULT_TELEMETRY_TEST_NAME,
    logfire: Annotated[
        bool,
        typer.Option("--logfire", help=HELP.telemetry.test_logfire),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Emit a test OpenTelemetry trace span and metric to the configured collector."""
    tracer = get_tracer()

    if dry_run or is_dry_run():
        render_request_plan(
            "devops telemetry test",
            plan_telemetry_test(name, tracer.endpoint, logfire=logfire),
        )
        return

    print_info(
        f"[bold]Emitting test trace span '{format_code_span(name)}' "
        f"to {format_code_span(tracer.endpoint)}...[/bold]",
        prefix=False,
    )
    start = time.perf_counter()

    with trace_span(name, attributes={"test": True, "cli": "devops-cli"}) as span_id:
        emit(TELEMETRY_TESTS_TOTAL, 1.0)
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
    tempo_cfg = getattr(settings, "tempo", None)
    tempo_url = tempo_cfg.url if tempo_cfg and hasattr(tempo_cfg, "url") else None
    if tempo_url:
        print_info(
            f"[dim]Query in Tempo: {format_link(tempo_url)} (Service: {tracer.service_name})[/dim]",
            prefix=False,
        )


# =============================================================================
# Command: devops telemetry profile
# =============================================================================


def _tempo_url() -> str | None:
    """Return the configured Tempo HTTP API URL."""
    tempo_cfg = getattr(load_settings(), "tempo", None)
    url = getattr(tempo_cfg, "url", None)
    return str(url) if url else None


def _devops_entry_argv(command: str) -> list[str]:
    """Return the argv that runs a devops-cli command line, refusing any other command line.

    The first word must be `devops`. The rest runs under `python -P -m` the module the `devops`
    script calls, in this interpreter, so neither another program nor another `devops` found
    first on PATH is what gets started (#980). `-P` keeps the working directory off `sys.path`,
    as it is for the `devops` script: plain `python -m` puts it first, so a `token.py` or a
    `devops_cli/` in the directory profiled from would run in place of devops-cli's own code.
    """
    import shlex
    import sys

    try:
        words = shlex.split(command)
    except ValueError:
        words = []
    if words[:1] != [CONST_DEVOPS_CLI_COMMAND]:
        print_error(MESSAGES.telemetry.profile_devops_only)
        raise typer.Exit(1)
    return [sys.executable, "-P", "-m", CONST_DEVOPS_CLI_ENTRY_MODULE, *words[1:]]


def _run_profiled_command(command: str, argv: list[str], tracer: OTelTelemetryClient) -> str:
    """Run a devops-cli command inside a profile span and return the trace it ran under."""
    from devops_cli.telemetry.waterfall import run_profiled_command

    return run_profiled_command(command, argv, tracer)


def _read_trace_from_tempo(trace_id: str, tempo_url: str) -> list[dict[str, Any]]:
    """Poll Tempo until the trace stops growing, within a fixed bound."""
    from devops_cli.telemetry.waterfall import poll_trace_spans

    return poll_trace_spans(
        trace_id,
        tempo_url,
        timeout=DEFAULT_TELEMETRY_PROFILE_POLL_SECONDS,
        interval=DEFAULT_TELEMETRY_PROFILE_POLL_INTERVAL_SECONDS,
        query_fn=query_tempo_trace,
    )


@app.command("profile")
@dry_run_class("request-plan")
def telemetry_profile_cmd(
    command: Annotated[
        str | None,
        typer.Argument(help=HELP.telemetry.command_to_profile),
    ] = None,
    trace_id: Annotated[
        str | None,
        typer.Option("--trace-id", "-t", help=HELP.telemetry.trace_id),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run a devops-cli command, or name a trace, and show its span waterfall as Tempo recorded it."""
    if dry_run or is_dry_run():
        render_request_plan(
            "devops telemetry profile",
            plan_telemetry_profile(command, trace_id, _tempo_url()),
        )
        return

    argv = _devops_entry_argv(command) if command else None

    from devops_cli.telemetry.tracer import build_span_waterfall_tree

    if not command and not trace_id:
        print_error("Pass a command to profile, or --trace-id to show a trace already in Tempo.")
        raise typer.Exit(2)

    tracer = get_tracer()
    if command and argv:
        if not tracer.enabled:
            print_error(
                "Telemetry export is off, so the command's spans would never reach a collector. "
                f"Enable it (telemetry.enabled, or {env_var_for_option('telemetry.enabled')}=true) and run the "
                "collector."
            )
            raise typer.Exit(1)
        trace_id = _run_profiled_command(command, argv, tracer)

    tempo_url = _tempo_url()
    if not tempo_url:
        print_error(
            "No Tempo URL configured. Run: devops config set tempo.url <url>",
            prefix=False,
        )
        raise typer.Exit(1)
    spans = _read_trace_from_tempo(str(trace_id), tempo_url)
    if not spans:
        print_error(
            f"No spans for trace {trace_id} reached Tempo at {tempo_url} within "
            f"{DEFAULT_TELEMETRY_PROFILE_POLL_SECONDS:.0f}s; check the collector and Tempo "
            "are running."
        )
        raise typer.Exit(1)

    tree = build_span_waterfall_tree(spans)
    total_trace_id = str(trace_id)
    min_start = min(int(s.get("startTimeUnixNano", 0)) for s in spans)
    max_end = max(int(s.get("endTimeUnixNano", 0)) for s in spans)
    total_dur_ms = max(0.0, (max_end - min_start) / 1e6)

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        payload = {
            "trace_id": total_trace_id,
            "total_duration_ms": round(total_dur_ms, 2),
            "span_count": len(spans),
            "waterfall": [n.to_dict() for n in tree],
        }
        emit_serialized(payload, resolved)
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
@dry_run_class("no-external-request")
def telemetry_open_ui_cmd() -> None:
    """Print and show the Tempo HTTP API endpoint for inspecting traces."""
    url = _tempo_url()
    if not url:
        print_info("[bold]Tempo HTTP API:[/bold] Unconfigured", prefix=False)
        print_info(MESSAGES.telemetry.port_forward_tip, prefix=False)
        return
    print_info(f"[bold]Tempo HTTP API:[/bold] {format_link(url)}", prefix=False)
    print_info(MESSAGES.telemetry.port_forward_tip, prefix=False)


# =============================================================================
# Command: devops telemetry semconv refresh
# =============================================================================


@semconv_app.command("refresh")
@dry_run_class("request-plan")
def telemetry_semconv_refresh_cmd(
    commit: Annotated[str, typer.Option("--commit", help=HELP.telemetry.semconv_commit)],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Resolve the GenAI semantic conventions at a commit with weaver and rewrite the snapshot."""
    if dry_run or is_dry_run():
        render_request_plan(
            "devops telemetry semconv refresh",
            plan_telemetry_semconv_refresh(commit),
        )
        return

    from devops_cli.telemetry.semconv import (
        GENAI_SNAPSHOT_PATH,
        refresh_genai_snapshot,
    )

    snapshot = refresh_genai_snapshot(commit, snapshot_path=GENAI_SNAPSHOT_PATH)
    print_success(
        MESSAGES.telemetry.semconv_refreshed.format(
            path=GENAI_SNAPSHOT_PATH,
            attributes=len(snapshot["attributes"]),
            metrics=len(snapshot["metrics"]),
            spans=len(snapshot["spans"]),
            **snapshot["source"],
        )
    )
