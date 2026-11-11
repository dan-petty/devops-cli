"""Refine records the class, the step and the time of a failed model call in the job record, and
the selection leaves the item out until the wait of its class has passed (#4061).

A timeout or a dropped stream is class `provider` and waits 1 hour. A reply that never validates
is class `parser` and waits 6 hours. The item is not marked as at fault for a failure that its text
did not cause. A success clears the three keys. `--item` overrules the wait.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx2
import pytest

from devops_cli.ai.client.models import (
    AIClientError,
    ReplyRejectedError,
    StructuredOutputValidationError,
)
from devops_cli.roadmap.failure import FailureClass, StepName, failure_class_of
from devops_cli.roadmap.refine.refine import (
    RefineFailure,
    RefinementProposal,
    RefinePlan,
    apply_refine,
    plan_refine,
    refine_left_out,
    select_candidates,
)
from devops_cli.roadmap.stores.store import RefineRecordKey
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    GATEWAY_ATTEMPTS,
    NO_OPEN_TOOL,
    REPO,
    SCHEMA_MISS,
    Answer,
    MockLLMClient,
    refine_round,
    requests_per_item,
    require_item,
    seed_new_items,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

START = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
MINUTE = timedelta(minutes=1)
HOUR = timedelta(hours=1)
TIMEOUT = httpx2.Response(504, text="Gateway Timeout")


@pytest.fixture(autouse=True)
def _time_stands_still_at_start(clock: ClockFake) -> None:
    """Build on the shared `clock` fixture: do not shadow it, or the retry waits of the model
    client run for real (#4459). The wall clock reads `START` until a test or a wait moves it."""
    clock.move_to(START)


def _waited(clock: ClockFake) -> timedelta:
    """The time the retry waits of the rounds so far moved the clock. A failure is recorded after
    its retries, so its time is `START` plus this wait plus the shifts of the test."""
    return timedelta(seconds=sum(clock.waits))


def _marks(store: InMemoryRoadmapStore, number: int) -> tuple[str | None, ...]:
    """The time, the step and the class of the last failure in the job record of issue `number`."""
    record = require_item(store, number).job_record
    return tuple(
        record.get(key)
        for key in (
            RefineRecordKey.FAILED_AT,
            RefineRecordKey.FAILED_STEP,
            RefineRecordKey.FAILED_CLASS,
        )
    )


def test_the_keys_and_the_steps_have_the_names_the_record_uses() -> None:
    assert (
        RefineRecordKey.FAILED_AT.value,
        RefineRecordKey.FAILED_STEP.value,
        RefineRecordKey.FAILED_CLASS.value,
        StepName.INVESTIGATE.value,
    ) == ("refine.failed_at", "refine.failed_step", "refine.failed_class", "investigate")


@pytest.mark.parametrize(
    ("error", "klass"),
    [
        pytest.param(AIClientError("timed out"), FailureClass.PROVIDER, id="transport"),
        pytest.param(
            StructuredOutputValidationError("never valid", violations=2),
            FailureClass.PARSER,
            id="schema",
        ),
        pytest.param(
            ReplyRejectedError("refused", reply="x"),
            failure_class_of(ReplyRejectedError("refused", reply="x")),
            id="rejected",
        ),
    ],
)
def test_a_refine_failure_takes_its_class_from_the_error_by_the_one_table(
    store: InMemoryRoadmapStore, error: AIClientError, klass: FailureClass
) -> None:
    (item,) = (require_item(store, number) for number in seed_new_items(store, ("P1-High",)))

    assert RefineFailure.of(item, error).failure_class is klass


def test_a_timeout_records_class_step_and_time_and_does_not_mark_the_item_as_at_fault(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    clock: ClockFake,
) -> None:
    """The three keys ride on one marks write, the plan says it has a write, and the item holds no
    failed body hash: the timeout says nothing about its text (#1526)."""
    (first,) = seed_new_items(store, ("P1-High",))
    scripted_gateway({first: TIMEOUT})
    before = store.writes.count("set_marks")

    plan = refine_round(store, git_repo)

    assert (
        plan.has_writes,
        _marks(store, first),
        require_item(store, first).job_record.get(RefineRecordKey.FAILED_BODY_HASH),
        store.writes.count("set_marks") - before,
        bool(clock.waits),
    ) == (True, ((START + _waited(clock)).isoformat(), "investigate", "provider"), None, 1, True)


def test_the_next_round_skips_the_item_until_the_time_passes_and_takes_the_others(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    clock: ClockFake,
) -> None:
    """A provider failure waits 1 hour: 59 minutes later the round sends no request for the item
    and lists it as waiting to retry, and at 1 hour the round takes it again."""
    first, second, third = seed_new_items(store)
    sent = scripted_gateway({first: TIMEOUT})
    refine_round(store, git_repo)

    clock.shift(59 * MINUTE)
    early = refine_round(store, git_repo)
    after_early = requests_per_item(sent)
    clock.shift(MINUTE)
    late = refine_round(store, git_repo)

    assert (
        after_early,
        [(w.item.number, w.step) for w in early.waiting_items if w.item.number == first],
        early.failed_items,
        [failure.item.number for failure in late.failed_items],
        requests_per_item(sent)[first],
        _marks(store, first),
    ) == (
        {first: GATEWAY_ATTEMPTS, second: 1, third: 1},
        [(first, "retry")],
        [],
        [first],
        2 * GATEWAY_ATTEMPTS,
        ((START + HOUR + _waited(clock)).isoformat(), "investigate", "provider"),
    )


def test_a_success_clears_the_three_keys(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    clock: ClockFake,
) -> None:
    (first,) = seed_new_items(store, ("P1-High",))
    answers: dict[int | None, Answer] = {first: TIMEOUT}
    scripted_gateway(answers)
    refine_round(store, git_repo)
    failed = _marks(store, first)
    failed_at = START + _waited(clock)
    del answers[first]
    clock.shift(2 * HOUR)

    refine_round(store, git_repo)

    assert (failed, _marks(store, first), require_item(store, first).status) == (
        (failed_at.isoformat(), "investigate", "provider"),
        (None, None, None),
        "Ready",
    )


def test_a_reply_that_never_validates_waits_six_hours_and_the_marks_ride_on_one_write(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    clock: ClockFake,
) -> None:
    """The failure that the item's text caused records the failed body hash and the three keys in
    one write, and the second try waits for the 6 hours of class `parser`."""
    (first,) = seed_new_items(store, ("P1-High",))
    sent = scripted_gateway({first: SCHEMA_MISS})
    before = store.writes.count("set_marks")
    refine_round(store, git_repo)
    recorded = (
        _marks(store, first),
        require_item(store, first).job_record.get(RefineRecordKey.FAILED_BODY_HASH) is not None,
        store.writes.count("set_marks") - before,
    )
    asked = len(sent)
    failed_at = START + _waited(clock)

    clock.shift(6 * HOUR - MINUTE)
    refine_round(store, git_repo)
    held = len(sent) - asked
    clock.shift(MINUTE)
    refine_round(store, git_repo)

    assert (recorded, held, len(sent) > asked) == (
        ((failed_at.isoformat(), "investigate", "parser"), True, 1),
        0,
        True,
    )


def test_the_second_failure_on_the_same_body_hands_the_wait_to_the_body_edit(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    clock: ClockFake,
) -> None:
    """The second failure settles the item to wait on an edit, so the three keys are cleared and
    only a person's edit ends the wait (#1526)."""
    (first,) = seed_new_items(store, ("P1-High",))
    scripted_gateway({first: SCHEMA_MISS})
    refine_round(store, git_repo)
    clock.shift(6 * HOUR)
    refine_round(store, git_repo)

    record = require_item(store, first).job_record
    assert (_marks(store, first), record.get(RefineRecordKey.NEXT_STEP)) == (
        (None, None, None),
        "edit",
    )


def test_a_body_edit_ends_the_wait_after_a_failure_that_the_text_caused(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    clock: ClockFake,
) -> None:
    (first,) = seed_new_items(store, ("P1-High",))
    scripted_gateway({first: SCHEMA_MISS})
    refine_round(store, git_repo)
    recorded = _marks(store, first)[2]
    clock.shift(HOUR)
    store.as_actor("alice").write_issue_body(first, "Body P1-High, edited")

    plan = plan_refine(store, repo=REPO, source=git_repo)

    assert (recorded, [failure.item.number for failure in plan.failed_items]) == ("parser", [first])


@pytest.mark.parametrize(
    ("failed_class", "ago", "taken"),
    [
        pytest.param("provider", 59 * MINUTE, False, id="provider-before-1h"),
        pytest.param("provider", HOUR, True, id="provider-at-1h"),
        pytest.param("ci_infra", 59 * MINUTE, False, id="ci_infra-before-1h"),
        pytest.param("parser", 5 * HOUR, False, id="parser-before-6h"),
        pytest.param("parser", 6 * HOUR, True, id="parser-at-6h"),
        pytest.param("plan_defect", 5 * HOUR, False, id="plan_defect-before-6h"),
        pytest.param("head_moved", timedelta(0), True, id="head_moved-no-wait"),
        pytest.param(None, 59 * MINUTE, False, id="no-class-waits-as-ci_infra"),
        pytest.param(None, HOUR, True, id="no-class-after-1h"),
        pytest.param("not_a_class", 59 * MINUTE, False, id="unknown-class-waits-as-ci_infra"),
        pytest.param("timeout", 59 * MINUTE, False, id="class-with-no-wait-waits-as-ci_infra"),
    ],
)
def test_the_wait_follows_the_recorded_class(
    store: InMemoryRoadmapStore,
    clock: ClockFake,
    failed_class: str | None,
    ago: timedelta,
    taken: bool,
) -> None:
    (first,) = seed_new_items(store, ("P1-High",))
    marks = {RefineRecordKey.FAILED_AT: (START - ago).isoformat()}
    if failed_class is not None:
        marks[RefineRecordKey.FAILED_CLASS] = failed_class
    store.set_marks(require_item(store, first), marks)

    selected, waiting = select_candidates(store)

    assert ([item.number for item in selected], [w.item.number for w in waiting]) == (
        ([first], []) if taken else ([], [first])
    )


def test_a_failure_time_that_is_no_time_holds_the_item_for_no_time(
    store: InMemoryRoadmapStore, clock: ClockFake
) -> None:
    (first,) = seed_new_items(store, ("P1-High",))
    store.set_marks(
        require_item(store, first),
        {RefineRecordKey.FAILED_AT: "not a time", RefineRecordKey.FAILED_CLASS: "parser"},
    )

    selected, _ = select_candidates(store)

    assert [item.number for item in selected] == [first]


def test_item_option_overrules_the_wait(store: InMemoryRoadmapStore, clock: ClockFake) -> None:
    (first,) = seed_new_items(store, ("P1-High",))
    store.set_marks(
        require_item(store, first),
        {RefineRecordKey.FAILED_AT: START.isoformat(), RefineRecordKey.FAILED_CLASS: "parser"},
    )

    selected, waiting = select_candidates(store, item_number=first)

    assert ([item.number for item in selected], waiting) == ([first], [])


def test_explain_gives_the_time_after_which_refine_takes_the_item_again(
    store: InMemoryRoadmapStore, clock: ClockFake
) -> None:
    (first,) = seed_new_items(store, ("P1-High",))
    store.set_marks(
        require_item(store, first),
        {
            RefineRecordKey.FAILED_AT: START.isoformat(),
            RefineRecordKey.FAILED_CLASS: "provider",
        },
    )

    reason = refine_left_out(store, require_item(store, first))

    assert reason is not None
    assert "2026-11-08 13:00" in reason


def test_a_round_whose_model_call_worked_clears_the_keys_of_an_earlier_failure(
    git_repo: Path, store: InMemoryRoadmapStore, clock: ClockFake
) -> None:
    """A round that fails a form check made its model call, so the earlier timeout is over. The
    job failure records its own tries and the three keys are cleared."""
    (first,) = seed_new_items(store, ("P1-High",))
    store.set_marks(
        require_item(store, first),
        {
            RefineRecordKey.FAILED_AT: (START - 2 * HOUR).isoformat(),
            RefineRecordKey.FAILED_STEP: "investigate",
            RefineRecordKey.FAILED_CLASS: "provider",
        },
    )
    no_criterion = RefinementProposal(
        existing_tool=NO_OPEN_TOOL, problem_statement="The item needs a design."
    )
    model = MockLLMClient(proposal=no_criterion.model_copy(update={"acceptance_criteria": []}))

    plan = plan_refine(store, repo=REPO, source=git_repo, model=model)
    apply_refine(store, plan)

    record = require_item(store, first).job_record
    assert (_marks(store, first), record.get(RefineRecordKey.TRIES)) == ((None, None, None), "1")


def test_a_placeholder_failure_still_records_nothing(
    store: InMemoryRoadmapStore, clock: ClockFake
) -> None:
    """A placeholder reply is a fault of the model (#3478): the rule of no record stands, and the
    next round asks the model again."""
    (first,) = seed_new_items(store, ("P1-High",))
    item = require_item(store, first)
    failure = RefineFailure(
        item=item,
        error="StructuredOutputValidationError",
        violations=1,
        placeholder=True,
        failure_class=FailureClass.PARSER,
    )
    before = len(store.job_writes())

    apply_refine(store, RefinePlan(repo=REPO, failed_items=[failure]))

    assert (len(store.job_writes()) - before, _marks(store, first)) == (0, (None, None, None))
