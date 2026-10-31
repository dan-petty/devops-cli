"""The Service sets the Status label of an item from its job record (#2920).

One pure function derives the Status. The sweep writes it with the family replace of the store, and
only for an open item that holds Ready or Planned with the label that a job last wrote. The roadmap
is in memory, and the one pull request that the sweep may read is routed through the GitHub fake.
"""

from __future__ import annotations

import pytest

from devops_cli.exceptions import GitHubRateLimitError, RoadmapItemChangedError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.status_sync import (
    StatusFacts,
    derive_status,
    facts_of,
    sync_status,
    sync_statuses,
)
from devops_cli.roadmap.store import (
    CloseReason,
    ImplementRecordKey,
    Item,
    ItemField,
)
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.roadmap_stage import STAGE_REPO

pytestmark = pytest.mark.usefixtures("keyring_store")

NO_PLANS = PlannedChanges("main", {}, {})
DELIVERY_PULL = 9


def _plans(*numbers: int) -> PlannedChanges:
    return PlannedChanges("main", {n: f"{n}-a-change" for n in numbers}, {})


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


def _job_item(store: InMemoryRoadmapStore, status: str, **marks: str) -> int:
    """An item whose Status a job wrote, so that the record names it."""
    number = store.seed_issue("fix(cli): one", fields={ItemField.PRIORITY: "P2-Medium"})
    store.set_field(
        _item(store, number),
        ItemField.STATUS,
        status,
        marks={ImplementRecordKey(key.replace("_", ".", 1)): value for key, value in marks.items()},
    )
    return number


def _item(store: InMemoryRoadmapStore, number: int) -> Item:
    item = store.item(number)
    assert item is not None
    return item


def _status(store: InMemoryRoadmapStore, number: int) -> str | None:
    return _item(store, number).status


def _pull(api: GitHubApiFake, *, draft: bool, state: str = "open") -> None:
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls/{DELIVERY_PULL}",
        github_json({"state": state, "draft": draft, "merged": False, "head": {"sha": "a" * 40}}),
    )


@pytest.mark.parametrize(
    ("facts", "status"),
    [
        (StatusFacts(), "Ready"),
        (StatusFacts(plan_merged=True), "Planned"),
        (StatusFacts(plan_merged=True, job_active=True), "In Progress"),
        (StatusFacts(plan_merged=True, pull_ready=True), "In Review"),
        (StatusFacts(plan_merged=True, job_active=True, pull_ready=True), "In Progress"),
        (StatusFacts(plan_merged=True, job_active=True, blocked=True), "Blocked"),
        (StatusFacts(blocked=True), "Blocked"),
    ],
)
def test_the_status_follows_the_facts_in_one_order(facts: StatusFacts, status: str) -> None:
    assert derive_status(facts) == status


def test_a_ready_item_whose_plan_is_merged_becomes_planned(
    store: InMemoryRoadmapStore,
) -> None:
    number = _job_item(store, "Ready")

    synced = sync_statuses(store, repo=STAGE_REPO, planned=_plans(number))

    assert (synced.changed, synced.failed, _status(store, number)) == ((number,), (), "Planned")


def test_an_archived_plan_counts_as_a_merged_plan(store: InMemoryRoadmapStore) -> None:
    number = _job_item(store, "Ready")

    sync_statuses(store, repo=STAGE_REPO, planned=PlannedChanges("main", {}, {number: "d-n-a"}))

    assert _status(store, number) == "Planned"


def test_a_planned_item_whose_plan_is_gone_is_ready_again(store: InMemoryRoadmapStore) -> None:
    number = _job_item(store, "Planned")

    sync_statuses(store, repo=STAGE_REPO, planned=NO_PLANS)

    assert _status(store, number) == "Ready"


def test_an_item_that_a_job_holds_is_in_progress(store: InMemoryRoadmapStore) -> None:
    number = _job_item(store, "Planned", implement_job="devops-cli-runner-1")

    sync_statuses(store, repo=STAGE_REPO, planned=_plans(number))

    assert _status(store, number) == "In Progress"


def test_an_item_whose_job_was_reported_is_not_held(store: InMemoryRoadmapStore) -> None:
    number = _job_item(
        store, "Planned", implement_job="devops-cli-runner-1", implement_job_state="failed"
    )

    synced = sync_statuses(store, repo=STAGE_REPO, planned=_plans(number))

    assert (synced.changed, _status(store, number)) == ((), "Planned")


@pytest.mark.parametrize(("draft", "status"), [(False, "In Review"), (True, "Planned")])
def test_the_pull_request_of_the_delivery_decides_in_review(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, draft: bool, status: str
) -> None:
    number = _job_item(store, "Planned", implement_pr=str(DELIVERY_PULL))
    _pull(github_api, draft=draft)

    sync_statuses(store, repo=STAGE_REPO, planned=_plans(number))

    assert _status(store, number) == status


