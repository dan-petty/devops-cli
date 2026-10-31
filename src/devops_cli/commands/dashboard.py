"""Interactive terminal UI dashboard and workstation observability command."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Final

import typer

from devops_cli.config.constants import CONST_DASHBOARD_DOMAINS
from devops_cli.config.defaults import (
    DEFAULT_DASHBOARD_REFRESH_SECONDS,
    DEFAULT_DASHBOARD_SUMMARY_POD_ROWS,
)
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.exceptions.validation import ValidationError
from devops_cli.lang import ERRORS, HELP
from devops_cli.output import (
    Group,
    Panel,
    Table,
    Text,
    box,
    get_console,
)

if TYPE_CHECKING:
    pass


def __getattr__(name: str) -> Any:
    if name in (
        "fetch_docker_status",
        "fetch_k8s_status",
        "fetch_review_status",
        "fetch_telemetry_status",
        "fetch_valkey_status",
    ):
        import devops_cli.ui.data_providers as dp

        return getattr(dp, name)
    if name in ("k8s_banner", "k8s_pod_row"):
        import devops_cli.ui.projections as proj

        return getattr(proj, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Derived from the configured domains so a new tab cannot be reachable in the TUI while
# remaining unselectable from the command line.
TAB_NUM_MAP: Final[dict[str, str]] = {
    **{
        str(index): f"tab-{domain}" for index, domain in enumerate(CONST_DASHBOARD_DOMAINS, start=1)
    },
    **{domain: f"tab-{domain}" for domain in CONST_DASHBOARD_DOMAINS},
    **{f"tab-{domain}": f"tab-{domain}" for domain in CONST_DASHBOARD_DOMAINS},
}

app = new_typer(
    name="dashboard",
    help=HELP.dashboard.app,
    rich_markup_mode="rich",
)


def _render_k8s_panel() -> Panel:
    """List the pods that need attention first, and count the ones left out."""
    fetch_k8s_status = getattr(sys.modules[__name__], "fetch_k8s_status")
    k8s_banner = getattr(sys.modules[__name__], "k8s_banner")
    k8s_pod_row = getattr(sys.modules[__name__], "k8s_pod_row")
    summary = fetch_k8s_status()
    table = Table(box=box.SIMPLE, show_header=True)
    table.add_column("Namespace", style="cyan")
    table.add_column("Pod Name", style="white")
    table.add_column("Status")
    table.add_column("Ready")
    table.add_column("Restarts")
    pods = sorted(summary.pods, key=lambda pod: not pod.unhealthy)
    for pod in pods[:DEFAULT_DASHBOARD_SUMMARY_POD_ROWS]:
        table.add_row(*k8s_pod_row(pod))
    if not summary.pods:
        table.add_row(
            "—",
            "No active pods" if summary.connected else "Cluster disconnected",
            "—",
            "—",
            "—",
        )
    hidden = len(pods) - DEFAULT_DASHBOARD_SUMMARY_POD_ROWS
    footer = [Text(f"{hidden} more pods not shown", style="dim")] if hidden > 0 else []
    content = Group(Text.from_markup(k8s_banner(summary)), table, *footer)
    return Panel(content, title="Kubernetes Status", border_style="blue")


def _render_docker_panel() -> Panel:
    fetch_docker_status = getattr(sys.modules[__name__], "fetch_docker_status")
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
    fetch_telemetry_status = getattr(sys.modules[__name__], "fetch_telemetry_status")
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
    fetch_review_status = getattr(sys.modules[__name__], "fetch_review_status")
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
    fetch_valkey_status = getattr(sys.modules[__name__], "fetch_valkey_status")
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
    resolved = TAB_NUM_MAP.get(cleaned)
    if resolved is None:
        choices = ", ".join(CONST_DASHBOARD_DOMAINS)
        raise ValidationError(
            ERRORS.dashboard.unknown_tab.format(value=tab, choices=choices),
            field="tab",
        )
    return resolved


def _run_dashboard_or_summary(
    summary: bool,
    refresh_interval: int,
    tab: str,
    dry_run: bool = False,
) -> None:
    resolved_tab = _resolve_initial_tab(tab)

    if dry_run or is_dry_run():
        from devops_cli.dry_run.requests import render_request_plan
        from devops_cli.telemetry.telemetry_plans import plan_dashboard

        render_request_plan("devops dashboard", plan_dashboard())
        return

    if summary or not sys.stdout.isatty():
        _render_summary()
        return

    from devops_cli.ui.dashboard import DashboardApp

    tui_app = DashboardApp(initial_tab=resolved_tab, refresh_interval=refresh_interval)
    tui_app.run()


@app.callback(invoke_without_command=True)
@dry_run_class("request-plan")
def main_dashboard(
    ctx: typer.Context,
    summary: bool = typer.Option(
        False,
        "--summary",
        "-s",
        help=HELP.dashboard.summary,
    ),
    refresh_interval: int = typer.Option(
        DEFAULT_DASHBOARD_REFRESH_SECONDS,
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
