"""The Status label that the Service sets from the job record of an item (#2920).

An item is Ready while it waits for a plan, Planned once its plan is on the default branch, and In
Progress while a runner Job holds it. `derive_status` is the one function that maps the facts of an
item to that Status. The rows `stage`, `implement` and `stage_ready` all call it, so the label and
the record cannot drift, and a drift is repaired in the next round of any of them. The runner Job
sets In Review when it marks its pull request ready (`implement_run.py`), as `devops pr ready` does
(`pull_status.py`). The function derives Blocked from a stop on record (`implement.stopped`): the stop
path of the runner and of the Job report call it, so one function names the Status of a stop. It
derives no In Review.

**What the Service writes.** `sync_status` writes the derived Status with the family replace of the
store (`set_field`). It writes only an open item that holds Ready or Planned, and only when the
label equals the Status that a job last recorded. A label that a person set, or added next to the
recorded one, has another value than the record, so it stays (ADR 0016). The sweep works from the
cached listing of its round, which may be minutes old. So `sync_status` reads the issue again just
before it writes, and skips an item that changed or closed since the cached read: the next round
decides again. An item that is New, In Progress, In Review or Blocked is never written: a person or
the tools of a pull request set those, and the Service must not turn them back.

**The facts.** The plan is merged when the change folder of the item is on the default branch,
active or archived (`planned.py`), or when its recorded stage pull request is merged. A Job holds
the item while the record holds `implement.job` and no `implement.job_state`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import partial

from devops_cli.config.constants import (
    CONST_ROADMAP_STATUS_BLOCKED,
    CONST_ROADMAP_STATUS_IN_PROGRESS,
    CONST_ROADMAP_STATUS_PLANNED,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.exceptions import GitHubRateLimitError
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.stage import StageFailure, write_each
from devops_cli.roadmap.store import (
    GitHubState,
    ImplementRecordKey,
    Item,
    ItemField,
    RoadmapStore,
)

logger = logging.getLogger(__name__)

# The Statuses that the Service writes from: no other Status is ever replaced.
_WRITTEN_FROM = frozenset({CONST_ROADMAP_STATUS_READY, CONST_ROADMAP_STATUS_PLANNED})


@dataclass(frozen=True)
class StatusFacts:
    """What decides the Status of an item: its plan is on the default branch, a runner Job holds
    it, a stop is on record."""

    plan_merged: bool = False
    job_active: bool = False
    stopped: bool = False


def derive_status(facts: StatusFacts) -> str:
    """The Status of an item with `facts`: In Progress while a Job holds it, else Blocked while a
    stop is on record, else Planned when the plan is merged, else Ready. The one function that rows
    and filters use."""
    if facts.job_active:
        return CONST_ROADMAP_STATUS_IN_PROGRESS
    if facts.stopped:
        return CONST_ROADMAP_STATUS_BLOCKED
    return CONST_ROADMAP_STATUS_PLANNED if facts.plan_merged else CONST_ROADMAP_STATUS_READY


def job_holds(item: Item) -> bool:
    """Whether a runner Job holds the item: the record names a Job that no round reported."""
    record = item.job_record
    return bool(record.get(ImplementRecordKey.JOB)) and not record.get(ImplementRecordKey.JOB_STATE)


def plan_merged(item: Item, planned: PlannedChanges) -> bool:
    """Whether the change folder of `item` is on the default branch, active or archived."""
    return item.number in planned.active or item.number in planned.archived


def owns_status(item: Item) -> bool:
    """Whether the Service may write the Status of `item`: it is open, holds Ready or Planned, and
    its label is the Status that a job last recorded, so no person changed it since."""
    return (
        item.state is GitHubState.OPEN
        and item.status in _WRITTEN_FROM
        and item.job_record.get(ItemField.STATUS) == item.status
    )


def facts_of(item: Item, *, plan_merged: bool) -> StatusFacts:
    """The facts of `item`. `plan_merged` comes from the caller, which knows the default branch or
    the stage pull request. A stop is on record while `implement.stopped` holds a step."""
    return StatusFacts(
        plan_merged=plan_merged,
        job_active=job_holds(item),
        stopped=bool(item.job_record.get(ImplementRecordKey.STOPPED)),
    )


def sync_status(store: RoadmapStore, item: Item, facts: StatusFacts) -> str | None:
    """Write the Status that `facts` give, when the Service owns the Status of `item` and the
    derived Status differs. The issue is read again first: an item that a person or another lane
    changed, or that closed, since `item` was read is left for the next round. The Status written,
    or None when nothing was written."""
    if not owns_status(item):
        return None
    status = derive_status(facts)
    if status == item.status:
        return None
    current = store.item(item.number)
    if current is None or current.status != item.status or not owns_status(current):
        return None
    store.set_field(current, ItemField.STATUS, status)
    return status


@dataclass(frozen=True)
class StatusSynced:
    """What a sweep did: the numbers of the items it wrote, and the items it could not."""

    changed: tuple[int, ...] = ()
    failed: tuple[StageFailure, ...] = ()


def _sync_one(store: RoadmapStore, item: Item, merged: bool, written: dict[int, str]) -> None:
    status = sync_status(store, item, facts_of(item, plan_merged=merged))
    if status is not None:
        written[item.number] = status


def sync_statuses(store: RoadmapStore, *, repo: str, planned: PlannedChanges) -> StatusSynced:
    """Set the Status of each item of `repo` that the Service owns, from the plans on the default
    branch and the record. An item that fails does not stop the others; a rate limit, rejected
    credentials and the stop of the Service stop the sweep. A sweep reads and writes only for an
    item whose Status it changes."""
    written: dict[int, str] = {}
    failed: list[StageFailure] = []
    writes = [
        (item, partial(_sync_one, store, item, plan_merged(item, planned), written))
        for item in store.items()
        if owns_status(item)
    ]
    write_each(writes, [], failed, also_stop=(GitHubRateLimitError,))
    logger.info(
        "The Status sweep of %s wrote %d item(s) and failed for %d", repo, len(written), len(failed)
    )
    return StatusSynced(tuple(written), tuple(failed))


__all__ = [
    "StatusFacts",
    "StatusSynced",
    "derive_status",
    "facts_of",
    "job_holds",
    "owns_status",
    "plan_merged",
    "sync_status",
    "sync_statuses",
]
