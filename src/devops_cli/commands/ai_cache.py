"""CLI commands to inspect, manage, and clear the LLM response cache."""

from __future__ import annotations

from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.ai.response_cache import get_llm_response_cache
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run
from devops_cli.lang import HELP

app = new_typer(
    help=HELP.ai.cache,
    no_args_is_help=True,
)
console = Console()


@app.command(name="status")
def cache_status(
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table, json"),
    ] = "table",
) -> None:
    """Display LLM response cache performance statistics, hit rates, and disk storage."""
    cache = get_llm_response_cache()
    stats = cache.get_stats()

    if output_format == "json":
        import json

        console.print_json(json.dumps(stats, indent=2))
        return

    table = Table(title="LLM Response Cache Performance", box=None)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="bold green")

    status_str = "[green]Enabled[/green]" if stats["enabled"] else "[yellow]Disabled[/yellow]"
    table.add_row("Cache Status", status_str)
    table.add_row(
        "Cache Directory",
        f"[link=file://{stats['cache_directory']}]{stats['cache_directory']}[/link]",
    )
    table.add_row("In-Memory Entries", str(stats["memory_entries"]))
    table.add_row("Persistent Disk Entries", str(stats["disk_entries"]))
    table.add_row("Cache Hits", str(stats["hits"]))
    table.add_row("Cache Misses", str(stats["misses"]))
    table.add_row("Total Lookups", str(stats["total_lookups"]))
    table.add_row("Hit Rate", f"{stats['hit_rate_percent']:.1f}%")

    # Format bytes
    disk_bytes = stats["disk_size_bytes"]
    if disk_bytes < 1024:
        size_str = f"{disk_bytes} B"
    elif disk_bytes < 1024 * 1024:
        size_str = f"{disk_bytes / 1024:.1f} KB"
    else:
        size_str = f"{disk_bytes / (1024 * 1024):.2f} MB"
    table.add_row("Disk Storage", size_str)

    ttl_days = stats["ttl_seconds"] / 86400
    table.add_row("TTL (Expiration)", f"{ttl_days:.1f} days ({stats['ttl_seconds']}s)")
    table.add_row("Max Capacity", f"{stats['max_entries']} entries")

    console.print(table)


@app.command(name="clear")
def cache_clear() -> None:
    """Purge all in-memory and persistent disk cache entries."""
    if is_dry_run():
        from devops_cli.output import render_dry_run_result

        render_dry_run_result(
            command="devops ai cache clear",
            action="clear_llm_cache",
            details={},
        )
        return

    cache = get_llm_response_cache()
    cleared_count = cache.clear()
    rprint(
        f"[bold green]✓[/bold green] Cleared [bold]{cleared_count}[/bold] "
        "LLM response cache entries."
    )
