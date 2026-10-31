"""The row `stage_ready`: the Service marks a green stage pull request ready (#2865).

The stage job opens a draft pull request for each item, and its plan is complete when it opens it.
A draft stays a draft only while a check runs or fails. A round of this row reads the open items
whose record holds `stage.pr` and not `stage.ready` of the same number, and holds no
`implement.job` (a runner Job works on that pull request and marks it ready itself). It never
reads the draft of a person, and with no such item it sends no request.

For each such item the round reads the pull request. One that is not an open draft is only
recorded in `stage.ready`, so no later round reads it. One that is merged also sets the Status of
its item with the function of `status_sync.py`: the plan is merged (#2920). An open draft goes to
`ready_to_mark` with its check runs. When the function says yes, the round reads the pull request once more. If a
person pushed a commit or marked it ready since the first read, the draft waits, because no check
judged that head. A window of milliseconds stays, since `gh pr ready` takes no expected head.
Else the round marks the pull request ready with `mark_ready`, the function that the implement
job uses, and records `stage.ready`. The check runs are read without the commit statuses: the App
token holds `checks: read` and no `statuses`.

`ready_to_mark` is the one decision. It reads the checks today; #2867 replaces its body with a
judgement of whether the work is complete.

A pull request that fails stops that item only. The round then fails and names each item. That
holds for a 404 too: GitHub answers 404 for a repository the token cannot see, so the answer does
not prove that the pull request is gone, and the row records nothing. Rejected credentials, a rate
limit and the stop of the Service stop the round, since each later read would fail too.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from functools import partial

from devops_cli.exceptions import GitHubRateLimitError
from devops_cli.github.check_verdict import CheckVerdictSummary, read_check_runs
from devops_cli.github.client import PullStatus
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement_pull import mark_ready
from devops_cli.roadmap.stage import StageFailure, raise_for_failed, write_each
from devops_cli.roadmap.status_sync import facts_of, sync_status
from devops_cli.roadmap.store import (
    GitHubState,
    ImplementRecordKey,
    Item,
    RoadmapStore,
    StageRecordKey,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StageDraft:
    """What the decision reads about a recorded draft: the item, the pull request as GitHub
    shows it, and the check runs of its head."""

    item: Item
    pull: PullStatus
    checks: CheckVerdictSummary


def ready_to_mark(draft: StageDraft) -> bool:
    """Whether the recorded draft is marked ready: every check run ended and passed (or was
    skipped). A failed, cancelled, unread or running check, and a head with no check run, keep the
    draft. This is the one seam of the decision (#2867)."""
    return draft.checks.is_passing


class _Outcome(StrEnum):
    MARKED = "marked"
    SETTLED = "settled"
    WAITING = "waiting"


@dataclass(frozen=True)
class StageReadyApplied:
    """What a round did, by issue number: the pull requests it marked ready, the ones it only
    recorded because they were not open drafts, and the drafts that wait for their checks."""

    marked: tuple[int, ...] = ()
    settled: tuple[int, ...] = ()
    waiting: tuple[int, ...] = ()


def _recorded_pull(item: Item) -> int | None:
    """The number of the draft that the round reads for `item`, or None when it reads none: the
    item is closed, holds no `stage.pr`, has `stage.ready` for it, or has a runner Job."""
    if item.state is not GitHubState.OPEN or item.job_record.get(ImplementRecordKey.JOB):
        return None
    recorded = item.job_record.get(StageRecordKey.PR) or ""
    if not recorded.isdigit() or item.job_record.get(StageRecordKey.READY) == recorded:
        return None
    return int(recorded)


def _settle(store: RoadmapStore, repo: str, item: Item, number: int) -> _Outcome:
    """Read pull request `number` of `item` and mark it ready when it is a green draft."""
    client = get_github_session().client
    status = client.get_pull_status(repo, number)
    if not status.is_open_draft:
        store.set_marks(item, {StageRecordKey.READY: str(number)})
        if status.merged:
            sync_status(store, item, facts_of(item, repo=repo, plan_merged=True))
        return _Outcome.SETTLED
    owner, name = repo.split("/", 1)
    checks = read_check_runs(owner, name, status.head_sha)
    if not ready_to_mark(StageDraft(item, status, checks)):
        return _Outcome.WAITING
    again = client.get_pull_status(repo, number)
    if not again.is_open_draft or again.head_sha != status.head_sha:
        return _Outcome.WAITING
    mark_ready(repo, number)
    store.set_marks(item, {StageRecordKey.READY: str(number)})
    return _Outcome.MARKED


def _run_one(
    store: RoadmapStore, repo: str, item: Item, number: int, outcomes: dict[int, _Outcome]
) -> None:
    outcomes[item.number] = _settle(store, repo, item, number)


def mark_stage_ready(store: RoadmapStore, *, repo: str) -> StageReadyApplied:
    """Mark each green stage draft of `repo` ready, as the module says. A pull request that fails
    stops its item only, and the round then fails naming each such item; rejected credentials and
    a rate limit and the stop of the Service stop the round."""
    outcomes: dict[int, _Outcome] = {}
    done: list[int] = []
    failed: list[StageFailure] = []
    writes = [
        (item, partial(_run_one, store, repo, item, number, outcomes))
        for item in store.items()
        if (number := _recorded_pull(item)) is not None
    ]
    write_each(writes, done, failed, also_stop=(GitHubRateLimitError,))
    raise_for_failed(failed, summary=MESSAGES.roadmap.stage_ready_failed)
    applied = StageReadyApplied(
        marked=tuple(n for n, o in outcomes.items() if o is _Outcome.MARKED),
        settled=tuple(n for n, o in outcomes.items() if o is _Outcome.SETTLED),
        waiting=tuple(n for n, o in outcomes.items() if o is _Outcome.WAITING),
    )
    logger.info(
        "The stage_ready row of %s marked %d, settled %d and left %d pull request(s) a draft",
        repo,
        len(applied.marked),
        len(applied.settled),
        len(applied.waiting),
    )
    return applied
