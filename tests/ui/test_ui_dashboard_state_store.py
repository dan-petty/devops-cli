"""Tests for Dashboard State Store behaviour in reactive dashboard."""

from __future__ import annotations

import threading

from devops_cli.config.constants import (
    CONST_DASHBOARD_DOMAINS,
)
from devops_cli.ui.state import DashboardState, DomainSnapshot
from tests.support.ui import (
    _docker,
    _k8s,
)
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS


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
        release.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    state.publish("k8s", _k8s())
    state.subscribe(slow)
    blocker = threading.Thread(target=lambda: state.publish("k8s", _k8s()))
    blocker.start()
    assert entered.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    read = threading.Event()

    def reader() -> None:
        state.snapshots()
        state.get("k8s")
        read.set()

    worker = threading.Thread(target=reader)
    worker.start()
    assert read.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS), (
        "the store stayed locked while a subscriber ran"
    )

    release.set()
    blocker.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    worker.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)


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
        thread.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    stored = state.snapshots()
    assert (len(stored), all(stored[d].data == d for d in domains)) == (40, True)
