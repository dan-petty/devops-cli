"""`devops roadmap stage` leaves out an item whose plan is on the default branch (#2714): a
person merged the staging pull request, so the branch is gone and the change folder is on `main`.
Git runs for real on a clone with an `origin`; the model and OpenSpec are faked."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from devops_cli.exceptions import GitOperationError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.stage import StagePlan, parse_filters, plan_stage
from devops_cli.roadmap.store import GitHubState, ItemField, StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import git_for_real
from tests.support.roadmap_implement import branch_of, merge_plan
from tests.support.roadmap_stage import (
    STAGE_NAME,
    STAGE_REPO,
    StageRepo,
    seed_stageable,
)

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture(autouse=True)
def stage_edges(model_fake: ModelFake, openspec_fake: OpenSpecFake) -> None:
    """A model that gives a valid plan for any item, and no OpenSpec on the path: an item that the
    job does not leave out is staged."""
    model_fake.answer(make_stage_proposal())
    openspec_fake.installed = False


def _plan(store: InMemoryRoadmapStore, repo: StageRepo, *, item: int | None = None) -> StagePlan:
    return plan_stage(
        store, repo=STAGE_REPO, source=repo.clone, filters=parse_filters(()), item_number=item
    )


def _reasons(plan: StagePlan) -> dict[int, str]:
    return {left.number: left.reason for left in plan.left_out}


def _merged_stage_record(store: InMemoryRoadmapStore, number: int) -> None:
    """The record of the stage job for an item whose staging pull request is merged."""
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {StageRecordKey.BRANCH: branch_of(number), StageRecordKey.PR: "7"})


def test_an_item_whose_plan_is_on_main_and_whose_branch_is_gone_is_left_out(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    number = seed_stageable(store)
    _merged_stage_record(store, number)
    merge_plan(stage_repo, number, slug="a-different-slug-than-the-title")

    plan = _plan(store, stage_repo)

    assert plan.ready == ()
    assert _reasons(plan) == {
        number: f"Its plan is on main: the change folder `{number}-a-different-slug-than-the-title`"
        " is there."
    }
    assert model_fake.calls == []


def test_an_item_whose_plan_is_on_main_and_whose_branch_is_still_on_origin_has_one_reason(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    number = seed_stageable(store)
    stage_repo.push_branch(branch_of(number), author=STAGE_NAME)
    merge_plan(stage_repo, number)

    plan = _plan(store, stage_repo)

    assert plan.ready == ()
    assert _reasons(plan)[number].startswith("Its plan is on main")
    assert len(plan.left_out) == 1


def test_an_item_whose_change_is_archived_on_main_is_left_out_and_the_reason_says_so(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    number = seed_stageable(store)
    merge_plan(stage_repo, number, archived=True)

    plan = _plan(store, stage_repo)

    assert plan.ready == ()
    assert _reasons(plan)[number] == (
        f"Its change is archived on main: the folder `2026-10-28-{number}-the-job-drops-a-comment`"
        " is there."
    )


def test_a_closed_item_with_a_plan_on_main_is_not_in_the_plan(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    number = store.seed_issue(
        "fix(roadmap): the job drops a comment",
        labels=("type/bug",),
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
        state=GitHubState.CLOSED,
    )
    merge_plan(stage_repo, number)

    plan = _plan(store, stage_repo)

    assert (plan.ready, plan.left_out) == ((), ())


def test_two_items_with_plans_on_main_each_have_a_reason(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    first, second = seed_stageable(store), seed_stageable(store)
    merge_plan(stage_repo, first, slug="first-plan")
    merge_plan(stage_repo, second, slug="second-plan")

    plan = _plan(store, stage_repo)

    reasons = _reasons(plan)
    assert plan.ready == ()
    assert reasons.keys() == {first, second}
    assert f"`{first}-first-plan`" in reasons[first]
    assert f"`{second}-second-plan`" in reasons[second]


def test_an_item_with_a_named_number_is_left_out_too(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    number = seed_stageable(store)
    merge_plan(stage_repo, number)

    plan = _plan(store, stage_repo, item=number)

    assert plan.ready == ()
    assert _reasons(plan)[number].startswith("Its plan is on main")


def test_an_item_with_no_plan_on_main_is_still_staged(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
) -> None:
    planned, free = seed_stageable(store), seed_stageable(store)
    merge_plan(stage_repo, planned)

    plan = _plan(store, stage_repo)

    assert [change.target.item.number for change in plan.ready] == [free]
    assert list(_reasons(plan)) == [planned]


def test_a_tree_that_cannot_be_read_fails_the_run_and_stages_no_item(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    process_fake: ProcessFake,
) -> None:
    seed_stageable(store)
    process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))

    def refuse(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(call.argv, 128, stdout="", stderr="fatal: bad tree")

    process_fake.answer(lambda call: "ls-tree" in call.argv, ProcessAnswer(side_effect=refuse))

    with pytest.raises(GitOperationError, match=r"ls-tree.*fatal: bad tree"):
        _plan(store, stage_repo)

    assert model_fake.calls == []


def test_a_round_reads_the_tree_once_for_many_items(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    process_fake: ProcessFake,
) -> None:
    for _ in range(3):
        number = seed_stageable(store)
        merge_plan(stage_repo, number, slug=f"plan-{number}")
    process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))

    _plan(store, stage_repo)

    assert len([call for call in process_fake.calls if "ls-tree" in call.argv]) == 1
