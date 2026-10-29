"""`devops roadmap stage`: a staged branch whose item closed loses its draft and its branch when
only the App wrote to it (#2654)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.stage import StagePlan, apply_stage, parse_filters, plan_stage
from devops_cli.roadmap.store import GitHubState, ItemField, StageRecordKey
from tests.support.fakes.github import API, github_json
from tests.support.roadmap_stage import STAGE_EMAIL, STAGE_REPO, StageRepo

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

pytestmark = pytest.mark.usefixtures("keyring_store")

BRANCH = "fix/3-the-job-drops-a-comment"
CLOSE = f"PATCH {API}/repos/{STAGE_REPO}/pulls/7"


@pytest.fixture(autouse=True)
def closed_pull(github_api: GitHubApiFake) -> GitHubApiFake:
    github_api.route("PATCH", f"/repos/{STAGE_REPO}/pulls/7", github_json({"number": 7}))
    return github_api


def _staged_item(
    state: GitHubState = GitHubState.CLOSED, *, branch: str = BRANCH
) -> InMemoryRoadmapStore:
    """A store whose issue #1 holds the record of a staged branch."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = store.seed_issue(
        "fix(roadmap): the job drops a comment",
        state=state,
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    item = store.item(number)
    assert item is not None
    store.set_marks(
        item,
        {
            StageRecordKey.BRANCH: branch,
            StageRecordKey.PR: "7",
            StageRecordKey.SHA: "abc",
            StageRecordKey.GROUPS: json.dumps([["Group", 100]]),
        },
    )
    return store


def _plan(store: InMemoryRoadmapStore, repo: StageRepo) -> StagePlan:
    return plan_stage(
        store, repo=STAGE_REPO, source=repo.clone, filters=parse_filters(()), item_number=None
    )


def _record(store: InMemoryRoadmapStore) -> dict[str, str | None]:
    item = store.item(1)
    assert item is not None
    return {
        key.value: value
        for key, value in item.job_record.items()
        if "." in key.value and value is not None
    }


def _branches(repo: StageRepo) -> list[str]:
    return repo.origin_git("branch", "--format=%(refname:short)").split()


def test_a_closed_item_loses_a_branch_that_only_the_app_wrote_to(
    stage_repo: StageRepo, closed_pull: GitHubApiFake
) -> None:
    stage_repo.push_branch(BRANCH, email=STAGE_EMAIL)
    store = _staged_item()

    plan = _plan(store, stage_repo)
    applied = apply_stage(store, plan, source=stage_repo.clone)

    assert [(r.number, r.branch, r.pull) for r in plan.removals] == [(1, BRANCH, 7)]
    assert applied.removed == (1,)
    assert _branches(stage_repo) == ["main"]
    assert closed_pull.requested == [CLOSE]
    assert json.loads(closed_pull.sent[0].content) == {"state": "closed"}
    assert _record(store) == {}


def test_a_closed_item_keeps_a_branch_that_holds_a_commit_of_another_author(
    stage_repo: StageRepo, closed_pull: GitHubApiFake
) -> None:
    stage_repo.push_branch(BRANCH, email=STAGE_EMAIL)
    stage_repo.push_branch(BRANCH, email="person@example.com")
    store = _staged_item()

    plan = _plan(store, stage_repo)
    applied = apply_stage(store, plan, source=stage_repo.clone)

    assert plan.removals == ()
    assert [(k.number, k.branch) for k in plan.kept] == [(1, BRANCH)]
    assert "commit(s) by another author" in plan.kept[0].reason
    assert applied.removed == ()
    assert BRANCH in _branches(stage_repo)
    assert closed_pull.requested == []
    assert _record(store)["stage.branch"] == BRANCH


def test_a_closed_item_whose_branch_is_gone_loses_its_record_and_costs_no_request(
    stage_repo: StageRepo, closed_pull: GitHubApiFake
) -> None:
    store = _staged_item()

    plan = _plan(store, stage_repo)
    apply_stage(store, plan, source=stage_repo.clone)

    assert [(r.number, r.gone) for r in plan.removals] == [(1, True)]
    assert closed_pull.requested == []
    assert _record(store) == {}


def test_an_open_item_keeps_its_staged_branch(
    stage_repo: StageRepo, closed_pull: GitHubApiFake
) -> None:
    stage_repo.push_branch(BRANCH, email=STAGE_EMAIL)
    store = _staged_item(GitHubState.OPEN)

    plan = _plan(store, stage_repo)
    apply_stage(store, plan, source=stage_repo.clone)

    assert (plan.removals, plan.kept) == ((), ())
    assert BRANCH in _branches(stage_repo)
    assert closed_pull.requested == []
