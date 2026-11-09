"""Pure projections from domain summaries to dashboard table rows and banners.

Row construction and banner text previously lived inside the widget methods that also
performed the network fetch, so neither could be exercised without constructing a running
Textual app against a live cluster. These functions are pure: a summary in, rows and a
banner line out.

Separating them is what lets the rendering be tested directly and keeps the widgets thin
enough to be obviously correct.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Iterable
from typing import Any

from devops_cli.config.constants import (
    CONST_DASHBOARD_DOMAIN_DOCKER,
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
    TelemetrySummary,
    ValkeySummary,
)
from devops_cli.ui.state import DomainSnapshot

CONST_STATUS_DOT_OK = "[green]●[/green]"
CONST_STATUS_DOT_WARN = "[yellow]●[/yellow]"
CONST_STATUS_DOT_ERROR = "[red]●[/red]"

DOMAIN_COLUMNS: dict[str, tuple[str, ...]] = {
    CONST_DASHBOARD_DOMAIN_DOCKER: ("Container ID", "Name", "Image", "Status"),
    CONST_DASHBOARD_DOMAIN_TELEMETRY: ("Metric Name", "Type", "Value / Count"),
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
# Row identities
# =============================================================================
#
# One identity per row, in row order, naming the record the row shows. A refresh redraws
# every table, and the identity is how the redraw finds the row the operator was on.


def docker_identities(summary: DockerSummary) -> list[tuple[str, ...]]:
    """Identify containers by id."""
    return _records(summary.containers, ("id",))


def telemetry_identities(summary: TelemetrySummary) -> list[tuple[str, ...]]:
    """Identify instruments by kind and name: a counter and a gauge may share a name."""
    return [(kind, name) for name, kind, _value in telemetry_rows(summary)]


def images_identities(summary: DockerSummary) -> list[tuple[str, ...]]:
    """Identify images by id."""
    return _records(summary.images, ("id",))


def networks_identities(summary: DockerSummary) -> list[tuple[str, ...]]:
    """Identify networks by id."""
    return _records(summary.networks, ("id",))


def volumes_identities(summary: DockerSummary) -> list[tuple[str, ...]]:
    """Identify volumes by name, which Docker keeps unique."""
    return _records(summary.volumes, ("name",))


def registries_identities(summary: DockerSummary) -> list[tuple[str, ...]]:
    """Identify registries by name."""
    return _records(summary.registries, ("name",))


def valkey_identities(summary: ValkeySummary) -> list[tuple[str, ...]]:
    """Identify cache properties by their name."""
    return [(name,) for name, _value in valkey_rows(summary)]


def row_keys(identities: Iterable[tuple[str, ...]]) -> list[str]:
    """Turn row identities into table row keys, unique even when identities repeat.

    Each identity is numbered by how often it has already occurred, so two containers
    sharing the empty-id fallback are two rows rather than a `DuplicateKey` that blanks the
    whole panel. Textual keys rows by string, so the result is encoded as JSON.
    """
    seen: Counter[tuple[str, ...]] = Counter()
    keys: list[str] = []
    for identity in identities:
        keys.append(json.dumps([*identity, seen[identity]]))
        seen[identity] += 1
    return keys


# =============================================================================
# Snapshot rendering
# =============================================================================

_BANNERS: dict[str, Callable[[Any], str]] = {
    CONST_DASHBOARD_DOMAIN_DOCKER: docker_banner,
    CONST_DASHBOARD_DOMAIN_TELEMETRY: telemetry_banner,
    CONST_DASHBOARD_DOMAIN_VALKEY: valkey_banner,
}

_ROWS: dict[str, Callable[[Any], list[tuple[str, ...]]]] = {
    CONST_DASHBOARD_DOMAIN_DOCKER: docker_rows,
    CONST_DASHBOARD_DOMAIN_TELEMETRY: telemetry_rows,
    CONST_DASHBOARD_DOMAIN_VALKEY: valkey_rows,
}

_IDENTITIES: dict[str, Callable[[Any], list[tuple[str, ...]]]] = {
    CONST_DASHBOARD_DOMAIN_DOCKER: docker_identities,
    CONST_DASHBOARD_DOMAIN_TELEMETRY: telemetry_identities,
    CONST_DASHBOARD_DOMAIN_VALKEY: valkey_identities,
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

DOCKER_RESOURCE_IDENTITIES: dict[str, Callable[[Any], list[tuple[str, ...]]]] = {
    CONST_DOCKER_RESOURCE_CONTAINERS: docker_identities,
    CONST_DOCKER_RESOURCE_IMAGES: images_identities,
    CONST_DOCKER_RESOURCE_NETWORKS: networks_identities,
    CONST_DOCKER_RESOURCE_VOLUMES: volumes_identities,
    CONST_DOCKER_RESOURCE_REGISTRIES: registries_identities,
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


def docker_resource_keys(resource: str, snapshot: Any) -> list[str]:
    """Key each row of one Docker resource view, in row order."""
    if snapshot.data is None:
        return []
    return row_keys(DOCKER_RESOURCE_IDENTITIES[resource](snapshot.data))


def docker_resource_label(resource: str, snapshot: Any) -> str:
    """Render a sub-tab label carrying its row count, so counts are visible unopened."""
    label = CONST_DOCKER_RESOURCE_LABELS[resource]
    if snapshot is None or snapshot.data is None:
        return label
    return f"{label} ({DOCKER_RESOURCE_COUNTS[resource](snapshot.data)})"


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


def render_keys(snapshot: DomainSnapshot) -> list[str]:
    """Key each row `render_rows` projects from the same snapshot, in the same order."""
    if snapshot.data is None:
        return []
    return row_keys(_IDENTITIES[snapshot.domain](snapshot.data))


def render_domain(
    snapshot: DomainSnapshot, *, stale_after: float | None = None
) -> tuple[str, list[tuple[str, ...]]]:
    """Render a domain snapshot into its banner text and table rows."""
    return render_banner(snapshot, stale_after=stale_after), render_rows(snapshot)


__all__ = [
    "DOCKER_RESOURCE_COLUMNS",
    "DOCKER_RESOURCE_IDENTITIES",
    "DOCKER_RESOURCE_ROWS",
    "DOMAIN_COLUMNS",
    "docker_banner",
    "docker_identities",
    "docker_resource_keys",
    "docker_resource_label",
    "docker_resource_rows",
    "docker_rows",
    "error_banner",
    "images_banner",
    "images_identities",
    "images_rows",
    "loading_banner",
    "networks_banner",
    "networks_identities",
    "networks_rows",
    "registries_banner",
    "registries_identities",
    "registries_rows",
    "render_banner",
    "render_domain",
    "render_keys",
    "render_rows",
    "row_keys",
    "stale_banner",
    "telemetry_banner",
    "telemetry_identities",
    "telemetry_rows",
    "valkey_banner",
    "valkey_identities",
    "valkey_rows",
    "volumes_banner",
    "volumes_identities",
    "volumes_rows",
]
