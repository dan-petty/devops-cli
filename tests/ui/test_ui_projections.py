"""Tests for Projections behaviour in reactive dashboard."""

from __future__ import annotations

import time

import pytest

from devops_cli.config.constants import (
    CONST_DASHBOARD_DOMAINS,
)
from devops_cli.ui.data_providers import (
    DockerSummary,
    K8sSummary,
    TelemetrySummary,
    ValkeySummary,
)
from devops_cli.ui.projections import (
    DOMAIN_COLUMNS,
    docker_banner,
    docker_rows,
    k8s_banner,
    k8s_rows,
    render_banner,
    render_domain,
    render_rows,
    telemetry_banner,
    telemetry_rows,
    valkey_banner,
    valkey_rows,
)
from devops_cli.ui.state import DomainSnapshot
from tests.support.ui import (
    SAMPLES,
    _docker,
    _k8s,
    _pod,
    _telemetry,
    _valkey,
)


def test_k8s_banner_names_the_context_nodes_and_pod_health() -> None:
    """The banner says which cluster it read, how many nodes are Ready and what needs a look."""
    summary = K8sSummary(
        connected=True,
        context="lab",
        nodes_ready=3,
        nodes_total=4,
        pods=[_pod("api-0"), _pod("api-1"), _pod("exporter-0", status="CrashLoopBackOff")],
    )
    assert k8s_banner(summary) == (
        "[green]●[/green] Kubernetes: Connected | context lab | 3/4 nodes Ready | "
        "3 pods, 1 unhealthy"
    )


def test_k8s_banner_says_why_the_node_count_is_missing() -> None:
    """Pods still render when listing nodes is forbidden, and the banner says so."""
    summary = K8sSummary(connected=True, context="lab", nodes_error="403 Forbidden")
    assert "| nodes: unavailable (403 Forbidden) |" in k8s_banner(summary)


def test_k8s_banner_reports_a_disconnected_cluster_with_the_context_and_error() -> None:
    """A disconnected cluster names the context it tried and why it failed."""
    summary = K8sSummary(connected=False, context="lab", error_message="ConnectionError: refused")
    assert k8s_banner(summary) == (
        "[yellow]●[/yellow] Kubernetes: Disconnected | context lab — ConnectionError: refused"
    )


def test_k8s_banner_shows_cluster_text_literally() -> None:
    """An error quoting a markup tag must not restyle the banner."""
    summary = K8sSummary(connected=False, context="lab", error_message="bad [bold]x[/bold]")
    assert k8s_banner(summary).endswith("bad \\[bold]x\\[/bold]")


def test_docker_banner_distinguishes_running_from_present() -> None:
    """The panel lists stopped containers too, so one count would match neither view."""
    assert docker_banner(_docker()).endswith("Docker: Active (1 running / 1 total)")


def test_docker_banner_counts_a_stopped_container_as_present_not_running() -> None:
    """A stopped container is present in the table but is not running."""
    summary = DockerSummary(
        connected=True,
        containers=[
            {"id": "a", "name": "up", "image": "i", "status": "running"},
            {"id": "b", "name": "down", "image": "i", "status": "exited"},
        ],
    )
    assert docker_banner(summary).endswith("(1 running / 2 total)")


def test_docker_banner_reports_an_inactive_daemon() -> None:
    """An unreachable daemon reads as inactive with nothing present."""
    assert docker_banner(DockerSummary()).endswith("Docker: Inactive (0 running / 0 total)")


def test_telemetry_banner_counts_each_instrument_kind() -> None:
    """Instrument counts come from the summary, not from the rendered rows."""
    assert telemetry_banner(_telemetry()).endswith("2 Counters, 1 Gauges, 0 Histograms")


def test_telemetry_banner_names_the_registry_it_read() -> None:
    """An empty in-process registry is indistinguishable from broken instrumentation."""
    assert "in-process" in telemetry_banner(_telemetry())


def test_telemetry_banner_reports_a_failed_backend_query() -> None:
    """A telemetry backend outage must not look like an absence of metrics."""
    summary = TelemetrySummary(source="in-process", error_message="http://prom: refused")
    assert "refused" in telemetry_banner(summary)


def test_valkey_banner_carries_version_memory_and_hit_ratio() -> None:
    """All three operational figures appear in one line."""
    banner = valkey_banner(_valkey())
    assert ("8.0.1" in banner, "12M" in banner, "94.5%" in banner) == (True, True, True)


def test_k8s_rows_project_pod_records() -> None:
    """Pod records become rows in declared column order."""
    assert k8s_rows(_k8s()) == [("devops-system", "api-0", "Running", "1/1", "0")]


