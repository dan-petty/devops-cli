"""The research agent: read what the project pins and watch the upstream of each pin (#3896)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.constants import CONST_OUTPUT_FORMAT_TABLE
from devops_cli.config.defaults import DEFAULT_TABLE_FORMAT
from devops_cli.core.cli import new_typer
from devops_cli.core.repo import find_repo_root
from devops_cli.dry_run.decorator import dry_run_class
from devops_cli.dry_run.requests import render_request_plan
from devops_cli.dry_run.state import is_dry_run
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_table
from devops_cli.output.serialization import emit_serialized, resolve_format
from devops_cli.research.advisories import advisory_requests, find_advisories
from devops_cli.research.inventory import read_inventory
from devops_cli.research.models import AdvisoryReport
from devops_cli.telemetry import trace_span

app = new_typer(
    help=HELP.research.app,
    no_args_is_help=True,
)


@app.callback()
def research() -> None:
    """Keep the group a group while it holds one command: `devops research inventory`."""


@app.command("inventory", help=HELP.research.inventory)
@dry_run_class("no-external-request")
@trace_span("research.inventory")
def inventory(
    root: Annotated[
        Path | None,
        typer.Option("--root", help=HELP.research.inventory_root),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help=HELP.options.json_output),
    ] = False,
) -> None:
    """List every pin of the project."""
    result = read_inventory(find_repo_root(root))
    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(result.model_dump(mode="json"), resolved)
        return

    messages = MESSAGES.research
    print_table(
        messages.inventory_title,
        [
            (messages.kind_column, "bold cyan"),
            messages.ecosystem_column,
            messages.name_column,
            messages.version_column,
            messages.location_column,
        ],
        [
            [c.kind.value, c.ecosystem.value, c.name, c.version, f"{c.file}:{c.line}"]
            for c in result.components
        ],
    )
    print_info(
        messages.inventory_summary.format(
            total=result.summary.total, unknown=result.summary.unknown
        )
    )


@app.command("advisories", help=HELP.research.advisories)
@dry_run_class("request-plan")
@trace_span("research.advisories")
def advisories(
    root: Annotated[
        Path | None,
        typer.Option("--root", help=HELP.research.inventory_root),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help=HELP.options.json_output),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """List the advisories that affect the pins of the project."""
    inventory = read_inventory(find_repo_root(root))
    resolved = resolve_format(output_format, json_output=json_output)
    if dry_run or is_dry_run():
        planned = advisory_requests(inventory)
        if resolved != CONST_OUTPUT_FORMAT_TABLE:
            emit_serialized({"dry_run": True, "requests": [r.__dict__ for r in planned]}, resolved)
        else:
            render_request_plan(MESSAGES.research.advisories_plan, planned)
        return

    report = find_advisories(inventory)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(report.model_dump(mode="json"), resolved)
    else:
        _print_advisories(report)
    if report.failures:
        raise typer.Exit(code=1)


def _print_advisories(report: AdvisoryReport) -> None:
    messages = MESSAGES.research
    if report.findings:
        print_table(
            messages.advisories_title,
            [
                (messages.name_column, "bold cyan"),
                messages.version_column,
                messages.advisory_column,
                messages.severity_column,
                messages.affected_column,
                messages.fixed_column,
            ],
            [
                [
                    f.component.name,
                    f.component.version,
                    f.advisory_id,
                    f.severity,
                    f.affected_range,
                    f.fixed_version,
                ]
                for f in report.findings
            ],
        )
    summary = report.summary
    print_info(
        messages.advisories_summary.format(
            findings=summary.findings,
            packages=summary.with_findings,
            queried=summary.queried,
            unpinned=summary.unpinned,
            not_covered=sum(summary.not_covered.values()),
        )
    )
    for failure in report.failures:
        print_error(
            messages.advisories_failure.format(
                name=failure.name,
                version=failure.version,
                advisory=failure.advisory_id or messages.advisories_query,
                reason=failure.reason,
            )
        )
