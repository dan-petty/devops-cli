"""The stage job takes a failed item again after a wait that its failure class sets (#4060).

A provider error and an error of the CI infrastructure wait 1 hour. A parser error and a refused
plan wait 6 hours. An item that changed while the job worked waits for no time. A record with no
class, or with a class that the job does not know, waits as `ci_infra`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from devops_cli.roadmap import failure as failure_module
from devops_cli.roadmap.explain import JobVerdict, explain_item
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.implement.implement import parse_implement_filters
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.stage.stage import parse_filters, select_stageable
from devops_cli.roadmap.stores.store import ItemField, StageRecordKey
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_implement import JobWorld
from tests.support.roadmap_stage import STAGE_REPO, seed_stageable

pytestmark = pytest.mark.usefixtures("keyring_store")

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
NO_PLANS = PlannedChanges("main", {}, {})
MINUTE = timedelta(minutes=1)
HOUR = timedelta(hours=1)

# The wait of each class, as the issue gives it. The tests hold these numbers apart from the table.
WAIT_OF = {
    FailureClass.PROVIDER: HOUR,
    FailureClass.PARSER: 6 * HOUR,
    FailureClass.PLAN_DEFECT: 6 * HOUR,
    FailureClass.CI_INFRA: HOUR,
    FailureClass.HEAD_MOVED: timedelta(0),
}


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


def _fail(
    store: InMemoryRoadmapStore, number: int, *, ago: timedelta, failure_class: str | None
) -> None:
    """Record the failure of item `number` as the job does, `ago` before `NOW`. A `failure_class`
    of None leaves the record as it was before the class existed."""
    item = store.item(number)
    assert item is not None
    marks = {
        StageRecordKey.FAILED_AT: (NOW - ago).isoformat(),
        StageRecordKey.FAILED_ERROR: "AIClientError",
    }
    if failure_class is not None:
        marks[StageRecordKey.FAILED_CLASS] = failure_class
    store.set_marks(item, marks)


def _selected(store: InMemoryRoadmapStore) -> list[int]:
    selection = select_stageable(
        store,
        filters=parse_filters(()),
        holder_of=lambda _issue, _branch: None,
        planned=NO_PLANS,
        item_number=None,
        limit=5,
        planned_limit=20,
        now=NOW,
    )
    return [target.item.number for target in selection.selected]


def _is_taken(store: InMemoryRoadmapStore, *, ago: timedelta, failure_class: str | None) -> bool:
    number = seed_stageable(store)
    _fail(store, number, ago=ago, failure_class=failure_class)
    return number in _selected(store)


@pytest.mark.parametrize("failure_class", list(WAIT_OF), ids=lambda klass: klass.value)
def test_a_failed_item_waits_for_the_time_of_its_class(failure_class: FailureClass) -> None:
    wait = WAIT_OF[failure_class]
    shortly_before = max(wait - MINUTE, timedelta(0))

    taken_before = _is_taken(
        InMemoryRoadmapStore(repo=STAGE_REPO),
        ago=shortly_before,
        failure_class=failure_class.value,
    )
    taken_at = _is_taken(
        InMemoryRoadmapStore(repo=STAGE_REPO), ago=wait, failure_class=failure_class.value
    )

    assert (taken_before, taken_at) == (wait == timedelta(0), True)


def test_a_provider_error_waits_one_hour_and_a_refused_plan_waits_six(
    store: InMemoryRoadmapStore,
) -> None:
    provider = seed_stageable(store, "fix(roadmap): the provider fails")
    refused = seed_stageable(store, "fix(roadmap): the plan is refused")
    _fail(store, provider, ago=HOUR, failure_class=FailureClass.PROVIDER.value)
    _fail(store, refused, ago=HOUR, failure_class=FailureClass.PLAN_DEFECT.value)

    assert _selected(store) == [provider]


def test_an_item_that_changed_while_the_job_worked_does_not_wait(
    store: InMemoryRoadmapStore,
) -> None:
    number = seed_stageable(store)
    _fail(store, number, ago=timedelta(0), failure_class=FailureClass.HEAD_MOVED.value)

    assert _selected(store) == [number]


def test_a_record_with_no_class_waits_as_ci_infra(store: InMemoryRoadmapStore) -> None:
    waits = seed_stageable(store, "fix(roadmap): a record with no class")
    taken = seed_stageable(store, "fix(roadmap): an old record")
    _fail(store, waits, ago=HOUR - MINUTE, failure_class=None)
    _fail(store, taken, ago=HOUR, failure_class=None)

    assert _selected(store) == [taken]


def test_a_record_with_a_class_that_is_unknown_waits_as_ci_infra(
    store: InMemoryRoadmapStore,
) -> None:
    waits = seed_stageable(store, "fix(roadmap): an unknown class")
    taken = seed_stageable(store, "fix(roadmap): another unknown class")
    _fail(store, waits, ago=HOUR - MINUTE, failure_class="no_such_class")
    _fail(store, taken, ago=HOUR, failure_class="no_such_class")

    assert _selected(store) == [taken]


def test_the_job_does_not_store_the_time_it_waits_until(store: InMemoryRoadmapStore) -> None:
    number = seed_stageable(store)
    _fail(store, number, ago=MINUTE, failure_class=FailureClass.PARSER.value)
    item = store.item(number)
    assert item is not None
    before = dict(item.job_record)

    _selected(store)

    held = store.item(number)
    assert held is not None
    assert held.job_record == before


def test_explain_gives_the_time_of_the_class_that_the_record_holds(job_world: JobWorld) -> None:
    number = job_world.store.seed_issue(
        "fix(roadmap): a plan the job refuses",
        body="The job refuses a plan.",
        labels=("type/bug", "effort/low"),
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
        author_association="OWNER",
    )
    held = job_world.store.item(number)
    assert held is not None
    failed_at = datetime.now(UTC) - 5 * MINUTE
    job_world.store.set_marks(
        held,
        {
            StageRecordKey.FAILED_AT: failed_at.isoformat(),
            StageRecordKey.FAILED_ERROR: "RoadmapStageError",
            StageRecordKey.FAILED_CLASS: FailureClass.PLAN_DEFECT.value,
        },
    )

    explained = explain_item(
        job_world.store,
        repo=STAGE_REPO,
        source=job_world.repo.clone,
        number=number,
        stage_filters=parse_filters(()),
        implement_filters=parse_implement_filters(()),
        stage_limit=3,
        implement_limit=1,
    )

    until = (failed_at + 6 * HOUR).astimezone(UTC).strftime("%Y-%m-%d %H:%M")
    assert explained.stage == JobVerdict(
        False,
        f"The last plan or write of the item failed (RoadmapStageError). "
        f"The job takes the item again after {until} UTC.",
    )


def test_the_wait_table_in_this_file_is_the_table_of_the_code() -> None:
    assert dict(failure_module.RETRY_AFTER) == WAIT_OF