def test_a_stopped_item_or_a_running_job_costs_no_pull_request_read(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake
) -> None:
    stopped = _job_item(store, "Planned", implement_pr="9", implement_stopped="group 1")
    running = _job_item(store, "Planned", implement_pr="9", implement_job="devops-cli-runner-1")

    sync_statuses(store, repo=STAGE_REPO, planned=_plans(stopped, running))

    assert (github_api.requested, _status(store, stopped), _status(store, running)) == (
        [],
        "Planned",
        "In Progress",
    )


@pytest.mark.parametrize("status", ["New", "In Progress", "In Review", "Blocked"])
def test_an_item_in_another_status_is_never_written(
    store: InMemoryRoadmapStore, status: str
) -> None:
    number = _job_item(store, status)

    synced = sync_statuses(store, repo=STAGE_REPO, planned=_plans(number))

    assert (synced.changed, _status(store, number)) == ((), status)


def test_a_closed_item_is_never_written(store: InMemoryRoadmapStore) -> None:
    number = _job_item(store, "Ready")
    store.close_by_hand(number, CloseReason.COMPLETED)

    synced = sync_statuses(store, repo=STAGE_REPO, planned=_plans(number))

    assert synced.changed == ()


def test_a_label_that_a_person_set_is_not_reverted(store: InMemoryRoadmapStore) -> None:
    """A job recorded Planned. A person then set `status/ready`: the label no longer is what a job
    wrote, so the plan on the default branch does not turn it back."""
    number = _job_item(store, "Planned")
    store.remove_label(number, "status/planned")
    store.add_label(number, "status/ready")

    synced = sync_statuses(store, repo=STAGE_REPO, planned=_plans(number))

    assert (synced.changed, _status(store, number)) == ((), "Ready")


def test_a_label_that_a_person_added_next_to_the_recorded_one_stays(
    store: InMemoryRoadmapStore,
) -> None:
    number = _job_item(store, "Ready")
    store.add_label(number, "status/in-progress")

    synced = sync_statuses(store, repo=STAGE_REPO, planned=_plans(number))

    assert (synced.changed, _status(store, number)) == ((), "In Progress")


def test_an_item_that_no_job_ever_labeled_is_left_alone(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue(
        "fix(cli): one", fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "Ready"}
    )

    synced = sync_statuses(store, repo=STAGE_REPO, planned=_plans(number))

    assert (synced.changed, _status(store, number)) == ((), "Ready")


def test_a_change_of_a_person_between_the_read_and_the_write_raises(
    store: InMemoryRoadmapStore,
) -> None:
    number = _job_item(store, "Ready")
    read = _item(store, number)
    store.remove_label(number, "status/ready")
    store.add_label(number, "status/blocked")

    with pytest.raises(RoadmapItemChangedError) as raised:
        sync_status(store, read, StatusFacts(plan_merged=True))

    assert ("Blocked" in str(raised.value), _status(store, number)) == (True, "Blocked")


def test_one_item_that_fails_does_not_stop_the_others(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake
) -> None:
    broken = _job_item(store, "Planned", implement_pr="8")
    fine = _job_item(store, "Ready")

    synced = sync_statuses(store, repo=STAGE_REPO, planned=_plans(broken, fine))

    assert (synced.changed, [failure.number for failure in synced.failed]) == ((fine,), [broken])


def test_a_rate_limit_stops_the_sweep(
    store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.github.client import GitHubClient

    for _ in range(2):
        _job_item(store, "Planned", implement_pr="9")
    read: list[int] = []

    def refuse(self: GitHubClient, repo: str, number: int) -> None:
        read.append(number)
        raise GitHubRateLimitError("No requests are left.", operation="roadmap.read")

    monkeypatch.setattr(GitHubClient, "get_pull_status", refuse)

    with pytest.raises(GitHubRateLimitError, match="No requests are left"):
        sync_statuses(store, repo=STAGE_REPO, planned=NO_PLANS)

    assert len(read) == 1


def test_a_round_with_nothing_to_write_sends_no_request(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake
) -> None:
    ready = _job_item(store, "Ready")

    synced = sync_statuses(store, repo=STAGE_REPO, planned=NO_PLANS)

    assert (synced.changed, github_api.requested, _status(store, ready)) == ((), [], "Ready")


def test_the_facts_of_a_merged_plan_pull_request(store: InMemoryRoadmapStore) -> None:
    number = _job_item(store, "Ready")

    facts = facts_of(_item(store, number), repo=STAGE_REPO, plan_merged=True)

    assert facts == StatusFacts(plan_merged=True)
