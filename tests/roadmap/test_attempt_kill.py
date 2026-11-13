"""SIGTERM ends a roadmap attempt with `AttemptKilled`, and the budget gives the class of the kill
(#5413).

The tests raise a real SIGTERM in the test process only after they see the handler of
`sigterm_raises`, so a defect fails the test and does not end the worker.
"""

from __future__ import annotations

import signal
import threading

import pytest

from devops_cli.core import clock as clock_seam
from devops_cli.exceptions import ServiceStoppingError
from devops_cli.roadmap.attempt_kill import (
    AttemptKill,
    AttemptKilled,
    kill_of,
    sigterm_raises,
)
from devops_cli.roadmap.time_budget import TimeBudget
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS


def test_sigterm_raises_attempt_killed_in_the_main_thread() -> None:
    before = signal.getsignal(signal.SIGTERM)

    with pytest.raises(AttemptKilled) as killed, sigterm_raises():
        assert signal.getsignal(signal.SIGTERM) not in (before, signal.SIG_DFL, None)
        signal.raise_signal(signal.SIGTERM)

    assert (killed.value.kill, killed.value.exit_status) == (None, 143)
    assert signal.getsignal(signal.SIGTERM) == before


def test_a_second_sigterm_meets_the_default_action() -> None:
    """The handler raises once and sets the default back, so a second SIGTERM in the grace period
    ends the process at once."""
    before = signal.getsignal(signal.SIGTERM)

    with pytest.raises(AttemptKilled) as killed, sigterm_raises():
        assert signal.getsignal(signal.SIGTERM) not in (before, signal.SIG_DFL, None)
        try:
            signal.raise_signal(signal.SIGTERM)
        finally:
            assert signal.getsignal(signal.SIGTERM) == signal.SIG_DFL

    assert killed.value.exit_status == 143
    assert signal.getsignal(signal.SIGTERM) == before


def test_sigterm_raises_sets_no_handler_in_another_thread() -> None:
    """Only the main thread can set a handler, and the Service runs the row in a worker thread
    with its own stop, so the context changes nothing there."""
    before = signal.getsignal(signal.SIGTERM)
    seen: list[object] = []

    def worker() -> None:
        with sigterm_raises():
            seen.append(signal.getsignal(signal.SIGTERM))

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(THREAD_HANDOFF_BOUND_SECONDS)

    assert seen == [before]


@pytest.mark.parametrize(
    ("kill", "status"), [(AttemptKill.EVICTED, 75), (AttemptKill.DEADLINE, 143)]
)
def test_the_exit_status_of_each_class(kill: AttemptKill, status: int) -> None:
    assert AttemptKilled(kill).exit_status == status


def test_the_budget_gives_the_class_of_a_kill(monkeypatch: pytest.MonkeyPatch) -> None:
    reading = [0.0]
    monkeypatch.setattr(clock_seam, "monotonic", lambda: reading[0])
    budget = TimeBudget.start(600, "roadmap.fix_plan.time_budget_seconds")

    reading[0] = 599.0
    early = (kill_of(budget, AttemptKilled()), kill_of(budget, ServiceStoppingError("stop")))
    reading[0] = 600.0
    late = (kill_of(budget, AttemptKilled()), kill_of(budget, ServiceStoppingError("stop")))

    assert early == (AttemptKill.EVICTED, AttemptKill.EVICTED)
    assert late == (AttemptKill.DEADLINE, AttemptKill.EVICTED)
