"""CLI command implementations for devops ai quiesce, failover, resume, and constellation."""

from __future__ import annotations

from typing import Annotated

import typer

from devops_cli.ai.controller.manager import ConstellationManager
from devops_cli.ai.controller.models import (
    ConstellationStatus,
    QuiesceState,
    SuspendedTask,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_FALLBACK_MODEL,
    DEFAULT_AI_FALLBACK_PROVIDER,
    DEFAULT_CONSTELLATION_DRAIN_TIMEOUT,
    DEFAULT_TABLE_FORMAT,
)
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    format_json,
    print_error,
    print_info,
    print_success,
    print_table,
    write_stdout,
)


def _build_status_badge(state: QuiesceState) -> str:
    """Format constellation lifecycle status badge."""
    badge_map = {
        QuiesceState.IDLE: "[dim]IDLE[/dim]",
        QuiesceState.QUIESCED: "[bold yellow]QUIESCED[/bold yellow]",
        QuiesceState.FAILOVER: "[bold red]FAILOVER[/bold red]",
        QuiesceState.RESUMED: "[bold green]RESUMED[/bold green]",
    }
    return badge_map.get(state, state.value)


def _build_task_rows(tasks: list[SuspendedTask]) -> list[list[str]]:
    """Build tabular rows representing suspended or routed constellation tasks."""
    rows: list[list[str]] = []
    for t in tasks:
        orig = f"{t.original_provider}/{t.original_model}"
        fb = f"{t.fallback_provider}/{t.fallback_model}" if t.fallback_provider else "-"
        rows.append(
            [
                t.task_id,
                t.task_type.value,
                t.name,
                t.status,
                orig,
                fb,
            ]
        )
    return rows


def _render_constellation_status_table(status: ConstellationStatus) -> None:
    """Render terminal summary table for constellation status."""
    active_fb_str = (
        f"{status.active_fallback[0]}/{status.active_fallback[1]}"
        if status.active_fallback
        else "None"
    )
    badge = _build_status_badge(status.state)

    print_info(f"Constellation State: {badge} | Active Fallback: [cyan]{active_fb_str}[/cyan]")
    if status.reason:
        print_info(f"Reason: [dim]{status.reason}[/dim]")

    if not status.tasks:
        print_info("No registered or suspended constellation tasks.")
        return

    rows = _build_task_rows(status.tasks)
    print_table(
        title=MESSAGES.ai.constellation_tasks_title,
        columns=[
            ("Task ID", "cyan"),
            ("Type", "magenta"),
            ("Name", "white"),
            ("Status", "bold"),
            ("Original Route", "dim"),
            ("Fallback Route", "yellow"),
        ],
        rows=rows,
        box_style=None,
    )


def run_quiesce_cmd(
    reason: Annotated[
        str,
        typer.Option("--reason", "-r", help=HELP.options.quiesce_reason),
    ] = MESSAGES.ai.default_quiesce_reason,
    drain_timeout: Annotated[
        float,
        typer.Option("--drain-timeout", help=HELP.options.drain_timeout),
    ] = DEFAULT_CONSTELLATION_DRAIN_TIMEOUT,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Cleanly suspend active agent loops, schedulers, and background task runners."""
    if drain_timeout < 0:
        print_error(MESSAGES.ai.invalid_drain_timeout.format(timeout=drain_timeout))
        raise typer.Exit(code=1)

    manager = ConstellationManager()
    res = manager.quiesce(reason=reason, drain_timeout=drain_timeout, dry_run=dry_run)

    if output_format.lower() == "json":
        write_stdout(format_json(res.model_dump()) + "\n")
        return

    badge = _build_status_badge(res.state)
    if dry_run:
        print_info(MESSAGES.ai.quiesce_dry_run.format(badge=badge, reason=res.reason))
    else:
        print_success(MESSAGES.ai.quiesce_executed.format(badge=badge, count=res.suspended_count))


def run_failover_cmd(
    target_provider: Annotated[
        str,
        typer.Option("--target-provider", help=HELP.options.fallback_provider),
    ] = DEFAULT_AI_FALLBACK_PROVIDER,
    target_model: Annotated[
        str,
        typer.Option("--target-model", help=HELP.options.fallback_model),
    ] = DEFAULT_AI_FALLBACK_MODEL,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Safely re-route pending tasks to designated fallback endpoint with zero state loss."""
    manager = ConstellationManager()
    res = manager.failover(
        target_provider=target_provider,
        target_model=target_model,
        dry_run=dry_run,
    )

    if output_format.lower() == "json":
        write_stdout(format_json(res.model_dump()) + "\n")
        return

    badge = _build_status_badge(res.state)
    target_str = f"{target_provider}/{target_model}"
    if dry_run:
        print_info(MESSAGES.ai.failover_dry_run.format(badge=badge, target=target_str))
    else:
        print_success(
            MESSAGES.ai.failover_executed.format(
                badge=badge, target=target_str, count=res.rerouted_count
            )
        )


def run_resume_cmd(
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Gracefully resume suspended constellation agent loops and task runners."""
    manager = ConstellationManager()
    res = manager.resume(dry_run=dry_run)

    if output_format.lower() == "json":
        write_stdout(format_json(res.model_dump()) + "\n")
        return

    badge = _build_status_badge(res.state)
    if dry_run:
        print_info(MESSAGES.ai.resume_dry_run.format(badge=badge, count=res.resumed_count))
    else:
        print_success(MESSAGES.ai.resume_executed.format(badge=badge, count=res.resumed_count))


def run_constellation_cmd(
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
) -> None:
    """Display constellation fleet status, active fallback routes, and suspended tasks."""
    manager = ConstellationManager()
    status = manager.status()

    if output_format.lower() == "json":
        write_stdout(format_json(status.model_dump()) + "\n")
        return

    _render_constellation_status_table(status)
