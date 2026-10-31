"""Tests for Shutdown behaviour in reactive dashboard."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from devops_cli.config.constants import (
    CONST_LOG_STREAM_QUEUE_SIZE,
)
from devops_cli.ui.dashboard import DashboardApp
from devops_cli.ui.widgets import LogPane
from tests.support.ui import (
    _settle,
    _stream_into,
)
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

_HOLD_OUTLIVE_BOUND_SECONDS = 2 * THREAD_HANDOFF_BOUND_SECONDS
"""How long a hold waits to ensure it outlives every wait observing it."""


async def test_quitting_does_not_wait_on_a_silent_log_stream(
    patched_fetchers: Callable[..., None],
) -> None:
    """Pressing `q` while tailing a quiet pod must not hang the application.

    A followed log never ends, and the read blocks until the next line arrives -- which
    for a quiet pod may be never. Textual waits for its thread workers on shutdown, so
    reading inside the worker meant quitting hung until the process was killed.

    The stream stays silent until the test releases it, after the application has shut down.
    A quit that does not wait for the stream ends with the stream still held: `release` is
    unset and the hold did not run out. A quit that waits ends only when the hold runs out,
    which the check reads. No clock decides the verdict: a slow host delays the quit and
    nothing more.
    """
    producing = threading.Event()
    release = threading.Event()
    hold_ran_out = threading.Event()

    def silent() -> Any:
        producing.set()
        # The hold outlives every wait that observes it, and records that it ran out by itself.
        if not release.wait(timeout=_HOLD_OUTLIVE_BOUND_SECONDS):
            hold_ran_out.set()
        yield "eventually"

    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    try:
        async with app.run_test() as pilot:
            pane = app.query_one("#log-pane", LogPane)
            pane.start_stream(silent)
            assert producing.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
            await pilot.press("q")
            assert await _settle(pilot, lambda: not app.is_running), "q did not stop the app"
        held = (release.is_set(), hold_ran_out.is_set())
    finally:
        release.set()

    assert held == (False, False), "the application shut down only after the stream was released"


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


async def test_the_stream_reader_runs_on_a_daemon_thread(
    patched_fetchers: Callable[..., None],
) -> None:
    """The reader is blocked in a read that cannot be interrupted.

    The only way to stop waiting for it is not to, so it must never be a thread the
    interpreter joins at exit.
    """
    release = threading.Event()
    reading = threading.Event()
    patched_fetchers()
    app = DashboardApp(refresh_interval=0)
    try:
        async with app.run_test():
            pane = app.query_one("#log-pane", LogPane)

            def _hanging_stream() -> list[str]:
                reading.set()
                release.wait()
                return ["x"]

            pane.start_stream(_hanging_stream)
            assert reading.wait(THREAD_HANDOFF_BOUND_SECONDS)
            assert pane._producer is not None
            assert pane._producer.daemon is True
    finally:
        release.set()


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
