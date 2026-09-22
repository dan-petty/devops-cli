"""Test suite for the reactive dashboard state store, log virtualization, and projections."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from textual.widgets import DataTable, Static, TabbedContent, TabPane

import devops_cli.ui.dashboard as dashboard_module
import devops_cli.ui.data_providers as data_providers
import devops_cli.ui.refresh as refresh_module
from devops_cli.commands.dashboard import TAB_NUM_MAP
from devops_cli.config.constants import (
    CONST_DASHBOARD_DOMAIN_AI,
    CONST_DASHBOARD_DOMAIN_DOCKER,
    CONST_DASHBOARD_DOMAINS,
    CONST_DOCKER_RESOURCES,
    CONST_LOG_STREAM_QUEUE_SIZE,
)
from devops_cli.ui.dashboard import DashboardApp
from devops_cli.ui.data_providers import (
    DockerSummary,
    K8sSummary,
    ReviewSessionInfo,
    ReviewSummary,
    TelemetrySummary,
    ValkeySummary,
    fetch_review_status,
    fetch_telemetry_status,
    list_review_sessions,
)
from devops_cli.ui.log_buffer import LogLine, VirtualLogBuffer, tail
from devops_cli.ui.projections import (
    DOCKER_RESOURCE_COLUMNS,
    DOMAIN_COLUMNS,
    ai_banner,
    ai_rows,
    docker_banner,
    docker_resource_label,
    docker_resource_rows,
    docker_rows,
    k8s_banner,
    k8s_rows,
    render_banner,
    render_domain,
    render_rows,
    review_session_rows,
    telemetry_banner,
    telemetry_rows,
    valkey_banner,
    valkey_rows,
)
from devops_cli.ui.refresh import (
    DOMAIN_FETCHERS,
    pod_log_source,
    refresh_all,
    refresh_domain,
)
from devops_cli.ui.state import DashboardState, DomainSnapshot
from devops_cli.ui.widgets import DockerPanel, DomainPanel, LogPane, ReviewPanel

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def state() -> DashboardState:
    """Provide an empty dashboard state store."""
    return DashboardState()


def _k8s() -> K8sSummary:
    return K8sSummary(
        connected=True,
        minikube_active=True,
        pods=[
            {
                "namespace": "devops-system",
                "name": "api-0",
                "status": "Running",
                "ready": "1/1",
                "restarts": "0",
            }
        ],
    )


def _docker() -> DockerSummary:
    return DockerSummary(
        connected=True,
        containers=[{"id": "abc123", "name": "valkey", "image": "valkey:8", "status": "running"}],
        images=[
            {
                "id": "img001",
                "tag": "valkey:8",
                "size": "41.2MB",
                "created": "2026-09-01 10:00:00",
            }
        ],
        networks=[
            {
                "id": "net001",
                "name": "bridge",
                "driver": "bridge",
                "scope": "local",
                "containers": "1",
            }
        ],
        volumes=[
            {
                "name": "data",
                "driver": "local",
                "mountpoint": "/var/lib/docker/volumes/data/_data",
                "size": "-",
                "created": "2026-09-01 10:00:00",
            }
        ],
        registries=[
            {"name": "https://index.docker.io/v1/", "kind": "default", "status": "configured"}
        ],
    )


def _telemetry() -> TelemetrySummary:
    return TelemetrySummary(
        counter_count=2,
        gauge_count=1,
        histogram_count=0,
        counters={"requests": 12.0, "errors": 1.0},
        gauges={"queue_depth": 3.0},
    )


def _review() -> ReviewSummary:
    return ReviewSummary(
        has_session=True,
        session_name="20260921-101500",
        total_findings=2,
        verified_count=1,
        severity_distribution={"HIGH": 1, "LOW": 1},
        findings=[
            {
                "severity": "HIGH",
                "title": "Unbounded log retention",
                "location": "ui/log_buffer.py:42",
                "status": "VERIFIED",
            }
        ],
    )


def _valkey() -> ValkeySummary:
    return ValkeySummary(
        connected=True,
        version="8.0.1",
        used_memory="12M",
        hit_ratio=94.5,
        connected_clients=3,
        key_count=120,
        total_commands=9001,
    )


SAMPLES: dict[str, Any] = {
    "k8s": _k8s,
    "docker": _docker,
    "telemetry": _telemetry,
    "ai": _review,
    "valkey": _valkey,
}


# =============================================================================
# Dashboard State Store
# =============================================================================


def test_publish_records_a_snapshot_readable_by_domain(state: DashboardState) -> None:
    """publish stores data retrievable via get, marked successful."""
    snapshot = state.publish("k8s", _k8s())
    stored = state.get("k8s")
    assert (stored.domain, stored.error, stored.ok) == ("k8s", None, True)
    assert stored.data is snapshot.data


def test_get_on_an_unfetched_domain_returns_an_empty_snapshot(state: DashboardState) -> None:
    """A domain never fetched reads as empty rather than raising."""
    snapshot = state.get("docker")
    assert (snapshot.domain, snapshot.data, snapshot.never_loaded, snapshot.ok) == (
        "docker",
        None,
        True,
        False,
    )


def test_publish_error_preserves_the_previously_fetched_data(state: DashboardState) -> None:
    """A failed refresh dims the panel rather than blanking it.

    Losing the last known state on a transient outage is worse than showing it with a
    warning, because the operator loses the only account of the system they had.
    """
    original = _k8s()
    state.publish("k8s", original)
    snapshot = state.publish_error("k8s", "connection refused")
    assert (snapshot.error, snapshot.data is original) == ("connection refused", True)


def test_publish_error_before_any_data_has_no_data_to_preserve(state: DashboardState) -> None:
    """An error on a never-loaded domain carries no data."""
    snapshot = state.publish_error("valkey", "unreachable")
    assert (snapshot.data, snapshot.error, snapshot.never_loaded) == (None, "unreachable", True)


def test_publish_error_truncates_runaway_provider_messages(state: DashboardState) -> None:
    """A huge exception string cannot blow out the banner line."""
    snapshot = state.publish_error("docker", "x" * 5000)
    assert snapshot.error is not None
    assert len(snapshot.error) == 256


def test_subscribers_are_notified_of_every_publish(state: DashboardState) -> None:
    """Listeners receive both successful and failed snapshots."""
    seen: list[tuple[str, str | None]] = []
    state.subscribe(lambda snap: seen.append((snap.domain, snap.error)))
    state.publish("k8s", _k8s())
    state.publish_error("docker", "down")
    assert seen == [("k8s", None), ("docker", "down")]


def test_a_failing_subscriber_cannot_abort_the_publish(state: DashboardState) -> None:
    """One broken listener must not take down the worker or the other listeners."""

    def explode(_: DomainSnapshot) -> None:
        raise RuntimeError("listener defect")

    seen: list[str] = []
    state.subscribe(explode)
    state.subscribe(lambda snap: seen.append(snap.domain))
    state.publish("k8s", _k8s())
    assert (seen, state.get("k8s").ok) == (["k8s"], True)


def test_unsubscribe_stops_further_notifications(state: DashboardState) -> None:
    """The handle returned by subscribe removes the listener."""
    seen: list[str] = []
    unsubscribe = state.subscribe(lambda snap: seen.append(snap.domain))
    state.publish("k8s", _k8s())
    unsubscribe()
    state.publish("docker", _docker())
    assert seen == ["k8s"]


def test_unsubscribing_twice_is_harmless(state: DashboardState) -> None:
    """Releasing an already-released subscription does not raise."""
    unsubscribe = state.subscribe(lambda _: None)
    unsubscribe()
    unsubscribe()
    assert state.snapshots() == {}


def test_subscribers_are_notified_outside_the_lock(state: DashboardState) -> None:
    """A slow listener must not stall an unrelated worker trying to publish.

    Notifying while holding the lock would serialise every worker behind the slowest
    subscriber, which is the stall this architecture exists to remove.
    """
    entered = threading.Event()
    release = threading.Event()

    def slow(_: DomainSnapshot) -> None:
        entered.set()
        release.wait(timeout=5)

    state.publish("k8s", _k8s())
    state.subscribe(slow)
    blocker = threading.Thread(target=lambda: state.publish("k8s", _k8s()))
    blocker.start()
    assert entered.wait(timeout=5)

    read = threading.Event()

    def reader() -> None:
        state.snapshots()
        state.get("k8s")
        read.set()

    worker = threading.Thread(target=reader)
    worker.start()
    assert read.wait(timeout=5), "the store stayed locked while a subscriber ran"

    release.set()
    blocker.join(timeout=5)
    worker.join(timeout=5)


def test_pending_domains_lists_every_domain_before_any_fetch(state: DashboardState) -> None:
    """All configured domains start pending."""
    assert state.pending_domains() == sorted(CONST_DASHBOARD_DOMAINS)


def test_pending_domains_shrinks_as_domains_load(state: DashboardState) -> None:
    """A domain with data is no longer pending, and an errored one still is."""
    state.publish("k8s", _k8s())
    state.publish_error("docker", "down")
    pending = state.pending_domains()
    assert ("k8s" in pending, "docker" in pending) == (False, True)


def test_failed_domains_lists_only_domains_whose_last_refresh_errored(
    state: DashboardState,
) -> None:
    """Recovery clears a domain from the failure list."""
    state.publish_error("k8s", "down")
    state.publish_error("docker", "down")
    state.publish("k8s", _k8s())
    assert state.failed_domains() == ["docker"]


def test_clear_discards_snapshots_but_keeps_subscribers(state: DashboardState) -> None:
    """Clearing state does not silently unregister the UI."""
    seen: list[str] = []
    state.subscribe(lambda snap: seen.append(snap.domain))
    state.publish("k8s", _k8s())
    state.clear()
    state.publish("docker", _docker())
    assert (state.get("k8s").never_loaded, seen) == (True, ["k8s", "docker"])


def test_snapshots_returns_an_isolated_copy(state: DashboardState) -> None:
    """Mutating the returned mapping cannot corrupt the store."""
    state.publish("k8s", _k8s())
    copy = state.snapshots()
    copy.clear()
    assert state.get("k8s").ok is True


def test_concurrent_publishes_across_threads_lose_nothing(state: DashboardState) -> None:
    """Every domain published from its own thread is recorded exactly once."""
    domains = [f"domain-{index}" for index in range(40)]
    threads = [threading.Thread(target=state.publish, args=(domain, domain)) for domain in domains]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    stored = state.snapshots()
    assert (len(stored), all(stored[d].data == d for d in domains)) == (40, True)


# =============================================================================
# Snapshot Age & Staleness
# =============================================================================


def test_a_never_loaded_snapshot_reports_zero_age() -> None:
    """Age is meaningless before the first successful fetch."""
    snapshot = DomainSnapshot(domain="k8s")
    assert (snapshot.age, snapshot.never_loaded) == (0.0, True)


def test_a_never_loaded_snapshot_is_not_reported_as_stale() -> None:
    """Empty and stale are rendered differently, so they must not be conflated."""
    assert DomainSnapshot(domain="k8s").is_stale(max_age=0.0) is False


def test_a_snapshot_ages_past_its_threshold() -> None:
    """Data fetched long ago is flagged stale."""
    old = DomainSnapshot(domain="k8s", data=_k8s(), updated_at=time.time() - 120.0)
    assert (old.is_stale(max_age=30.0), old.is_stale(max_age=600.0)) == (True, False)


def test_a_freshly_published_snapshot_is_not_stale(state: DashboardState) -> None:
    """A just-published snapshot falls inside any sane threshold."""
    snapshot = state.publish("k8s", _k8s())
    assert snapshot.is_stale(max_age=30.0) is False


def test_an_errored_snapshot_retains_the_age_of_the_data_it_shows(
    state: DashboardState,
) -> None:
    """The banner must age from when the data was fetched, not when the error occurred."""
    state.publish("k8s", _k8s())
    fetched_at = state.get("k8s").updated_at
    snapshot = state.publish_error("k8s", "down")
    assert snapshot.updated_at == fetched_at


# =============================================================================
# Refresh Coordination
# =============================================================================


def test_refresh_domain_publishes_the_fetched_result(state: DashboardState) -> None:
    """A successful fetch lands in the store."""
    snapshot = refresh_domain(state, "k8s", {"k8s": _k8s})
    assert snapshot is not None
    assert (snapshot.error, snapshot.data.connected) == (None, True)


def test_refresh_domain_converts_a_provider_failure_into_a_snapshot(
    state: DashboardState,
) -> None:
    """An exception on a worker thread must never escape.

    An escaping exception kills the worker silently, leaving the panel showing data that
    never updates again with no indication anything is wrong.
    """

    def broken() -> Any:
        raise ConnectionError("cluster unreachable")

    snapshot = refresh_domain(state, "k8s", {"k8s": broken})
    assert snapshot is not None
    assert snapshot.error == "ConnectionError: cluster unreachable"


def test_refresh_domain_releases_its_claim_after_a_failure(state: DashboardState) -> None:
    """A failed fetch must not leave the domain permanently locked out of refreshing."""

    def broken() -> Any:
        raise ConnectionError("down")

    refresh_domain(state, "k8s", {"k8s": broken})
    recovered = refresh_domain(state, "k8s", {"k8s": _k8s})
    assert (state.in_flight(), recovered is not None) == ([], True)


def test_a_refresh_tick_does_not_stack_a_second_fetch_on_a_slow_domain(
    state: DashboardState,
) -> None:
    """Ticks arriving while a fetch is in flight are skipped rather than queued.

    The timer fires on a fixed interval but a fetch against a dead endpoint can outlast
    many ticks; without this the slowest domain accumulates a thread per tick for as long
    as it stays slow.
    """
    entered = threading.Event()
    release = threading.Event()
    calls: list[int] = []

    def slow() -> Any:
        calls.append(1)
        entered.set()
        release.wait(timeout=5)
        return _k8s()

    worker = threading.Thread(target=refresh_domain, args=(state, "k8s", {"k8s": slow}))
    worker.start()
    assert entered.wait(timeout=5)

    assert (refresh_domain(state, "k8s", {"k8s": slow}), state.in_flight()) == (None, ["k8s"])

    release.set()
    worker.join(timeout=5)
    assert (calls, state.in_flight()) == ([1], [])


def test_refresh_domain_reports_an_unregistered_domain_as_an_error(
    state: DashboardState,
) -> None:
    """A domain with no provider surfaces as a visible error, not a silent blank panel."""
    snapshot = refresh_domain(state, "nonexistent", {})
    assert snapshot is not None
    assert snapshot.error == "No provider registered for domain 'nonexistent'"


def test_refresh_all_publishes_every_requested_domain(state: DashboardState) -> None:
    """The sequential path covers each domain once."""
    fetchers = {domain: SAMPLES[domain] for domain in CONST_DASHBOARD_DOMAINS}
    published = refresh_all(state, CONST_DASHBOARD_DOMAINS, fetchers)
    assert [snap.domain for snap in published] == list(CONST_DASHBOARD_DOMAINS)


def test_every_configured_domain_has_a_registered_provider() -> None:
    """A domain declared but never fetched would render as a permanently empty tab."""
    assert sorted(DOMAIN_FETCHERS) == sorted(CONST_DASHBOARD_DOMAINS)


# =============================================================================
# Projections
# =============================================================================


def test_k8s_banner_reports_connection_and_minikube() -> None:
    """The banner surfaces both cluster reachability and local Minikube state."""
    banner = k8s_banner(_k8s())
    assert ("Connected" in banner, "Minikube: Active" in banner) == (True, True)


def test_k8s_banner_reports_a_disconnected_cluster() -> None:
    """A disconnected cluster is stated plainly rather than shown as an empty table."""
    assert "Disconnected" in k8s_banner(K8sSummary(connected=False))


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


def test_ai_banner_summarises_the_latest_session() -> None:
    """The banner names the session and its severity distribution."""
    banner = ai_banner(_review())
    assert ("20260921-101500" in banner, "HIGH: 1" in banner) == (True, True)


def test_ai_banner_states_when_no_session_exists() -> None:
    """Absence of review history is stated, not rendered as a session with zero findings."""
    assert ai_banner(ReviewSummary()) == "No active or past AI code review sessions found."


def test_ai_banner_handles_a_session_with_no_severity_distribution() -> None:
    """An empty distribution renders as None rather than a trailing separator."""
    assert ai_banner(ReviewSummary(has_session=True, session_name="s")).endswith("| None")


def test_valkey_banner_carries_version_memory_and_hit_ratio() -> None:
    """All three operational figures appear in one line."""
    banner = valkey_banner(_valkey())
    assert ("8.0.1" in banner, "12M" in banner, "94.5%" in banner) == (True, True, True)


def test_k8s_rows_project_pod_records() -> None:
    """Pod records become rows in declared column order."""
    assert k8s_rows(_k8s()) == [("devops-system", "api-0", "Running", "1/1", "0")]


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


def test_ai_rows_truncate_long_finding_titles() -> None:
    """An overlong title is clipped so it cannot push other columns off screen."""
    summary = ReviewSummary(has_session=True, findings=[{"title": "T" * 200}])
    assert ai_rows(summary)[0][1] == "T" * 45


def test_ai_rows_substitute_defaults_for_absent_finding_fields() -> None:
    """A partially written findings file renders rather than raising on the UI thread."""
    summary = ReviewSummary(has_session=True, findings=[{}])
    assert ai_rows(summary) == [("MEDIUM", "Untitled", "—", "UNVERIFIED")]


def test_k8s_rows_tolerate_a_pod_record_missing_keys() -> None:
    """A provider that omits a key yields an empty cell, never an exception."""
    summary = K8sSummary(connected=True, pods=[{"name": "api-0"}])
    assert k8s_rows(summary) == [("", "api-0", "", "", "")]


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


# =============================================================================
# Virtualized Log Buffer
# =============================================================================


def test_retention_is_bounded_however_long_the_stream_runs() -> None:
    """Memory is bounded by the retention limit, not by stream length.

    Retaining every line of a long tail is how the dashboard gets OOM-killed on a busy
    namespace, which is the whole reason this buffer exists.
    """
    buffer = VirtualLogBuffer(max_lines=100, viewport=10)
    buffer.extend(f"line-{index}" for index in range(100_000))
    assert (buffer.retained, buffer.total_appended) == (100, 100_000)


def test_sequence_numbers_count_evicted_lines() -> None:
    """Position in the stream stays true after eviction."""
    buffer = VirtualLogBuffer(max_lines=3, viewport=3)
    buffer.extend(["a", "b", "c", "d", "e"])
    assert [line.sequence for line in buffer.viewport_lines()] == [3, 4, 5]


def test_dropped_counts_lines_evicted_to_stay_within_the_limit() -> None:
    """The count of discarded lines is reported rather than hidden."""
    buffer = VirtualLogBuffer(max_lines=10, viewport=5)
    buffer.extend(f"line-{index}" for index in range(25))
    assert (buffer.retained, buffer.dropped) == (10, 15)


def test_the_viewport_hands_out_only_the_visible_slice() -> None:
    """Rendering the whole buffer is what drops frames; only the slice is returned."""
    buffer = VirtualLogBuffer(max_lines=1000, viewport=5)
    buffer.extend(f"line-{index}" for index in range(100))
    visible = buffer.viewport_lines()
    assert (len(visible), visible[-1].text) == (5, "line-99")


def test_a_following_viewport_tracks_newly_appended_lines() -> None:
    """While following, the newest line stays on screen."""
    buffer = VirtualLogBuffer(max_lines=100, viewport=3)
    buffer.extend(["a", "b", "c"])
    buffer.append("d")
    assert [line.text for line in buffer.viewport_lines()] == ["b", "c", "d"]


def test_scrolling_back_detaches_the_viewport_from_the_stream() -> None:
    """Reading history must not be yanked away by incoming lines.

    A viewport that keeps jumping to the end makes an active log impossible to read, which
    is the practical failure of a naive auto-scrolling tail.
    """
    buffer = VirtualLogBuffer(max_lines=100, viewport=3)
    buffer.extend(f"line-{index}" for index in range(10))
    buffer.scroll(-4)
    before = [line.text for line in buffer.viewport_lines()]
    buffer.append("line-10")
    after = [line.text for line in buffer.viewport_lines()]
    assert (buffer.following, before == after) == (False, True)


def test_scrolling_to_the_end_reattaches_to_the_stream() -> None:
    """Returning to the newest line resumes following."""
    buffer = VirtualLogBuffer(max_lines=100, viewport=3)
    buffer.extend(f"line-{index}" for index in range(10))
    buffer.scroll(-5)
    buffer.scroll_to_end()
    buffer.append("line-10")
    assert (buffer.following, buffer.viewport_lines()[-1].text) == (True, "line-10")


def test_scrolling_forward_to_the_end_reattaches_without_an_explicit_jump() -> None:
    """Scrolling back to the bottom by hand resumes following too."""
    buffer = VirtualLogBuffer(max_lines=100, viewport=3)
    buffer.extend(f"line-{index}" for index in range(10))
    buffer.scroll(-4)
    buffer.scroll(10)
    assert (buffer.following, buffer.offset) == (True, 7)


def test_scrolling_clamps_to_the_retained_range() -> None:
    """The viewport cannot be driven outside the buffer."""
    buffer = VirtualLogBuffer(max_lines=100, viewport=3)
    buffer.extend(["a", "b", "c", "d"])
    assert (buffer.scroll(-999), buffer.scroll(999)) == (0, 1)


def test_a_detached_viewport_holds_position_as_lines_are_evicted() -> None:
    """Eviction shifts indices beneath the reader, so the offset is corrected."""
    buffer = VirtualLogBuffer(max_lines=5, viewport=2)
    buffer.extend(["a", "b", "c", "d", "e"])
    buffer.scroll(-3)
    buffer.extend(["f", "g", "h", "i", "j"])
    assert (buffer.following, buffer.offset < buffer.retained) == (False, True)


def test_resizing_the_viewport_while_following_keeps_the_newest_lines() -> None:
    """A terminal resize must not scroll the stream away."""
    buffer = VirtualLogBuffer(max_lines=100, viewport=3)
    buffer.extend(f"line-{index}" for index in range(10))
    buffer.resize_viewport(5)
    assert [line.text for line in buffer.viewport_lines()][-1] == "line-9"


def test_resizing_the_viewport_while_detached_keeps_the_reader_in_place() -> None:
    """Growing the viewport must not silently jump a detached reader to the end."""
    buffer = VirtualLogBuffer(max_lines=100, viewport=3)
    buffer.extend(f"line-{index}" for index in range(20))
    buffer.scroll(-10)
    offset = buffer.offset
    buffer.resize_viewport(5)
    assert (buffer.following, buffer.offset) == (False, offset)


def test_a_viewport_larger_than_the_buffer_shows_everything_retained() -> None:
    """A short stream is fully visible without padding or error."""
    buffer = VirtualLogBuffer(max_lines=100, viewport=50)
    buffer.extend(["a", "b"])
    assert [line.text for line in buffer.viewport_lines()] == ["a", "b"]


def test_degenerate_sizes_are_coerced_to_something_renderable() -> None:
    """A zero or negative size would make the buffer undisplayable."""
    buffer = VirtualLogBuffer(max_lines=0, viewport=-5)
    buffer.append("a")
    assert (buffer.retained, buffer.viewport) == (1, 1)


def test_search_finds_matching_retained_lines_case_insensitively() -> None:
    """Operators search logs without matching the casing exactly."""
    buffer = VirtualLogBuffer(max_lines=100, viewport=5)
    buffer.extend(["INFO started", "ERROR failed", "info stopped"])
    assert [line.text for line in buffer.search("info")] == ["INFO started", "info stopped"]


def test_search_honours_a_result_limit() -> None:
    """A match on every line must not return the whole buffer."""
    buffer = VirtualLogBuffer(max_lines=1000, viewport=5)
    buffer.extend(f"error {index}" for index in range(500))
    assert len(buffer.search("error", limit=10)) == 10


def test_an_empty_search_matches_nothing() -> None:
    """An empty needle returns nothing rather than every line."""
    buffer = VirtualLogBuffer(max_lines=10, viewport=5)
    buffer.extend(["a", "b"])
    assert buffer.search("") == []


def test_clear_discards_lines_but_preserves_the_stream_count() -> None:
    """Clearing the view does not rewrite how much of the stream has been seen."""
    buffer = VirtualLogBuffer(max_lines=10, viewport=5)
    buffer.extend(["a", "b", "c"])
    buffer.clear()
    assert (buffer.retained, buffer.total_appended, buffer.following) == (0, 3, True)


def test_status_reports_retention_drops_and_follow_state() -> None:
    """The status line states what is retained, what was lost, and whether it is live."""
    buffer = VirtualLogBuffer(max_lines=3, viewport=2)
    buffer.extend(["a", "b", "c", "d", "e"])
    assert buffer.status() == "3 retained of 5, 2 dropped (following)"


def test_status_omits_the_drop_count_when_nothing_was_evicted() -> None:
    """A short stream reports cleanly without a zero-drop clause."""
    buffer = VirtualLogBuffer(max_lines=10, viewport=5)
    buffer.extend(["a", "b"])
    assert buffer.status() == "2 retained of 2 (following)"


def test_status_reports_a_detached_viewport() -> None:
    """A reader scrolled into history is told the view is not live."""
    buffer = VirtualLogBuffer(max_lines=10, viewport=2)
    buffer.extend(["a", "b", "c", "d"])
    buffer.scroll(-2)
    assert buffer.status().endswith("4 retained of 4")


def test_append_returns_the_line_it_recorded() -> None:
    """Producers can observe the assigned sequence number."""
    buffer = VirtualLogBuffer(max_lines=10, viewport=5)
    assert buffer.append("hello") == LogLine(sequence=1, text="hello")


def test_concurrent_producers_do_not_lose_or_duplicate_lines() -> None:
    """Workers append while the UI reads, so every operation must be guarded."""
    buffer = VirtualLogBuffer(max_lines=10_000, viewport=20)

    def produce(worker: int) -> None:
        buffer.extend(f"worker-{worker}-line-{index}" for index in range(200))

    threads = [threading.Thread(target=produce, args=(worker,)) for worker in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    sequences = {line.sequence for line in buffer.viewport_lines()}
    assert (buffer.total_appended, len(sequences)) == (1600, 20)


def test_reading_a_viewport_during_concurrent_appends_never_tears() -> None:
    """A read must always return a valid slice, never a partially mutated one."""
    buffer = VirtualLogBuffer(max_lines=500, viewport=10)
    stop = threading.Event()

    def produce() -> None:
        index = 0
        while not stop.is_set():
            buffer.append(f"line-{index}")
            index += 1

    producer = threading.Thread(target=produce)
    producer.start()
    try:
        widths = {len(buffer.viewport_lines()) for _ in range(500)}
    finally:
        stop.set()
        producer.join(timeout=5)
    assert widths <= {10} or widths.issubset(set(range(11)))


def test_tail_returns_the_final_lines() -> None:
    """The helper trims a finished sequence to its last lines."""
    assert tail(["a", "b", "c", "d"], count=2) == ["c", "d"]


def test_tail_of_a_non_positive_count_is_empty() -> None:
    """Asking for no lines returns none rather than the whole sequence."""
    assert tail(["a", "b"], count=0) == []


def test_tail_of_a_short_sequence_returns_all_of_it() -> None:
    """Requesting more lines than exist is not an error."""
    assert tail(["a"], count=10) == ["a"]


# =============================================================================
# Widget & App Integration
# =============================================================================


@pytest.fixture
def patched_fetchers(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Replace the live providers so the dashboard refreshes deterministically.

    The app performs one refresh on mount regardless of the auto-refresh interval, so a
    test that does not control the providers is racing real network calls.
    """

    def apply(**overrides: Callable[[], Any]) -> None:
        fetchers = {domain: SAMPLES[domain] for domain in CONST_DASHBOARD_DOMAINS}
        fetchers.update(overrides)
        monkeypatch.setattr(refresh_module, "DOMAIN_FETCHERS", fetchers)

    return apply


