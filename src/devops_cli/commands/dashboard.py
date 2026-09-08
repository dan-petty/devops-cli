"""Interactive terminal UI dashboard and workstation observability command."""

from __future__ import annotations

import sys
from typing import Final

import typer

from devops_cli.core.cli import new_typer
from devops_cli.lang import HELP
from devops_cli.output import (
    Group,
    Panel,
    Table,
    Text,
    box,
    get_console,
)
from devops_cli.ui.data_providers import (
    fetch_docker_status,
    fetch_k8s_status,
    fetch_review_status,
    fetch_telemetry_status,
    fetch_valkey_status,
)

TAB_NUM_MAP: Final[dict[str, str]] = {
    "1": "tab-k8s",
    "2": "tab-docker",
    "3": "tab-telemetry",
    "4": "tab-ai",
    "5": "tab-valkey",
    "k8s": "tab-k8s",
    "docker": "tab-docker",
    "telemetry": "tab-telemetry",
    "ai": "tab-ai",
    "valkey": "tab-valkey",
}

app = new_typer(
    name="dashboard",
    help=HELP.dashboard.app,
    rich_markup_mode="rich",
)


def _render_k8s_panel() -> Panel:
    summary = fetch_k8s_status()
    table = Table(box=box.SIMPLE, show_header=True)
    table.add_column("Namespace", style="cyan")
    table.add_column("Pod Name", style="white")
    table.add_column("Status", style="green")
    table.add_column("Ready")
    table.add_column("Restarts")
    for p in summary.pods[:10]:
        table.add_row(p["namespace"], p["name"], p["status"], p["ready"], p["restarts"])
    if not summary.pods:
        table.add_row(
            "—",
            "No active pods" if summary.connected else "Cluster disconnected",
            "—",
            "—",
            "—",
        )
    status_badge = (
        "[green]Connected[/green]" if summary.connected else "[yellow]Disconnected[/yellow]"
    )
    mk_text = " | Minikube: Active" if summary.minikube_active else ""
    content = Group(
        Text.from_markup(f"Status: {status_badge}{mk_text}"),
        table,
    )
    return Panel(content, title="Kubernetes Status", border_style="blue")


