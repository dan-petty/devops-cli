"""The kill of a roadmap attempt, and its class (#5413).

Kubernetes ends the pod of a Job in the same way for an eviction, a node drain and the deadline of
the Job (`activeDeadlineSeconds`): SIGTERM, then SIGKILL after the grace period of the pod, 30 s
by default. With no handler, Python ends the process at SIGTERM, so the attempt keeps its marks
and gets no result. While `sigterm_raises` lasts, the first SIGTERM raises `AttemptKilled` in the
main thread instead, and the step writes the class of the kill in the grace period. The handler
sets the default action back before it raises, so a second SIGTERM ends the process at once.

`AttemptKilled` is a `BaseException`, as `KeyboardInterrupt` is, so no `except Exception` of a
model client, a retry or a tool catches it. pydantic-ai runs an agent with
`pydantic_graph._utils.run_until_complete`, which cancels its task, runs the cleanup and raises the
exception again.

The pod of a Job mounts no service account token, so the step cannot read the condition
`DisruptionTarget` of its pod. The time budget of the step gives the class (`kill_of`): the budget
is below the deadline of the Job, so the Job controller sends SIGTERM only after the budget is
spent.

- `deadline`: SIGTERM after the budget is spent. The attempt spent its tokens, so it counts.
- `evicted`: SIGTERM before that, from an eviction, a node drain, a rollout or a person who deletes
  the Job, and a stop of the Service (`ServiceStoppingError`) while an attempt runs. The cause is
  outside the job.

The exit status of a command that a kill ended is 75 (`EX_TEMPFAIL` of sysexits.h) for `evicted`,
so a retry policy of a Job can run the unit again, and 143 (128 + SIGTERM) for `deadline` and for a
kill outside an attempt. The failure classifier reads 143 as `timeout`.
"""

from __future__ import annotations

import signal
import threading
from contextlib import contextmanager
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from devops_cli.exceptions import ServiceStoppingError

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from types import FrameType

    from devops_cli.roadmap.time_budget import TimeBudget


class AttemptKill(StrEnum):
    """The class of a kill that ended an attempt, as the module says."""

    EVICTED = "evicted"
    DEADLINE = "deadline"


# 128 + SIGTERM: the status of a process that SIGTERM ends. 75 is `EX_TEMPFAIL` of sysexits.h.
_SIGTERM_EXIT_STATUS: Final[int] = 128 + signal.SIGTERM
_KILL_EXIT_STATUS: Final[Mapping[AttemptKill, int]] = MappingProxyType(
    {AttemptKill.EVICTED: 75, AttemptKill.DEADLINE: _SIGTERM_EXIT_STATUS}
)


class AttemptKilled(BaseException):
    """SIGTERM ended the work while `sigterm_raises` lasted. `kill` is the class that the step
    gave the kill, or None for a kill outside an attempt."""

    def __init__(self, kill: AttemptKill | None = None) -> None:
        super().__init__(kill.value if kill is not None else "SIGTERM")
        self.kill = kill

    @property
    def exit_status(self) -> int:
        """The exit status of the command that the kill ended."""
        return _KILL_EXIT_STATUS[self.kill] if self.kill is not None else _SIGTERM_EXIT_STATUS


def _raise_killed(_signum: int, _frame: FrameType | None) -> None:
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    raise AttemptKilled


@contextmanager
def sigterm_raises() -> Iterator[None]:
    """While the block runs, the first SIGTERM raises `AttemptKilled` in the main thread, and the
    handler before the block comes back after it. In another thread the block runs with no
    handler: only the main thread can set one, and the Service has its own stop."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = signal.signal(signal.SIGTERM, _raise_killed)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous if previous is not None else signal.SIG_DFL)


def kill_of(budget: TimeBudget, error: AttemptKilled | ServiceStoppingError) -> AttemptKill:
    """The class of the kill `error` of an attempt with the time budget `budget`: a stop of the
    Service is `evicted`, and SIGTERM is `deadline` once the budget is spent, else `evicted`."""
    if isinstance(error, ServiceStoppingError) or not budget.spent():
        return AttemptKill.EVICTED
    return AttemptKill.DEADLINE


__all__ = ["AttemptKill", "AttemptKilled", "kill_of", "sigterm_raises"]