async def _settle(pilot: Any, predicate: Callable[[], bool], timeout: float = 10.0) -> bool:
    """Pump the UI until a predicate holds, so tests do not depend on a fixed sleep."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        await pilot.pause(0.05)
    return predicate()


@pytest.mark.asyncio
async def test_the_dashboard_mounts_one_panel_per_configured_domain(
    patched_fetchers: Callable[..., None],
) -> None:
    """Adding a domain must not require editing the app's compose block."""
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test():
        panels = {panel.domain for panel in app.query(DomainPanel).results(DomainPanel)}
        panels |= {panel.domain for panel in app.query(DockerPanel).results(DockerPanel)}
        panels |= {panel.domain for panel in app.query(ReviewPanel).results(ReviewPanel)}
        assert panels == set(CONST_DASHBOARD_DOMAINS)


@pytest.mark.asyncio
async def test_every_panel_declares_the_columns_its_domain_projects(
    patched_fetchers: Callable[..., None],
) -> None:
    """A panel installs its own headers, so the app holds no per-domain column code."""
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test():
        widths = {
            panel.domain: len(panel.query_one(DataTable).columns)
            for panel in app.query(DomainPanel).results(DomainPanel)
        }
        # Docker and AI Review compose nested tabs, so they are not plain DomainPanels.
        assert widths == {
            domain: len(DOMAIN_COLUMNS[domain])
            for domain in CONST_DASHBOARD_DOMAINS
            if domain not in (CONST_DASHBOARD_DOMAIN_DOCKER, CONST_DASHBOARD_DOMAIN_AI)
        }


