"""Tests for Widget & App Integration behaviour in reactive dashboard."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from textual.widgets import DataTable, Static, TabbedContent

from devops_cli.config.constants import (
    CONST_DASHBOARD_DOMAIN_DOCKER,
    CONST_DASHBOARD_DOMAINS,
)
from devops_cli.ui.dashboard import DashboardApp
from devops_cli.ui.data_providers import (
    DockerSummary,
)
from devops_cli.ui.projections import (
    DOMAIN_COLUMNS,
)
from devops_cli.ui.state import DashboardState, DomainSnapshot
from devops_cli.ui.widgets import DockerPanel, DomainPanel, K8sPanel
from tests.support.ui import (
    SAMPLES,
    _k8s,
    _settle,
)
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS


async def test_the_dashboard_mounts_one_panel_per_configured_domain(
    patched_fetchers: Callable[..., None],
) -> None:
    """Adding a domain must not require editing the app's compose block."""
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    async with app.run_test():
        panels = {panel.domain for panel in app.query(DomainPanel).results(DomainPanel)}
        panels |= {panel.domain for panel in app.query(DockerPanel).results(DockerPanel)}
        panels |= {panel.domain for panel in app.query(K8sPanel).results(K8sPanel)}
        assert panels == set(CONST_DASHBOARD_DOMAINS)


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
        widths["k8s"] = len(app.query_one("#k8s-table", DataTable).columns)
        # Docker composes nested tabs, so it is not a plain DomainPanel.
        assert widths == {
            domain: len(DOMAIN_COLUMNS[domain])
            for domain in CONST_DASHBOARD_DOMAINS
            if domain != CONST_DASHBOARD_DOMAIN_DOCKER
        }


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
        counts["k8s"] = app.query_one("#k8s-table", DataTable).row_count
        counts["docker"] = app.query_one("#docker-table", DataTable).row_count
        assert counts == {"k8s": 1, "docker": 1, "telemetry": 3, "valkey": 7}


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


async def test_a_slow_subsystem_does_not_freeze_the_interface(
    patched_fetchers: Callable[..., None],
) -> None:
    """The dashboard stays navigable while a domain is still being fetched.

    This is the defect the reactive architecture exists to fix: the previous design called
    every provider synchronously from the keypress handler, so one unreachable cluster
    froze every unrelated tab for the duration of its timeout.

    The k8s fetch is held until the test releases it, with no bound of its own, so it outlives
    every wait that observes it. A 10 s hold ran out on a loaded host before the test looked,
    and the fetch was then over (#2092). The test releases the hold before the app exits on every
    path, since Textual waits for its thread workers when it shuts down.
    """
    release = threading.Event()
    entered = threading.Event()

    def slow_k8s() -> Any:
        entered.set()
        release.wait()
        return _k8s()

    patched_fetchers(k8s=slow_k8s)
    state = DashboardState()
    app = DashboardApp(refresh_interval=0, state=state)
    async with app.run_test() as pilot:
        try:
            assert entered.wait(THREAD_HANDOFF_BOUND_SECONDS), "the k8s worker never started"

            await pilot.press("2")
            await pilot.pause()
            active_while_blocked = app.query_one(TabbedContent).active

            docker_table = app.query_one("#docker-table", DataTable)
            await _settle(pilot, lambda: docker_table.row_count > 0)
            rendered_while_blocked = docker_table.row_count
            k8s_still_fetching = state.in_flight() == ["k8s"]
        finally:
            release.set()
        await _settle(pilot, lambda: not state.pending_domains())

    assert (active_while_blocked, rendered_while_blocked, k8s_still_fetching) == (
        "tab-docker",
        1,
        True,
    )


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


async def test_a_refresh_keypress_never_blocks_on_the_providers(
    patched_fetchers: Callable[..., None],
) -> None:
    """The key that triggers a refresh must return immediately.

    Dispatching to workers is what keeps the keypress handler from becoming the place the
    interface hangs. Each provider is held until the test releases it after the handler returns.
    A handler that called a provider would return only after the hold, with that fetch done, so
    the test reads no clock (#1902).
    """
    release = threading.Event()
    fetched: list[str] = []

    def slow_for(domain: str) -> Callable[[], Any]:
        def fetch() -> Any:
            release.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
            fetched.append(domain)
            return SAMPLES[domain]()

        return fetch

    patched_fetchers(**{domain: slow_for(domain) for domain in CONST_DASHBOARD_DOMAINS})
    app = DashboardApp(refresh_interval=0)
    try:
        async with app.run_test() as pilot:
            app.action_refresh_data()
            fetched_when_returned = list(fetched)
            release.set()
            await pilot.pause()
        assert fetched_when_returned == []
    finally:
        release.set()


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
