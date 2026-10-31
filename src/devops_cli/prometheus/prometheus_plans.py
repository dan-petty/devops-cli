"""Planned requests for Prometheus commands in dry-run mode.

A dry run makes zero external requests and returns ordered PlannedRequest items (#412, #886).
"""

from __future__ import annotations

from urllib.parse import quote

from devops_cli.dry_run.requests import PlannedRequest


def plan_prometheus_query(
    base_url: str,
    expr: str,
    at: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for prometheus query."""
    target = f"{base_url}/api/v1/query?query={quote(expr)}"
    if at:
        target += f"&time={quote(at)}"
    return [
        PlannedRequest(
            method="GET",
            target=target,
        )
    ]


def plan_prometheus_query_range(
    base_url: str,
    expr: str,
    start: str,
    end: str,
    step: str,
) -> list[PlannedRequest]:
    """Generate planned requests for prometheus query-range."""
    target = f"{base_url}/api/v1/query_range?query={quote(expr)}&start={quote(start)}&end={quote(end)}&step={quote(step)}"
    return [
        PlannedRequest(
            method="GET",
            target=target,
        )
    ]


def plan_prometheus_analyze(
    base_url: str,
    expr: str,
    start: str,
    end: str,
    step: str,
) -> list[PlannedRequest]:
    """Generate planned requests for prometheus analyze."""
    target = f"{base_url}/api/v1/query_range?query={quote(expr)}&start={quote(start)}&end={quote(end)}&step={quote(step)}"
    return [
        PlannedRequest(
            method="GET",
            target=target,
        )
    ]


def plan_prometheus_rules(base_url: str) -> list[PlannedRequest]:
    """Generate planned requests for prometheus rules."""
    return [
        PlannedRequest(
            method="GET",
            target=f"{base_url}/api/v1/rules",
        )
    ]


def plan_prometheus_targets(base_url: str) -> list[PlannedRequest]:
    """Generate planned requests for prometheus targets."""
    return [
        PlannedRequest(
            method="GET",
            target=f"{base_url}/api/v1/targets",
        )
    ]