@pytest.mark.asyncio
async def test_the_initial_refresh_populates_every_panel(
    patched_fetchers: Callable[..., None],
) -> None:
    """Data fetched on a worker thread reaches the table it belongs to.

    This exercises the whole path the refactor introduced: worker thread, state store,
    hand-off to the UI thread, projection, table.
    """
    patched_fetchers()
    state = DashboardState()
    app = DashboardApp(refresh_interval=0, state=state)
    async with app.run_test() as pilot:
        await _settle(pilot, lambda: not state.pending_domains())
        counts = {
            panel.domain: panel.query_one(DataTable).row_count
            for panel in app.query(DomainPanel).results(DomainPanel)
        }
        counts["docker"] = app.query_one("#docker-table", DataTable).row_count
        counts["ai"] = app.query_one("#ai-table", DataTable).row_count
        assert counts == {"k8s": 1, "docker": 1, "telemetry": 3, "ai": 1, "valkey": 7}


@pytest.mark.asyncio
async def test_a_panel_renders_a_snapshot_handed_to_it(
    patched_fetchers: Callable[..., None],
) -> None:
    """Applying a snapshot updates both the banner and the table."""
    patched_fetchers()
    state = DashboardState()
    app = DashboardApp(refresh_interval=0, state=state)
    async with app.run_test() as pilot:
        await _settle(pilot, lambda: not state.pending_domains())
        panel = app.query_one("#panel-docker", DockerPanel)
        panel.apply(DomainSnapshot(domain="docker", data=DockerSummary(), updated_at=time.time()))
        table = panel.query_one("#docker-table", DataTable)
        assert (table.row_count, "Docker: Inactive" in str(panel.query_one(Static).render())) == (
            0,
            True,
        )


