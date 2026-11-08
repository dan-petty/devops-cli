"""The seconds of one step of a roadmap job (#4066).

A job sends one sample of `devops_cli_roadmap_step_seconds` for each call of a step, under four
labels: `repo`, `row`, `step` and `result`. The stage row (#4066) and the implement row (#4067)
share this scheme, so a dashboard groups by `row` and `step` and needs no second metric. The `step`
value is the value of a `StepName` member. The `result` is `ok`, or `error` when an exception
leaves the step or the caller calls `fail()` on the handle: a watch that ends with a failed check
raises nothing, and it is an error all the same. The exception goes on as before: the timer
swallows none.
"""

from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from devops_cli.core import clock
from devops_cli.telemetry.instruments import ROADMAP_STEP_SECONDS, emit

if TYPE_CHECKING:
    from collections.abc import Iterator

    from devops_cli.roadmap.failure import StepName

RESULT_OK: Final = "ok"
RESULT_ERROR: Final = "error"
IMPLEMENT_ROW: Final = "implement"


@dataclass
class StepTimer:
    """The handle of a timed step. A caller that ends a step with a failure and no exception calls
    `fail()`, and the sample gets the result `error`."""

    result: str = RESULT_OK

    def fail(self) -> None:
        self.result = RESULT_ERROR


@contextmanager
def observe_step(repo: str | None, row: str, step: StepName) -> Iterator[StepTimer]:
    """Time the block on the monotonic clock and send the seconds under `repo`, `row`, `step` and
    the result. A caller with no repository, such as the replay of the golden set, sends nothing,
    so a replay adds no `repo` value to the series."""
    started = clock.monotonic()
    timer = StepTimer()
    try:
        yield timer
    except BaseException:
        timer.fail()
        raise
    finally:
        if repo:
            emit(
                ROADMAP_STEP_SECONDS,
                clock.monotonic() - started,
                {"repo": repo, "row": row, "step": step.value, "result": timer.result},
            )


def observe_implement(repo: str | None, step: StepName) -> AbstractContextManager[StepTimer]:
    """`observe_step` for the implement row (#4067): the steps `checks`, `publish` and `watch`."""
    return observe_step(repo, IMPLEMENT_ROW, step)


__all__ = [
    "IMPLEMENT_ROW",
    "RESULT_ERROR",
    "RESULT_OK",
    "StepTimer",
    "observe_implement",
    "observe_step",
]
