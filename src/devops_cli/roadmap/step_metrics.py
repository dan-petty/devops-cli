"""The seconds of one step of a roadmap job (#4066).

A job sends one sample of `devops_cli_roadmap_step_seconds` for each call of a step, under four
labels: `repo`, `row`, `step` and `result`. The stage row (#4066) and the implement row (#4067)
share this scheme, so a dashboard groups by `row` and `step` and needs no second metric. The `step`
value is the value of a `StepName` member. The `result` is `ok`, or `error` when an exception
leaves the step. The exception goes on as before: the timer swallows none.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Final

from devops_cli.core import clock
from devops_cli.telemetry.instruments import ROADMAP_STEP_SECONDS, emit

if TYPE_CHECKING:
    from collections.abc import Iterator

    from devops_cli.roadmap.failure import StepName

RESULT_OK: Final = "ok"
RESULT_ERROR: Final = "error"


@contextmanager
def observe_step(repo: str | None, row: str, step: StepName) -> Iterator[None]:
    """Time the block on the monotonic clock and send the seconds under `repo`, `row`, `step` and
    the result. A caller with no repository, such as the replay of the golden set, sends nothing,
    so a replay adds no `repo` value to the series."""
    started = clock.monotonic()
    result = RESULT_OK
    try:
        yield
    except BaseException:
        result = RESULT_ERROR
        raise
    finally:
        if repo:
            emit(
                ROADMAP_STEP_SECONDS,
                clock.monotonic() - started,
                {"repo": repo, "row": row, "step": step.value, "result": result},
            )


__all__ = ["RESULT_ERROR", "RESULT_OK", "observe_step"]