@pytest.mark.asyncio
async def test_a_slow_subsystem_does_not_freeze_the_interface(
    patched_fetchers: Callable[..., None],
) -> None:
    """The dashboard stays navigable while a domain is still being fetched.

    This is the defect the reactive architecture exists to fix: the previous design called
    every provider synchronously from the keypress handler, so one unreachable cluster
    froze every unrelated tab for the duration of its timeout.
    """
    release = threading.Event()
    entered = threading.Event()

    def slow_k8s() -> Any:
        entered.set()
        release.wait(timeout=10)
        return _k8s()

    patched_fetchers(k8s=slow_k8s)
    state = DashboardState()
    app = DashboardApp(refresh_interval=0, state=state)
    try:
        async with app.run_test() as pilot:
            assert entered.wait(timeout=10), "the k8s worker never started"

            await pilot.press("2")
            await pilot.pause()
            active_while_blocked = app.query_one(TabbedContent).active

            docker_table = app.query_one("#docker-table", DataTable)
            await _settle(pilot, lambda: docker_table.row_count > 0)
            rendered_while_blocked = docker_table.row_count
            k8s_still_fetching = state.in_flight() == ["k8s"]

            release.set()
            await _settle(pilot, lambda: not state.pending_domains())

        assert (active_while_blocked, rendered_while_blocked, k8s_still_fetching) == (
            "tab-docker",
            1,
            True,
        )
    finally:
        release.set()


