"""Static linting of Grafana dashboards before they reach a server.

A dashboard with overlapping panels, a duplicate panel id, an unbound datasource, or a
malformed PromQL target renders blank or wrong, and the only signal is a human noticing.
Every one of these is detectable from the JSON alone.

PromQL targets are checked with the same validator the Prometheus commands use, so a
query that would be rejected at the command line is rejected here too.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from devops_cli.config.constants import (
    CONST_GRAFANA_DASHBOARD_GRID_WIDTH,
    CONST_GRAFANA_DEFAULT_DATASOURCE_TYPE,
)
from devops_cli.grafana.schema import Dashboard, Panel
from devops_cli.models.grafana import DashboardLintIssue, DashboardLintReport


def _issue(severity: str, message: str, panel: str = "") -> DashboardLintIssue:
    """Build a lint issue record."""
    return DashboardLintIssue(severity=severity, message=message, panel=panel)


def _check_identity(dashboard: Dashboard) -> list[DashboardLintIssue]:
    """Verify the dashboard carries the identity Grafana needs to store it."""
    issues: list[DashboardLintIssue] = []
    if not dashboard.uid.strip():
        issues.append(_issue("error", "Dashboard has no uid; Grafana cannot address it"))
    if not dashboard.title.strip():
        issues.append(_issue("warning", "Dashboard has no title"))
    return issues


def _check_panel_ids(panels: list[Panel]) -> list[DashboardLintIssue]:
    """Verify panel ids are present and unique.

    Grafana keys panel links and annotations by id, so a duplicate silently targets the
    wrong panel.
    """
    counts = Counter(panel.id for panel in panels)
    return [
        _issue("error", f"Panel id {panel_id} is used by {count} panels")
        for panel_id, count in sorted(counts.items())
        if count > 1
    ]


def _check_layout(panels: list[Panel]) -> list[DashboardLintIssue]:
    """Verify panels fit the grid and do not overlap one another."""
    issues: list[DashboardLintIssue] = []

    for panel in panels:
        if panel.grid_pos.right > CONST_GRAFANA_DASHBOARD_GRID_WIDTH:
            issues.append(
                _issue(
                    "error",
                    f"Panel extends to column {panel.grid_pos.right}, past the "
                    f"{CONST_GRAFANA_DASHBOARD_GRID_WIDTH}-column grid",
                    panel.title,
                )
            )
        if panel.grid_pos.w <= 0 or panel.grid_pos.h <= 0:
            issues.append(_issue("error", "Panel has zero or negative size", panel.title))

    positioned = [panel for panel in panels if not panel.is_row]
    for index, panel in enumerate(positioned):
        for other in positioned[index + 1 :]:
            if panel.grid_pos.overlaps(other.grid_pos):
                issues.append(
                    _issue(
                        "error",
                        f"Panel overlaps {other.title!r}; one will be hidden",
                        panel.title,
                    )
                )
    return issues


def _check_targets(panels: list[Panel]) -> list[DashboardLintIssue]:
    """Verify every visualisation panel has usable, well-formed queries."""
    from devops_cli.prometheus.promql import validate_promql

    issues: list[DashboardLintIssue] = []
    for panel in panels:
        if panel.is_row:
            continue
        if not panel.targets:
            issues.append(_issue("warning", "Panel has no query targets", panel.title))
            continue

        seen_refs: set[str] = set()
        for query in panel.targets:
            if query.ref_id in seen_refs:
                issues.append(
                    _issue(
                        "error",
                        f"Duplicate target refId {query.ref_id!r}; a series will be dropped",
                        panel.title,
                    )
                )
            seen_refs.add(query.ref_id)

            if not query.expr.strip():
                issues.append(_issue("error", "Panel target has an empty query", panel.title))
                continue
            if query.datasource.type != CONST_GRAFANA_DEFAULT_DATASOURCE_TYPE:
                continue
            validation = validate_promql(query.expr)
            if not validation:
                issues.append(_issue("error", f"Invalid PromQL: {validation.summary}", panel.title))
    return issues


def _check_datasources(panels: list[Panel]) -> list[DashboardLintIssue]:
    """Verify visualisation panels declare a datasource binding."""
    return [
        _issue("warning", "Panel has no datasource binding", panel.title)
        for panel in panels
        if not panel.is_row and panel.datasource is None
    ]


def lint_dashboard(dashboard: Dashboard) -> DashboardLintReport:
    """Run every static check against a dashboard."""
    issues: list[DashboardLintIssue] = []
    issues.extend(_check_identity(dashboard))
    issues.extend(_check_panel_ids(dashboard.panels))
    issues.extend(_check_layout(dashboard.panels))
    issues.extend(_check_targets(dashboard.panels))
    issues.extend(_check_datasources(dashboard.panels))

    return DashboardLintReport(
        dashboard_uid=dashboard.uid,
        dashboard_title=dashboard.title,
        panel_count=len(dashboard.panels),
        issues=issues,
    )


def load_dashboard(payload: dict[str, Any]) -> Dashboard:
    """Project a raw dashboard JSON payload into the typed schema.

    Grafana exports wrap the dashboard under a `dashboard` key; a file saved from the
    provisioning directory does not. Both are accepted.
    """
    body = payload.get("dashboard") if isinstance(payload.get("dashboard"), dict) else payload
    return Dashboard.model_validate(body)


def lint_dashboard_file(path: Path) -> DashboardLintReport:
    """Load and lint a dashboard JSON file."""
    import json

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return DashboardLintReport(
            dashboard_title=path.name,
            issues=[_issue("error", f"Could not parse dashboard JSON: {exc}")],
        )

    if not isinstance(payload, dict):
        return DashboardLintReport(
            dashboard_title=path.name,
            issues=[_issue("error", "Dashboard JSON root is not an object")],
        )

    report = lint_dashboard(load_dashboard(payload))
    report.source_file = path.name
    return report


__all__ = [
    "lint_dashboard",
    "lint_dashboard_file",
    "load_dashboard",
]
