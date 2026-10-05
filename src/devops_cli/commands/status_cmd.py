"""CLI command for inspecting published operational status of upstream cloud services."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from devops_cli.config.constants import CONST_STATUS_COMMAND_SERVICES
from devops_cli.core.cli import new_typer
from devops_cli.exceptions.telemetry import ServiceStatusError
from devops_cli.output import (
    format_json,
    print_error,
    print_success,
    print_table,
    write_stdout,
)
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


@app.callback(invoke_without_command=True)
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
    emit_telemetry: Annotated[
        bool,
        typer.Option(
            "--emit-telemetry",
            help="Emit operational service status metrics over OpenTelemetry to Prometheus",
        ),
    ] = False,
) -> None:
    """Inspect published operational status of upstream cloud platforms."""
    if ctx.invoked_subcommand is not None:
        return

    targets = _resolve_target_services(service)
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
                service_status.record_service_status_in_registry(summary, svc)
        except ServiceStatusError as exc:
            print_error(f"Failed to fetch {svc} status: {exc.message}")

    if not results:
        raise typer.Exit(1)

    if json_output:
        serialized = {k: v.model_dump() for k, v in results.items()}
        write_stdout(format_json(serialized) + "\n")
        return

    if len(results) > 1:
        _render_all_services_overview(results)

    for svc_key, summary in results.items():
        service_status.render_statuspage_summary(summary, svc_key.capitalize())

    if emit_telemetry:
        print_success("Emitted service status metrics to Prometheus.")