@pytest.mark.asyncio
async def test_a_failing_provider_leaves_the_rest_of_the_dashboard_working(
    patched_fetchers: Callable[..., None],
) -> None:
    """One broken subsystem must not take the dashboard down with it."""

    def broken() -> Any:
        raise ConnectionError("cluster unreachable")

    patched_fetchers(k8s=broken)
    state = DashboardState()
    app = DashboardApp(refresh_interval=0, state=state)
    async with app.run_test() as pilot:
        await _settle(pilot, lambda: state.failed_domains() == ["k8s"])
        await _settle(pilot, lambda: app.query_one("#valkey-table", DataTable).row_count == 7)
        banner = str(app.query_one("#k8s-banner", Static).render())
        assert (
            state.failed_domains(),
            app.query_one("#valkey-table", DataTable).row_count,
            "refresh failed" in banner,
        ) == (["k8s"], 7, True)


@pytest.mark.asyncio
async def test_a_refresh_keypress_never_blocks_on_the_providers(
    patched_fetchers: Callable[..., None],
) -> None:
    """The key that triggers a refresh must return immediately.

    Dispatching to workers is what keeps the keypress handler from becoming the place the
    interface hangs, so the handler is timed rather than merely assumed to be fast.
    """
    release = threading.Event()

    def slow_for(domain: str) -> Callable[[], Any]:
        def fetch() -> Any:
            release.wait(timeout=10)
            return SAMPLES[domain]()

        return fetch

    patched_fetchers(**{domain: slow_for(domain) for domain in CONST_DASHBOARD_DOMAINS})
    app = DashboardApp(refresh_interval=0)
    try:
        async with app.run_test() as pilot:
            started = time.monotonic()
            app.action_refresh_data()
            elapsed = time.monotonic() - started
            release.set()
            await pilot.pause()
        assert elapsed < 1.0, f"refresh blocked the UI thread for {elapsed:.2f}s"
    finally:
        release.set()


@pytest.mark.asyncio
async def test_unrenderable_data_is_confined_to_its_own_panel(
    patched_fetchers: Callable[..., None],
) -> None:
    """A projection failure reports in its own banner instead of killing the dashboard.

    The hand-off from worker to UI runs on the UI thread, so an escaping exception there
    fails the worker and takes down a dashboard whose other subsystems are healthy.
    """

    def wrong_shape() -> Any:
        return _k8s()  # a K8sSummary handed to the Docker projection

    patched_fetchers(docker=wrong_shape)
    state = DashboardState()
    app = DashboardApp(refresh_interval=0, state=state)
    async with app.run_test() as pilot:
        await _settle(pilot, lambda: state.failed_domains() == ["docker"])
        await _settle(pilot, lambda: app.query_one("#valkey-table", DataTable).row_count == 7)
        banner = str(app.query_one("#docker-banner", Static).render())
        assert (
            state.failed_domains(),
            "render failed" in banner,
            app.query_one("#valkey-table", DataTable).row_count,
        ) == (["docker"], True, 7)


# =============================================================================
# CLI Tab Resolution
# =============================================================================


@pytest.mark.parametrize(
    ("selector", "expected"),
    [(str(i), f"tab-{d}") for i, d in enumerate(CONST_DASHBOARD_DOMAINS, start=1)]
    + [(d, f"tab-{d}") for d in CONST_DASHBOARD_DOMAINS],
)
def test_every_domain_is_selectable_by_number_and_by_name(selector: str, expected: str) -> None:
    """A tab reachable in the TUI must also be selectable from the command line.

    The map is derived from the configured domains rather than written out, so adding a
    domain cannot leave the `--tab` option silently behind.
    """
    assert TAB_NUM_MAP[selector] == expected


# =============================================================================
# Log Pane
# =============================================================================


async def _stream_into(pilot: Any, pane: LogPane, lines: list[str]) -> None:
    """Stream a finite list of lines into a pane and wait for it to drain."""
    pane.start_stream(lambda: iter(lines))
    await _settle(pilot, lambda: pane.buffer.total_appended >= len(lines))
    await pilot.pause()


@pytest.mark.asyncio
async def test_the_log_pane_renders_only_its_viewport(
    patched_fetchers: Callable[..., None],
) -> None:
    """A stream far longer than the screen renders a bounded number of lines.

    Rendering the whole buffer is what drops frames; the pane must only ever draw the
    slice that is actually visible.
    """
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        pane = app.query_one("#log-pane", LogPane)
        pane.buffer.resize_viewport(5)
        await _stream_into(pilot, pane, [f"line-{index}" for index in range(500)])
        body = str(app.query_one("#log-body", Static).render())
        assert (len(body.splitlines()), pane.buffer.total_appended) == (5, 500)


@pytest.mark.asyncio
async def test_the_log_pane_retains_a_bounded_window_of_a_long_stream(
    patched_fetchers: Callable[..., None],
) -> None:
    """Memory is bounded by retention, not by how long the tail has been running."""
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        pane = app.query_one("#log-pane", LogPane)
        pane.buffer = VirtualLogBuffer(max_lines=100, viewport=5)
        await _stream_into(pilot, pane, [f"line-{index}" for index in range(5000)])
        assert (pane.buffer.retained, pane.buffer.dropped) == (100, 4900)


