"""Prometheus query and rule management (httpx REST API)."""

from __future__ import annotations

import time
from typing import Annotated, Any

import httpx2
import typer

from devops_cli.config.defaults import (
    DEFAULT_HTTP_LONG_TIMEOUT_SECONDS,
    DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_PROMETHEUS_QUERY_RANGE_START,
    DEFAULT_PROMETHEUS_QUERY_RANGE_STEP,
)
from devops_cli.config.settings import Settings, load_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.http.validation import validate_service_url
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.models.prometheus import PrometheusQueryResult
from devops_cli.output import (
    print_error,
    print_info,
    print_table,
    print_warning,
)

app = new_typer(help=HELP.prometheus.app, no_args_is_help=True)

_MAX_PROMQL_LEN = 4096


# =============================================================================
# Prometheus URL & Request Validation Helpers
# =============================================================================


def _base_url(settings: Settings) -> str:
    if not settings.prometheus.url:
        print_error(
            MESSAGES.prometheus.url_not_configured,
            prefix=False,
        )
        raise typer.Exit(1)
    try:
        validate_service_url(
            settings.prometheus.url, "Prometheus", allow=settings.ai.allow_private_network
        )
    except ValueError as exc:
        print_error(str(exc), prefix=False)
        raise typer.Exit(1)
    return settings.prometheus.url.rstrip("/")


def _validate_expr(expr: str) -> None:
    if len(expr) > _MAX_PROMQL_LEN:
        print_error(
            ERRORS.prometheus.expr_too_long.format(max_len=_MAX_PROMQL_LEN),
            prefix=False,
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
        print_error(
            ERRORS.prometheus.unexpected_content_type.format(content_type=content_type),
            prefix=False,
        )
        raise typer.Exit(1)
    data = response.json()
    return data if isinstance(data, dict) else {}


# =============================================================================
# Command: devops prometheus query
# =============================================================================


@app.command()
def query(
    expr: Annotated[str, typer.Argument(help=HELP.prometheus.expr)],
    at: Annotated[str | None, typer.Option("--time", "-t", help=HELP.prometheus.time_at)] = None,
) -> None:
    """Execute an instant PromQL query."""
    if is_dry_run():
        render_dry_run_result(
            command="devops prometheus query",
            target=expr,
            action="promql_instant_query",
            details={"expr": expr, "time": at},
        )
        return

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
        print_error(f"Query failed: {result.error or 'unknown'}", prefix=False)
        raise typer.Exit(1)

    if not result.series:
        print_warning(MESSAGES.prometheus.no_results, prefix=False)
        return

    rows = [[series.label_str or "(no labels)", series.value] for series in result.series]
    print_table(
        title=expr[:80],
        columns=[("Labels", "dim"), ("Value", "cyan")],
        rows=rows,
    )


# =============================================================================
# Command: devops prometheus query-range
# =============================================================================


@app.command("query-range")
def query_range(
    expr: Annotated[str, typer.Argument(help=HELP.prometheus.expr)],
    start: Annotated[
        str, typer.Option("--start", "-s", help=HELP.prometheus.start_time)
    ] = DEFAULT_PROMETHEUS_QUERY_RANGE_START,
    end: Annotated[str | None, typer.Option("--end", "-e", help=HELP.prometheus.end_time)] = None,
    step: Annotated[
        str, typer.Option("--step", help=HELP.prometheus.step)
    ] = DEFAULT_PROMETHEUS_QUERY_RANGE_STEP,
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
    if result.status != "success":
        print_error(f"Query failed: {result.error or 'unknown'}", prefix=False)
        raise typer.Exit(1)

    total_points = sum(len(s.values) for s in result.series)
    print_info(f"[bold]{expr[:80]}[/bold]", prefix=False)
    print_info(
        f"{len(result.series)} series, {total_points} total data points (step={step})",
        prefix=False,
    )
    for series in result.series:
        print_info(
            f"  [cyan]{series.label_str or '(no labels)'}[/cyan]: {len(series.values)} points",
            prefix=False,
        )


# =============================================================================
# Command: devops prometheus rules
# =============================================================================


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

    rows: list[list[str]] = []
    data = _read_json(response) if response.content else {}
    groups = data.get("data", {}).get("groups", []) if isinstance(data, dict) else []
    for group in groups:
        for rule in group.get("rules", []):
            name = rule.get("name") or rule.get("alert", "")
            health = rule.get("health", "")
            health_str = "[green]ok[/green]" if health == "ok" else f"[red]{health}[/red]"
            rows.append(
                [
                    group.get("name", ""),
                    name,
                    rule.get("type", ""),
                    health_str,
                ]
            )

    print_table(
        title="Prometheus Rules",
        columns=[("Group", "cyan"), "Name", "Type", "Health"],
        rows=rows,
    )


# =============================================================================
# Command: devops prometheus targets
# =============================================================================


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

    rows: list[list[str]] = []
    data = _read_json(response)
    for target in data.get("data", {}).get("activeTargets", []):
        up = target.get("health", "unknown") == "up"
        labels = target.get("labels") or {}
        rows.append(
            [
                labels.get("job", ""),
                labels.get("instance", ""),
                "[green]up[/green]" if up else "[red]down[/red]",
                target.get("lastScrape", "")[:19],
            ]
        )

    print_table(
        title="Prometheus Scrape Targets",
        columns=[("Job", "cyan"), "Instance", "State", "Last Scrape"],
        rows=rows,
    )
