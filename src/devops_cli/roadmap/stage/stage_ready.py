"""The row `stage_ready`: the Service marks a green stage pull request ready (#2865).

The stage job opens a draft pull request for each item, and its plan is complete when it opens it.
A draft stays a draft only while a check runs or fails. A round of this row reads the open items
whose record holds `stage.pr` and not `stage.ready` of the same number, and holds no
`implement.job` (a runner Job works on that pull request). It never
reads the draft of a person, and with no such item it sends no request.

For each such item the round reads the pull request. One that is not an open draft is only
recorded in `stage.ready`, so no later round reads it. One that is merged also sets the Status of
its item with the function of `status_sync.py`: the plan is merged (#2920). An open draft goes to
`draft_readiness` with its check runs. A green draft that holds the label `verdict/fix-plan` stays a
draft, and the round comments that the label is the reason once and records `stage.needs_fix`
(#3264). When the function says yes and the label is absent, the round reads the pull request once
more. If a person pushed a commit or marked it ready since the first read, the draft waits, because
no check judged that head. A window of milliseconds stays, since `gh pr ready` takes no expected
head. Else the round marks the pull request ready with `mark_ready`, the function that the ready
path of the step `fix-checks` uses for a delivery draft, and records `stage.ready`. The check runs are read without the commit statuses: the App
token holds `checks: read` and no `statuses`.

`draft_readiness` is the one decision. It reads the checks today; #2867 replaces its body with a
judgement of whether the work is complete.

With the setting `roadmap.stage.jev_completeness` on, a green draft without the label also goes to
the Jev completeness check (#4308). It asks TypeSafe Jev whether the plan delivers each acceptance
criterion of the issue. Jev reads the diff of the head commit since its merge base with the base
branch, from the compare endpoint. The diff of the pulls endpoint is not used: GitHub can keep a
stale `base.sha` after the merge base moved, and then that diff holds files of other changes
(#5388). A criterion in doubt, a weak test score or an error of Jev keeps the draft
a draft. The round posts one note and records `stage.jev` with the head commit, so it asks again
only for a new head commit, or after an error. The check only holds: a pass leaves the decision to
the checks above, and the check never marks a draft ready, merges or closes.

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

from devops_cli.config.constants import CONST_ROADMAP_STAGE_COMMENT_MARKER
from devops_cli.config.settings import load_settings
from devops_cli.exceptions import GitHubRateLimitError
from devops_cli.github.check_verdict import read_check_runs
from devops_cli.github.client import GitHubClient, PullStatus
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement.implement_pull import (
    Answer,
    ChangeFacts,
    Draft,
    draft_readiness,
    kind_of,
)
from devops_cli.roadmap.jev_completeness import (
    CompletenessOutcome,
    check_completeness,
    completeness_note,
)
from devops_cli.roadmap.stage.stage import StageFailure, raise_for_failed, write_each
from devops_cli.roadmap.stage.stage_criteria import acceptance_criteria
from devops_cli.roadmap.stage.stage_verify import FIX_PLAN_LABEL
from devops_cli.roadmap.status_sync import facts_of, job_holds, sync_status
from devops_cli.roadmap.steps.comment import Target, post
from devops_cli.roadmap.steps.ready import mark_ready
from devops_cli.roadmap.stores.store import (
    GitHubState,
    Item,
    RoadmapStore,
    StageRecordKey,
)

logger = logging.getLogger(__name__)


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
    if item.state is not GitHubState.OPEN or job_holds(item):
        return None
    recorded = item.job_record.get(StageRecordKey.PR) or ""
    if not recorded.isdigit() or item.job_record.get(StageRecordKey.READY) == recorded:
        return None
    return int(recorded)


def _jev_holds(store: RoadmapStore, repo: str, item: Item, number: int, status: PullStatus) -> bool:
    """Whether the Jev completeness check keeps draft `number` a draft (#4308). It asks Jev when
    the setting is on and the record holds no `held` mark for the head. A hold posts one note and
    records the head; an error posts its note once for the head and asks again in the next round.
    The diff is the compare of the base branch and the head commit (#5388)."""
    if not load_settings().roadmap.stage.jev_completeness:
        return False
    head = status.head_sha
    mark = item.job_record.get(StageRecordKey.JEV) or ""
    if mark == f"{head}:{CompletenessOutcome.HELD}":
        return True
    client = get_github_session().client
    diff = client.get_compare_diff(repo, status.base_ref, head)
    result = check_completeness(acceptance_criteria(item.body), diff, "plan")
    if not result.holds:
        if mark:
            store.set_marks(item, {StageRecordKey.JEV: None})
        return False
    error_mark = f"{head}:{CompletenessOutcome.ERROR}"
    if not (result.outcome is CompletenessOutcome.ERROR and mark == error_mark):
        post(
            Target(repo, number, client=client),
            CONST_ROADMAP_STAGE_COMMENT_MARKER,
            f"jev-{head}",
            completeness_note(result, number),
        )
    store.set_marks(item, {StageRecordKey.JEV: f"{head}:{result.outcome}"})
    return True


def _read_plan_change(
    client: GitHubClient, repo: str, status: PullStatus, item: Item
) -> ChangeFacts | None:
    """The change folder of the plan at the head commit: its tasks.md, which a plan adds and
    never archives, or None when there is none (#3584)."""
    branch = item.job_record.get(StageRecordKey.BRANCH) or status.head_ref
    change = branch.partition("/")[2] if branch else ""
    if not change:
        return None
    tasks_text = client.get_file_at(repo, f"openspec/changes/{change}/tasks.md", status.head_sha)
    if tasks_text is None:
        return None
    return ChangeFacts(archived=False, tasks_text=tasks_text, archive_required=False)


def _settle(store: RoadmapStore, repo: str, item: Item, number: int) -> _Outcome:
    """Read pull request `number` of `item` and mark it ready when it is a green draft."""
    client = get_github_session().client
    status = client.get_pull_status(repo, number)
    if not status.is_open_draft:
        store.set_marks(item, {StageRecordKey.READY: str(number)})
        if status.merged:
            sync_status(store, item, facts_of(item, plan_merged=True))
        return _Outcome.SETTLED
    owner, name = repo.split("/", 1)
    checks = read_check_runs(owner, name, status.head_sha)
    change = _read_plan_change(client, repo, status, item)
    draft = Draft(kind_of(item, number, status.title), status, item, checks, change=change)
    readiness = draft_readiness(draft)
    if readiness.answer is not Answer.READY:
        return _Outcome.WAITING
    if FIX_PLAN_LABEL in status.labels:
        if item.job_record.get(StageRecordKey.NEEDS_FIX) != str(number):
            post(
                Target(repo, number, client=client),
                CONST_ROADMAP_STAGE_COMMENT_MARKER,
                f"needs-fix-{number}",
                MESSAGES.roadmap.stage_ready_needs_fix.format(pull=number),
            )
            store.set_marks(item, {StageRecordKey.NEEDS_FIX: str(number)})
        return _Outcome.WAITING
    if item.job_record.get(StageRecordKey.NEEDS_FIX):
        store.set_marks(item, {StageRecordKey.NEEDS_FIX: None})
    if _jev_holds(store, repo, item, number, status):
        return _Outcome.WAITING
    again = client.get_pull_status(repo, number)
    if not again.is_open_draft or again.head_sha != status.head_sha:
        return _Outcome.WAITING
    mark_ready(repo, number, expected_head=status.head_sha, draft=draft)
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