@pytest.mark.asyncio
async def test_the_log_pane_shows_the_newest_lines_while_following(
    patched_fetchers: Callable[..., None],
) -> None:
    """A live tail keeps the most recent output on screen."""
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        pane = app.query_one("#log-pane", LogPane)
        pane.buffer.resize_viewport(3)
        await _stream_into(pilot, pane, ["a", "b", "c", "d", "e"])
        body = str(app.query_one("#log-body", Static).render())
        assert body.splitlines() == ["c", "d", "e"]


@pytest.mark.asyncio
async def test_scrolling_the_log_pane_stops_it_following(
    patched_fetchers: Callable[..., None],
) -> None:
    """Reading back through history must not be yanked to the end by new output."""
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        pane = app.query_one("#log-pane", LogPane)
        pane.buffer.resize_viewport(3)
        await _stream_into(pilot, pane, [f"line-{index}" for index in range(20)])
        pane.action_scroll_pages(-2)
        scrolled = str(app.query_one("#log-body", Static).render())
        pane.action_follow()
        followed = str(app.query_one("#log-body", Static).render())
        assert (scrolled != followed, followed.splitlines()[-1]) == (True, "line-19")


@pytest.mark.asyncio
async def test_the_log_pane_status_reports_stream_position(
    patched_fetchers: Callable[..., None],
) -> None:
    """The pane states what it retained, what it dropped, and which pod it is tailing."""
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        pane = app.query_one("#log-pane", LogPane)
        pane.buffer = VirtualLogBuffer(max_lines=5, viewport=3)
        pane.title = "devops-system/api-0"
        await _stream_into(pilot, pane, [f"line-{index}" for index in range(10)])
        status = str(app.query_one("#log-status", Static).render())
        assert status == "devops-system/api-0 — 5 retained of 10, 5 dropped (following)"


@pytest.mark.asyncio
async def test_a_broken_log_stream_is_reported_in_the_pane(
    patched_fetchers: Callable[..., None],
) -> None:
    """A stream that dies mid-tail says so instead of silently stopping."""
    patched_fetchers()

    def failing() -> Any:
        yield "first line"
        raise ConnectionError("pod deleted")

    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        pane = app.query_one("#log-pane", LogPane)
        pane.start_stream(failing)
        await _settle(pilot, lambda: pane.buffer.total_appended >= 2)
        texts = [line.text for line in pane.buffer.viewport_lines()]
        assert texts[-1] == "stream ended: ConnectionError: pod deleted"


@pytest.mark.asyncio
async def test_redraws_are_coalesced_under_a_fast_stream(
    patched_fetchers: Callable[..., None],
) -> None:
    """A burst of lines must not schedule a redraw per line.

    Redrawing once per line puts the UI thread under exactly the load the virtualized pane
    exists to avoid, so the coalescing is asserted rather than assumed.
    """
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        pane = app.query_one("#log-pane", LogPane)
        pane.redraw_interval = 10.0
        draws = 0
        original = pane.refresh_view

        def counted() -> None:
            nonlocal draws
            draws += 1
            original()

        pane.refresh_view = counted  # type: ignore[method-assign]
        await _stream_into(pilot, pane, [f"line-{index}" for index in range(2000)])
        assert (draws <= 3, pane.buffer.total_appended) == (True, 2000)


@pytest.mark.asyncio
async def test_starting_a_stream_discards_the_previous_pod_output(
    patched_fetchers: Callable[..., None],
) -> None:
    """Switching pods must not interleave two pods' logs in one pane."""
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        pane = app.query_one("#log-pane", LogPane)
        await _stream_into(pilot, pane, ["pod-a line"])
        await _stream_into(pilot, pane, ["pod-b line"])
        texts = [line.text for line in pane.buffer.viewport_lines()]
        assert texts == ["pod-b line"]


