"""Service status monitoring client for external platforms (GitHub, Cloudflare).

Fetches Atlassian Statuspage v2 summary feeds, parses operational indicators,
key components, and active incidents, and emits OpenTelemetry metrics and in-memory gauges.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx2

from devops_cli.config.constants import (
    CONST_CLOUDFLARE_STATUS_KEY_COMPONENTS,
    CONST_GITHUB_STATUS_KEY_COMPONENTS,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_STATUSPAGE_HTTP_TIMEOUT_SECONDS,
    CONST_URL_CLOUDFLARE_STATUS_SUMMARY,
    CONST_URL_GITHUB_STATUS_SUMMARY,
)
from devops_cli.exceptions.telemetry import ServiceStatusError
from devops_cli.http.client import new_http_client
from devops_cli.models.statuspage import StatuspageComponent, StatuspageSummary
from devops_cli.telemetry.instruments import (
    UPSTREAM_COMPONENT_STATUS,
    UPSTREAM_SERVICE_STATUS,
    emit,
)

logger = logging.getLogger(__name__)


def fetch_statuspage_summary(
    url: str,
    timeout: float = CONST_STATUSPAGE_HTTP_TIMEOUT_SECONDS,
) -> StatuspageSummary:
    """Fetch and parse Atlassian Statuspage v2 summary from target endpoint."""
    try:
        with new_http_client(timeout=timeout) as client:
            resp = client.get(url, headers={"User-Agent": "devops-cli"})
            resp.raise_for_status()
            payload = resp.json()
            return StatuspageSummary.model_validate(payload)
    except httpx2.HTTPError as exc:
        safe_msg = str(exc)[:CONST_MAX_ERROR_DETAIL_LENGTH]
        logger.warning("Failed to fetch service status from %s: %s", url, safe_msg)
        raise ServiceStatusError(f"HTTP request failed for {url}: {safe_msg}") from exc
    except Exception as exc:
        safe_msg = str(exc)[:CONST_MAX_ERROR_DETAIL_LENGTH]
        logger.warning("Failed to parse service status from %s: %s", url, safe_msg)
        raise ServiceStatusError(f"Failed to parse status payload from {url}: {safe_msg}") from exc


def fetch_github_status(
    timeout: float = CONST_STATUSPAGE_HTTP_TIMEOUT_SECONDS,
) -> StatuspageSummary:
    """Fetch GitHub published operational status summary."""
    return fetch_statuspage_summary(CONST_URL_GITHUB_STATUS_SUMMARY, timeout=timeout)


def fetch_cloudflare_status(
    timeout: float = CONST_STATUSPAGE_HTTP_TIMEOUT_SECONDS,
) -> StatuspageSummary:
    """Fetch Cloudflare published operational status summary."""
    return fetch_statuspage_summary(CONST_URL_CLOUDFLARE_STATUS_SUMMARY, timeout=timeout)


def fetch_all_service_statuses(
    timeout: float = CONST_STATUSPAGE_HTTP_TIMEOUT_SECONDS,
) -> dict[str, StatuspageSummary]:
    """Fetch published operational statuses for all monitored upstream services."""
    return {
        "github": fetch_github_status(timeout=timeout),
        "cloudflare": fetch_cloudflare_status(timeout=timeout),
    }


def filter_key_components(
    summary: StatuspageSummary,
    service: str,
) -> list[StatuspageComponent]:
    """Filter components down to primary operational components for the given service."""
    if service == "github":
        return [c for c in summary.components if c.name in CONST_GITHUB_STATUS_KEY_COMPONENTS]
    if service == "cloudflare":
        return [c for c in summary.components if c.name in CONST_CLOUDFLARE_STATUS_KEY_COMPONENTS]
    return [c for c in summary.components if not c.group]


def emit_service_status_telemetry(summary: StatuspageSummary, service: str) -> None:
    """Emit upstream service status and key component metrics over OpenTelemetry to Prometheus."""
    emit(
        UPSTREAM_SERVICE_STATUS,
        float(summary.status.severity_code),
        {"service": service, "indicator": summary.status.indicator},
    )
    for comp in filter_key_components(summary, service):
        emit(
            UPSTREAM_COMPONENT_STATUS,
            float(comp.status_code),
            {"service": service, "component": comp.name, "status": comp.status},
        )


def record_service_status_in_registry(
    summary: StatuspageSummary,
    service: str,
    registry: Any | None = None,
) -> None:
    """Record upstream service status and component metrics into InMemoryMetricsRegistry."""
    from devops_cli.telemetry.metrics import GLOBAL_METRICS

    reg = registry or GLOBAL_METRICS
    reg.set_gauge(
        UPSTREAM_SERVICE_STATUS.name,
        float(summary.status.severity_code),
        {"service": service, "indicator": summary.status.indicator},
    )
    for comp in filter_key_components(summary, service):
        reg.set_gauge(
            UPSTREAM_COMPONENT_STATUS.name,
            float(comp.status_code),
            {"service": service, "component": comp.name, "status": comp.status},
        )


def format_status_badge(status_str: str) -> str:
    """Format an operational indicator or component status with appropriate color tag."""
    s = status_str.lower()
    if s in ("operational", "none", "resolved"):
        return f"[bold green]{status_str}[/bold green]"
    if s in ("minor", "degraded_performance", "monitoring"):
        return f"[bold yellow]{status_str}[/bold yellow]"
    if s in ("major", "partial_outage", "identified"):
        return f"[bold red]{status_str}[/bold red]"
    return f"[bold red reverse]{status_str}[/bold red reverse]"


def render_statuspage_summary(summary: StatuspageSummary, service_name: str) -> None:
    """Render a structured status panel, key components table, and active incidents."""
    from devops_cli.output import print_panel, print_table

    badge = format_status_badge(summary.status.indicator)
    desc = summary.status.description
    updated = summary.page.updated_at or "-"
    url = summary.page.url

    panel_text = (
        f"Platform: [bold]{service_name}[/bold]\n"
        f"Indicator: {badge} ({desc})\n"
        f"Status Page: [link={url}]{url}[/link]\n"
        f"Updated: [cyan]{updated}[/cyan]"
    )
    print_panel(panel_text, title=f"{service_name} Operational Status")

    key_comps = filter_key_components(summary, service_name.lower())
    if key_comps:
        comp_columns = [("Component", "bold cyan"), "Status", "Description"]
        comp_rows = [
            [c.name, format_status_badge(c.status), c.description or "-"] for c in key_comps
        ]
        print_table(f"{service_name} Key Components", comp_columns, comp_rows)

    active_inc = summary.active_incidents
    if active_inc:
        inc_columns = [("Incident", "bold cyan"), "Impact", "Status", "Updated"]
        inc_rows = [
            [inc.name, format_status_badge(inc.impact), inc.status, inc.updated_at or "-"]
            for inc in active_inc
        ]
        print_table(f"{service_name} Active Incidents", inc_columns, inc_rows)