def _render_docker_panel() -> Panel:
    summary = fetch_docker_status()
    table = Table(box=box.SIMPLE, show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Image", style="dim")
    table.add_column("Status", style="green")
    for c in summary.containers[:10]:
        table.add_row(c["id"][:12], c["name"], c["image"], c["status"])
    if not summary.containers:
        table.add_row(
            "—",
            "No running containers" if summary.connected else "Docker daemon inactive",
            "—",
            "—",
        )
    status_badge = "[green]Active[/green]" if summary.connected else "[yellow]Inactive[/yellow]"
    content = Group(
        Text.from_markup(f"Status: {status_badge} ({len(summary.containers)} containers)"),
        table,
    )
    return Panel(content, title="Docker Containers", border_style="green")


def _render_telemetry_panel() -> Panel:
    summary = fetch_telemetry_status()
    table = Table(box=box.SIMPLE, show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Type", style="dim")
    table.add_column("Value / Count", style="green")
    for name, val in list(summary.counters.items())[:5]:
        table.add_row(name, "Counter", f"{val:.1f}")
    for name, val in list(summary.gauges.items())[:5]:
        table.add_row(name, "Gauge", f"{val:.1f}")
    if not summary.counters and not summary.gauges:
        table.add_row("—", "No recorded metrics", "0")
    content = Group(
        Text.from_markup(
            f"Counters: {summary.counter_count} | Gauges: {summary.gauge_count} | Histograms: {summary.histogram_count}"
        ),
        table,
    )
    return Panel(content, title="Telemetry Metrics", border_style="magenta")


def _render_ai_panel() -> Panel:
    summary = fetch_review_status()
    table = Table(box=box.SIMPLE, show_header=True)
    table.add_column("Severity", style="bold")
    table.add_column("Title", style="white")
    table.add_column("Location", style="dim")
    table.add_column("Status")
    for f in summary.findings[:5]:
        table.add_row(
            f.get("severity", "MEDIUM"),
            f.get("title", "Untitled")[:40],
            f.get("location", "—"),
            f.get("status", "UNVERIFIED"),
        )
    if not summary.findings:
        table.add_row("—", "No findings", "—", "—")
    if summary.has_session:
        dist_str = (
            " | ".join(f"{k}: {v}" for k, v in summary.severity_distribution.items()) or "None"
        )
        header_txt = f"Session: {summary.session_name} | Total: {summary.total_findings} (Verified: {summary.verified_count}) | {dist_str}"
    else:
        header_txt = "No active review sessions found."
    content = Group(
        Text.from_markup(header_txt),
        table,
    )
    return Panel(content, title="AI Review Findings", border_style="yellow")


def _render_valkey_panel() -> Panel:
    summary = fetch_valkey_status()
    table = Table(box=box.SIMPLE, show_header=True)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Status", "Connected" if summary.connected else "Offline")
    table.add_row("Version", summary.version)
    table.add_row("Used Memory", summary.used_memory)
    table.add_row("Hit Ratio", f"{summary.hit_ratio:.1f}%")
    table.add_row("Key Count", str(summary.key_count))
    content = Group(
        Text.from_markup(
            f"Valkey Cache: {'Connected' if summary.connected else 'Offline'} | Hit Ratio: {summary.hit_ratio:.1f}%"
        ),
        table,
    )
    return Panel(content, title="Valkey Caching", border_style="red")


def _render_summary() -> None:
    console = get_console()
    console.print(
        Panel(
            "[bold]Workstation Dashboard Summary[/bold]\n"
            "Real-time overview of Kubernetes, Docker, Telemetry, AI Reviews, and Valkey caching.",
            title="Workstation Dashboard Summary",
            border_style="cyan",
        )
    )
    console.print(_render_k8s_panel())
    console.print(_render_docker_panel())
    console.print(_render_telemetry_panel())
    console.print(_render_ai_panel())
    console.print(_render_valkey_panel())


def _resolve_initial_tab(tab: str) -> str:
    cleaned = tab.strip().lower()
    return TAB_NUM_MAP.get(cleaned, cleaned if cleaned.startswith("tab-") else f"tab-{cleaned}")


def _run_dashboard_or_summary(
    summary: bool,
    refresh_interval: int,
    tab: str,
    dry_run: bool = False,
) -> None:
    if summary or dry_run or not sys.stdout.isatty():
        _render_summary()
        return

    from devops_cli.ui.dashboard import DashboardApp

    resolved_tab = _resolve_initial_tab(tab)
    tui_app = DashboardApp(initial_tab=resolved_tab, refresh_interval=refresh_interval)
    tui_app.run()


@app.callback(invoke_without_command=True)
def main_dashboard(
    ctx: typer.Context,
    summary: bool = typer.Option(
        False,
        "--summary",
        "-s",
        help=HELP.dashboard.summary,
    ),
    refresh_interval: int = typer.Option(
        5,
        "--refresh-interval",
        "-r",
        help=HELP.dashboard.refresh_interval,
    ),
    tab: str = typer.Option(
        "k8s",
        "--tab",
        "-t",
        help=HELP.dashboard.tab,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=HELP.dashboard.dry_run,
    ),
) -> None:
    """Launch interactive terminal UI dashboard or display static summary."""
    if ctx.invoked_subcommand is not None:
        return
    _run_dashboard_or_summary(
        summary=summary, refresh_interval=refresh_interval, tab=tab, dry_run=dry_run
    )


@app.command("dashboard")
def dashboard_cmd(
    summary: bool = typer.Option(
        False,
        "--summary",
        "-s",
        help=HELP.dashboard.summary,
    ),
    refresh_interval: int = typer.Option(
        5,
        "--refresh-interval",
        "-r",
        help=HELP.dashboard.refresh_interval,
    ),
    tab: str = typer.Option(
        "k8s",
        "--tab",
        "-t",
        help=HELP.dashboard.tab,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=HELP.dashboard.dry_run,
    ),
) -> None:
    """Launch interactive terminal UI dashboard or display static summary."""
    _run_dashboard_or_summary(
        summary=summary, refresh_interval=refresh_interval, tab=tab, dry_run=dry_run
    )


@app.command("tui")
def tui_cmd(
    summary: bool = typer.Option(
        False,
        "--summary",
        "-s",
        help=HELP.dashboard.summary,
    ),
    refresh_interval: int = typer.Option(
        5,
        "--refresh-interval",
        "-r",
        help=HELP.dashboard.refresh_interval,
    ),
    tab: str = typer.Option(
        "k8s",
        "--tab",
        "-t",
        help=HELP.dashboard.tab,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=HELP.dashboard.dry_run,
    ),
) -> None:
    """Launch interactive terminal UI dashboard or display static summary (alias for dashboard)."""
    _run_dashboard_or_summary(
        summary=summary, refresh_interval=refresh_interval, tab=tab, dry_run=dry_run
    )
