"""The Status label of an item, and the one writer that every job uses for it (#2920, #5018).

An item is New while it waits for refine, Ready while it waits for a plan, Planned once its plan is
on the default branch, In Progress while a runner Job, an open pull request or the claim of an agent
works on it, In Review once that pull request is ready for review, and Blocked while a stop is on
record. `derive_status` is the one function that maps the facts of an item to that Status.

**The one writer.** `write_status` derives the Status from the facts that its caller gives, writes
the label with the family replace of the store (`set_field`) only when it differs, and reads the
issue again after the write. A label that another writer changed in between raises
`RoadmapStatusLostError`, so a lost write is never silent. When the label is equal, it writes only
the marks and the body of its caller. The store refuses either write with `RoadmapItemChangedError`
when someone changed the Status since the caller read the item (ADR 0002, #5114). A dry run
returns the would-be write and sends no request. Every job writes the Status through it: the rows `stage`, `stage_ready` and
`implement`, the runner Job (In Progress, In Review and Blocked), the Job report and the clear rules
of a stop, refine, repair, intake, `devops roadmap return`, the claim of
`devops repos worktrees add`, and `devops pr create` and `devops pr ready` (`pull_status.py`). No other module writes a Status label: a structural test holds
that. The writer holds no guard of its own: each caller decides whether the item is its to write.

**What the sweep writes.** `sync_status` writes the derived Status only for an open item that holds
Ready or Planned, and only when the label equals the Status that a job last recorded. A label that a
person set, or added next to the recorded one, has another value than the record, so it stays (ADR
0016). The sweep works from the cached listing of its round, which may be minutes old. So
`sync_status` reads the issue again just before it writes, and skips an item that changed or closed
since the cached read: the next round decides again. An item that is New, In Progress, In Review or
Blocked is never written by the sweep: a person, the runner Job or the tools of a pull request set
those, and the Service must not turn them back.

**The facts.** The plan is merged when the change folder of the item is on the default branch,
active or archived (`planned.py`), or when its recorded stage pull request is merged. A Job holds
the item while the record holds `implement.job` and no `implement.job_state`. A stop is on record
while `implement.stopped` holds a step.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

from devops_cli.config.constants import (
    CONST_ROADMAP_STATUS_BLOCKED,
    CONST_ROADMAP_STATUS_IN_PROGRESS,
    CONST_ROADMAP_STATUS_IN_REVIEW,
    CONST_ROADMAP_STATUS_NEW,
    CONST_ROADMAP_STATUS_PLANNED,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.exceptions import GitHubRateLimitError
from devops_cli.exceptions.roadmap import RoadmapStatusLostError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stores.store import (
    GitHubState,
    ImplementRecordKey,
    Item,
    ItemField,
    RoadmapStore,
    item_of,
)

if TYPE_CHECKING:
    from devops_cli.roadmap.planned import PlannedChanges
    from devops_cli.roadmap.stage.stage import StageFailure

logger = logging.getLogger(__name__)

# The Statuses that the Service writes from: no other Status is ever replaced.
_WRITTEN_FROM = frozenset({CONST_ROADMAP_STATUS_READY, CONST_ROADMAP_STATUS_PLANNED})


@dataclass(frozen=True)
class StatusFacts:
    """What decides the Status of an item: it waits for refine (`needs_refine`: intake filed it,
    or a job returned it), a pull request that delivers it is ready for review (`pull_ready`) or
    open (`pull_open`), an agent claimed it for a worktree (`agent_claimed`, #4685), a runner Job
    holds it, a stop is on record, its plan is on the default branch."""

    plan_merged: bool = False
    job_active: bool = False
    stopped: bool = False
    pull_open: bool = False
    pull_ready: bool = False
    needs_refine: bool = False
    agent_claimed: bool = False


def derive_status(facts: StatusFacts) -> str:
    """The Status of an item with `facts`: New while it waits for refine, else In Review while its
    pull request is ready for review, else In Progress while a Job holds it, its pull request is
    open or an agent claimed it, else Blocked while a stop is on record, else Planned when the plan is merged, else Ready.
    The one function that rows and filters use."""
    if facts.needs_refine:
        return CONST_ROADMAP_STATUS_NEW
    if facts.pull_ready:
        return CONST_ROADMAP_STATUS_IN_REVIEW
    if facts.job_active or facts.pull_open or facts.agent_claimed:
        return CONST_ROADMAP_STATUS_IN_PROGRESS
    if facts.stopped:
        return CONST_ROADMAP_STATUS_BLOCKED
    return CONST_ROADMAP_STATUS_PLANNED if facts.plan_merged else CONST_ROADMAP_STATUS_READY


@dataclass(frozen=True)
class StatusWrite:
    """What `write_status` did to item `number`, or in a dry run would do: the Status label that
    the item held (`before`) and the derived Status."""

    number: int
    before: str | None
    status: str
    dry_run: bool = False

    @property
    def changes(self) -> bool:
        """Whether the label differs from the derived Status, so a run writes it."""
        return self.before != self.status

    @property
    def written(self) -> bool:
        """Whether the label write was sent: it differs, and this is no dry run."""
        return self.changes and not self.dry_run


def write_status(
    store: RoadmapStore,
    item: Item,
    facts: StatusFacts,
    *,
    dry_run: bool = False,
    marks: Mapping[Any, str | int | None] | None = None,
    body: str | None = None,
) -> StatusWrite:
    """Write the Status that `facts` give on `item`, the one writer of a Status label. The label
    is written only when it differs from the Status that `item` holds, with `marks` and `body` in
    the same write; the issue is then read again, and a label that is not the written Status
    raises `RoadmapStatusLostError`. When the label is equal, `marks` and `body` are written
    alone, with no read after the write. Both writes raise `RoadmapItemChangedError` and write
    nothing when someone changed the Status since `item` was read: the caller decided on that
    read (ADR 0002, #5114). A dry run sends no request and returns the would-be write."""
    done = StatusWrite(item.number, item.status, derive_status(facts), dry_run=dry_run)
    if dry_run:
        return done
    if done.changes:
        store.set_field(item, ItemField.STATUS, done.status, marks=marks, body=body)
        _read_back(store, done)
    elif marks or body is not None:
        store.set_marks(item, marks or {}, body=body, unchanged=ItemField.STATUS)
    return done


def _read_back(store: RoadmapStore, done: StatusWrite) -> None:
    """Read the issue of `done` again, and raise when its label is not the written Status. The
    read is of the issue, not of the Item: intake writes New before the Priority that makes the
    issue an Item."""
    back = store.issue(done.number)
    found = item_of(back).status if back is not None else None
    if found == done.status:
        return
    texts = MESSAGES.roadmap
    raise RoadmapStatusLostError(
        texts.status_write_lost.format(
            number=done.number, status=done.status, found=found or texts.status_write_lost_none
        ),
        details={"number": done.number, "status": done.status, "found": found},
    )


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
    return write_status(store, current, facts).status


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
    # `stage.py` imports this module for its Status writes, so the loop of its writes is imported
    # only when a sweep runs: an import at the top would make a cycle.
    from devops_cli.roadmap.stage.stage import write_each

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
    "StatusWrite",
    "derive_status",
    "facts_of",
    "job_holds",
    "owns_status",
    "plan_merged",
    "sync_status",
    "sync_statuses",
    "write_status",
]
