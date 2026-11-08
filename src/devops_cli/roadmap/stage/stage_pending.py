"""The intent mark of the stage job (#4051).

The job writes `stage.pending` before it pushes the branch of an item, and the record after the
draft pull request clears it. When the record write fails, or the worker dies between the push and
the record, the mark stays with a pushed branch and no `stage.pr`: an orphan. Only this mark proves
that the job made the branch, so a pushed branch with no mark, which can belong to a person or to
an agent, is never an orphan. A mark younger than `CONST_ROADMAP_STAGE_ORPHAN_AGE_SECONDS` is left
alone, since another run can be in the middle of its publish.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from pydantic import AwareDatetime, BaseModel, ConfigDict

from devops_cli.config.constants import CONST_ROADMAP_STAGE_ORPHAN_AGE_SECONDS
from devops_cli.roadmap.stores.store import GitHubState, Item, StageRecordKey

logger = logging.getLogger(__name__)


class PendingStage(BaseModel):
    """The record `stage.pending`: the branch the job is about to push and the time of the mark."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    branch: str
    time: AwareDatetime

    @property
    def record(self) -> str:
        """The value of `stage.pending`."""
        return self.model_dump_json()


def recorded_pending(item: Item) -> PendingStage | None:
    """The intent mark that the job record of `item` holds, or None when it holds none. A record
    that is no mark is logged and read as none, so it never stops a round."""
    recorded = item.job_record.get(StageRecordKey.PENDING)
    if not recorded:
        return None
    try:
        return PendingStage.model_validate_json(recorded)
    except ValueError:
        logger.warning("The pending stage recorded on #%d is not an intent mark.", item.number)
        return None


def orphan_mark(item: Item, now: datetime) -> PendingStage | None:
    """The mark of `item` when the item can hold an orphan: it is open, its record holds no
    pull request, and the mark is at least as old as the age limit at `now`."""
    if item.state is not GitHubState.OPEN or item.job_record.get(StageRecordKey.PR):
        return None
    pending = recorded_pending(item)
    if pending is None:
        return None
    if now - pending.time < timedelta(seconds=CONST_ROADMAP_STAGE_ORPHAN_AGE_SECONDS):
        return None
    return pending
