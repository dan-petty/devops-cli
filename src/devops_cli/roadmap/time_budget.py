"""The time budget of a roadmap step (#5363).

A step that a Job runs must end before the deadline of the Job, with a margin, so that it writes
its result line and its comment: when the deadline comes first, Kubernetes stops the pod and the
attempt leaves nothing. `TimeBudget` holds the seconds of a setting and the clock reading of the
start. The step calls `raise_if_spent` at its safe points, before each model call, and the error
`RoadmapTimeBudgetError` names the setting, its value and the work that does not start. A call that
is running when the budget ends goes on, so the margin must hold one more call.
"""

from __future__ import annotations

from dataclasses import dataclass

from devops_cli.core import clock
from devops_cli.exceptions import RoadmapTimeBudgetError
from devops_cli.lang import MESSAGES


@dataclass(frozen=True)
class TimeBudget:
    """The `seconds` that the setting `setting` gives a step, from the clock reading `started`."""

    seconds: int
    setting: str
    started: float

    @classmethod
    def start(cls, seconds: int, setting: str) -> TimeBudget:
        """A budget of `seconds` that starts now."""
        return cls(seconds, setting, clock.monotonic())

    def elapsed(self) -> float:
        """The seconds since the start."""
        return clock.monotonic() - self.started

    def spent(self) -> bool:
        """Whether the budget is spent."""
        return self.elapsed() >= self.seconds

    def raise_if_spent(self, work: str) -> None:
        """Raise `RoadmapTimeBudgetError` once the budget is spent, so `work` does not start."""
        if self.spent():
            raise RoadmapTimeBudgetError(
                MESSAGES.roadmap.time_budget_spent.format(
                    seconds=self.seconds, setting=self.setting, work=work
                )
            )


__all__ = ["TimeBudget"]
