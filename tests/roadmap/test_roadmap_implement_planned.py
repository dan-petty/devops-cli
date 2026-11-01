"""`devops roadmap implement` takes a Planned item (#2714): the plan of its change is on the
default branch, because a person merged the staging pull request, and its staged branch is gone.
Git runs for real on a clone with an `origin`, and GitHub is faked."""

from __future__ import annotations

import subprocess

import pytest

from devops_cli.exceptions import GitOperationError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement import (
    ImplementPlan,
    ImplementTarget,
    parse_implement_filters,
    plan_implement,
)
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import CloseReason, ImplementRecordKey, StageRecordKey
from tests.support.fakes.github import GitHubApiFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import git_for_real
from tests.support.roadmap_implement import (
    BRANCH,
    PULL,
    TICKED_ALL,
    TICKED_FIRST,
    merge_plan,
    push_staged_branch,
    route_pull_status,
    seed_staged,
)
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store", "app_slug")

SLUG = "an-other-slug-than-the-title"


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def repo(stage_repo: StageRepo) -> StageRepo:
    return stage_repo


def _plan(
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    *,
    item: int | None = None,
    limit: int = 1,
) -> ImplementPlan:
    return plan_implement(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_implement_filters(()),
        item_number=item,
        limit=limit,
    )


def _reasons(plan: ImplementPlan) -> dict[int, str]:
    return {left.number: left.reason for left in plan.left_out}


def _targets(plan: ImplementPlan) -> list[tuple[int, str, int | None]]:
    return [(t.item.number, t.branch, t.pull) for t in plan.selected]


