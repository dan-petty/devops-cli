"""The wait on a person: what gives the item a new look, and the bounds of the check (#1335). A wait
that older rules set gets one new look (#4795)."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest

from devops_cli.config import constants
from devops_cli.roadmap.body_hash import hash_text
from devops_cli.roadmap.refine.refine import (
    apply_refine,
    plan_refine,
    select_candidates,
)
from devops_cli.roadmap.stores.store import (
    CloseReason,
    RefineRecordKey,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    CITED_PATH,
    QUESTION,
    READY,
    REFINE_MARKER,
    REPO,
    BodyReadCountingStore,
    refine_round,
    require_item,
    seed_item,
    seed_person_wait,
    stage_returns,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_a_person_wait_whose_question_names_an_issue_that_closed_after_it_gets_a_new_look(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    store.seed_visibility(is_private=True)
    named = seed_item(store, "In Progress", "P1-High")
    number = seed_person_wait(store, f"Does the work of #{named} cover this item?")
    model_fake.answer(READY)
    waiting = plan_refine(store, repo=REPO, source=git_repo)
    store.as_actor("alice").close_by_hand(named, CloseReason.COMPLETED)

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [w.item.number for w in waiting.waiting_items if w.item.number == number],
        [r.item.number for r in again.refined_items],
    ) == ([number], [number])


def test_a_person_wait_ends_when_an_issue_that_a_reply_the_round_read_names_closes(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The questions of refine may name no issue, while the comment of a person that the round
    read does: the wait text holds both."""
    store.seed_visibility(is_private=True)
    named = seed_item(store, "In Progress", "P1-High")
    number = seed_item(store, "New", "P1-High")
    store.set_marks(
        require_item(store, number),
        {
            RefineRecordKey.BODY_HASH: hash_text(require_item(store, number).body),
            RefineRecordKey.NEXT_STEP: "person",
        },
    )
    store.as_actor("alice").comment(number, f"This waits for #{named}.")
    store.seed_comment(number, f"{REFINE_MARKER}\nA person answers these questions.")
    model_fake.answer(READY)
    waiting = plan_refine(store, repo=REPO, source=git_repo)
    store.as_actor("alice").close_by_hand(named, CloseReason.COMPLETED)

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [w.item.number for w in waiting.waiting_items],
        [r.item.number for r in again.refined_items],
    ) == ([number], [number])


@pytest.mark.parametrize("closes_after", [False, True], ids=["closed-before", "other-repository"])
def test_a_person_wait_keeps_waiting_when_the_issue_it_names_is_no_new_cause(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, closes_after: bool
) -> None:
    """An issue that closed before the wait began is no cause that ended, and the number of an
    issue of another repository names no issue of this one."""
    store.seed_visibility(is_private=True)
    named = seed_item(store, "In Progress", "P1-High")
    person = store.as_actor("alice")
    if not closes_after:
        person.close_by_hand(named, CloseReason.COMPLETED)
    reference = f"other/repo#{named}" if closes_after else f"#{named}"
    number = seed_person_wait(store, f"Does the work of {reference} cover this item?")
    if closes_after:
        person.close_by_hand(named, CloseReason.COMPLETED)
    calls = model_fake.call_count

    plan = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [w.item.number for w in plan.waiting_items],
        plan.refined_items,
        model_fake.call_count - calls,
    ) == ([number], [], 0)


def test_a_person_wait_whose_text_names_a_path_that_changed_gets_a_new_look_with_no_block_paths(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    store.seed_visibility(is_private=True)
    number = seed_person_wait(store, f"Should `{CITED_PATH}:2` return a name?", paths=None)
    model_fake.answer(READY)
    store.seed_commit("src/other.py", at=datetime.now(UTC) + timedelta(minutes=5))
    unchanged = plan_refine(store, repo=REPO, source=git_repo)
    store.seed_commit(CITED_PATH, at=datetime.now(UTC) + timedelta(minutes=5))

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [w.item.number for w in unchanged.waiting_items],
        [r.item.number for r in again.refined_items],
    ) == ([number], [number])


