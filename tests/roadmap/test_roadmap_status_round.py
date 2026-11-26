"""A replay of one item through the rows that set its Status label (#2920).

The item is staged, its plan merges, a runner Job takes it, its pull request is ready, and its
issue closes. The rows `stage_ready` and `implement` run for real: git runs on a clone with an
`origin`, GitHub and the Kubernetes API are faked at their edges. The runner Job writes In Review
itself (`implement_run`), so the test writes it the same way. When the issue closes, the next round
of the row `implement` removes the label (#4660).
"""

from __future__ import annotations

import copy
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.roadmap.run import STATUS_LANE_ROWS, run_due_jobs
from devops_cli.roadmap.stores.store import (
    CloseReason,
    GitHubState,
    ImplementRecordKey,
    Item,
    ItemField,
)
from tests.support.fakes.github import GitHubApiFake, github_json, route_compare_files
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import git_for_real
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_implement import BRANCH, PASS, PULL, merge_plan, seed_staged
from tests.support.roadmap_run import NOW, POLL_KEY, stamp_successes
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store", "app_slug", "cluster")

IMPLEMENT_ROW = next(row for row in STATUS_LANE_ROWS if row.name == "implement")
WATCH_ROW = next(row for row in STATUS_LANE_ROWS if row.name == "watch")
HEAD = "a" * 40
DELIVERY_PULL = 7
CRONJOBS = ("batch", "v1", "cronjobs")
JOBS = ("batch", "v1", "jobs")
# The trigger that the router gives each lane for an `issues.closed` delivery.
CLOSED_KEY = ("webhook", "issues", "closed")


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


def _unlabels(store: InMemoryRoadmapStore) -> list[tuple[int | None, str | None]]:
    """Each label removal that the store made as a job, in order: the issue and the label."""
    return [
        (write.number, write.value)
        for write in store.job_writes()
        if write.operation == "unlabel_issue"
    ]


def _all_labels(store: InMemoryRoadmapStore, number: int) -> set[str]:
    return set(next(issue for issue in store.issues() if issue.number == number).labels)


def _held(store: InMemoryRoadmapStore, number: int) -> Item:
    item = store.item(number)
    assert item is not None
    return item


def _draft_with_green_checks(api: GitHubApiFake) -> None:
    payload = {
        "state": "open",
        "draft": True,
        "merged": False,
        "head": {"sha": HEAD, "ref": BRANCH},
        "base": {"ref": "main"},
    }
    api.route("GET", f"/repos/{STAGE_REPO}/pulls/{PULL}", github_json(payload))
    changed = {
        "filename": "openspec/changes/1-the-job-drops-a-comment/proposal.md",
        "status": "added",
    }
    route_compare_files(api, STAGE_REPO, "main", HEAD, changed, merge_base="b" * 40)
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/commits/{HEAD}/check-runs?per_page=100",
        github_json({"total_count": 1, "check_runs": [PASS]}),
    )


def _round_of_the_service(api: GitHubApiFake, gh: ProcessFake) -> None:
    """A round of `run_due_jobs`: git runs for real, and the session finds the login that the
    clone commits as."""
    _real_git_and_ready_pull_requests(gh)
    api.route("GET", "/user", github_json({"login": "test-bot"}))
    api.route("GET", "/users/test-bot", github_json({"id": 4242, "login": "test-bot"}))


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
    WATCH_ROW.runner(store=store, repo=STAGE_REPO)
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

    # The merge closes the issue, and the next round removes the label.
    store.close_by_hand(number, CloseReason.COMPLETED)
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


def test_the_row_watch_sets_planned_for_a_plan_pull_request_that_merged(
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
        "head": {"sha": HEAD, "ref": BRANCH},
    }
    api.route("GET", f"/repos/{STAGE_REPO}/pulls/{PULL}", github_json(payload))

    WATCH_ROW.runner(store=store, repo=STAGE_REPO)

    assert _labels(store, number) == ["status/planned"]


def test_an_issues_closed_delivery_removes_the_status_label_with_one_request(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    tmp_path: Path,
) -> None:
    """Test first for #4660: the router gives an `issues.closed` delivery to each lane as the
    trigger `("webhook", "issues", "closed")`. One minute after the last success of the row
    `implement`, only the trigger makes the row due, and its round removes `status/ready` of the
    closed issue with one request. No workflow of the repository takes part."""
    _round_of_the_service(*github_api_and_gh)
    number = store.seed_issue(
        "A merged item",
        fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "Ready"},
        state=GitHubState.CLOSED,
    )
    stamp_successes(tmp_path, implement=NOW - timedelta(minutes=1))

    ran = run_due_jobs(
        STAGE_REPO,
        store,
        batch={CLOSED_KEY: 1},
        table=(IMPLEMENT_ROW,),
        data_dir=tmp_path,
        remote_url=str(stage_repo.origin),
        now=NOW,
    )

    assert (ran, _unlabels(store), _labels(store, number)) == (
        ("implement",),
        [(number, "status/ready")],
        [],
    )


def test_a_closed_issue_that_holds_owner_agent_loses_the_label_in_the_next_round(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    tmp_path: Path,
) -> None:
    """Test first for #4660: a closed issue whose label no delivery removed, such as a claim that
    an agent made after the close, loses the label in the next poll round of the row `implement`.
    The issue keeps its other labels, and the round after that sends no removal."""
    _round_of_the_service(*github_api_and_gh)
    number = store.seed_issue(
        "Claimed after the close",
        labels=("owner/agent", "type/bug"),
        fields={ItemField.PRIORITY: "P2-Medium"},
        state=GitHubState.CLOSED,
    )
    stamp_successes(tmp_path, implement=NOW - timedelta(minutes=8))

    def poll(at: timedelta) -> tuple[str, ...]:
        return run_due_jobs(
            STAGE_REPO,
            store,
            batch={POLL_KEY: 1},
            table=(IMPLEMENT_ROW,),
            data_dir=tmp_path,
            remote_url=str(stage_repo.origin),
            now=NOW + at,
        )

    first = (poll(timedelta(0)), _unlabels(store), _all_labels(store, number))
    second = (poll(timedelta(minutes=8)), _unlabels(store))

    assert (first, second) == (
        (("implement",), [(number, "owner/agent")], {"type/bug", "priority/p2-medium"}),
        (("implement",), [(number, "owner/agent")]),
    )
