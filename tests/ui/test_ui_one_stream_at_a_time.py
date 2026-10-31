"""Tests for One Stream at a Time behaviour in reactive dashboard."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import pytest

import devops_cli.ui.dashboard as dashboard_module
from devops_cli.ui.dashboard import DashboardApp
from devops_cli.ui.data_providers import (
    K8sSummary,
)
from devops_cli.ui.widgets import LogPane
from tests.support.ui import (
    _endless,
    _loaded,
    _pod,
    _pods,
    _settle,
    _sidecar_pod,
    _stream_ended,
)


async def _switched_cleanly(
    pilot: Any, pane: LogPane, old_stream_ended: Callable[[], bool], old: str, new: str
) -> bool:
    """Wait for the new stream, and for the old one to end, after which a leak would show."""
    await _settle(pilot, lambda: bool(pane.buffer.search(new)))
    ended = await _settle(pilot, old_stream_ended)
    return ended and not pane.buffer.search(old) and bool(pane.buffer.search(new))


async def test_switching_containers_stops_the_previous_stream(
    patched_fetchers: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The old producer kept reading and its consumer kept writing into the shared buffer."""
    release = threading.Event()
    patched_fetchers(k8s=lambda: _sidecar_pod(annotated=True))
    monkeypatch.setattr(dashboard_module, "pod_log_source", _endless(release))
    app = DashboardApp(refresh_interval=0)
    try:
        async with app.run_test() as pilot:
            await _loaded(pilot, app)
            pane = app.query_one("#log-pane", LogPane)
            await pilot.press("enter")
            await _settle(pilot, lambda: bool(pane.buffer.search("web-0/app")))
            old_stream_ended = _stream_ended(pane)
            await pilot.press("c")
            assert await _switched_cleanly(
                pilot, pane, old_stream_ended, "web-0/app", "web-0/sidecar"
            )
    finally:
        release.set()


async def test_opening_a_second_pod_stops_the_first_pods_stream(
    patched_fetchers: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Enter on a second pod mixed both pods' live logs in one pane."""
    release = threading.Event()
    patched_fetchers(k8s=lambda: _pods(2))
    monkeypatch.setattr(dashboard_module, "pod_log_source", _endless(release))
    app = DashboardApp(refresh_interval=0)
    try:
        async with app.run_test() as pilot:
            await _loaded(pilot, app)
            pane = app.query_one("#log-pane", LogPane)
            await pilot.press("enter")
            await _settle(pilot, lambda: bool(pane.buffer.search("pod-00/")))
            old_stream_ended = _stream_ended(pane)
            await pilot.press("1", "down", "enter")
            assert await _switched_cleanly(pilot, pane, old_stream_ended, "pod-00/", "pod-01/")
    finally:
        release.set()


class _ClosableSource:
    """A pod log source recording when the pane closes it."""

    def __init__(self, name: str, closed: list[str]) -> None:
        self.name = name
        self.closed = closed

    def __call__(self) -> Any:
        return iter([f"{self.name} line"])

    def close(self) -> None:
        self.closed.append(self.name)


async def test_switching_streams_closes_the_one_before(
    patched_fetchers: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stopped stream of a quiet container kept its connection and thread until exit.

    `c` and Enter on another pod close the stream they replace; quitting closes the last.
    """
    closed: list[str] = []
    patched_fetchers(
        k8s=lambda: K8sSummary(
            connected=True, pods=[_pod("web-0", containers=("app", "sidecar")), _pod("web-1")]
        )
    )
    monkeypatch.setattr(
        dashboard_module,
        "pod_log_source",
        lambda pod, namespace, container=None, **_: _ClosableSource(f"{pod}/{container}", closed),
    )
    app = DashboardApp(refresh_interval=0)
    async with app.run_test() as pilot:
        await _loaded(pilot, app)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        await pilot.press("1", "down", "enter")
        await pilot.pause()
        switched = list(closed)
    assert (switched, closed) == (
        ["web-0/app", "web-0/sidecar"],
        ["web-0/app", "web-0/sidecar", "web-1/app"],
    )