def test_k8s_rows_colour_an_unhealthy_pod() -> None:
    """A pod that needs attention stands out from the healthy ones around it."""
    summary = K8sSummary(connected=True, pods=[_pod("exporter-0", status="CrashLoopBackOff")])
    assert k8s_rows(summary) == [
        tuple(
            f"[red]{cell}[/red]"
            for cell in ("default", "exporter-0", "CrashLoopBackOff", "0/1", "0")
        )
    ]


def test_docker_rows_project_container_records() -> None:
    """Container records become rows in declared column order."""
    assert docker_rows(_docker()) == [("abc123", "valkey", "valkey:8", "running")]


def test_telemetry_rows_label_counters_and_gauges_distinctly() -> None:
    """Both instrument kinds share a table, so each row states which it is."""
    assert telemetry_rows(_telemetry()) == [
        ("requests", "Counter", "12.0"),
        ("errors", "Counter", "1.0"),
        ("queue_depth", "Gauge", "3.0"),
    ]


def test_valkey_rows_render_every_server_property() -> None:
    """The Valkey tab is a property table, so each figure gets its own row."""
    assert valkey_rows(_valkey()) == [
        ("Server Version", "8.0.1"),
        ("Status", "Connected"),
        ("Used Memory", "12M"),
        ("Cache Hit Ratio", "94.5%"),
        ("Connected Clients", "3"),
        ("Key Count", "120"),
        ("Total Commands", "9001"),
    ]


def test_valkey_rows_report_an_offline_server() -> None:
    """A disconnected cache reads as Offline in the status row."""
    assert valkey_rows(ValkeySummary())[1] == ("Status", "Offline")


@pytest.mark.parametrize("domain", CONST_DASHBOARD_DOMAINS)
def test_projected_rows_match_the_declared_column_count(domain: str) -> None:
    """Every row must have exactly as many cells as the table has columns.

    A mismatch raises inside Textual when the row is added, on the UI thread, which is
    exactly the class of failure this separation exists to catch in a test instead.
    """
    snapshot = DomainSnapshot(domain=domain, data=SAMPLES[domain](), updated_at=time.time())
    widths = {len(row) for row in render_rows(snapshot)}
    assert widths == {len(DOMAIN_COLUMNS[domain])}


@pytest.mark.parametrize("domain", CONST_DASHBOARD_DOMAINS)
def test_every_domain_declares_its_columns(domain: str) -> None:
    """A domain without columns would mount an unusable table."""
    assert len(DOMAIN_COLUMNS[domain]) > 0


def test_render_banner_reports_a_domain_that_has_not_loaded_yet() -> None:
    """Before the first result the panel says it is loading, not that it is empty."""
    assert "loading" in render_banner(DomainSnapshot(domain="k8s"))


def test_render_banner_reports_a_failed_refresh() -> None:
    """A failure is named in the banner along with the reason."""
    snapshot = DomainSnapshot(domain="k8s", error="ConnectionError: refused")
    banner = render_banner(snapshot)
    assert ("refresh failed" in banner, "refused" in banner) == (True, True)


def test_render_banner_marks_aged_data_as_stale() -> None:
    """Data shown long after it was fetched is labelled rather than presented as current."""
    snapshot = DomainSnapshot(domain="k8s", data=_k8s(), updated_at=time.time() - 300.0)
    assert "stale" in render_banner(snapshot, stale_after=30.0)


def test_render_banner_leaves_fresh_data_unmarked() -> None:
    """A recent fetch carries no staleness annotation."""
    snapshot = DomainSnapshot(domain="k8s", data=_k8s(), updated_at=time.time())
    assert "stale" not in render_banner(snapshot, stale_after=30.0)


def test_render_rows_keeps_the_last_data_through_a_failed_refresh() -> None:
    """The table survives an outage showing what it last knew."""
    snapshot = DomainSnapshot(
        domain="k8s", data=_k8s(), updated_at=time.time() - 10.0, error="down"
    )
    assert len(render_rows(snapshot)) == 1


def test_render_rows_are_empty_before_the_first_fetch() -> None:
    """An unloaded domain renders an empty table rather than raising."""
    assert render_rows(DomainSnapshot(domain="k8s")) == []


def test_render_domain_returns_both_banner_and_rows() -> None:
    """The combined renderer pairs the banner with its table contents."""
    snapshot = DomainSnapshot(domain="docker", data=_docker(), updated_at=time.time())
    banner, rows = render_domain(snapshot)
    assert ("Docker: Active" in banner, len(rows)) == (True, 1)
