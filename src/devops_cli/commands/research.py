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
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_info, print_table
from devops_cli.output.serialization import emit_serialized, resolve_format
from devops_cli.research.inventory import read_inventory
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
