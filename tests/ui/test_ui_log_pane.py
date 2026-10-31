"""Tests for Log Pane behaviour in reactive dashboard."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import pytest
from textual.widgets import DataTable, Static, TabbedContent

import devops_cli.ui.dashboard as dashboard_module
from devops_cli.ui.dashboard import DashboardApp
from devops_cli.ui.log_buffer import VirtualLogBuffer
from devops_cli.ui.refresh import (
    pod_log_source,
)
from devops_cli.ui.state import DashboardState
from devops_cli.ui.widgets import DomainPanel, LogPane
from tests.support.fakes.kubernetes import (
    FakeCluster,
)
from tests.support.ui import (
    _settle,
    _stream_ended,
    _stream_into,
)
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS


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


async def test_the_log_pane_renders_ansi_and_unencoded_markup_without_error(
    patched_fetchers: Callable[..., None],
) -> None:
    """Log lines containing ANSI escapes and unescaped markup brackets must not fail with MarkupError."""
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    raw_log = (
        "\x1b[90m2026-09-30T11:06:39Z\x1b[0m \x1b[31mERR\x1b[0m "
        '\x1b[1mCannot create service\x1b[0m \x1b[36merror=\x1b[0m\x1b[31m\x1b[1m"service not found"\x1b[0m\x1b[0m '
        "&ServiceBackendPort{Name:,Number:80,}"
    )
    async with app.run_test() as pilot:
        pane = app.query_one("#log-pane", LogPane)
        pane.title = "kube-system/traefik-0 [custom]"
        await _stream_into(pilot, pane, [raw_log])
        body = str(app.query_one("#log-body", Static).render())
        status = str(app.query_one("#log-status", Static).render())
        assert (
            "Cannot create service" in body,
            "&ServiceBackendPort{Name:,Number:80,}" in body,
            status,
        ) == (
            True,
            True,
            "kube-system/traefik-0 [custom] — 1 retained of 1 (following)",
        )


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


async def test_selecting_a_pod_opens_its_logs(
    patched_fetchers: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Choosing a pod row tails that pod without leaving the dashboard."""
    patched_fetchers()
    requested: list[tuple[str, str, str | None]] = []

    def fake_source(
        pod: str, namespace: str, container: str | None = None, tail_lines: int = 100
    ) -> Callable[[], Any]:
        requested.append((namespace, pod, container))
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
        ) == (
            [("devops-system", "api-0", "api")],
            "tab-logs",
            "devops-system/api-0 [api] (1 of 1 containers)",
        )


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
        lambda pod, namespace, container=None, tail_lines=100: requested.append(pod),
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
        gate.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
        yield "second"
        yield "third"

    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        pane = app.query_one("#log-pane", LogPane)
        pane.start_stream(gated)
        await _settle(pilot, lambda: pane.buffer.total_appended == 1)
        stream_ended = _stream_ended(pane)
        pane.stop_stream()
        gate.set()
        assert (await _settle(pilot, stream_ended), pane.buffer.total_appended) == (True, 1)


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


async def test_log_pane_streams_framed_pod_logs(
    patched_fetchers: Callable[..., None], cluster: FakeCluster
) -> None:
    """A LogPane streaming pod_log_source frames chunks incrementally without split lines."""
    from devops_cli.ui.dashboard import DashboardApp

    patched_fetchers()
    cluster.core.answers["read_namespaced_pod_log"] = {("shop", "web-0"): [b"a\nb", b"c\nd\n"]}

    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        pane = app.query_one("#log-pane", LogPane)
        pane.start_stream(pod_log_source("web-0", "shop"))
        await _settle(pilot, lambda: pane.buffer.total_appended >= 3)
        entries = [line.text for line in pane.buffer.viewport_lines()]
        assert entries[-3:] == ["a", "bc", "d"]


class _FakeLogStream:
    """A followed log as the service returns it: lines, and close() to stop reading."""

    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self.closed = 0

    def __iter__(self) -> Any:
        return iter(self.lines)

    def close(self) -> None:
        self.closed += 1


@pytest.mark.parametrize("closed_first", [False, True])
def test_closing_a_pod_log_source_closes_its_stream_whenever_it_opens(
    monkeypatch: pytest.MonkeyPatch, closed_first: bool
) -> None:
    """The pane may stop a stream before its worker has opened the connection."""
    stream = _FakeLogStream(["one"])

    class FakeService:
        @staticmethod
        def get_instance() -> Any:
            return FakeService()

        def read_pod_logs(self, **kwargs: Any) -> Any:
            return stream

    monkeypatch.setattr("devops_cli.k8s.service.KubernetesService", FakeService)
    source = pod_log_source("api-0", "devops-system")
    if closed_first:
        source.close()
    opened = source()
    if not closed_first:
        source.close()
    assert (list(opened), stream.closed) == (["one"], 1)
