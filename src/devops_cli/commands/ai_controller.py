"""CLI command implementations for devops ai quiesce, failover, resume, and constellation."""

from __future__ import annotations

from typing import Annotated

import typer

from devops_cli.ai.controller.manager import ConstellationManager
from devops_cli.ai.controller.models import (
    ConstellationStatus,
    QuiesceState,
)
from devops_cli.config.constants import CONST_OUTPUT_FORMAT_TABLE
from devops_cli.config.defaults import (
    DEFAULT_AI_FALLBACK_MODEL,
    DEFAULT_AI_FALLBACK_PROVIDER,
    DEFAULT_TABLE_FORMAT,
)
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    print_info,
    print_success,
)
from devops_cli.output.serialization import emit_serialized, normalize_format


def _build_status_badge(state: QuiesceState) -> str:
    """Format constellation lifecycle status badge."""
    badge_map = {
        QuiesceState.IDLE: "[dim]IDLE[/dim]",
        QuiesceState.QUIESCED: "[bold yellow]QUIESCED[/bold yellow]",
        QuiesceState.FAILOVER: "[bold red]FAILOVER[/bold red]",
        QuiesceState.RESUMED: "[bold green]RESUMED[/bold green]",
    }
    return badge_map.get(state, state.value)


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
    if status.quiesced_at:
        print_info(f"Set at: [dim]{status.quiesced_at}[/dim]")
    print_info(MESSAGES.ai.constellation_flag_only)


def run_quiesce_cmd(
    reason: Annotated[
        str,
        typer.Option("--reason", "-r", help=HELP.options.quiesce_reason),
    ] = MESSAGES.ai.default_quiesce_reason,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Set the constellation quiesce flag with a reason; it stops nothing."""
    manager = ConstellationManager()
    res = manager.quiesce(reason=reason, dry_run=dry_run)

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(res.model_dump(), resolved)
        return

    badge = _build_status_badge(res.state)
    if dry_run:
        print_info(MESSAGES.ai.quiesce_dry_run.format(badge=badge, reason=res.reason))
    else:
        print_success(MESSAGES.ai.quiesce_executed.format(badge=badge, reason=res.reason))


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
    """Record a fallback route in the constellation flag; it reroutes nothing."""
    manager = ConstellationManager()
    res = manager.failover(
        target_provider=target_provider,
        target_model=target_model,
        dry_run=dry_run,
    )

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(res.model_dump(), resolved)
        return

    badge = _build_status_badge(res.state)
    target_str = f"{target_provider}/{target_model}"
    if dry_run:
        print_info(MESSAGES.ai.failover_dry_run.format(badge=badge, target=target_str))
    else:
        print_success(MESSAGES.ai.failover_executed.format(badge=badge, target=target_str))


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
    """Clear the constellation quiesce or failover flag."""
    manager = ConstellationManager()
    res = manager.resume(dry_run=dry_run)

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(res.model_dump(), resolved)
        return

    badge = _build_status_badge(res.state)
    if dry_run:
        print_info(MESSAGES.ai.resume_dry_run.format(badge=badge))
    else:
        print_success(f"{badge} {res.message}")


def run_constellation_cmd(
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
) -> None:
    """Show the constellation flag: its state, reason and recorded fallback route."""
    manager = ConstellationManager()
    status = manager.status()

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(status.model_dump(), resolved)
        return

    _render_constellation_status_table(status)
