"""Tests for Refresh Coordination behaviour in reactive dashboard."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from devops_cli.config.constants import (
    CONST_DASHBOARD_DOMAINS,
)
from devops_cli.ui.refresh import (
    DOMAIN_FETCHERS,
    refresh_domain,
)
from devops_cli.ui.state import DashboardState
from tests.support.ui import (
    _k8s,
)
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS


def test_refresh_domain_publishes_the_fetched_result(
    state: DashboardState, patched_fetchers: Callable[..., None]
) -> None:
    """A successful fetch lands in the store."""
    patched_fetchers(k8s=_k8s)
    snapshot = refresh_domain(state, "k8s")
    assert snapshot is not None
    assert (snapshot.error, snapshot.data.connected) == (None, True)


def test_refresh_domain_converts_a_provider_failure_into_a_snapshot(
    state: DashboardState, patched_fetchers: Callable[..., None]
) -> None:
    """An exception on a worker thread must never escape.

    An escaping exception kills the worker silently, leaving the panel showing data that
    never updates again with no indication anything is wrong.
    """

    def broken() -> Any:
        raise ConnectionError("cluster unreachable")

    patched_fetchers(k8s=broken)
    snapshot = refresh_domain(state, "k8s")
    assert snapshot is not None
    assert snapshot.error == "ConnectionError: cluster unreachable"


def test_refresh_domain_releases_its_claim_after_a_failure(
    state: DashboardState, patched_fetchers: Callable[..., None]
) -> None:
    """A failed fetch must not leave the domain permanently locked out of refreshing."""

    def broken() -> Any:
        raise ConnectionError("down")

    patched_fetchers(k8s=broken)
    refresh_domain(state, "k8s")
    patched_fetchers(k8s=_k8s)
    recovered = refresh_domain(state, "k8s")
    assert (state.in_flight(), recovered is not None) == ([], True)


def test_a_refresh_tick_does_not_stack_a_second_fetch_on_a_slow_domain(
    state: DashboardState, patched_fetchers: Callable[..., None]
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
        release.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
        return _k8s()

    patched_fetchers(k8s=slow)
    worker = threading.Thread(target=refresh_domain, args=(state, "k8s"))
    worker.start()
    assert entered.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    assert (refresh_domain(state, "k8s"), state.in_flight()) == (None, ["k8s"])

    release.set()
    worker.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    assert (calls, state.in_flight()) == ([1], [])


def test_refresh_domain_reports_an_unregistered_domain_as_an_error(
    state: DashboardState,
) -> None:
    """A domain with no provider surfaces as a visible error, not a silent blank panel."""
    snapshot = refresh_domain(state, "nonexistent")
    assert snapshot is not None
    assert snapshot.error == "No provider registered for domain 'nonexistent'"


def test_every_configured_domain_has_a_registered_provider() -> None:
    """A domain declared but never fetched would render as a permanently empty tab."""
    assert sorted(DOMAIN_FETCHERS) == sorted(CONST_DASHBOARD_DOMAINS)
