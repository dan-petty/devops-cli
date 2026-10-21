"""The wall clock and waiting seam faked for tests, and the `clock` fixture that installs it (#1320).

Wall-clock reads are faked with `time-machine` with ticking turned off, so time moves only when a
test or a wait advances it. Waiting through `devops_cli.core.clock` (`sleep` and `async_sleep`) or
through the stdlib fallback `time.sleep` shifts `time-machine`'s wall clock and the seam's
monotonic reading by the requested duration, returns at once, and appends `float(seconds)` to
`waits`. `asyncio.sleep` is never replaced, so event loops and libraries that call `asyncio.sleep`
to yield keep their scheduling.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any

import pytest
import time_machine

from devops_cli.core import clock as clock_seam


class ClockFake:
    """In-memory fake for the clock seam: shifts `time-machine` and records every wait."""

    def __init__(self, traveller: time_machine.Traveller) -> None:
        self._traveller = traveller
        self._monotonic = 0.0
        self._lock = threading.Lock()
        self._sleep_barrier: threading.Barrier | None = None
        self.waits: list[float] = []

    def sleep(self, seconds: float) -> None:
        """Record a synchronous wait, advance the wall and monotonic clocks, and return at once."""
        duration = float(seconds)
        barrier = self._sleep_barrier
        if barrier is not None:
            barrier.wait()
        with self._lock:
            self.waits.append(duration)
            self._traveller.shift(duration)
            self._monotonic += duration

    async def async_sleep(self, delay: float, result: Any = None) -> Any:
        """Record an asynchronous wait, advance the wall and monotonic clocks, and return `result`."""
        duration = float(delay)
        with self._lock:
            self.waits.append(duration)
            self._traveller.shift(duration)
            self._monotonic += duration
        return result

    def monotonic(self) -> float:
        """The monotonic reading `ratelimit.limits(clock=...)` reads."""
        return self._monotonic

    def move_to(self, destination: time_machine.DestinationType) -> None:
        """Move the wall clock to `destination` without ticking or recording a wait."""
        with self._lock:
            self._traveller.move_to(destination, tick=False)

    def shift(self, delta: float | timedelta) -> None:
        """Advance the wall and monotonic clocks by `delta` without recording a wait."""
        seconds = delta.total_seconds() if isinstance(delta, timedelta) else float(delta)
        with self._lock:
            self._traveller.shift(seconds)
            self._monotonic += seconds

    @contextmanager
    def concurrent_sleeps(self, parties: int) -> Iterator[None]:
        """Hold `parties` concurrent `sleep` callers at a barrier before advancing the clock."""
        self._sleep_barrier = threading.Barrier(parties, timeout=5.0)
        try:
            yield
        finally:
            self._sleep_barrier = None


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[ClockFake]:
    """Start `time-machine` without ticking, route the clock seam and `time.sleep` through
    `ClockFake`, and leave `asyncio.sleep` untouched."""
    travel = time_machine.travel(time.time(), tick=False)
    traveller = travel.start()
    try:
        fake = ClockFake(traveller)
        monkeypatch.setattr(clock_seam, "sleep", fake.sleep)
        monkeypatch.setattr(clock_seam, "async_sleep", fake.async_sleep)
        monkeypatch.setattr(clock_seam, "monotonic", fake.monotonic)
        monkeypatch.setattr(time, "sleep", fake.sleep)
        yield fake
    finally:
        travel.stop()
