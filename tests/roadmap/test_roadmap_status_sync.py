"""The Service sets the Status label of an item from its job record (#2920).

One pure function derives the Status. The sweep writes it with the family replace of the store, and
only for an open item that holds Ready or Planned with the label that a job last wrote. The roadmap
is in memory. The function derives Blocked from a stop on record. The runner Job and
`devops pr ready` set In Review, so the function does not derive it. A sweep never writes a Blocked
item: only the clear rules of the row `implement` do (`stop_clear.py`).
"""

from __future__ import annotations

import pytest

from devops_cli.exceptions import GitHubOperationError, GitHubRateLimitError
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
        (StatusFacts(stopped=True), "Blocked"),
        (StatusFacts(plan_merged=True, stopped=True), "Blocked"),
        (StatusFacts(plan_merged=True, job_active=True, stopped=True), "In Progress"),
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


def test_a_ready_item_with_a_stop_on_record_becomes_blocked(store: InMemoryRoadmapStore) -> None:
    number = _job_item(store, "Ready", implement_stopped="group 1")

    synced = sync_statuses(store, repo=STAGE_REPO, planned=NO_PLANS)

    assert (synced.changed, _status(store, number)) == ((number,), "Blocked")


def test_a_planned_item_with_a_stop_on_record_becomes_blocked(
    store: InMemoryRoadmapStore,
) -> None:
    number = _job_item(store, "Planned", implement_stopped="job")

    sync_statuses(store, repo=STAGE_REPO, planned=_plans(number))

    assert _status(store, number) == "Blocked"


def test_a_blocked_item_with_a_stop_on_record_is_not_written(
    store: InMemoryRoadmapStore,
) -> None:
    number = _job_item(store, "Blocked", implement_stopped="group 1")

    synced = sync_statuses(store, repo=STAGE_REPO, planned=_plans(number))

    assert (synced.changed, _status(store, number)) == ((), "Blocked")


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

    assert (synced.changed, synced.failed, _status(store, number)) == ((), (), "Ready")


def test_a_label_that_a_person_added_next_to_the_recorded_one_stays(
    store: InMemoryRoadmapStore,
) -> None:
    number = _job_item(store, "Ready")
    store.add_label(number, "status/in-progress")

    synced = sync_statuses(store, repo=STAGE_REPO, planned=_plans(number))

    assert (synced.changed, synced.failed, _status(store, number)) == ((), (), "In Progress")


def test_an_item_that_no_job_ever_labeled_is_left_alone(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue(
        "fix(cli): one", fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "Ready"}
    )

    synced = sync_statuses(store, repo=STAGE_REPO, planned=_plans(number))

    assert (synced.changed, synced.failed, _status(store, number)) == ((), (), "Ready")


def test_a_change_of_a_person_after_the_cached_read_is_not_written_over(
    store: InMemoryRoadmapStore,
) -> None:
    """The sweep reads the issue again before it writes. A label that a person set since the
    cached read stays, and the sweep reports no failure."""
    number = _job_item(store, "Ready")
    cached = _item(store, number)
    store.remove_label(number, "status/ready")
    store.add_label(number, "status/blocked")

    written = sync_status(store, cached, StatusFacts(plan_merged=True))

    assert (written, _status(store, number)) == (None, "Blocked")


def test_a_write_of_another_lane_after_the_cached_read_is_not_written_over(
    store: InMemoryRoadmapStore,
) -> None:
    """The model lane reads its items before a model run of minutes. The status lane may mark a
    Job in the meantime. The stale view neither fails nor turns In Progress back to Planned."""
    number = _job_item(store, "Ready")
    cached = _item(store, number)
    store.remove_label(number, "status/ready")
    store.add_label(number, "status/in-progress")

    written = sync_status(store, cached, StatusFacts(plan_merged=True))

    assert (written, _status(store, number)) == (None, "In Progress")


def test_an_issue_that_closed_after_the_cached_read_gets_no_label(
    store: InMemoryRoadmapStore,
) -> None:
    """The workflow `clear-status` removes the labels when an issue closes. A write from a view
    that is older than the close would leave a label on a closed issue."""
    number = _job_item(store, "Ready")
    cached = _item(store, number)
    store.close_by_hand(number, CloseReason.COMPLETED)

    written = sync_status(store, cached, StatusFacts(plan_merged=True))

    assert (written, _status(store, number)) == (None, "Ready")


def test_one_item_that_fails_does_not_stop_the_others(
    store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = _job_item(store, "Planned")
    fine = _job_item(store, "Ready")
    write = InMemoryRoadmapStore.set_field

    def refuse(self: InMemoryRoadmapStore, item: Item, *args: object, **kwargs: object) -> None:
        if item.number == broken:
            raise GitHubOperationError("The write failed.", operation="roadmap.item.set_field")
        write(self, item, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(InMemoryRoadmapStore, "set_field", refuse)

    synced = sync_statuses(store, repo=STAGE_REPO, planned=_plans(fine))

    assert (synced.changed, [failure.number for failure in synced.failed]) == ((fine,), [broken])


def test_a_rate_limit_stops_the_sweep(
    store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    for _ in range(2):
        _job_item(store, "Ready")
    written: list[int] = []

    def refuse(self: InMemoryRoadmapStore, item: Item, *args: object, **kwargs: object) -> None:
        written.append(item.number)
        raise GitHubRateLimitError("No requests are left.", operation="roadmap.write")

    monkeypatch.setattr(InMemoryRoadmapStore, "set_field", refuse)

    with pytest.raises(GitHubRateLimitError, match="No requests are left"):
        sync_statuses(store, repo=STAGE_REPO, planned=_plans(1, 2))

    assert len(written) == 1


def test_a_sweep_sends_no_request_to_github_but_the_label_writes(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake
) -> None:
    ready = _job_item(store, "Ready")
    planned = _job_item(store, "Ready", implement_pr=str(DELIVERY_PULL))

    synced = sync_statuses(store, repo=STAGE_REPO, planned=_plans(planned))

    assert (synced.changed, github_api.requested, _status(store, ready)) == (
        (planned,),
        [],
        "Ready",
    )


def test_the_facts_of_an_item_with_a_merged_plan_and_no_job(store: InMemoryRoadmapStore) -> None:
    number = _job_item(store, "Ready")

    facts = facts_of(_item(store, number), plan_merged=True)

    assert facts == StatusFacts(plan_merged=True)


def test_the_facts_of_an_item_that_a_job_holds(store: InMemoryRoadmapStore) -> None:
    number = _job_item(store, "Planned", implement_job="devops-cli-runner-1")

    facts = facts_of(_item(store, number), plan_merged=True)

    assert facts == StatusFacts(plan_merged=True, job_active=True)


def test_the_facts_of_an_item_with_a_stop_on_record(store: InMemoryRoadmapStore) -> None:
    number = _job_item(store, "Ready", implement_stopped="group 2")

    facts = facts_of(_item(store, number), plan_merged=False)

    assert facts == StatusFacts(stopped=True)
