"""Planned requests for Grafana commands in dry-run mode.

A dry run makes zero external requests and returns ordered PlannedRequest items (#412, #886).
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from devops_cli.dry_run.requests import PlannedRequest


def plan_grafana_alerts(base_url: str) -> list[PlannedRequest]:
    """Generate planned requests for grafana alerts."""
    return [
        PlannedRequest(
            method="GET",
            target=f"{base_url}/api/v1/provisioning/alert-rules",
        )
    ]


def plan_grafana_dashboards_export(base_url: str, uid: str) -> list[PlannedRequest]:
    """Generate planned requests for grafana dashboards export."""
    return [
        PlannedRequest(
            method="GET",
            target=f"{base_url}/api/dashboards/uid/{quote(uid, safe='')}",
        )
    ]


def plan_grafana_dashboards_import(
    base_url: str,
    file: Path,
    folder_id: int = 0,
) -> list[PlannedRequest]:
    """Generate planned requests for grafana dashboards import."""
    return [
        PlannedRequest(
            method="POST",
            target=f"{base_url}/api/dashboards/db",
            stdin=f"<dashboard-json:{file}> (folder_id={folder_id})",
        )
    ]


def plan_grafana_dashboards_list(base_url: str) -> list[PlannedRequest]:
    """Generate planned requests for grafana dashboards list."""
    return [
        PlannedRequest(
            method="GET",
            target=f"{base_url}/api/search?type=dash-db",
        )
    ]


def plan_grafana_dashboards_sync(base_url: str, files: list[Path]) -> list[PlannedRequest]:
    """Generate planned requests for grafana dashboards sync."""
    if not files:
        return [
            PlannedRequest(
                method="POST",
                target=f"{base_url}/api/dashboards/db",
                condition="<dashboard-files-found>",
            )
        ]
    return [
        PlannedRequest(
            method="POST",
            target=f"{base_url}/api/dashboards/db",
            stdin=f"<dashboard-json:{f}>",
        )
        for f in files
    ]


def plan_grafana_datasources(base_url: str) -> list[PlannedRequest]:
    """Generate planned requests for grafana datasources."""
    return [
        PlannedRequest(
            method="GET",
            target=f"{base_url}/api/datasources",
        )
    ]


def plan_grafana_search(base_url: str, query: str = "") -> list[PlannedRequest]:
    """Generate planned requests for grafana search."""
    target = f"{base_url}/api/search"
    if query:
        target += f"?query={quote(query)}"
    return [
        PlannedRequest(
            method="GET",
            target=target,
        )
    ]
