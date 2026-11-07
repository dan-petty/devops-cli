"""Prometheus query and rule management (httpx REST API)."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Any

import typer

from devops_cli.config.constants import CONST_OUTPUT_FORMAT_TABLE
from devops_cli.config.defaults import (
    DEFAULT_ANOMALY_Z_THRESHOLD,
    DEFAULT_PROMETHEUS_QUERY_RANGE_START,
    DEFAULT_PROMETHEUS_QUERY_RANGE_STEP,
    DEFAULT_TABLE_FORMAT,
)
from devops_cli.config.settings import Settings, load_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.dry_run.requests import render_request_plan
from devops_cli.http.egress import configured_level
from devops_cli.http.urls import service_base_url
from devops_cli.lang import HELP, MESSAGES
from devops_cli.models.prometheus import PrometheusQueryResult
from devops_cli.output import (
    print_error,
    print_info,
    print_table,
    print_warning,
)
from devops_cli.output.serialization import emit_serialized, resolve_format
from devops_cli.prometheus.client import (
    DurationTooLongError,
    PrometheusClient,
    PrometheusContentTypeError,
    expression_problem,
    parse_duration,
)
from devops_cli.prometheus.prometheus_plans import (
    plan_prometheus_analyze,
    plan_prometheus_query,
    plan_prometheus_query_range,
    plan_prometheus_rules,
    plan_prometheus_targets,
)

# A refusal at the connect ends each command with its message and no traceback.
app = new_typer(help=HELP.prometheus.app, no_args_is_help=True)


# =============================================================================
# Prometheus URL & Request Validation Helpers
# =============================================================================


def _base_url(settings: Settings) -> str:
    """Return the Prometheus base URL. The check reads only the URL and makes no lookup."""
    if not settings.prometheus.url:
        print_error(
            MESSAGES.prometheus.url_not_configured,
            prefix=False,
        )
        raise typer.Exit(1)
    try:
        return service_base_url(settings.prometheus.url, "prometheus.url")
    except ValueError as exc:
        from devops_cli.security.sanitizer import mask_secrets

        print_error(mask_secrets(str(exc)), prefix=False)
        raise typer.Exit(1) from exc


@contextmanager
def _prometheus(settings: Settings, base: str) -> Iterator[PrometheusClient]:
    """Open a client of the server at `base`, at the configured egress level.

    A server that answers with something other than JSON ends the command with the content type it
    sent.
    """
    with PrometheusClient(base, configured_level(settings.ai)) as client:
        try:
            yield client
        except PrometheusContentTypeError as exc:
            print_error(str(exc), prefix=False)
            raise typer.Exit(1) from exc


def _dry_run_base_url() -> str:
    """Return the Prometheus base URL safely for dry-run request planning."""
    settings = load_settings()
    if settings.prometheus.url:
        try:
            return service_base_url(settings.prometheus.url, "prometheus.url")
        except ValueError:
            pass
    return "https://prometheus.example.com"


def _validate_expr(expr: str) -> None:
    """End the command when the expression must not be sent."""
    if (problem := expression_problem(expr)) is not None:
        print_error(problem, prefix=False)
        raise typer.Exit(1)


def _seconds(duration: str) -> float:
    """Read a relative duration; one over 365 days is a bad parameter."""
    try:
        return parse_duration(duration)
    except DurationTooLongError as exc:
        raise typer.BadParameter(str(exc)) from exc


# =============================================================================
# Command: devops prometheus query
# =============================================================================


@app.command()
@dry_run_class("request-plan")
def query(
    expr: Annotated[str, typer.Argument(help=HELP.prometheus.expr)],
    at: Annotated[str | None, typer.Option("--time", "-t", help=HELP.prometheus.time_at)] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Execute an instant PromQL query."""
    if dry_run or is_dry_run():
        render_request_plan(
            "devops prometheus query",
            plan_prometheus_query(_dry_run_base_url(), expr, at=at),
        )
        return

    _validate_expr(expr)
    settings = load_settings()
    base = _base_url(settings)

    with _prometheus(settings, base) as prometheus:
        payload = prometheus.query(expr, at=at)

    result = PrometheusQueryResult.from_instant_response(payload)
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
@dry_run_class("request-plan")
def query_range(
    expr: Annotated[str, typer.Argument(help=HELP.prometheus.expr)],
    start: Annotated[
        str, typer.Option("--start", "-s", help=HELP.prometheus.start_time)
    ] = DEFAULT_PROMETHEUS_QUERY_RANGE_START,
    end: Annotated[str | None, typer.Option("--end", "-e", help=HELP.prometheus.end_time)] = None,
    step: Annotated[
        str, typer.Option("--step", help=HELP.prometheus.step)
    ] = DEFAULT_PROMETHEUS_QUERY_RANGE_STEP,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Execute a range PromQL query and summarise the result."""
    if dry_run or is_dry_run():
        render_request_plan(
            "devops prometheus query-range",
            plan_prometheus_query_range(_dry_run_base_url(), expr, start, end or "now", step),
        )
        return

    _validate_expr(expr)
    settings = load_settings()
    base = _base_url(settings)

    now = time.time()
    start_ts = str(now - _seconds(start))
    end_ts = end or str(now)

    with _prometheus(settings, base) as prometheus:
        payload = prometheus.query_range(expr, start=start_ts, end=end_ts, step=step)

    result = PrometheusQueryResult.from_range_response(payload)
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
# Command: devops prometheus analyze
# =============================================================================


def _analysis_rows(analysis: Any) -> list[list[str]]:
    """Render a series analysis as summary table rows."""
    return [
        ["Samples", str(analysis.sample_count)],
        ["Latest", f"{analysis.latest:g}"],
        ["Min / Max", f"{analysis.minimum:g} / {analysis.maximum:g}"],
        ["Mean / Median", f"{analysis.mean:g} / {analysis.median:g}"],
        ["Std deviation", f"{analysis.stdev:g}"],
        ["Trend", f"{analysis.trend.value} (slope {analysis.slope:g}/sample)"],
        ["Anomalies", str(len(analysis.anomalies))],
        ["Forecast", ", ".join(f"{v:g}" for v in analysis.forecast) or "—"],
    ]


@app.command("analyze")
@dry_run_class("request-plan")
def analyze(
    expr: Annotated[str, typer.Argument(help=HELP.prometheus.expr)],
    start: Annotated[
        str, typer.Option("--start", "-s", help=HELP.prometheus.start_time)
    ] = DEFAULT_PROMETHEUS_QUERY_RANGE_START,
    step: Annotated[
        str, typer.Option("--step", help=HELP.prometheus.step)
    ] = DEFAULT_PROMETHEUS_QUERY_RANGE_STEP,
    threshold: Annotated[
        float, typer.Option("--threshold", "-t", help=HELP.prometheus.anomaly_threshold)
    ] = DEFAULT_ANOMALY_Z_THRESHOLD,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[bool, typer.Option("--json", help=HELP.options.json_output)] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Detect anomalies and project the trend of a metric series, computed locally."""
    if dry_run or is_dry_run():
        render_request_plan(
            "devops prometheus analyze",
            plan_prometheus_analyze(_dry_run_base_url(), expr, start, "now", step),
        )
        return

    from devops_cli.prometheus.analysis import analyze_series, extract_series_values

    _validate_expr(expr)

    settings = load_settings()
    base = _base_url(settings)
    now = time.time()
    start_ts = str(now - _seconds(start))

    with _prometheus(settings, base) as prometheus:
        payload = prometheus.query_range(expr, start=start_ts, end=str(now), step=step)

    results = (payload.get("data") or {}).get("result") or []
    if not results:
        print_info(MESSAGES.prometheus.no_series_to_analyze.format(expr=expr[:80]), prefix=False)
        return

    timestamps, values = extract_series_values(results[0])
    analysis = analyze_series(values, timestamps, threshold=threshold)

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(analysis.model_dump(mode="json"), resolved)
        return

    print_table(
        title=MESSAGES.prometheus.table_title_analysis.format(expr=expr[:60]),
        columns=[("Metric", "cyan"), "Value"],
        rows=_analysis_rows(analysis),
    )

    if analysis.has_anomalies:
        print_table(
            title=MESSAGES.prometheus.table_title_anomalies,
            columns=[("Timestamp", "cyan"), ("Value", "right"), ("Z-score", "right"), "Direction"],
            rows=[
                [
                    time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(a.timestamp)),
                    f"{a.value:g}",
                    f"{a.z_score:+.2f}",
                    a.direction,
                ]
                for a in analysis.anomalies
            ],
        )


# =============================================================================
# Command: devops prometheus rules
# =============================================================================


@app.command()
@dry_run_class("request-plan")
def rules(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """List Prometheus recording and alerting rules."""
    if dry_run or is_dry_run():
        render_request_plan(
            "devops prometheus rules",
            plan_prometheus_rules(_dry_run_base_url()),
        )
        return

    settings = load_settings()
    base = _base_url(settings)

    with _prometheus(settings, base) as prometheus:
        data = prometheus.rules()

    rows: list[list[str]] = []
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
@dry_run_class("request-plan")
def targets(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """List active Prometheus scrape targets."""
    if dry_run or is_dry_run():
        render_request_plan(
            "devops prometheus targets",
            plan_prometheus_targets(_dry_run_base_url()),
        )
        return

    settings = load_settings()
    base = _base_url(settings)

    with _prometheus(settings, base) as prometheus:
        data = prometheus.targets()

    rows: list[list[str]] = []
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