def test_an_item_with_its_plan_on_main_and_its_branch_gone_is_planned_with_a_new_branch(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(store)  # the record names a branch and a merged pull request
    merge_plan(repo, number, slug=SLUG)

    plan = _plan(store, repo)

    held = store.item(number)
    assert held is not None
    assert plan.selected == (ImplementTarget(held, f"fix/{number}-{SLUG}", None),)
    assert plan.left_out == ()
    assert github_api.requested == []


def test_the_default_filter_takes_ready_items_of_low_effort_of_any_type_and_priority(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    slow = seed_staged(
        store, record=False, title="feat(cli): add a flag", labels=("type/feature", "effort/high")
    )
    chore = seed_staged(
        store,
        record=False,
        title="chore(deps): bump a tool",
        labels=("type/chore", "effort/low"),
        priority="P3-Low",
    )
    docs = seed_staged(
        store,
        record=False,
        title="docs(k8s): fix a path",
        labels=("type/docs", "effort/low"),
        priority="P0-Critical",
    )
    feature = seed_staged(
        store,
        record=False,
        title="feat(cli): add a switch",
        labels=("type/feature", "effort/low"),
        priority="P2-Medium",
    )
    medium = seed_staged(
        store, record=False, title="test(cli): hold a flag", labels=("type/test", "effort/medium")
    )
    for number, slug in (
        (slow, "add-a-flag"),
        (chore, "bump-a-tool"),
        (docs, "fix-a-path"),
        (feature, "add-a-switch"),
        (medium, "hold-a-flag"),
    ):
        merge_plan(repo, number, slug=slug)

    plan = _plan(store, repo, limit=5)

    assert _targets(plan) == [
        (docs, f"docs/{docs}-fix-a-path", None),
        (feature, f"feat/{feature}-add-a-switch", None),
        (chore, f"chore/{chore}-bump-a-tool", None),
    ]
    assert plan.left_out == ()


def test_a_planned_item_with_a_stray_local_branch_with_a_commit_of_its_own_is_left_out(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(store, record=False)
    merge_plan(repo, number)
    repo.stray_branch(BRANCH, own_commit=True)

    plan = _plan(store, repo)

    assert plan.selected == ()
    assert BRANCH in _reasons(plan)[number]
    assert "1 commit" in _reasons(plan)[number]


def test_a_planned_item_with_a_stray_local_branch_that_origin_holds_is_planned(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(store, record=False)
    merge_plan(repo, number)
    repo.stray_branch(BRANCH)

    plan = _plan(store, repo)

    assert _targets(plan) == [(number, BRANCH, None)]


def test_an_item_with_no_record_and_a_plan_on_main_is_planned(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(store, record=False)
    merge_plan(repo, number)

    plan = _plan(store, repo)

    assert _targets(plan) == [(number, BRANCH, None)]


def test_the_type_of_the_branch_is_the_type_of_the_title(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(
        store, record=False, labels=("type/bug", "effort/low"), title="perf(roadmap): be fast"
    )
    merge_plan(repo, number, slug="be-fast")

    plan = _plan(store, repo)

    assert _targets(plan) == [(number, f"perf/{number}-be-fast", None)]


def test_an_item_with_its_plan_on_main_and_its_staged_branch_on_origin_takes_the_staged_path(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    push_staged_branch(stage_repo)
    route_pull_status(github_api)
    number = seed_staged(store)
    merge_plan(stage_repo, number)

    plan = _plan(store, stage_repo)

    assert _targets(plan) == [(number, BRANCH, PULL)]


def test_a_staged_item_with_a_stray_local_branch_with_a_commit_of_its_own_is_left_out(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    push_staged_branch(stage_repo)
    route_pull_status(github_api)
    number = seed_staged(store)
    stage_repo.stray_branch(BRANCH, own_commit=True)

    plan = _plan(store, stage_repo)

    assert plan.selected == ()
    assert BRANCH in _reasons(plan)[number]
    assert "1 commit" in _reasons(plan)[number]


def test_a_retry_finds_the_branch_and_the_pull_request_that_the_job_recorded(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    """The stage pair names a merged pull request. The implement pair names the open draft."""
    new_branch = f"fix/1-{SLUG}"
    stage_repo.push_branch(new_branch, author="devops-roadmap[bot]")
    route_pull_status(github_api, pull=9)
    number = seed_staged(store, record=False)
    item = store.item(number)
    assert item is not None
    store.set_marks(
        item,
        {
            StageRecordKey.BRANCH: BRANCH,
            StageRecordKey.PR: str(PULL),
            ImplementRecordKey.BRANCH: new_branch,
            ImplementRecordKey.PR: "9",
        },
    )
    merge_plan(stage_repo, number, slug=SLUG)

    plan = _plan(store, stage_repo)

    assert _targets(plan) == [(number, new_branch, 9)]


def test_a_recorded_branch_that_is_gone_does_not_stop_a_planned_item(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(store, record=False)
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {ImplementRecordKey.BRANCH: "fix/1-gone", ImplementRecordKey.PR: "9"})
    merge_plan(repo, number, slug=SLUG)

    plan = _plan(store, repo)

    assert _targets(plan) == [(number, f"fix/{number}-{SLUG}", None)]


def test_two_planned_items_are_selected_by_priority_and_then_by_number(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    first = seed_staged(store, record=False)
    second = seed_staged(store, record=False)
    urgent = seed_staged(store, record=False, priority="P0-Critical")
    for number in (first, second, urgent):
        merge_plan(repo, number, slug=f"plan-{number}")

    plan = _plan(store, repo, limit=2)

    assert [number for number, _, _ in _targets(plan)] == [urgent, first]


def test_a_planned_item_that_a_pushed_branch_holds_is_left_out_with_the_holder(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(store, record=False)
    repo.push_branch(f"fix/{number}-someone-elses-work")
    merge_plan(repo, number)

    plan = _plan(store, repo)

    assert plan.selected == ()
    assert _reasons(plan) == {
        number: f"Issue {number} is held by a pushed branch: "
        f"origin/fix/{number}-someone-elses-work."
    }


def test_a_planned_item_that_a_worktree_holds_is_left_out(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(store, record=False)
    merge_plan(repo, number)
    held = repo.clone.parent / "held"
    repo.git("worktree", "add", "-q", "-b", f"fix/{number}-mine", str(held), "origin/main")

    plan = _plan(store, repo)

    assert plan.selected == ()
    assert "worktree" in _reasons(plan)[number]


def test_an_item_whose_change_is_archived_on_main_is_left_out_and_the_reason_says_so(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(store, record=False)
    merge_plan(repo, number, archived=True)

    plan = _plan(store, repo)

    assert plan.selected == ()
    assert _reasons(plan) == {
        number: "Its change is archived on main: the folder "
        f"`2026-10-28-{number}-the-job-drops-a-comment` is there."
    }


def test_a_planned_item_with_every_task_ticked_is_left_out_and_the_reason_says_so(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(store, record=False)
    merge_plan(repo, number, tasks=TICKED_ALL)

    plan = _plan(store, repo)

    assert plan.selected == ()
    assert _reasons(plan) == {
        number: f"Every task of its change `{number}-the-job-drops-a-comment` is ticked, so no "
        "group is left to run."
    }


def test_a_planned_item_whose_change_has_no_tasks_is_left_out_and_the_next_is_selected(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    broken = seed_staged(store, record=False)
    merge_plan(repo, broken)
    repo.git("rm", "-q", f"openspec/changes/{broken}-the-job-drops-a-comment/tasks.md")
    repo.git("commit", "-q", "-m", "fix: delete tasks")
    repo.git("push", "-q", "origin", "main")
    valid = seed_staged(store, record=False)
    merge_plan(repo, valid)

    plan = _plan(store, repo, limit=2)

    assert [n for n, _, _ in _targets(plan)] == [valid]
    reason = _reasons(plan)[broken]
    assert reason.startswith(
        f"Its change `{broken}-the-job-drops-a-comment` has no readable tasks.md on main: "
    )
    assert "does not exist" in reason


def test_a_planned_item_with_one_group_ticked_is_selected(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(store, record=False)
    merge_plan(repo, number, tasks=TICKED_FIRST)

    plan = _plan(store, repo)

    assert [n for n, _, _ in _targets(plan)] == [number]


def test_a_planned_item_whose_title_has_no_type_is_left_out(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(store, record=False, title="the job drops a comment")
    merge_plan(repo, number)

    plan = _plan(store, repo)

    assert plan.selected == ()
    assert "Conventional Commit type" in _reasons(plan)[number]


def test_a_planned_item_whose_folder_gives_no_branch_name_is_left_out(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(store, record=False)
    merge_plan(repo, number, slug="Not_A_Slug")

    plan = _plan(store, repo)

    assert plan.selected == ()
    assert _reasons(plan) == {
        number: f"Its change folder `{number}-Not_A_Slug` gives the branch "
        f"`fix/{number}-Not_A_Slug`, which breaks the form <type>/<issue>-<slug>."
    }


def test_a_planned_item_with_a_stop_on_record_waits_for_a_retry(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(store, record=False)
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {ImplementRecordKey.STOPPED: "group 1"})
    merge_plan(repo, number)

    plan = _plan(store, repo)

    assert plan.selected == ()
    assert "implement: retry" in _reasons(plan)[number]


def test_a_named_planned_item_that_is_closed_is_left_out(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(store, record=False)
    merge_plan(repo, number)
    store.close_by_hand(number, CloseReason.COMPLETED)

    plan = _plan(store, repo, item=number)

    assert (plan.selected, _reasons(plan)) == ((), {number: MESSAGES.roadmap.item_left_closed})


def test_a_planned_item_that_is_in_progress_with_no_job_is_left_out(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(store, record=False, status="In Progress")
    merge_plan(repo, number)

    plan = _plan(store, repo, item=number)

    assert _reasons(plan) == {number: "Its Status is In Progress, not Ready or Planned."}


def test_a_planned_item_of_an_author_who_is_not_trusted_is_left_out(
    store: InMemoryRoadmapStore, repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = seed_staged(store, record=False, author_association="NONE")
    merge_plan(repo, number)

    plan = _plan(store, repo)

    assert _reasons(plan) == {
        number: "Its author is NONE, not the owner, a member or a collaborator."
    }


def test_a_tree_that_cannot_be_read_fails_the_plan_and_selects_no_item(
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    github_api: GitHubApiFake,
    process_fake: ProcessFake,
) -> None:
    seed_staged(store, record=False)
    process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))

    def refuse(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(call.argv, 128, stdout="", stderr="fatal: bad tree")

    process_fake.answer(lambda call: "ls-tree" in call.argv, ProcessAnswer(side_effect=refuse))

    with pytest.raises(GitOperationError, match=r"ls-tree.*fatal: bad tree"):
        _plan(store, repo)