@pytest.mark.asyncio
async def test_selecting_a_pod_opens_its_logs(
    patched_fetchers: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Choosing a pod row tails that pod without leaving the dashboard."""
    patched_fetchers()
    requested: list[tuple[str, str]] = []

    def fake_source(pod: str, namespace: str, tail_lines: int = 100) -> Callable[[], Any]:
        requested.append((namespace, pod))
        return lambda: iter(["log line one", "log line two"])

    monkeypatch.setattr(dashboard_module, "pod_log_source", fake_source)
    state = DashboardState()
    app = DashboardApp(refresh_interval=0, state=state)
    async with app.run_test() as pilot:
        await _settle(pilot, lambda: not state.pending_domains())
        table = app.query_one("#k8s-table", DataTable)
        table.focus()
        table.move_cursor(row=0)
        await pilot.pause()
        await pilot.press("enter")
        pane = app.query_one("#log-pane", LogPane)
        await _settle(pilot, lambda: pane.buffer.total_appended >= 2)
        await pilot.pause()
        assert (
            requested,
            app.query_one(TabbedContent).active,
            pane.title,
        ) == ([("devops-system", "api-0")], "tab-logs", "devops-system/api-0")


@pytest.mark.asyncio
async def test_selecting_a_row_outside_the_pod_table_starts_no_stream(
    patched_fetchers: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the Kubernetes table streams logs; other tables have no pod to tail."""
    patched_fetchers()
    requested: list[str] = []
    monkeypatch.setattr(
        dashboard_module,
        "pod_log_source",
        lambda pod, namespace, tail_lines=100: requested.append(pod),
    )
    state = DashboardState()
    app = DashboardApp(refresh_interval=0, state=state)
    async with app.run_test() as pilot:
        await _settle(pilot, lambda: not state.pending_domains())
        await pilot.press("2")
        await pilot.pause()
        table = app.query_one("#docker-table", DataTable)
        table.focus()
        table.move_cursor(row=0)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert (requested, app.query_one(TabbedContent).active) == ([], "tab-docker")


@pytest.mark.asyncio
async def test_the_logs_tab_is_reachable_by_its_own_key(
    patched_fetchers: Callable[..., None],
) -> None:
    """The log pane is bound to a letter, leaving the numbers for the domain tabs."""
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await pilot.press("l")
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "tab-logs"


def test_a_domain_panel_labels_itself_from_the_configured_labels() -> None:
    """Panels present the configured display name rather than the internal key."""
    assert (DomainPanel("k8s").label, DomainPanel("unknown").label) == (
        "Kubernetes",
        "Unknown",
    )


@pytest.mark.asyncio
async def test_stopping_a_stream_halts_consumption(
    patched_fetchers: Callable[..., None],
) -> None:
    """A tail that is no longer wanted stops appending mid-stream.

    Without this, every pod the operator glanced at would leave a worker and an open log
    connection alive for the life of the app.
    """
    patched_fetchers()
    gate = threading.Event()

    def gated() -> Any:
        yield "first"
        gate.wait(timeout=10)
        yield "second"
        yield "third"

    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        pane = app.query_one("#log-pane", LogPane)
        pane.start_stream(gated)
        await _settle(pilot, lambda: pane.buffer.total_appended == 1)
        pane.stop_stream()
        gate.set()
        await pilot.pause(0.2)
        assert pane.buffer.total_appended == 1


@pytest.mark.asyncio
async def test_scrolling_by_single_lines_moves_the_viewport(
    patched_fetchers: Callable[..., None],
) -> None:
    """Line-at-a-time scrolling steps the view rather than paging it."""
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        pane = app.query_one("#log-pane", LogPane)
        pane.buffer.resize_viewport(3)
        await _stream_into(pilot, pane, [f"line-{index}" for index in range(10)])
        before = pane.buffer.offset
        pane.action_scroll_lines(-1)
        assert (pane.buffer.offset, pane.buffer.following) == (before - 1, False)


def test_a_pod_log_source_opens_the_stream_only_when_it_is_consumed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The blocking connection must be established on the worker, not at wiring time.

    Opening it eagerly would put the connect on whichever thread built the source, which is
    the UI thread — reintroducing the freeze this design removes.
    """
    opened: list[str] = []

    class FakeService:
        @staticmethod
        def get_instance() -> Any:
            return FakeService()

        def read_pod_logs(self, **kwargs: Any) -> Any:
            opened.append(kwargs["pod"])
            return iter(["one", "two"])

    monkeypatch.setattr("devops_cli.k8s.service.KubernetesService", FakeService)
    source = pod_log_source("api-0", "devops-system")
    assert opened == []
    assert (list(source()), opened) == (["one", "two"], ["api-0"])


def test_a_pod_log_source_splits_a_non_streaming_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A server that returns the whole log as text still yields line by line."""

    class FakeService:
        @staticmethod
        def get_instance() -> Any:
            return FakeService()

        def read_pod_logs(self, **kwargs: Any) -> Any:
            return "alpha\nbeta\n"

    monkeypatch.setattr("devops_cli.k8s.service.KubernetesService", FakeService)
    assert list(pod_log_source("api-0", "devops-system")()) == ["alpha", "beta"]


@pytest.mark.asyncio
async def test_selecting_a_pod_row_with_no_pod_name_starts_no_stream(
    patched_fetchers: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed pod record must not open a stream against an empty pod name."""
    patched_fetchers(k8s=lambda: K8sSummary(connected=True, pods=[{"namespace": "default"}]))
    requested: list[str] = []
    monkeypatch.setattr(
        dashboard_module,
        "pod_log_source",
        lambda pod, namespace, tail_lines=100: requested.append(pod),
    )
    state = DashboardState()
    app = DashboardApp(refresh_interval=0, state=state)
    async with app.run_test() as pilot:
        await _settle(pilot, lambda: not state.pending_domains())
        table = app.query_one("#k8s-table", DataTable)
        table.focus()
        table.move_cursor(row=0)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert (requested, app.query_one(TabbedContent).active) == ([], "tab-k8s")


# =============================================================================
# Docker Inventory
# =============================================================================


def test_stopped_containers_are_listed_alongside_running_ones() -> None:
    """The panel disagreed with `docker ps -a`: it listed only running containers."""
    summary = DockerSummary(
        connected=True,
        containers=[
            {"id": "a", "name": "up", "image": "i", "status": "running"},
            {"id": "b", "name": "down", "image": "i", "status": "exited"},
        ],
    )
    assert [row[3] for row in docker_rows(summary)] == ["running", "exited"]


@pytest.mark.parametrize(
    ("resource", "expected_first"),
    [
        ("containers", "abc123"),
        ("images", "img001"),
        ("networks", "net001"),
        ("volumes", "data"),
        ("registries", "https://index.docker.io/v1/"),
    ],
)
def test_each_docker_resource_projects_from_the_shared_snapshot(
    resource: str, expected_first: str
) -> None:
    """Every Docker view is rendered from one inventory, not from its own daemon query."""
    snapshot = DomainSnapshot(domain="docker", data=_docker(), updated_at=time.time())
    assert docker_resource_rows(resource, snapshot)[0][0] == expected_first


@pytest.mark.parametrize("resource", list(CONST_DOCKER_RESOURCES))
def test_each_docker_resource_row_matches_its_column_count(resource: str) -> None:
    """A mismatch raises inside Textual on the UI thread when the row is added."""
    snapshot = DomainSnapshot(domain="docker", data=_docker(), updated_at=time.time())
    widths = {len(row) for row in docker_resource_rows(resource, snapshot)}
    assert widths == {len(DOCKER_RESOURCE_COLUMNS[resource])}


@pytest.mark.parametrize("resource", list(CONST_DOCKER_RESOURCES))
def test_a_docker_resource_renders_nothing_before_the_first_fetch(resource: str) -> None:
    """An unloaded panel renders empty rather than raising."""
    assert docker_resource_rows(resource, DomainSnapshot(domain="docker")) == []


def test_a_docker_sub_tab_label_carries_its_row_count() -> None:
    """Counts are readable without opening each tab."""
    snapshot = DomainSnapshot(domain="docker", data=_docker(), updated_at=time.time())
    assert docker_resource_label("images", snapshot) == "Images (1)"


def test_a_docker_sub_tab_label_omits_a_count_before_loading() -> None:
    """A count of zero before the first fetch would claim the daemon has nothing."""
    assert docker_resource_label("images", DomainSnapshot(domain="docker")) == "Images"


@pytest.mark.asyncio
async def test_every_docker_resource_lives_under_the_single_docker_tab(
    patched_fetchers: Callable[..., None],
) -> None:
    """Docker resources are Docker state and belong under one header.

    Promoting each to a top-level tab made them compete with Kubernetes and Valkey for
    attention, and crowded the footer past the point of truncation.
    """
    patched_fetchers()
    state = DashboardState()
    app = DashboardApp(refresh_interval=0, state=state)
    async with app.run_test() as pilot:
        await _settle(pilot, lambda: not state.pending_domains())
        panel = app.query_one("#panel-docker", DockerPanel)
        tabs = {
            pane.id for pane in panel.query_one("#docker-resources", TabbedContent).query(TabPane)
        }
        assert tabs == {f"docker-{resource}" for resource in CONST_DOCKER_RESOURCES}


@pytest.mark.asyncio
async def test_the_docker_panel_populates_every_resource_table(
    patched_fetchers: Callable[..., None],
) -> None:
    """One fetch fills all five views."""
    patched_fetchers()
    state = DashboardState()
    app = DashboardApp(refresh_interval=0, state=state)
    async with app.run_test() as pilot:
        await _settle(pilot, lambda: not state.pending_domains())
        panel = app.query_one("#panel-docker", DockerPanel)
        counts = {
            resource: panel.query_one(f"#{panel._table_id(resource)}", DataTable).row_count
            for resource in CONST_DOCKER_RESOURCES
        }
        assert counts == dict.fromkeys(CONST_DOCKER_RESOURCES, 1)


# =============================================================================
# Review Session Selection
# =============================================================================


def _sessions() -> list[ReviewSessionInfo]:
    """Sessions as the provider returns them: newest first."""
    return [
        ReviewSessionInfo(name="20260921-212653", completed=False),
        ReviewSessionInfo(name="20260920-124350", completed=True, finding_count=55),
        ReviewSessionInfo(name="20260919-145233", completed=True, finding_count=286),
    ]


def test_review_sessions_render_newest_first() -> None:
    """The provider orders them; re-sorting here would let the two disagree."""
    summary = ReviewSummary(has_session=True, sessions=_sessions())
    snapshot = DomainSnapshot(domain="ai", data=summary, updated_at=time.time())
    assert [row[0] for row in review_session_rows(snapshot)] == [
        "20260921-212653",
        "20260920-124350",
        "20260919-145233",
    ]


def test_an_incomplete_session_shows_no_finding_count() -> None:
    """A session that never wrote findings has no count, and zero would imply it found none."""
    summary = ReviewSummary(has_session=True, sessions=_sessions())
    snapshot = DomainSnapshot(domain="ai", data=summary, updated_at=time.time())
    rows = review_session_rows(snapshot)
    assert (rows[0][1], rows[0][2], rows[1][1], rows[1][2]) == (
        "incomplete",
        "-",
        "complete",
        "55",
    )


def test_review_sessions_render_nothing_before_the_first_fetch() -> None:
    """An unloaded panel renders empty rather than raising."""
    assert review_session_rows(DomainSnapshot(domain="ai")) == []


def test_the_review_banner_reports_incomplete_sessions() -> None:
    """A run still in progress is worth knowing about without being shown as the result."""
    summary = ReviewSummary(
        has_session=True,
        session_name="20260920-124350",
        total_findings=55,
        incomplete=["20260921-212653"],
    )
    assert "1 incomplete" in ai_banner(summary)


def test_the_review_banner_omits_the_note_when_every_session_completed() -> None:
    """There is nothing to report when nothing is outstanding."""
    summary = ReviewSummary(has_session=True, session_name="s", total_findings=1)
    assert "incomplete" not in ai_banner(summary)


# =============================================================================
# Review Session Discovery
# =============================================================================


def _make_sessions(tmp_path: Path, spec: dict[str, int | None]) -> Path:
    """Create review session directories; a None count writes no findings.json."""
    reviews = tmp_path / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    for name, count in spec.items():
        directory = reviews / name
        directory.mkdir()
        if count is not None:
            payload = {"findings": [{"severity": "LOW", "title": f"f{i}"} for i in range(count)]}
            (directory / "findings.json").write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


def test_an_in_progress_review_does_not_displace_the_last_completed_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A running review creates its directory before it writes any findings.

    Taking the newest directory therefore presented an empty session as the latest result
    and hid the last real review behind it.
    """
    root = _make_sessions(
        tmp_path, {"20260921-212653": None, "20260920-124350": 55, "20260919-145233": 286}
    )
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(root))
    summary = fetch_review_status()
    assert (summary.session_name, summary.total_findings) == ("20260920-124350", 55)


def test_sessions_are_listed_newest_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Session names are timestamps, so reverse lexical order is reverse chronological."""
    root = _make_sessions(
        tmp_path, {"20260919-145233": 1, "20260921-212653": None, "20260920-124350": 2}
    )
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(root))
    assert [info.name for info in list_review_sessions()] == [
        "20260921-212653",
        "20260920-124350",
        "20260919-145233",
    ]


def test_an_explicitly_selected_session_is_displayed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Choosing an earlier review opens it rather than the newest completed one."""
    root = _make_sessions(tmp_path, {"20260920-124350": 55, "20260919-145233": 286})
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(root))
    summary = fetch_review_status("20260919-145233")
    assert (summary.session_name, summary.total_findings) == ("20260919-145233", 286)


