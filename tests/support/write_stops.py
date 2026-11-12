"""Stop a roadmap job after each of its GitHub writes and run it again (ADR 0021, #4793).

A release or a ConfigMap edit stops the Service between two writes of a job, and the next round
runs the job again on what the stopped run left. `stop_after_each_write` runs the job once on a
copy of the store to count its writes. Then, for each write, it runs the job on a fresh copy that
stops right after that write, with the error of a stopping Service (`stop_error`), and runs the
job again on that copy. A job is safe to run two times when no stop leaves a comment that the
whole run does not leave: `StopReplay.extra_comments` is empty for each stop.
"""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from devops_cli.exceptions import RoadmapRunError
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.service_stop import stop_error


@dataclass(frozen=True)
class StoppedRun:
    """A run of a job that stopped after its `at`-th write, and the run after it: the writes of
    each, and the comments that the store holds at the end."""

    at: int
    stopped: tuple[str, ...]
    again: tuple[str, ...]
    comments: Counter[str]


@dataclass(frozen=True)
class StopReplay:
    """The writes and the comments of a whole run, and the run of the job for each stop."""

    whole: tuple[str, ...]
    comments: Counter[str]
    runs: tuple[StoppedRun, ...]

    def extra_comments(self) -> list[tuple[int, list[str]]]:
        """Each stop that left a comment that the whole run does not leave, with the comments."""
        extra = ((run.at, sorted((run.comments - self.comments).elements())) for run in self.runs)
        return [(at, bodies) for at, bodies in extra if bodies]


def _comments(store: InMemoryRoadmapStore) -> Counter[str]:
    return Counter(comment.body for comment in store.comments_since(None))


def _run_to_the_stop(
    store: InMemoryRoadmapStore, job: Callable[[InMemoryRoadmapStore], object]
) -> None:
    """Run `job` until the stop: the job either ends the run with the stop error or records the
    stop and returns, as a row of the Service does."""
    stopping = stop_error().error_code
    try:
        job(store)
    except RoadmapRunError as error:
        if error.error_code != stopping:
            raise


def stop_after_each_write(
    store: InMemoryRoadmapStore, job: Callable[[InMemoryRoadmapStore], object]
) -> StopReplay:
    """Run `job` on copies of `store`: one whole run, then one run for each of its writes that
    stops after that write, and the run after the stop. `store` itself stays as it is."""
    seeded = len(store.writes)
    whole = copy.deepcopy(store)
    job(whole)
    runs = []
    for at in range(1, len(whole.writes) - seeded + 1):
        stopped = copy.deepcopy(store)
        stopped.fail_write(at=at, applied=True, error=stop_error())
        _run_to_the_stop(stopped, job)
        first = len(stopped.writes)
        job(stopped)
        runs.append(
            StoppedRun(
                at,
                tuple(stopped.writes[seeded:first]),
                tuple(stopped.writes[first:]),
                _comments(stopped),
            )
        )
    return StopReplay(tuple(whole.writes[seeded:]), _comments(whole), tuple(runs))
