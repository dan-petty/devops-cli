"""CLI commands to inspect, manage, and clear the LLM response cache."""

from __future__ import annotations

from typing import Annotated

import typer

from devops_cli.config.defaults import DEFAULT_TABLE_FORMAT
from devops_cli.core.cli import new_typer
from devops_cli.lang import HELP, MESSAGES

app = new_typer(
    help=HELP.ai.cache,
    no_args_is_help=True,
)


@app.command(name="status")
def cache_status(
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
) -> None:
    """Display LLM response cache performance statistics, hit rates, and disk storage."""
    from devops_cli.ai.response_cache import get_llm_response_cache
    from devops_cli.output import format_json, print_table, write_stdout

    cache = get_llm_response_cache()
    stats = cache.get_stats()

    if output_format == "json":
        write_stdout(format_json(stats) + "\n")
        return

    status_str = "[green]Enabled[/green]" if stats.enabled else "[yellow]Disabled[/yellow]"

    # Format bytes
    disk_bytes = stats.disk_size_bytes
    if disk_bytes < 1024:
        size_str = f"{disk_bytes} B"
    elif disk_bytes < 1024 * 1024:
        size_str = f"{disk_bytes / 1024:.1f} KB"
    else:
        size_str = f"{disk_bytes / (1024 * 1024):.2f} MB"

    ttl_days = stats.ttl_seconds / 86400

    rows = [
        ["Cache Status", status_str],
        [
            "Cache Directory",
            f"[link=file://{stats.cache_directory}]{stats.cache_directory}[/link]",
        ],
        ["In-Memory Entries", str(stats.memory_entries)],
        ["Persistent Disk Entries", str(stats.disk_entries)],
        ["Cache Hits", str(stats.hits)],
        ["Cache Misses", str(stats.misses)],
        ["Total Lookups", str(stats.total_lookups)],
        ["Hit Rate", f"{stats.hit_rate_percent:.1f}%"],
        ["Disk Storage", size_str],
        ["TTL (Expiration)", f"{ttl_days:.1f} days ({stats.ttl_seconds}s)"],
        ["Max Capacity", f"{stats.max_entries} entries"],
    ]

    print_table(
        title=MESSAGES.ai.cache_title,
        columns=[("Metric", "cyan"), ("Value", "bold green")],
        rows=rows,
        box_style=None,
    )


@app.command(name="clear")
def cache_clear() -> None:
    """Purge all in-memory and persistent disk cache entries."""
    from devops_cli.dry_run import is_dry_run, render_dry_run_result
    from devops_cli.output import print_success

    if is_dry_run():
        render_dry_run_result(
            command="devops ai cache clear",
            action="clear_llm_cache",
            details={},
        )
        return

    from devops_cli.ai.response_cache import get_llm_response_cache

    cache = get_llm_response_cache()
    cleared_count = cache.clear()
    print_success(MESSAGES.ai.cache_cleared.format(count=cleared_count))