def test_a_selected_session_name_cannot_escape_the_reviews_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The selection names a session, so it must not be usable as a path."""
    root = _make_sessions(tmp_path, {"20260920-124350": 5})
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(root))
    assert fetch_review_status("../../etc").has_session is False


def test_incomplete_sessions_are_reported_without_being_shown_as_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """They are worth knowing about, but they are not findings."""
    root = _make_sessions(tmp_path, {"20260921-212653": None, "20260920-124350": 55})
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(root))
    summary = fetch_review_status()
    assert (summary.incomplete, summary.session_name) == (
        ["20260921-212653"],
        "20260920-124350",
    )


def test_a_review_with_nothing_completed_still_shows_the_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Showing the in-flight session beats showing nothing at all."""
    root = _make_sessions(tmp_path, {"20260921-212653": None})
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(root))
    summary = fetch_review_status()
    assert (summary.has_session, summary.session_name, summary.total_findings) == (
        True,
        "20260921-212653",
        0,
    )


def test_a_malformed_findings_file_counts_as_zero_rather_than_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One corrupt session must not break the session list."""
    reviews = tmp_path / "reviews" / "20260920-124350"
    reviews.mkdir(parents=True)
    (reviews / "findings.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    assert [(i.name, i.finding_count) for i in list_review_sessions()] == [("20260920-124350", 0)]


def test_no_reviews_directory_lists_no_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A workspace that has never been reviewed is not an error."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    assert (list_review_sessions(), fetch_review_status().has_session) == ([], False)


# =============================================================================
# Telemetry Source
# =============================================================================


def test_telemetry_falls_back_to_the_in_process_registry_without_a_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no Prometheus configured the panel reports what this process recorded."""
    monkeypatch.setattr(data_providers, "_prometheus_base_url", lambda: None)
    assert fetch_telemetry_status().source == "in-process"


def test_a_failed_backend_query_names_the_endpoint_that_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ "Connection refused" against a configured endpoint is a different problem from
    having no metrics, and the banner has to distinguish them."""
    monkeypatch.setattr(data_providers, "_prometheus_base_url", lambda: "http://prom:9090")
    monkeypatch.setattr(
        data_providers,
        "_fetch_prometheus_metrics",
        lambda url: (_ for _ in ()).throw(ConnectionError("connection refused")),
    )
    summary = fetch_telemetry_status()
    assert ("http://prom:9090" in summary.error_message, summary.source) == (True, "in-process")


# =============================================================================
# Shutdown
# =============================================================================


@pytest.mark.asyncio
async def test_quitting_does_not_wait_on_a_silent_log_stream(
    patched_fetchers: Callable[..., None],
) -> None:
    """Pressing `q` while tailing a quiet pod must not hang the application.

    A followed log never ends, and the read blocks until the next line arrives -- which
    for a quiet pod may be never. Textual waits for its thread workers on shutdown, so
    reading inside the worker meant quitting hung until the process was killed.
    """
    producing = threading.Event()
    release = threading.Event()

    def silent() -> Any:
        producing.set()
        release.wait(timeout=30)
        yield "eventually"

    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    try:
        async with app.run_test() as pilot:
            pane = app.query_one("#log-pane", LogPane)
            pane.start_stream(silent)
            assert producing.wait(timeout=10)
            started = time.monotonic()
            await pilot.press("q")
            await pilot.pause(0.2)
        elapsed = time.monotonic() - started
    finally:
        release.set()

    assert elapsed < 5.0, f"quitting took {elapsed:.1f}s while a stream was open"


@pytest.mark.asyncio
async def test_unmounting_the_pane_stops_its_stream(
    patched_fetchers: Callable[..., None],
) -> None:
    """The pane owns the stream, so the pane stops it.

    Doing this from the application does not work: by the time the app unmounts, the
    widget tree is torn down and a query for the pane returns nothing, leaving the
    consumer spinning and the interpreter unable to exit.
    """
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        pane = app.query_one("#log-pane", LogPane)
        pane.start_stream(lambda: iter(["one"]))
        await _settle(pilot, lambda: pane.buffer.total_appended >= 1)
        pane.on_unmount()
        assert pane._stop.is_set()


@pytest.mark.asyncio
async def test_the_stream_reader_runs_on_a_daemon_thread(
    patched_fetchers: Callable[..., None],
) -> None:
    """The reader is blocked in a read that cannot be interrupted.

    The only way to stop waiting for it is not to, so it must never be a thread the
    interpreter joins at exit.
    """
    release = threading.Event()
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    try:
        async with app.run_test() as pilot:
            pane = app.query_one("#log-pane", LogPane)
            pane.start_stream(lambda: iter(release.wait(30) or ["x"]))
            await pilot.pause(0.1)
            assert pane._producer is not None
            assert pane._producer.daemon is True
    finally:
        release.set()


@pytest.mark.asyncio
async def test_a_producer_faster_than_the_terminal_does_not_grow_without_bound(
    patched_fetchers: Callable[..., None],
) -> None:
    """The hand-off queue is bounded; the log buffer is the retention mechanism.

    Blocking the producer instead would stall the stream, and growing the queue would
    reintroduce the unbounded memory the virtualized buffer exists to prevent.
    """
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        pane = app.query_one("#log-pane", LogPane)
        await _stream_into(pilot, pane, [f"line-{index}" for index in range(5000)])
        assert pane._lines.qsize() <= CONST_LOG_STREAM_QUEUE_SIZE