def test_a_round_gives_no_more_new_looks_than_its_limit(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """Four items that the stage job returned, and a limit of two: the round refines two and
    makes two model calls. The others wait for a later round."""
    store.seed_visibility(is_private=True)
    for _ in range(4):
        seed_item(store, "New", "P1-High")
    model_fake.answer(READY)
    apply_refine(store, plan_refine(store, repo=REPO, source=git_repo, limit=10))
    for item in store.open_items():
        stage_returns(store, item.number)
    calls = model_fake.call_count

    limited = plan_refine(store, repo=REPO, source=git_repo, limit=2)

    assert (len(limited.refined_items), model_fake.call_count - calls) == (2, 2)


def test_the_check_of_a_wait_text_reads_at_most_the_bound_of_issues_and_of_paths(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """A wait text that names twelve issues and twelve paths costs the bound of reads for each."""
    store.seed_visibility(is_private=True)
    named = [seed_item(store, "In Progress", "P1-High") for _ in range(12)]
    paths = [f"src/gone_{index}.py" for index in range(12)]
    text = " ".join([*(f"#{number}" for number in named), *(f"`{path}`" for path in paths)])
    number = seed_person_wait(store, text)
    store.reads.clear()

    _, waiting = select_candidates(store, limit=3)

    bound = constants.CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS
    assert (
        [w.item.number for w in waiting if w.item.number == number],
        dict(Counter(store.reads)),
    ) == (
        [number],
        {"item": bound, "path_changed_at": bound},
    )


# ── A wait that older rules set gets one new look (#4795) ─────────────────────────────────

_DAY_BEFORE = timedelta(days=-1)
_HOUR_AFTER = timedelta(hours=1)


def _wait_set_at(commented: timedelta, rules: timedelta | None) -> tuple[InMemoryRoadmapStore, int]:
    """A New item that waits on a person since refine's comment at `commented` from the time of the
    current rules, whose job record holds the rules of `rules` from that time as the version of the
    rules of that round, or no version, as a round wrote it before rounds recorded one. The clock
    of the roadmap then reads now."""
    current = constants.CONST_ROADMAP_REFINE_RULES_SINCE
    clock = [current + commented]
    store = BodyReadCountingStore(repo=REPO, clock=lambda: clock[0])
    store.seed_visibility(is_private=True)
    number = seed_person_wait(store, "Which store holds the record?")
    if rules is not None:
        version = (current + rules).isoformat()
        store.set_marks(require_item(store, number), {RefineRecordKey.RULES: version})
    clock[0] = datetime.now(UTC)
    return store, number


@pytest.mark.parametrize(
    ("commented", "rules"),
    [(_DAY_BEFORE, None), (_HOUR_AFTER, _DAY_BEFORE)],
    ids=["comment-before-the-rules", "older-recorded-rules"],
)
def test_a_person_wait_that_older_rules_set_gets_one_new_look_on_an_unchanged_body(
    git_repo: Path, model_fake: ModelFake, commented: timedelta, rules: timedelta | None
) -> None:
    """A rule that changed since the round that left the wait could set another step. The next
    round refines the item once and records the current rules. When the new proposal asks a
    person again, a round after it leaves the item in its wait with no model call."""
    store, number = _wait_set_at(commented, rules)
    model_fake.answer(QUESTION)
    first = refine_round(store, git_repo)
    calls = model_fake.call_count

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [r.item.number for r in first.refined_items],
        require_item(store, number).job_record.get(RefineRecordKey.RULES),
        [(w.item.number, w.step.value) for w in again.waiting_items],
        model_fake.call_count - calls,
    ) == (
        [number],
        constants.CONST_ROADMAP_REFINE_RULES_SINCE.isoformat(),
        [(number, "person")],
        0,
    )


@pytest.mark.parametrize(
    ("commented", "rules"),
    [(_HOUR_AFTER, None), (_DAY_BEFORE, timedelta(0))],
    ids=["comment-after-the-rules", "current-recorded-rules"],
)
def test_a_person_wait_that_the_current_rules_set_gets_no_new_look(
    git_repo: Path, model_fake: ModelFake, commented: timedelta, rules: timedelta | None
) -> None:
    """The version that the job record holds counts before the time of refine's comment."""
    store, number = _wait_set_at(commented, rules)
    calls = model_fake.call_count

    plan = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [(w.item.number, w.step.value) for w in plan.waiting_items],
        plan.refined_items,
        model_fake.call_count - calls,
    ) == ([(number, "person")], [], 0)


@pytest.mark.parametrize("no_zone", [False, True], ids=["no-time", "no-zone"])
def test_a_recorded_version_that_is_no_time_counts_as_none_and_one_with_no_zone_as_utc(
    git_repo: Path, model_fake: ModelFake, caplog: pytest.LogCaptureFixture, no_zone: bool
) -> None:
    """A hand edit of the job record can write a version that is no time, which gives way to the
    time of refine's comment with a warning, or a time with no zone, which is a UTC time. Both
    waits here are older than the rules."""
    older = constants.CONST_ROADMAP_REFINE_RULES_SINCE + _DAY_BEFORE
    store, number = _wait_set_at(_HOUR_AFTER if no_zone else _DAY_BEFORE, None)
    version = older.replace(tzinfo=None).isoformat() if no_zone else "not a time"
    store.set_marks(require_item(store, number), {RefineRecordKey.RULES: version})
    model_fake.answer(READY)

    plan = plan_refine(store, repo=REPO, source=git_repo)

    warned = f"The rules version recorded on #{number} is not a time."
    assert (
        [r.item.number for r in plan.refined_items],
        [r.getMessage() for r in caplog.records if r.getMessage() == warned],
    ) == ([number], [] if no_zone else [warned])
