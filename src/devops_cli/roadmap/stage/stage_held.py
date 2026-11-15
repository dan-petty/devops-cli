"""The stage job replaces its own draft plan that fails the plan check (#3387).

The stage job leaves an item out while its branch is on origin, so a draft plan that fails a check
has no way back: a person must edit or close the draft by hand. `may_replace` decides, from the
facts of the one draft pull request of a held item (`DraftRead`), whether the job stages the item
again on the branch of that draft. The plan must fail `check_proposal`, the draft must hold no
unresolved review thread, its branch must end at the commit that `stage.sha` records with commits of
the App alone, it must change no path outside the change folder of the item, and the job must not
have re-staged the plan of the same text (`Restage`, `stage.restage`). Every other draft holds the
item as it did before.

The module holds the rule and the record of one re-stage. It reads no GitHub and runs no git: its
caller gives it the facts, so a test passes them as data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from devops_cli.roadmap.body_hash import body_hashes
from devops_cli.roadmap.plan_check import PlanProblem
from devops_cli.roadmap.stores.store import Item, StageRecordKey

logger = logging.getLogger(__name__)


class Restage(BaseModel):
    """The record `stage.restage`: the draft pull request that the job replaced, and the hash of the
    text of the item that the replaced plan came from. The job re-stages the plan of one text once,
    so a plan that fails the check again holds the item until a person edits its text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pull: int
    text_hash: str

    @property
    def record(self) -> str:
        """The value of `stage.restage`."""
        return self.model_dump_json()


def restage_record(item: Item, pull: int) -> str:
    """The value of `stage.restage` for a re-stage of the draft pull request `pull` of `item`."""
    return Restage(pull=pull, text_hash=body_hashes(item.body)[0]).record


def recorded_restage(item: Item) -> Restage | None:
    """The re-stage that the job record of `item` holds, or None when it holds none. A record that
    is no re-stage is logged and read as none, so it never stops a round."""
    recorded = item.job_record.get(StageRecordKey.RESTAGE)
    if not recorded:
        return None
    try:
        return Restage.model_validate_json(recorded)
    except ValueError:
        logger.warning("The re-stage recorded on #%d is not a re-stage.", item.number)
        return None


def restaged_now(item: Item) -> bool:
    """Whether the job already re-staged the draft plan of the text that `item` holds now. A body
    edit is a new text, and its plan gets the one re-stage that the record bounds."""
    recorded = recorded_restage(item)
    return recorded is not None and recorded.text_hash == body_hashes(item.body)[0]


@dataclass(frozen=True)
class DraftRead:
    """The facts of the one draft pull request of a held item that decide whether the job replaces
    its plan (#3387).

    `pull` is the number of the draft, `draft` whether the pull request is still a draft,
    `at_recorded_commit` whether the tip of its branch is the commit that `stage.sha` records,
    `app_authored` whether each commit of the branch past the default branch has the App as its
    author, `unresolved_threads` the count of its review threads that no person resolved,
    `problems` what the plan check finds in its change files, `outside_paths` the paths that its
    branch changes outside the change folder of the item, and `restaged` whether the job already
    re-staged the plan of the text that the item holds now (`restaged_now`).
    """

    pull: int
    draft: bool
    at_recorded_commit: bool
    app_authored: bool
    unresolved_threads: int
    problems: tuple[PlanProblem, ...]
    outside_paths: tuple[str, ...]
    restaged: bool


def may_replace(read: DraftRead | None) -> bool:
    """Whether the stage job stages the item again on the branch of the draft that `read` gives,
    and updates that draft: the plan fails the plan check, and no other rule holds the item. `read`
    is None when the item has no draft that the job may read, and the job replaces nothing then."""
    if read is None:
        return False
    return (
        read.draft
        and read.at_recorded_commit
        and read.app_authored
        and read.unresolved_threads == 0
        and not read.outside_paths
        and bool(read.problems)
        and not read.restaged
    )
