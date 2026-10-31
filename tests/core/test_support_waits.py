"""The one bound a test waits with for something it expects another thread to do (#1664), and
the wait with no bound of its own for an event of a process the test started (#2092)."""

from __future__ import annotations

import subprocess
import threading

import pytest

from tests.support import waits
from tests.support.waits import (
    POLL_INTERVAL_SECONDS,
    THREAD_HANDOFF_BOUND_SECONDS,
    wait_until,
    wait_while_running,
)

LATE_EVENT_SECONDS = 1.5
"""How late the event comes: later than the one-second deadlines that failed correct code while
a loaded host kept a ready thread waiting for a CPU."""


class _VirtualTime:
    """The `time` `wait_until` reads, on a clock only its sleeps move, so how late a thread is
    scheduled cannot change what the wait sees. A sleep that starts at `stall_at` or later lasts
    `stall` seconds more, as a thread a loaded host does not run on time."""

    def __init__(self, stall_at: float = float("inf"), stall: float = 0.0) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []
        self._stall_at, self._stall = stall_at, stall

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        overslept = self._stall if self.now >= self._stall_at else 0.0
        self._stall_at = float("inf") if overslept else self._stall_at
        self.now += seconds + overslept


@pytest.fixture
def virtual_time(monkeypatch: pytest.MonkeyPatch) -> _VirtualTime:
    clock = _VirtualTime()
    monkeypatch.setattr(waits, "time", clock)
    return clock


def test_a_wait_for_an_event_that_fires_after_a_second_and_a_half_fails_with_a_one_second_deadline(
    virtual_time: _VirtualTime,
) -> None:
    """On a clock only the wait's sleeps move, an event from 1.5 s on is not seen by a wait with a
    one-second deadline, which gives up once its deadline has passed."""
    seen = wait_until(lambda: virtual_time.now >= LATE_EVENT_SECONDS, bound=1.0)

    assert (seen, virtual_time.now >= 1.0, virtual_time.now < LATE_EVENT_SECONDS) == (
        False,
        True,
        True,
    )


def test_a_wait_for_an_event_that_fires_after_a_second_and_a_half_succeeds_with_the_bound() -> None:
    """An event a timer sets 1.5 s after the wait starts is seen within the bound."""
    fired = threading.Event()
    timer = threading.Timer(LATE_EVENT_SECONDS, fired.set)
    timer.start()
    try:
        assert wait_until(fired.is_set, bound=THREAD_HANDOFF_BOUND_SECONDS) is True
    finally:
        timer.cancel()


def test_a_poll_that_oversleeps_its_deadline_does_not_count_a_later_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sleep that runs past the deadline, as on a loaded host, ends the wait before the
    condition is read again, so an event that came after the deadline is not counted."""
    clock = _VirtualTime(stall_at=1.0 - POLL_INTERVAL_SECONDS, stall=0.7)
    monkeypatch.setattr(waits, "time", clock)

    seen = wait_until(lambda: clock.now >= LATE_EVENT_SECONDS, bound=1.0)

    assert (seen, clock.now >= LATE_EVENT_SECONDS) == (False, True)


def test_a_condition_that_already_holds_is_read_once_and_not_waited_for(
    virtual_time: _VirtualTime,
) -> None:
    """A wait whose event has happened returns at once, so the bound costs a passing test
    nothing: the condition is read once and no poll interval is slept."""
    reads: list[bool] = []

    def holds() -> bool:
        reads.append(True)
        return True

    assert (wait_until(holds), len(reads), virtual_time.sleeps) == (True, 1, [])


PROCESS_HOLD_SECONDS = int(10 * THREAD_HANDOFF_BOUND_SECONDS)
"""How long the running process sleeps: longer than every wait that observes it, so it runs until
the test stops it."""


@pytest.mark.live("sleep")
def test_a_wait_while_a_process_runs_sees_an_event_later_than_the_handoff_bound(
    virtual_time: _VirtualTime,
) -> None:
    """On a clock only the wait's sleeps move, the wait sees an event that comes at twice the
    handoff bound while the process still runs, as a fresh `devops` started its child on a
    loaded host after more than the bound (#2092)."""
    late = 2 * THREAD_HANDOFF_BOUND_SECONDS
    process = subprocess.Popen(["sleep", str(PROCESS_HOLD_SECONDS)])
    try:
        seen = wait_while_running(lambda: virtual_time.now >= late, process)
        still_running = process.poll() is None
    finally:
        process.kill()
        process.wait()

    assert (seen, still_running, virtual_time.now >= late) == (True, True, True)


@pytest.mark.live("true")
def test_a_wait_while_a_process_runs_ends_once_the_process_exits_without_the_event(
    virtual_time: _VirtualTime,
) -> None:
    """A process that exits without the event ends the wait: the condition is read once after the
    exit and no poll interval is slept."""
    process = subprocess.Popen(["true"])
    process.wait(THREAD_HANDOFF_BOUND_SECONDS)
    reads: list[bool] = []

    def never() -> bool:
        reads.append(False)
        return False

    assert (wait_while_running(never, process), reads, virtual_time.sleeps) == (False, [False], [])
