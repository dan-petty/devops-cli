"""`devops roadmap implement`: which Staged items the job takes, and why it leaves one out
(#2665). Git runs for real on a clone with an `origin`, and GitHub is faked."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement import (
    DEFAULT_IMPLEMENT_FILTERS,
    ImplementPlan,
    ImplementTarget,
    dry_run_implement,
    parse_implement_filters,
    plan_implement,
)
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import ImplementRecordKey
from tests.support.fakes.github import GitHubApiFake
from tests.support.fakes.process import ProcessFake
from tests.support.roadmap_implement import (
    BRANCH,
    PULL,
    push_staged_branch,
    route_pull_status,
    seed_staged,
)
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store", "app_slug")


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def api(github_api: GitHubApiFake) -> GitHubApiFake:
    route_pull_status(github_api)
    return github_api


def _plan(
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    *filters: str,
    item: int | None = None,
    limit: int = 1,
    probe: int | None = None,
) -> ImplementPlan:
    return plan_implement(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_implement_filters(filters),
        item_number=item,
        limit=limit,
        probe=probe,
    )


def _reasons(plan: ImplementPlan) -> dict[int, str]:
    return {left.number: left.reason for left in plan.left_out}


def test_the_default_filter_names_the_ready_and_planned_items_of_low_effort() -> None:
    assert DEFAULT_IMPLEMENT_FILTERS == ("status=ready", "status=planned", "effort=low")


def test_a_staged_low_effort_p1_bug_is_selected_with_its_branch_and_pull_request(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    number = seed_staged(store)

    plan = _plan(store, staged_repo)

    held = store.item(number)
    assert held is not None
    assert plan.selected == (ImplementTarget(held, BRANCH, PULL),)
    assert plan.left_out == ()


def test_an_item_that_the_filter_does_not_name_is_not_in_the_plan(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    seed_staged(store, labels=("type/bug", "effort/high"))
    seed_staged(store, labels=("type/feature", "effort/medium"))
    seed_staged(store, labels=("type/docs",))

    plan = _plan(store, staged_repo)

    assert (plan.selected, plan.left_out) == ((), ())


def test_the_highest_priority_goes_first_and_the_limit_caps_the_run(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    seed_staged(store)
    push_staged_branch(staged_repo, number=2)
    route_pull_status(api, pull=6)
    urgent = seed_staged(store, priority="P0-Critical", pull=6)

    plan = _plan(store, staged_repo)

    assert [target.item.number for target in plan.selected] == [urgent]


def test_an_item_that_is_neither_ready_nor_planned_is_left_out_whatever_the_filter_says(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    number = seed_staged(store, status="In Review")

    plan = _plan(store, staged_repo, "status=in-review", "priority=p1-high")

    assert (plan.selected, _reasons(plan)) == (
        (),
        {number: "Its Status is In Review, not Ready or Planned."},
    )


def test_a_staged_item_with_the_status_planned_is_selected_by_the_default_filter(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    number = seed_staged(store, status="Planned")

    plan = _plan(store, staged_repo)

    assert [target.item.number for target in plan.selected] == [number]


def test_an_item_in_progress_stays_in_the_plan_while_its_record_names_a_job_nobody_reported(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    """The Service sets In Progress when it makes the Job, and the Job plans its own item."""
    number = seed_staged(store, status="In Progress")
    held = store.item(number)
    assert held is not None
    store.set_marks(held, {ImplementRecordKey.JOB: "devops-cli-runner-1"})

    plan = _plan(store, staged_repo, item=number)

    assert [target.item.number for target in plan.selected] == [number]


def test_an_item_in_progress_with_no_job_is_left_out_and_the_reason_names_the_status(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    number = seed_staged(store, status="In Progress")

    plan = _plan(store, staged_repo, item=number)

    assert (plan.selected, _reasons(plan)) == (
        (),
        {number: "Its Status is In Progress, not Ready or Planned."},
    )


def test_an_item_that_stage_has_not_recorded_is_left_out_as_not_staged(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    number = seed_staged(store, record=False)

    plan = _plan(store, staged_repo)

    assert _reasons(plan) == {
        number: "It is neither Staged nor Planned: its record holds no staged branch or pull "
        "request, and main holds no change folder for it."
    }


def test_an_item_with_a_stop_on_record_is_left_out_and_the_reason_names_the_retry_comment(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    number = seed_staged(store)
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {ImplementRecordKey.STOPPED: "group 2"})

    plan = _plan(store, staged_repo)

    assert _reasons(plan) == {
        number: "A step stopped it at group 2. A person fixes the cause and comments "
        "`implement: retry`."
    }


def test_a_retry_comment_of_the_owner_after_the_stop_comment_selects_the_item_again(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    number = seed_staged(store)
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {ImplementRecordKey.STOPPED: "group 2"})
    store.comment(number, "<!-- devops roadmap implement -->\nStopped at group 2.")
    store.seed_comment(number, "implement: retry", author_association="OWNER")

    plan = _plan(store, staged_repo)

    assert [(target.item.number, target.retry) for target in plan.selected] == [(number, True)]


@pytest.mark.parametrize("association", ["NONE", "CONTRIBUTOR", None])
def test_a_retry_comment_of_a_stranger_leaves_the_item_out(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    association: str | None,
) -> None:
    number = seed_staged(store)
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {ImplementRecordKey.STOPPED: "group 2"})
    store.seed_comment(number, "implement: retry", author_association=association)

    plan = _plan(store, staged_repo)

    assert (plan.selected, list(_reasons(plan))) == ((), [number])


def test_a_retry_comment_from_before_the_stop_comment_does_not_count(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    number = seed_staged(store)
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {ImplementRecordKey.STOPPED: "group 2"})
    store.seed_comment(number, "implement: retry", author_association="OWNER")
    store.comment(number, "<!-- devops roadmap implement -->\nStopped at group 2.")

    plan = _plan(store, staged_repo)

    assert (plan.selected, list(_reasons(plan))) == ((), [number])


def test_an_item_of_an_author_who_is_not_trusted_is_left_out(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    number = seed_staged(store, author_association="NONE")

    plan = _plan(store, staged_repo)

    assert _reasons(plan) == {
        number: "Its author is NONE, not the owner, a member or a collaborator."
    }


def test_an_item_whose_branch_is_not_on_origin_is_left_out(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, api: GitHubApiFake
) -> None:
    number = seed_staged(store)

    plan = _plan(store, stage_repo)

    assert _reasons(plan) == {number: f"Its staged branch `{BRANCH}` is not on origin."}


def test_a_branch_with_a_commit_by_another_author_is_left_out_and_names_the_author(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, api: GitHubApiFake
) -> None:
    push_staged_branch(stage_repo)
    stage_repo.push_branch(BRANCH, author="Casey Person")
    number = seed_staged(store)

    plan = _plan(store, stage_repo)

    assert _reasons(plan) == {
        number: "Its branch has a commit by Casey Person, not by devops-roadmap[bot]."
    }


@pytest.mark.parametrize(
    "status",
    [
        {"state": "open", "draft": False, "merged": False},
        {"state": "closed", "draft": False, "merged": False},
        {"state": "closed", "draft": False, "merged": True},
    ],
)
def test_an_item_whose_pull_request_is_not_an_open_draft_is_left_out(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    github_api: GitHubApiFake,
    status: dict[str, object],
) -> None:
    route_pull_status(github_api, status)
    number = seed_staged(store)

    plan = _plan(store, staged_repo)

    assert _reasons(plan) == {number: f"Its pull request #{PULL} is not an open draft."}


def test_an_item_that_a_worktree_holds_is_left_out(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    number = seed_staged(store)
    staged_repo.git("fetch", "-q", "origin", BRANCH)
    held = staged_repo.clone.parent / "held"
    staged_repo.git("worktree", "add", "-q", "--track", "-b", BRANCH, str(held), f"origin/{BRANCH}")

    plan = _plan(store, staged_repo)

    assert list(_reasons(plan)) == [number]
    assert "worktree" in _reasons(plan)[number]


def test_an_item_that_is_named_is_judged_by_its_own_state_and_not_by_the_filter(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    number = seed_staged(store, labels=("type/bug", "effort/high"))

    plan = _plan(store, staged_repo, item=number)

    assert [target.item.number for target in plan.selected] == [number]


def test_a_named_issue_that_is_no_item_is_left_out(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    plan = _plan(store, staged_repo, item=99)

    assert _reasons(plan) == {99: MESSAGES.roadmap.item_left_not_item}


def test_the_job_leaves_every_item_out_when_no_app_slug_is_set(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    config: Callable[..., Path],
) -> None:
    config(service={"github_app": {"slug": None}})
    number = seed_staged(store)

    plan = _plan(store, staged_repo)

    assert "service.github_app.slug" in _reasons(plan)[number]


def test_a_filter_that_names_an_unknown_family_is_refused() -> None:
    from devops_cli.exceptions import ValidationError

    with pytest.raises(ValidationError) as raised:
        parse_implement_filters(("color=red",))
    assert raised.value.error_code == "VALIDATION_ERROR"


def test_a_dry_run_lists_the_requests_of_a_run_and_makes_none(
    github_api: GitHubApiFake, process_fake: ProcessFake
) -> None:
    plan = dry_run_implement(STAGE_REPO, item=7, limit=1)

    commands = [" ".join(request.argv) for request in plan.requests + plan.write_requests]
    assert (
        plan.dry_run,
        plan.selected,
        github_api.requested,
        process_fake.calls,
        any("pulls/<pull request>" in command for command in commands),
        any(command.endswith("pr ready <pull request>") for command in commands),
        any("rebase origin/main" in command for command in commands),
    ) == (True, (), [], [], True, True, True)


@pytest.mark.parametrize(
    ("owner", "reason"),
    [("owner/human", "It is claimed by human."), ("owner/agent", "It is claimed by agent.")],
)
def test_an_item_that_an_agent_or_a_person_claimed_is_left_out(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, owner: str, reason: str
) -> None:
    number = seed_staged(store, labels=("type/bug", "effort/low", owner))

    plan = _plan(store, staged_repo)

    assert (plan.selected, _reasons(plan)) == ((), {number: reason})


def test_a_named_item_that_an_agent_claimed_is_left_out(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    number = seed_staged(store, labels=("type/bug", "effort/low", "owner/agent"))

    plan = _plan(store, staged_repo, item=number)

    assert (plan.selected, _reasons(plan)) == ((), {number: "It is claimed by agent."})


def test_an_item_that_the_service_holds_is_selected(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    number = seed_staged(store, labels=("type/bug", "effort/low", "owner/service"))

    plan = _plan(store, staged_repo)

    assert [target.item.number for target in plan.selected] == [number]


def test_the_probe_past_the_limit_is_judged_and_the_plan_says_it_passes_every_rule(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake
) -> None:
    first = seed_staged(store, priority="P0-Critical")
    push_staged_branch(staged_repo, number=2)
    route_pull_status(api, pull=6)
    second = seed_staged(store, pull=6)

    plain = _plan(store, staged_repo)
    probed = _plan(store, staged_repo, probe=second)

    assert (
        [t.item.number for t in plain.selected],
        plain.beyond,
        [t.item.number for t in probed.selected],
        probed.beyond,
    ) == ([first], (), [first], (second,))
