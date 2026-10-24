"""How long a test waits for something it expects another thread or process to do (#1664).

A wait that expects its event (an `Event.wait`, `Queue.get`, `Thread.join`, `Future.result`, a
`Barrier`'s timeout, a Service worker's `wait_active`, a poll) uses `THREAD_HANDOFF_BOUND_SECONDS`.
It returns as soon as the event happens, so the bound costs a passing test nothing and only a
failing test waits it out. One- and two-second deadlines failed correct code whenever a loaded
host kept a ready thread waiting longer than that for a CPU.

Anything a test relies on to stay alive or blocked, such as a sleeping child process or a job
held until the test releases it, must outlive the bound of every wait that observes it, or record
whether the test ended it and assert that it did. A hold that runs out on the same bound as its
observer ends inside the observer's window, and the test then passes with the bug it checks for.

A wait that checks that nothing happens is the other kind. It keeps a short window of its own,
opened only once the test has waited, with the bound, for the threads involved to go idle or to
reach the point where the event would happen, and a comment at the wait says so.

A wait for an event of a process that the test started, such as a fresh `devops` that starts a
child, uses `wait_while_running` and has no bound of its own. The start of a fresh interpreter
that imports devops-cli is the step that a loaded host stretches the most: in a full run at a load
average of 40 to 106 it took longer than the bound (#2092). Such a process either causes the event
or exits, and one that does neither fails the test at the hang bound of pytest-timeout.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from typing import Any, Final

THREAD_HANDOFF_BOUND_SECONDS: Final[float] = 30.0
"""How long a test waits for an event it expects another thread or process to cause."""

POLL_INTERVAL_SECONDS: Final[float] = 0.01
"""How long `wait_until` sleeps between two reads of a condition that does not hold yet."""


def wait_until(condition: Callable[[], bool], bound: float = THREAD_HANDOFF_BOUND_SECONDS) -> bool:
    """Whether `condition` came to hold within `bound` seconds, read again every poll interval
    until it does; a condition that holds already is read once. The deadline is checked after
    each sleep and before the next read, so a sleep that overruns it counts no later event."""
    deadline = time.monotonic() + bound
    while True:
        if condition():
            return True
        time.sleep(POLL_INTERVAL_SECONDS)
        if time.monotonic() >= deadline:
            return False


def wait_while_running(condition: Callable[[], bool], process: subprocess.Popen[Any]) -> bool:
    """Whether `condition` came to hold while `process` ran, read again every poll interval until
    it holds or `process` exits. A condition that holds already is read once. After the exit it is
    read once more, since a process can cause its event just before it exits. The wait has no
    bound of its own: a process that hangs fails the test at the hang bound of pytest-timeout."""
    while process.poll() is None:
        if condition():
            return True
        time.sleep(POLL_INTERVAL_SECONDS)
    return condition()
