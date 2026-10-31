"""CLI command for inspecting published operational status of upstream cloud services."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from devops_cli.config.constants import (
    CONST_OUTPUT_FORMAT_TABLE,
    CONST_STATUS_COMMAND_SERVICES,
)
from devops_cli.config.defaults import DEFAULT_TABLE_FORMAT
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.exceptions.telemetry import ServiceStatusError
from devops_cli.output import (
    print_error,
    print_success,
    print_table,
)
from devops_cli.output.serialization import emit_serialized, resolve_format
from devops_cli.telemetry import service_status

app = new_typer(
    help="Inspect published operational status of upstream cloud platforms (GitHub, Cloudflare)",
    no_args_is_help=False,
)


def _render_all_services_overview(statuses: dict[str, Any]) -> None:
    """Render high-level overview table of all monitored upstream services."""
    columns = [("Service", "bold cyan"), "Status", "Indicator", "Description", "Active Incidents"]
    rows = []
    for svc_key, summary in statuses.items():
        svc_name = svc_key.capitalize()
        status_badge = service_status.format_status_badge(summary.status.indicator)
        inc_count = str(len(summary.active_incidents))
        rows.append(
            [
                svc_name,
                status_badge,
                summary.status.indicator,
                summary.status.description,
                f"[bold red]{inc_count}[/bold red]"
                if summary.active_incidents
                else "[green]0[/green]",
            ]
        )
    print_table("Monitored Upstream Platforms Status", columns, rows)


def _resolve_target_services(service: str) -> tuple[str, ...]:
    """Validate and resolve requested services."""
    clean_svc = service.lower().strip()
    if clean_svc not in CONST_STATUS_COMMAND_SERVICES:
        valid_opts = ", ".join(CONST_STATUS_COMMAND_SERVICES)
        raise typer.BadParameter(f"Invalid service '{service}'. Must be one of: {valid_opts}")
    if clean_svc == "all":
        return ("github", "cloudflare")
    return (clean_svc,)


def _handle_status_dry_run(targets: tuple[str, ...], output_format: str, json_output: bool) -> None:
    from devops_cli.dry_run.requests import render_request_plan
    from devops_cli.telemetry.service_status import service_status_requests

    planned = service_status_requests(targets)
    resolved_format = resolve_format(output_format, json_output=json_output)
    if resolved_format != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(
            {"dry_run": True, "requests": [r.__dict__ for r in planned]}, resolved_format
        )
        return
    render_request_plan("Plan for status", planned)


def _fetch_target_statuses(targets: tuple[str, ...], emit_telemetry: bool) -> dict[str, Any]:
    fetchers = {
        "github": service_status.fetch_github_status,
        "cloudflare": service_status.fetch_cloudflare_status,
    }
    results = {}
    for svc in targets:
        try:
            summary = fetchers[svc]()
            results[svc] = summary
            if emit_telemetry:
                service_status.emit_service_status_telemetry(summary, svc)
        except ServiceStatusError as exc:
            print_error(f"Failed to fetch {svc} status: {exc.message}")
    return results


@app.callback(invoke_without_command=True)
@dry_run_class("request-plan")
def status_main(
    ctx: typer.Context,
    service: Annotated[
        str,
        typer.Option("--service", "-s", help="Target service to inspect (all, github, cloudflare)"),
    ] = "all",
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output status details in JSON format"),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format (table, json, yaml, csv)"),
    ] = DEFAULT_TABLE_FORMAT,
    emit_telemetry: Annotated[
        bool,
        typer.Option(
            "--emit-telemetry",
            help="Emit operational service status metrics over OpenTelemetry to Prometheus",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview statuspage requests without HTTP calls"),
    ] = False,
) -> None:
    """Inspect published operational status of upstream cloud platforms."""
    if ctx.invoked_subcommand is not None:
        return

    targets = _resolve_target_services(service)
    if dry_run or is_dry_run():
        _handle_status_dry_run(targets, output_format, json_output)
        return

    results = _fetch_target_statuses(targets, emit_telemetry)
    if not results:
        raise typer.Exit(1)

    resolved_format = resolve_format(output_format, json_output=json_output)
    if resolved_format != CONST_OUTPUT_FORMAT_TABLE:
        serialized = {k: v.model_dump() for k, v in results.items()}
        emit_serialized(serialized, resolved_format)
        return

    if len(results) > 1:
        _render_all_services_overview(results)

    for svc_key, summary in results.items():
        service_status.render_statuspage_summary(summary, svc_key.capitalize())

    if emit_telemetry:
        print_success("Emitted service status metrics to Prometheus.")
