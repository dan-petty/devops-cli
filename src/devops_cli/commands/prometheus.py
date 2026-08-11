"""Prometheus query and rule management (httpx REST API)."""

from __future__ import annotations

import time
from typing import Annotated, Any

import httpx2
import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.config.defaults import (
    DEFAULT_HTTP_LONG_TIMEOUT_SECONDS,
    DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import Settings, load_settings
from devops_cli.core.cli import new_typer
from devops_cli.http.validation import validate_service_url
from devops_cli.models.prometheus import PrometheusQueryResult

app = new_typer(help="Prometheus query and rule management.", no_args_is_help=True)
console = Console()

_MAX_PROMQL_LEN = 4096


def _base_url(settings: Settings) -> str:
    if not settings.prometheus.url:
        rprint(
            "[red]Prometheus URL not configured. Run: devops config set prometheus.url <url>[/red]"
        )
        raise typer.Exit(1)
    try:
        validate_service_url(
            settings.prometheus.url, "Prometheus", allow=settings.ai.allow_private_network
        )
    except ValueError as exc:
        rprint(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    return settings.prometheus.url.rstrip("/")


def _validate_expr(expr: str) -> None:
    if len(expr) > _MAX_PROMQL_LEN:
        rprint(
            f"[red]PromQL expression exceeds maximum length of {_MAX_PROMQL_LEN} characters.[/red]"
        )
        raise typer.Exit(1)


def _parse_duration(s: str) -> float:
    """Parse simple relative durations like '1h', '30m', '7d' to seconds."""
    if not s:
        return 0.0
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    unit = s[-1].lower()
    res = 0.0
    if unit in units and s[:-1].isdigit():
        res = float(int(s[:-1]) * units[unit])
    else:
        try:
            res = float(s)
        except ValueError:
            return 0.0

    max_seconds = 31_536_000.0  # 365 days
    if res > max_seconds:
        raise typer.BadParameter("Duration exceeds maximum allowed value (365 days).")
    return res


def _read_json(response: httpx2.Response) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        rprint(f"[red]Unexpected Content-Type '{content_type}' from Prometheus API endpoint.[/red]")
        raise typer.Exit(1)
    data = response.json()
    return data if isinstance(data, dict) else {}


@app.command()
def query(
    expr: Annotated[str, typer.Argument(help="PromQL expression")],
    at: Annotated[
        str | None, typer.Option("--time", "-t", help="Evaluation time (RFC3339 or Unix)")
    ] = None,
) -> None:
    """Execute an instant PromQL query."""
    _validate_expr(expr)
    settings = load_settings()
    base = _base_url(settings)
    params: dict[str, Any] = {"query": expr}
    if at:
        params["time"] = at

    with httpx2.Client() as http_client:
        response = http_client.get(
            f"{base}/api/v1/query",
            params=params,
            timeout=DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    result = PrometheusQueryResult.from_instant_response(_read_json(response))
    if result.status != "success":
        rprint(f"[red]Query failed: {result.error or 'unknown'}[/red]")
        raise typer.Exit(1)

    if not result.series:
        rprint("[yellow]No results.[/yellow]")
        return

    table = Table(title=expr[:80])
    table.add_column("Labels", style="dim")
    table.add_column("Value", style="cyan")

    for series in result.series:
        table.add_row(series.label_str or "(no labels)", series.value)
    console.print(table)


@app.command("query-range")
def query_range(
    expr: Annotated[str, typer.Argument(help="PromQL expression")],
    start: Annotated[
        str, typer.Option("--start", "-s", help="Start: duration ago (e.g. 1h) or Unix ts")
    ] = "1h",
    end: Annotated[str | None, typer.Option("--end", "-e")] = None,
    step: Annotated[str, typer.Option("--step")] = "60s",
) -> None:
    """Execute a range PromQL query and summarise the result."""
    _validate_expr(expr)
    settings = load_settings()
    base = _base_url(settings)

    now = time.time()
    try:
        start_ts = str(now - _parse_duration(start))
    except ValueError:
        start_ts = start
    end_ts = end or str(now)

    params = {"query": expr, "start": start_ts, "end": end_ts, "step": step}
    with httpx2.Client() as http_client:
        response = http_client.get(
            f"{base}/api/v1/query_range",
            params=params,
            timeout=DEFAULT_HTTP_LONG_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    result = PrometheusQueryResult.from_range_response(_read_json(response))
    total_points = sum(len(s.values) for s in result.series)
    rprint(f"[bold]{expr[:80]}[/bold]")
    rprint(f"{len(result.series)} series, {total_points} total data points (step={step})")
    for series in result.series:
        rprint(f"  [cyan]{series.label_str or '(no labels)'}[/cyan]: {len(series.values)} points")


@app.command()
def rules() -> None:
    """List Prometheus recording and alerting rules."""
    settings = load_settings()
    base = _base_url(settings)

    with httpx2.Client() as http_client:
        response = http_client.get(
            f"{base}/api/v1/rules",
            timeout=DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    table = Table(title="Prometheus Rules")
    table.add_column("Group", style="cyan")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Health")

    data = _read_json(response) if response.content else {}
    groups = data.get("data", {}).get("groups", []) if isinstance(data, dict) else []
    for group in groups:
        for rule in group.get("rules", []):
            name = rule.get("name") or rule.get("alert", "")
            health = rule.get("health", "")
            table.add_row(
                group.get("name", ""),
                name,
                rule.get("type", ""),
                "[green]ok[/green]" if health == "ok" else f"[red]{health}[/red]",
            )
    console.print(table)


@app.command()
def targets() -> None:
    """List active Prometheus scrape targets."""
    settings = load_settings()
    base = _base_url(settings)

    with httpx2.Client() as http_client:
        response = http_client.get(
            f"{base}/api/v1/targets",
            timeout=DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    table = Table(title="Prometheus Scrape Targets")
    table.add_column("Job", style="cyan")
    table.add_column("Instance")
    table.add_column("State")
    table.add_column("Last Scrape")

    data = _read_json(response)
    for target in data.get("data", {}).get("activeTargets", []):
        up = target.get("health", "unknown") == "up"
        labels = target.get("labels") or {}
        table.add_row(
            labels.get("job", ""),
            labels.get("instance", ""),
            "[green]up[/green]" if up else "[red]down[/red]",
            target.get("lastScrape", "")[:19],
        )
    console.print(table)
