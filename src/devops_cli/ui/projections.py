"""Pure projections from domain summaries to dashboard table rows and banners.

Row construction and banner text previously lived inside the widget methods that also
performed the network fetch, so neither could be exercised without constructing a running
Textual app against a live cluster. These functions are pure: a summary in, rows and a
banner line out.

Separating them is what lets the rendering be tested directly and keeps the widgets thin
enough to be obviously correct.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from devops_cli.config.constants import (
    CONST_DASHBOARD_DOMAIN_AI,
    CONST_DASHBOARD_DOMAIN_DOCKER,
    CONST_DASHBOARD_DOMAIN_K8S,
    CONST_DASHBOARD_DOMAIN_LABELS,
    CONST_DASHBOARD_DOMAIN_TELEMETRY,
    CONST_DASHBOARD_DOMAIN_VALKEY,
    CONST_DOCKER_RESOURCE_CONTAINERS,
    CONST_DOCKER_RESOURCE_IMAGES,
    CONST_DOCKER_RESOURCE_LABELS,
    CONST_DOCKER_RESOURCE_NETWORKS,
    CONST_DOCKER_RESOURCE_REGISTRIES,
    CONST_DOCKER_RESOURCE_VOLUMES,
)
from devops_cli.ui.data_providers import (
    DockerSummary,
    K8sSummary,
    ReviewSummary,
    TelemetrySummary,
    ValkeySummary,
)
from devops_cli.ui.state import DomainSnapshot

CONST_STATUS_DOT_OK = "[green]●[/green]"
CONST_STATUS_DOT_WARN = "[yellow]●[/yellow]"
CONST_STATUS_DOT_ERROR = "[red]●[/red]"

CONST_AI_TITLE_MAX_CHARS = 45

DOMAIN_COLUMNS: dict[str, tuple[str, ...]] = {
    CONST_DASHBOARD_DOMAIN_K8S: ("Namespace", "Pod Name", "Status", "Ready", "Restarts"),
    CONST_DASHBOARD_DOMAIN_DOCKER: ("Container ID", "Name", "Image", "Status"),
    CONST_DASHBOARD_DOMAIN_TELEMETRY: ("Metric Name", "Type", "Value / Count"),
    CONST_DASHBOARD_DOMAIN_AI: ("Severity", "Title", "Location", "Status"),
    CONST_DASHBOARD_DOMAIN_VALKEY: ("Metric Property", "Value"),
}


def _dot(connected: bool) -> str:
    """Render a connection indicator."""
    return CONST_STATUS_DOT_OK if connected else CONST_STATUS_DOT_WARN


def _label(domain: str) -> str:
    """Return the display label for a domain."""
    return CONST_DASHBOARD_DOMAIN_LABELS.get(domain, domain.title())


def _records(records: list[dict[str, str]], keys: tuple[str, ...]) -> list[tuple[str, ...]]:
    """Project a list of mappings into table rows, tolerating absent keys.

    A provider that omits a key yields an empty cell rather than raising: a partially
    populated table is recoverable, an exception on the UI thread is not.
    """
    return [tuple(str(record.get(key, "")) for key in keys) for record in records]


# =============================================================================
# Banners
# =============================================================================


def k8s_banner(summary: K8sSummary) -> str:
    """Render the Kubernetes connection banner."""
    state = "Connected" if summary.connected else "Disconnected"
    minikube = " | Minikube: Active" if summary.minikube_active else ""
    return f"{_dot(summary.connected)} Kubernetes: {state}{minikube}"


def docker_banner(summary: DockerSummary) -> str:
    """Render the Docker daemon banner.

    Running and total are both shown: the panel lists stopped containers too, so a single
    count would not match either what is listed or what is actually running.
    """
    state = "Active" if summary.connected else "Inactive"
    running = summary.running_containers
    return (
        f"{_dot(summary.connected)} Docker: {state} "
        f"({running} running / {len(summary.containers)} total)"
    )


def images_banner(summary: DockerSummary) -> str:
    """Render the Docker image inventory banner."""
    dangling = sum(1 for record in summary.images if record.get("tag", "").startswith("<none>"))
    suffix = f", {dangling} dangling" if dangling else ""
    return f"{_dot(summary.connected)} Images: {len(summary.images)}{suffix}"


def networks_banner(summary: DockerSummary) -> str:
    """Render the Docker network inventory banner."""
    return f"{_dot(summary.connected)} Networks: {len(summary.networks)}"


def volumes_banner(summary: DockerSummary) -> str:
    """Render the Docker volume inventory banner."""
    return f"{_dot(summary.connected)} Volumes: {len(summary.volumes)}"


def registries_banner(summary: DockerSummary) -> str:
    """Render the configured registry banner."""
    return f"{_dot(summary.connected)} Registries: {len(summary.registries)} configured"


def telemetry_banner(summary: TelemetrySummary) -> str:
    """Render the instrument count banner, naming where the figures came from.

    An empty in-process registry is indistinguishable from broken instrumentation unless
    the panel says which registry it read.
    """
    counts = (
        f"{summary.counter_count} Counters, {summary.gauge_count} Gauges, "
        f"{summary.histogram_count} Histograms"
    )
    if summary.error_message:
        return f"{CONST_STATUS_DOT_WARN} Telemetry ({summary.source}): {counts} — {summary.error_message}"
    return f"{_dot(True)} Telemetry ({summary.source}): {counts}"


def ai_banner(summary: ReviewSummary) -> str:
    """Render the review session banner.

    The session shown is the newest **completed** one. A review that is still running
    creates its directory before it writes any findings, so the newest directory was being
    presented as the latest result with zero findings, hiding the last real review.
    """
    if not summary.has_session:
        return "No active or past AI code review sessions found."
    pending = f" | {len(summary.incomplete)} incomplete" if summary.incomplete else ""
    distribution = (
        " | ".join(f"{name}: {count}" for name, count in summary.severity_distribution.items())
        or "None"
    )
    return (
        f"Review {summary.session_name} | "
        f"Total: {summary.total_findings} (Verified: {summary.verified_count}) | "
        f"{distribution}{pending}"
    )


def valkey_banner(summary: ValkeySummary) -> str:
    """Render the Valkey cache banner.

    An offline cache names the endpoint that was tried and why it failed. "Offline" alone
    cannot distinguish a cache that is not deployed from one that is deployed and refusing
    connections, and sends the reader to the wrong place.
    """
    endpoint = f" @ {summary.endpoint}" if summary.endpoint else ""
    if not summary.connected:
        reason = f" — {summary.error_message}" if summary.error_message else ""
        return f"{_dot(False)} Valkey Cache: Offline{endpoint}{reason}"
    return (
        f"{_dot(True)} Valkey Cache: {summary.version}{endpoint} | "
        f"Used Memory: {summary.used_memory} | Hit Ratio: {summary.hit_ratio:.1f}%"
    )


def loading_banner(domain: str) -> str:
    """Render the banner shown before a domain has produced its first result."""
    return f"{CONST_STATUS_DOT_WARN} {_label(domain)}: loading…"


def error_banner(domain: str, error: str) -> str:
    """Render the banner for a domain whose refresh failed."""
    return f"{CONST_STATUS_DOT_ERROR} {_label(domain)}: refresh failed — {error}"


def stale_banner(domain: str, banner: str, age_seconds: float) -> str:
    """Mark an otherwise-successful banner as showing aged data."""
    return f"{banner}  [dim](stale: {age_seconds:.0f}s)[/dim]"


# =============================================================================
# Rows
# =============================================================================


def k8s_rows(summary: K8sSummary) -> list[tuple[str, ...]]:
    """Project pods into table rows."""
    return _records(summary.pods, ("namespace", "name", "status", "ready", "restarts"))


def docker_rows(summary: DockerSummary) -> list[tuple[str, ...]]:
    """Project containers into table rows."""
    return _records(summary.containers, ("id", "name", "image", "status"))


def telemetry_rows(summary: TelemetrySummary) -> list[tuple[str, ...]]:
    """Project counters and gauges into table rows."""
    rows: list[tuple[str, ...]] = [
        (name, "Counter", f"{value:.1f}") for name, value in summary.counters.items()
    ]
    rows.extend((name, "Gauge", f"{value:.1f}") for name, value in summary.gauges.items())
    return rows


def ai_rows(summary: ReviewSummary) -> list[tuple[str, ...]]:
    """Project review findings into table rows."""
    return [
        (
            str(finding.get("severity", "MEDIUM")),
            str(finding.get("title", "Untitled"))[:CONST_AI_TITLE_MAX_CHARS],
            str(finding.get("location", "—")),
            str(finding.get("status", "UNVERIFIED")),
        )
        for finding in summary.findings
    ]


def images_rows(summary: DockerSummary) -> list[tuple[str, ...]]:
    """Project Docker images into table rows."""
    return _records(summary.images, ("id", "tag", "size", "created"))


def networks_rows(summary: DockerSummary) -> list[tuple[str, ...]]:
    """Project Docker networks into table rows."""
    return _records(summary.networks, ("id", "name", "driver", "scope", "containers"))


def volumes_rows(summary: DockerSummary) -> list[tuple[str, ...]]:
    """Project Docker volumes into table rows."""
    return _records(summary.volumes, ("name", "driver", "mountpoint", "size", "created"))


def registries_rows(summary: DockerSummary) -> list[tuple[str, ...]]:
    """Project configured registries into table rows."""
    return _records(summary.registries, ("name", "kind", "status"))


def valkey_rows(summary: ValkeySummary) -> list[tuple[str, ...]]:
    """Project cache server properties into table rows."""
    return [
        ("Server Version", summary.version),
        ("Status", "Connected" if summary.connected else "Offline"),
        ("Used Memory", summary.used_memory),
        ("Cache Hit Ratio", f"{summary.hit_ratio:.1f}%"),
        ("Connected Clients", str(summary.connected_clients)),
        ("Key Count", str(summary.key_count)),
        ("Total Commands", str(summary.total_commands)),
    ]


# =============================================================================
# Snapshot rendering
# =============================================================================

_BANNERS: dict[str, Callable[[Any], str]] = {
    CONST_DASHBOARD_DOMAIN_K8S: k8s_banner,
    CONST_DASHBOARD_DOMAIN_DOCKER: docker_banner,
    CONST_DASHBOARD_DOMAIN_TELEMETRY: telemetry_banner,
    CONST_DASHBOARD_DOMAIN_AI: ai_banner,
    CONST_DASHBOARD_DOMAIN_VALKEY: valkey_banner,
}

_ROWS: dict[str, Callable[[Any], list[tuple[str, ...]]]] = {
    CONST_DASHBOARD_DOMAIN_K8S: k8s_rows,
    CONST_DASHBOARD_DOMAIN_DOCKER: docker_rows,
    CONST_DASHBOARD_DOMAIN_TELEMETRY: telemetry_rows,
    CONST_DASHBOARD_DOMAIN_AI: ai_rows,
    CONST_DASHBOARD_DOMAIN_VALKEY: valkey_rows,
}


DOCKER_RESOURCE_COLUMNS: dict[str, tuple[str, ...]] = {
    CONST_DOCKER_RESOURCE_CONTAINERS: ("Container ID", "Name", "Image", "Status"),
    CONST_DOCKER_RESOURCE_IMAGES: ("Image ID", "Repository:Tag", "Size", "Created"),
    CONST_DOCKER_RESOURCE_NETWORKS: ("Network ID", "Name", "Driver", "Scope", "Containers"),
    CONST_DOCKER_RESOURCE_VOLUMES: ("Name", "Driver", "Mountpoint", "Size", "Created"),
    CONST_DOCKER_RESOURCE_REGISTRIES: ("Registry", "Kind", "Status"),
}

DOCKER_RESOURCE_ROWS: dict[str, Callable[[Any], list[tuple[str, ...]]]] = {
    CONST_DOCKER_RESOURCE_CONTAINERS: docker_rows,
    CONST_DOCKER_RESOURCE_IMAGES: images_rows,
    CONST_DOCKER_RESOURCE_NETWORKS: networks_rows,
    CONST_DOCKER_RESOURCE_VOLUMES: volumes_rows,
    CONST_DOCKER_RESOURCE_REGISTRIES: registries_rows,
}

DOCKER_RESOURCE_COUNTS: dict[str, Callable[[Any], int]] = {
    CONST_DOCKER_RESOURCE_CONTAINERS: lambda summary: len(summary.containers),
    CONST_DOCKER_RESOURCE_IMAGES: lambda summary: len(summary.images),
    CONST_DOCKER_RESOURCE_NETWORKS: lambda summary: len(summary.networks),
    CONST_DOCKER_RESOURCE_VOLUMES: lambda summary: len(summary.volumes),
    CONST_DOCKER_RESOURCE_REGISTRIES: lambda summary: len(summary.registries),
}


def docker_resource_rows(resource: str, snapshot: Any) -> list[tuple[str, ...]]:
    """Render one Docker resource view from the shared inventory snapshot."""
    if snapshot.data is None:
        return []
    return DOCKER_RESOURCE_ROWS[resource](snapshot.data)


def docker_resource_label(resource: str, snapshot: Any) -> str:
    """Render a sub-tab label carrying its row count, so counts are visible unopened."""
    label = CONST_DOCKER_RESOURCE_LABELS[resource]
    if snapshot is None or snapshot.data is None:
        return label
    return f"{label} ({DOCKER_RESOURCE_COUNTS[resource](snapshot.data)})"


REVIEW_SESSION_COLUMNS: tuple[str, ...] = ("Session", "Status", "Findings")


def review_session_rows(snapshot: Any) -> list[tuple[str, ...]]:
    """Project review sessions into table rows, newest first.

    Sessions are already ordered newest-first by the provider; re-sorting here would let
    the two disagree.
    """
    if snapshot.data is None:
        return []
    return [
        (
            info.name,
            "complete" if info.completed else "incomplete",
            str(info.finding_count) if info.completed else "-",
        )
        for info in snapshot.data.sessions
    ]


def render_banner(snapshot: DomainSnapshot, *, stale_after: float | None = None) -> str:
    """Render the banner line for a domain snapshot.

    A failed refresh reports the error, a domain that has not yet loaded reports loading,
    and aged data is marked rather than hidden.
    """
    if snapshot.error is not None:
        return error_banner(snapshot.domain, snapshot.error)
    if snapshot.data is None:
        return loading_banner(snapshot.domain)
    banner = _BANNERS[snapshot.domain](snapshot.data)
    if stale_after is not None and snapshot.age >= stale_after:
        return stale_banner(snapshot.domain, banner, snapshot.age)
    return banner


def render_rows(snapshot: DomainSnapshot) -> list[tuple[str, ...]]:
    """Render the table rows for a domain snapshot.

    Rows come from the last data retrieved even when the most recent refresh failed: a
    transient outage should dim the panel, not blank it, since the previous figures remain
    the best available account of the system.
    """
    if snapshot.data is None:
        return []
    return _ROWS[snapshot.domain](snapshot.data)


def render_domain(
    snapshot: DomainSnapshot, *, stale_after: float | None = None
) -> tuple[str, list[tuple[str, ...]]]:
    """Render a domain snapshot into its banner text and table rows."""
    return render_banner(snapshot, stale_after=stale_after), render_rows(snapshot)


__all__ = [
    "DOCKER_RESOURCE_COLUMNS",
    "DOCKER_RESOURCE_ROWS",
    "DOMAIN_COLUMNS",
    "REVIEW_SESSION_COLUMNS",
    "ai_banner",
    "ai_rows",
    "docker_banner",
    "docker_resource_label",
    "docker_resource_rows",
    "docker_rows",
    "error_banner",
    "images_banner",
    "images_rows",
    "k8s_banner",
    "k8s_rows",
    "loading_banner",
    "networks_banner",
    "networks_rows",
    "registries_banner",
    "registries_rows",
    "render_banner",
    "render_domain",
    "render_rows",
    "review_session_rows",
    "stale_banner",
    "telemetry_banner",
    "telemetry_rows",
    "valkey_banner",
    "valkey_rows",
    "volumes_banner",
    "volumes_rows",
]
