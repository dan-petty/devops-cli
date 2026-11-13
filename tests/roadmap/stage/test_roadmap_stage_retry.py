"""The stage row holds a failed item in its job record and goes on with the others (#3493)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from devops_cli.roadmap import failure as failure_module
from devops_cli.roadmap.explain import JobVerdict, explain_item
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.implement.implement import parse_implement_filters
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.stage.stage import (
    StageApplied,
    StageFailure,
    StagePlan,
    parse_filters,
    select_stageable,
)
from devops_cli.roadmap.stores.store import ItemField, StageRecordKey
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_implement import JobWorld
from tests.support.roadmap_stage import STAGE_REPO, apply_stage, seed_stageable

pytestmark = pytest.mark.usefixtures("keyring_store")

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
# A record with no class waits as `ci_infra` (#4060); `_fail` writes no class.
RETRY = timedelta(hours=1)
NO_PLANS = PlannedChanges("main", {}, {})


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


def _fail(store: InMemoryRoadmapStore, number: int, *, ago: timedelta) -> None:
    """Record the failure of item `number` as the job does, `ago` before `NOW`."""
    item = store.item(number)
    assert item is not None
    store.set_marks(
        item,
        {
            StageRecordKey.FAILED_AT: (NOW - ago).isoformat(),
            StageRecordKey.FAILED_ERROR: "AIClientError",
        },
    )


def _taken(store: InMemoryRoadmapStore, *, item: int | None = None) -> tuple[list[int], dict]:
    selection = select_stageable(
        store,
        filters=parse_filters(()),
        holder_of=lambda _issue, _branch: None,
        planned=NO_PLANS,
        item_number=item,
        limit=5,
        planned_limit=20,
        now=NOW,
    )
    return (
        [target.item.number for target in selection.selected],
        {left.number: left.reason for left in selection.left_out},
    )


def test_a_failed_item_is_recorded_with_its_error_class_and_time(
    store: InMemoryRoadmapStore,
) -> None:
    number = seed_stageable(store)
    item = store.item(number)
    assert item is not None
    plan = StagePlan(
        STAGE_REPO,
        failed=(
            StageFailure(
                number,
                item.title,
                "StructuredOutputValidationError",
                "",
                item,
                failure_class=FailureClass.PARSER,
                step=failure_module.StepName.PLAN,
            ),
        ),
    )

    applied = apply_stage(store, plan, source=".", now=NOW)

    held = store.item(number)
    assert held is not None
    assert (applied, held.job_record[StageRecordKey.FAILED_AT]) == (
        StageApplied(),
        NOW.isoformat(),
    )
    assert held.job_record[StageRecordKey.FAILED_ERROR] == "StructuredOutputValidationError"


def test_the_job_takes_a_failed_item_again_only_after_the_retry_delay(
    store: InMemoryRoadmapStore,
) -> None:
    failed = seed_stageable(store)
    other = seed_stageable(store, "fix(roadmap): the job drops a label")
    _fail(store, failed, ago=RETRY - timedelta(minutes=1))

    before, reasons = _taken(store)
    _fail(store, failed, ago=RETRY)
    after, _ = _taken(store)

    assert (before, after) == ([other], [failed, other])
    assert "AIClientError" in reasons[failed]
    assert "2026-11-04 12:01 UTC" in reasons[failed]


def test_a_person_who_names_the_item_overrules_the_retry_delay(
    store: InMemoryRoadmapStore,
) -> None:
    number = seed_stageable(store)
    _fail(store, number, ago=timedelta(minutes=1))

    taken, _ = _taken(store, item=number)

    assert taken == [number]


def test_a_failure_time_that_is_no_time_holds_the_item_for_no_time(
    store: InMemoryRoadmapStore,
) -> None:
    number = seed_stageable(store)
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {StageRecordKey.FAILED_AT: "yesterday"})

    taken, _ = _taken(store)

    assert taken == [number]


def test_explain_reports_an_item_that_the_job_holds_from_the_record_on_github(
    job_world: JobWorld,
) -> None:
    number = job_world.store.seed_issue(
        "fix(roadmap): another job drops a label",
        body="The job drops a label.",
        labels=("type/bug", "effort/low"),
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
        author_association="OWNER",
    )
    held = job_world.store.item(number)
    assert held is not None
    failed_at = datetime.now(UTC) - timedelta(minutes=5)
    job_world.store.set_marks(
        held,
        {
            StageRecordKey.FAILED_AT: failed_at.isoformat(),
            StageRecordKey.FAILED_ERROR: "AIClientError",
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

    until = (failed_at + RETRY).astimezone(UTC).strftime("%Y-%m-%d %H:%M")
    assert explained.stage == JobVerdict(
        False,
        f"The last plan or write of the item failed (AIClientError). "
        f"The job takes the item again after {until} UTC.",
    )
