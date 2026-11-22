"""The real-sleep budget of a test, and the poll exemption of `wait_until` (#4669, #6696).

The floor charges every real `time.sleep` of the run to the total here, and fails a test whose
sleeps pass `REAL_SLEEP_BUDGET_SECONDS`. A poll of `wait_until` waits for another thread, and a
loaded host can keep that thread waiting for longer than the budget, so the poll sleeps of the
current thread are charged nothing: `wait_until` enters `poll_sleep()` around each poll, and a
real sleep outside a poll is charged as before.

The audit hook runs for the `time.sleep` of every thread, so the exemption is thread-local: a
sleep of another thread is charged even while this one polls.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

REAL_SLEEP_BUDGET_SECONDS: Final[float] = 0.25
"""How much real sleep a test may take before the floor fails it."""

_LOCK = threading.Lock()
_CHARGED_SECONDS: float = 0.0
_POLL_DEPTH = threading.local()


def charge(seconds: float) -> None:
    """Add the real sleep of `seconds` to the charged total, unless the current thread is inside
    a poll of `wait_until`, which waits for another thread and costs the test nothing."""
    global _CHARGED_SECONDS
    if seconds <= 0 or poll_depth() > 0:
        return
    with _LOCK:
        _CHARGED_SECONDS += seconds


def charged_seconds() -> float:
    """The real sleep, in seconds, that the tests of this process have been charged."""
    with _LOCK:
        return _CHARGED_SECONDS


def poll_depth() -> int:
    """How many polls of `wait_until` the current thread is inside."""
    return int(getattr(_POLL_DEPTH, "depth", 0))


@contextmanager
def poll_sleep() -> Iterator[None]:
    """Charge no real sleep that the current thread makes inside the block, as a poll of
    `wait_until` does: the thread waits for another thread, which a loaded host stretches."""
    depth = poll_depth()
    _POLL_DEPTH.depth = depth + 1
    try:
        yield
    finally:
        _POLL_DEPTH.depth = depth
