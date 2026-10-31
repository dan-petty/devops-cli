"""A replay of one item through the rows that set its Status label (#2920).

The item is staged, its plan merges, a runner Job takes it, its pull request is ready, and its
issue closes. The rows `stage_ready` and `implement` run for real: git runs on a clone with an
`origin`, GitHub and the Kubernetes API are faked at their edges. The runner Job writes In Review
itself (`implement_run`), so the test writes it the same way. The workflow `clear-status` removes
the label when the issue closes, so the test removes it the same way.
"""

from __future__ import annotations

import copy
import subprocess
from typing import Any

import pytest
import yaml

from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.run import STATUS_LANE_ROWS
from devops_cli.roadmap.store import CloseReason, ImplementRecordKey, Item, ItemField
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.implement_step import git_for_real
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_implement import PASS, PULL, merge_plan, seed_staged
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store", "app_slug")

IMPLEMENT_ROW = next(row for row in STATUS_LANE_ROWS if row.name == "implement")
STAGE_READY_ROW = next(row for row in STATUS_LANE_ROWS if row.name == "stage_ready")
HEAD = "a" * 40
DELIVERY_PULL = 7
CRONJOBS = ("batch", "v1", "cronjobs")
JOBS = ("batch", "v1", "jobs")


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def kube(cluster: FakeCluster) -> FakeCluster:
    document = yaml.safe_load((REPO_ROOT / "k8s/devops/cronjob-runner.yaml").read_text("utf-8"))
    cluster.custom_objects.objects[CRONJOBS] = [copy.deepcopy(document)]
    return cluster


def _labels(store: InMemoryRoadmapStore, number: int) -> list[str]:
    issue = next(issue for issue in store.issues() if issue.number == number)
    return [label for label in issue.labels if label.startswith("status/")]


def _held(store: InMemoryRoadmapStore, number: int) -> Item:
    item = store.item(number)
    assert item is not None
    return item


def _draft_with_green_checks(api: GitHubApiFake) -> None:
    payload = {"state": "open", "draft": True, "merged": False, "head": {"sha": HEAD}}
    api.route("GET", f"/repos/{STAGE_REPO}/pulls/{PULL}", github_json(payload))
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/commits/{HEAD}/check-runs?per_page=100",
        github_json({"total_count": 1, "check_runs": [PASS]}),
    )


def _real_git_and_ready_pull_requests(gh: ProcessFake) -> None:
    """Git runs for real on the clone, and `gh pr ready` succeeds."""
    gh.answer("git", ProcessAnswer(side_effect=git_for_real))
    gh.answer(
        lambda call: call.argv[1:3] == ("pr", "ready"),
        ProcessAnswer(side_effect=lambda call: subprocess.CompletedProcess(call.argv, 0, "", "")),
    )


def test_the_label_follows_the_item_from_staging_to_the_close(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    kube: FakeCluster,
) -> None:
    api, gh = github_api_and_gh
    _real_git_and_ready_pull_requests(gh)
    number = seed_staged(store, labels=("type/bug", "effort/high"))
    store.set_field(_held(store, number), ItemField.STATUS, "Ready")
    seen: dict[str, list[str]] = {}

    # Staged: the plan pull request is a green draft, and the Service marks it ready.
    _draft_with_green_checks(api)
    STAGE_READY_ROW.runner(store=store, repo=STAGE_REPO)
    seen["staged"] = _labels(store, number)

    # The plan merges: its change folder is on the default branch. The item has high effort, so
    # the default filter takes no Job for it yet.
    merge_plan(stage_repo, number)
    IMPLEMENT_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)
    seen["plan merged"] = _labels(store, number)

    # A person lowers the effort, and the next round makes the Job.
    store.remove_label(number, "effort/high")
    store.add_label(number, "effort/low")
    IMPLEMENT_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)
    seen["job running"] = _labels(store, number)

    # The Job marks its pull request ready and sets In Review, then ends.
    store.set_field(
        _held(store, number),
        ItemField.STATUS,
        "In Review",
        marks={ImplementRecordKey.PR: str(DELIVERY_PULL)},
    )
    kube.custom_objects.objects[JOBS][0]["status"] = {
        "conditions": [{"type": "Complete", "status": "True"}]
    }
    IMPLEMENT_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)
    seen["pull request ready"] = _labels(store, number)

    # The merge closes the issue, and the workflow removes the label.
    store.close_by_hand(number, CloseReason.COMPLETED)
    store.remove_label(number, "status/in-review")
    IMPLEMENT_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)
    seen["closed"] = _labels(store, number)

    assert seen == {
        "staged": ["status/ready"],
        "plan merged": ["status/planned"],
        "job running": ["status/in-progress"],
        "pull request ready": ["status/in-review"],
        "closed": [],
    }


def test_a_person_who_moves_the_label_keeps_it_through_every_round(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    kube: FakeCluster,
) -> None:
    _real_git_and_ready_pull_requests(github_api_and_gh[1])
    number = seed_staged(store, labels=("type/bug", "effort/high"))
    store.set_field(_held(store, number), ItemField.STATUS, "Ready")
    merge_plan(stage_repo, number)
    IMPLEMENT_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)
    assert _labels(store, number) == ["status/planned"]

    # A person moves Planned back to Ready, a Status that the Service writes from.
    store.remove_label(number, "status/planned")
    store.add_label(number, "status/ready")
    IMPLEMENT_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)
    IMPLEMENT_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)

    assert _labels(store, number) == ["status/ready"]


def test_the_row_stage_ready_sets_planned_for_a_plan_pull_request_that_merged(
    store: InMemoryRoadmapStore,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
) -> None:
    api, _gh = github_api_and_gh
    number = seed_staged(store)
    store.set_field(_held(store, number), ItemField.STATUS, "Ready")
    payload: dict[str, Any] = {
        "state": "closed",
        "draft": False,
        "merged": True,
        "head": {"sha": HEAD},
    }
    api.route("GET", f"/repos/{STAGE_REPO}/pulls/{PULL}", github_json(payload))

    STAGE_READY_ROW.runner(store=store, repo=STAGE_REPO)

    assert _labels(store, number) == ["status/planned"]
