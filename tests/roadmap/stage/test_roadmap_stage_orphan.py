"""`devops roadmap stage`: the orphan draft that a failed marks write leaves (#4051).

The job writes the intent mark `stage.pending` (the branch name and the time) before the push. A
round removes the draft and the branch of an open item that has the mark and no `stage.pr`, when
the mark is at least one hour old and only the identity of the clone wrote to the branch. A pushed
branch with no mark belongs to a person or to an agent: the job never touches it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.request_plan import StoreRequests, stage_requests
from devops_cli.roadmap.stage import stage as stage_module
from devops_cli.roadmap.stage.stage import StagePlan, parse_filters, plan_stage
from devops_cli.roadmap.stores.store import CloseReason, ItemField, StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import API, github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_NAME,
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    apply_stage,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=2)
BRANCH = "fix/1-the-job-drops-a-comment"
OTHER_BRANCH = "fix/2-the-job-loses-a-label"
PULLS = f"/repos/{STAGE_REPO}/pulls"
OPENED = github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201)
MARK_AGE = timedelta(hours=1)


class Killed(BaseException):
    """The death of the worker: no handler of the job catches it."""


def _mark(branch: str, time: datetime) -> str:
    """The value of `stage.pending`: the branch name and the time, as JSON."""
    return json.dumps({"branch": branch, "time": time.isoformat()})


def _pushed(repo: StageRepo) -> list[str]:
    return repo.origin_git("branch", "--format=%(refname:short)").split()


def _record(store: InMemoryRoadmapStore, number: int = 1) -> dict[str, str | None]:
    item = store.item(number)
    assert item is not None
    return {
        key.value: value
        for key, value in item.job_record.items()
        if "." in key.value and value is not None
    }


def _closing(api: GitHubApiFake, pull: int) -> str:
    """Answer the close of draft `pull` and return the request line that makes it."""
    api.route("PATCH", f"{PULLS}/{pull}", github_json({"number": pull}))
    return f"PATCH {API}{PULLS}/{pull}"


def _orphan(
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    api: GitHubApiFake,
    *,
    title: str = "fix(roadmap): the job drops a comment",
    branch: str = BRANCH,
    marked: datetime = NOW - timedelta(hours=3),
    author: str = STAGE_NAME,
    pushed: bool = True,
    drafted: bool = True,
    recorded_pull: str | None = None,
) -> tuple[int, str]:
    """An open Ready item with the intent mark, the pushed branch and its draft. It has no
    `type/bug` label, so a round with the filter `type=bug` selects no item and only the pass over
    the orphans runs. Returns the item number and the request line that closes its draft."""
    number = store.seed_issue(
        title, fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"}
    )
    item = store.item(number)
    assert item is not None
    marks = {StageRecordKey.PENDING: _mark(branch, marked)}
    if recorded_pull is not None:
        marks[StageRecordKey.PR] = recorded_pull
    store.set_marks(item, marks)
    if pushed:
        repo.push_branch(branch, author=author)
    close = ""
    if drafted:
        pull = store.seed_pull(f"plan {number}", head_ref=branch, draft=True)
        close = _closing(api, pull)
    return number, close


def _plan(store: InMemoryRoadmapStore, repo: StageRepo, *, now: datetime = LATER) -> StagePlan:
    return plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(("status=ready", "type=bug")),
        item_number=None,
        now=now,
    )


def _round(
    store: InMemoryRoadmapStore, repo: StageRepo, *, now: datetime = LATER
) -> tuple[StagePlan, tuple[int, ...], MagicMock]:
    """One round that selects no item: its plan, the numbers it removed, and the spy on the read
    of the open pull requests (the calls of the plan and of the writes)."""
    with patch.object(store, "open_pulls", wraps=store.open_pulls) as reads:
        plan = _plan(store, repo, now=now)
        applied = apply_stage(store, plan, source=repo.clone, now=now)
    return plan, applied.removed, reads


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def staging(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, openspec_fake: OpenSpecFake
) -> InMemoryRoadmapStore:
    """A store with one Ready bug that a round stages, and the answers of GitHub and OpenSpec."""
    seed_stageable(store)
    store.seed_file(".github/labels.yml", '- name: "type/docs"\n  color: "0075ca"\n')
    github_api.route("POST", PULLS, OPENED)
    openspec_fake.script_sequence(validate_args("1-the-job-drops-a-comment"), (0, VALID_REPORT))
    return store


def _stage_round(
    store: InMemoryRoadmapStore, repo: StageRepo, *, now: datetime
) -> tuple[StagePlan, tuple[int, ...], tuple[int, ...]]:
    """One round with the default filter: the plan, the items it staged and the items it removed."""
    plan = plan_stage(store, repo=STAGE_REPO, source=repo.clone, filters=parse_filters(()), now=now)
    applied = apply_stage(store, plan, source=repo.clone, now=now)
    return plan, applied.staged, applied.removed


def test_a_round_after_the_marks_write_fails_removes_the_orphan_and_plans_the_item_again(
    staging: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    model_fake.answer(make_stage_proposal())
    # The first write of marks is the intent mark, the second one is the record after the draft.
    staging.fail_write(write="set_marks", at=2)

    _, staged, _ = _stage_round(staging, stage_repo, now=NOW)

    assert staged == ()
    assert github_api.requested == [f"POST {API}{PULLS}"]
    assert _pushed(stage_repo) == [BRANCH, "main"]
    record = _record(staging)
    assert StageRecordKey.PR.value not in record
    mark = json.loads(record[StageRecordKey.PENDING.value] or "")
    assert (mark["branch"], datetime.fromisoformat(mark["time"])) == (BRANCH, NOW)

    pull = staging.seed_pull("plan 1", head_ref=BRANCH, draft=True)
    closing = _closing(github_api, pull)
    github_api.requested.clear()

    plan, staged, removed = _stage_round(staging, stage_repo, now=LATER)

    assert [(r.number, r.branch, r.gone) for r in plan.removals] == [(1, BRANCH, False)]
    assert (staged, removed) == ((), (1,))
    assert github_api.requested == [closing]
    assert json.loads(github_api.sent[-1].content) == {"state": "closed"}
    assert _pushed(stage_repo) == ["main"]
    assert _record(staging) == {}

    github_api.requested.clear()

    _, staged, removed = _stage_round(staging, stage_repo, now=LATER)

    assert (staged, removed) == ((1,), ())
    assert github_api.requested == [f"POST {API}{PULLS}"]
    assert _pushed(stage_repo) == [BRANCH, "main"]
    record = _record(staging)
    assert (record["stage.branch"], record["stage.pr"]) == (BRANCH, "5")
    assert StageRecordKey.PENDING.value not in record


def test_a_worker_killed_after_the_push_leaves_a_branch_that_the_next_round_deletes_killed_after_push(
    staging: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_fake.answer(make_stage_proposal())

    def killed(*_: object) -> None:
        raise Killed

    monkeypatch.setattr(stage_module, "_open_pull", killed)
    plan = plan_stage(
        staging, repo=STAGE_REPO, source=stage_repo.clone, filters=parse_filters(()), now=NOW
    )
    with pytest.raises(Killed) as death:
        apply_stage(staging, plan, source=stage_repo.clone, now=NOW)
    assert death.type is Killed
    monkeypatch.undo()

    assert _pushed(stage_repo) == [BRANCH, "main"]
    assert github_api.requested == []
    record = _record(staging)
    assert json.loads(record[StageRecordKey.PENDING.value] or "")["branch"] == BRANCH
    assert StageRecordKey.PR.value not in record

    plan, _, removed = _stage_round(staging, stage_repo, now=LATER)

    assert [(r.number, r.branch, r.gone) for r in plan.removals] == [(1, BRANCH, False)]
    assert removed == (1,)
    assert github_api.requested == []
    assert _pushed(stage_repo) == ["main"]
    assert _record(staging) == {}


def test_a_retitle_between_the_failure_and_the_next_round_leaves_the_orphan_found_by_its_mark(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, closing = _orphan(store, stage_repo, github_api)
    store.set_title(number, "fix(roadmap): the job loses a label")

    plan, removed, _ = _round(store, stage_repo)

    assert [(r.number, r.branch) for r in plan.removals] == [(1, BRANCH)]
    assert removed == (1,)
    assert github_api.requested == [closing]
    assert _pushed(stage_repo) == ["main"]
    assert _record(store) == {}


def test_a_branch_with_a_foreign_commit_is_kept_and_reported(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    _orphan(store, stage_repo, github_api)
    stage_repo.push_branch(BRANCH, author="Person")

    plan, removed, reads = _round(store, stage_repo)

    assert plan.removals == ()
    assert [(k.number, k.branch) for k in plan.kept] == [(1, BRANCH)]
    assert "commit(s) by another author" in plan.kept[0].reason
    assert removed == ()
    assert BRANCH in _pushed(stage_repo)
    assert github_api.requested == []
    assert reads.call_count == 0
    assert StageRecordKey.PENDING.value in _record(store)


def test_the_orphan_of_the_job_goes_and_the_other_branch_of_an_agent_is_kept_other_branch_kept(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    _, closing = _orphan(store, stage_repo, github_api)
    agent = store.seed_issue(
        "fix(roadmap): the job loses a label",
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    stage_repo.push_branch(OTHER_BRANCH, author="Agent")
    agent_pull = store.seed_pull("agent work", head_ref=OTHER_BRANCH, draft=True)
    _closing(github_api, agent_pull)

    plan, removed, _ = _round(store, stage_repo)

    assert [(r.number, r.branch) for r in plan.removals] == [(1, BRANCH)]
    assert (plan.kept, removed) == ((), (1,))
    assert github_api.requested == [closing]
    assert _pushed(stage_repo) == [OTHER_BRANCH, "main"]
    assert _record(store, agent) == {}


@pytest.mark.parametrize(
    "age", [timedelta(minutes=-5), timedelta(0), MARK_AGE - timedelta(seconds=1)]
)
def test_a_mark_younger_than_the_age_limit_is_left_alone_and_costs_no_request(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake, age: timedelta
) -> None:
    _orphan(store, stage_repo, github_api, marked=LATER - age)

    plan, removed, reads = _round(store, stage_repo)

    assert (plan.removals, plan.kept, removed) == ((), (), ())
    assert github_api.requested == []
    assert reads.call_count == 0
    assert BRANCH in _pushed(stage_repo)
    assert StageRecordKey.PENDING.value in _record(store)


def test_a_young_mark_is_left_alone_until_it_reaches_the_age_limit_young_mark(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    _, closing = _orphan(store, stage_repo, github_api, marked=NOW)

    plan, removed, _ = _round(store, stage_repo, now=NOW + MARK_AGE - timedelta(seconds=1))

    assert (plan.removals, plan.kept, removed) == ((), (), ())
    assert github_api.requested == []
    assert BRANCH in _pushed(stage_repo)

    plan, removed, _ = _round(store, stage_repo, now=NOW + MARK_AGE)

    assert [r.number for r in plan.removals] == [1]
    assert removed == (1,)
    assert github_api.requested == [closing]
    assert _pushed(stage_repo) == ["main"]


def test_a_mark_of_exactly_the_age_limit_is_judged(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    _, closing = _orphan(store, stage_repo, github_api, marked=LATER - MARK_AGE)

    plan, removed, _ = _round(store, stage_repo)

    assert [r.number for r in plan.removals] == [1]
    assert removed == (1,)
    assert github_api.requested == [closing]


def test_an_orphan_whose_branch_is_gone_loses_its_record_and_costs_no_request(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    _orphan(store, stage_repo, github_api, pushed=False, drafted=False)

    plan, removed, reads = _round(store, stage_repo)

    assert [(r.number, r.gone) for r in plan.removals] == [(1, True)]
    assert removed == (1,)
    assert github_api.requested == []
    assert reads.call_count == 0
    assert _record(store) == {}


def test_an_item_with_a_recorded_pull_request_is_no_orphan(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    _orphan(store, stage_repo, github_api, recorded_pull="9")
    github_api.route(
        "GET",
        f"{PULLS}/9",
        github_json({"state": "open", "draft": True, "merged": False}),
    )

    plan, removed, reads = _round(store, stage_repo)

    assert (plan.removals, plan.kept, removed) == ((), (), ())
    assert github_api.requested == [f"GET {API}{PULLS}/9"]
    assert reads.call_count == 0
    assert BRANCH in _pushed(stage_repo)


def test_a_closed_item_with_the_mark_is_not_an_orphan(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, _ = _orphan(store, stage_repo, github_api)
    store.close_by_hand(number, CloseReason.COMPLETED)

    plan, removed, _ = _round(store, stage_repo)

    assert (plan.removals, plan.kept, removed) == ((), (), ())
    assert BRANCH in _pushed(stage_repo)


def test_a_staged_item_costs_one_more_write_of_marks_for_the_intent_request_count(
    staging: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    model_fake.answer(make_stage_proposal())

    with patch.object(staging, "open_pulls", wraps=staging.open_pulls) as reads:
        _, staged, _ = _stage_round(staging, stage_repo, now=NOW)

    assert staged == (1,)
    assert staging.writes.count("set_marks") == 2
    assert StageRecordKey.PENDING.value not in _record(staging)
    assert reads.call_count == 0


def test_a_round_with_two_orphans_reads_the_open_pull_requests_once_request_count(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    _, first = _orphan(store, stage_repo, github_api)
    _, second = _orphan(
        store,
        stage_repo,
        github_api,
        title="fix(roadmap): the job loses a label",
        branch=OTHER_BRANCH,
    )

    plan, removed, reads = _round(store, stage_repo)

    assert [r.number for r in plan.removals] == [1, 2]
    assert removed == (1, 2)
    assert reads.call_count == 1
    assert github_api.requested == [first, second]


def test_a_round_with_an_orphan_and_no_draft_still_reads_the_open_pull_requests_once_request_count(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    _orphan(store, stage_repo, github_api, drafted=False)

    _, removed, reads = _round(store, stage_repo)

    assert removed == (1,)
    assert reads.call_count == 1
    assert github_api.requested == []


def test_a_round_without_an_orphan_reads_no_open_pull_requests_request_count(
    store: InMemoryRoadmapStore, stage_repo: StageRepo
) -> None:
    store.seed_issue("fix(roadmap): the job drops a comment")
    stage_repo.push_branch(BRANCH, author="Person")

    plan, removed, reads = _round(store, stage_repo)

    assert (plan.removals, plan.kept, removed) == ((), (), ())
    assert reads.call_count == 0
    assert BRANCH in _pushed(stage_repo)


def test_the_dry_run_lists_the_write_of_the_intent_mark_before_the_push() -> None:
    _, writes = stage_requests(STAGE_REPO)

    texts = MESSAGES.roadmap
    record = StoreRequests(STAGE_REPO).set_marks(texts.plan_placeholders["item"])[-1]
    marks = [i for i, w in enumerate(writes) if (w.target, w.argv) == (record.target, record.argv)]
    push = next(i for i, w in enumerate(writes) if "push" in w.argv and "-u" in w.argv)
    worktree = next(i for i, w in enumerate(writes) if "worktree" in w.argv and "add" in w.argv)

    assert [i for i in marks if worktree < i < push] != []
