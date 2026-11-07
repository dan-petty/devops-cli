"""The cap on the comments that refine leaves on one item in a window (#1335)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest

from devops_cli.config import constants
from devops_cli.roadmap.refine.refine import (
    apply_refine,
    plan_refine,
)
from devops_cli.roadmap.stores.store import (
    RefineRecordKey,
)
from devops_cli.telemetry.instruments import ROADMAP_REFINE_COMMENTS_CAPPED_TOTAL
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    READY,
    REPO,
    BodyReadCountingStore,
    refine_round,
    require_item,
    seed_item,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


# ── A cap on refine's comments on one item (#2475) ────────────────────────────────────────

_CAP = constants.CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM


_CAP_HOURS = constants.CONST_ROADMAP_REFINE_COMMENT_CAP_WINDOW_HOURS


def _echo_loop(store: InMemoryRoadmapStore, number: int) -> None:
    """Refine's cap of comments on item `number`, another bot's reply after each."""
    for _ in range(_CAP):
        store.comment(number, f"{constants.CONST_ROADMAP_REFINE_COMMENT_MARKER}\nA next step.")
        store.as_actor("echo-bot[bot]").comment(number, "A reply from another bot.")


def _capped_store(age: timedelta) -> tuple[BodyReadCountingStore, list[datetime]]:
    """An empty roadmap whose clock reads `age` ago until a test moves it."""
    when = [datetime.now(UTC) - age]
    store = BodyReadCountingStore(repo=REPO, clock=lambda: when[0])
    store.seed_visibility(is_private=True)
    return store, when


def _cap_detail(number: int) -> str:
    """The detail line of an item that the cap on refine's comments leaves alone."""
    return (
        f"Refine wrote {_CAP} comments on this item in the last {_CAP_HOURS} hours, which is its "
        f"limit. A round after the oldest of these comments is {_CAP_HOURS} hours old looks at "
        f"the item again. A person refines it now with --item {number}."
    )


def _cap_warning(number: int) -> str:
    """The warning of a comment that the cap stopped."""
    return (
        f"Refine left #{number} alone and wrote no comment: it reached its limit of {_CAP} "
        f"comments on the item in {_CAP_HOURS} hours."
    )


def _refine_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == "devops_cli.roadmap.refine.refine"]


@pytest.mark.parametrize(
    ("age", "capped"),
    [(timedelta(hours=23), True), (timedelta(hours=25), False)],
    ids=["within-the-day", "older-than-the-day"],
)
def test_refine_leaves_an_item_it_commented_on_up_to_its_cap_in_24_hours_alone(
    git_repo: Path,
    model_fake: ModelFake,
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
    age: timedelta,
    capped: bool,
) -> None:
    """Another bot that replies to each refine comment would make refine refine the item, and
    comment on it, at each round. Once refine wrote its cap of comments on an item in the last 24
    hours, a round leaves the item waiting on a person: no model call and no comment, one
    warning, and one count of the comment that the cap stopped. Comments older than 24 hours do
    not count."""
    store, when = _capped_store(age)
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(READY)
    _echo_loop(store, number)
    when[0] = datetime.now(UTC)
    calls = model_fake.call_count

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.refine.refine"):
        plan = refine_round(store, git_repo)

    stopped = (
        [],
        [(number, "person", (_cap_detail(number),))],
        0,
        2 * _CAP,
        [({}, 1.0)],
        [_cap_warning(number)],
    )
    refined = ([(number, "ready")], [], 1, 2 * _CAP + 1, [], [])
    assert (
        [(r.item.number, r.next_step) for r in plan.refined_items],
        [(w.item.number, w.step, w.details) for w in plan.waiting_items],
        model_fake.call_count - calls,
        len(store.comments_on(number)),
        otlp.points(ROADMAP_REFINE_COMMENTS_CAPPED_TOTAL.name),
        _refine_warnings(caplog),
    ) == (stopped if capped else refined)


def test_items_at_the_comment_cap_take_no_place_under_the_limit(
    git_repo: Path, model_fake: ModelFake
) -> None:
    """Another bot answers each refine comment on as many items as a round takes. The cap
    leaves these items waiting on a person, and they take no place under the limit, so the
    round refines the next item and is not held for 24 hours."""
    store, when = _capped_store(timedelta(hours=1))
    capped = [seed_item(store, "New", "P0-Critical") for _ in range(3)]
    for number in capped:
        _echo_loop(store, number)
    other = seed_item(store, "New", "P1-High")
    when[0] = datetime.now(UTC)
    model_fake.answer(READY)

    plan = plan_refine(store, repo=REPO, source=git_repo, limit=3)

    assert (
        [r.item.number for r in plan.refined_items],
        [(w.item.number, w.step) for w in plan.waiting_items],
        model_fake.call_count,
    ) == ([other], [(number, "person") for number in capped], 1)


def test_the_cap_counts_and_logs_each_comment_it_stops_once(
    git_repo: Path,
    model_fake: ModelFake,
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The cap stops the comment that would answer the item's newest comment. The round records
    when that comment was made, so a later round that finds no newer comment leaves the item
    alone again with no write, no count and no warning: the count follows the stopped comments,
    not the rounds. A newer reply is a new comment that the cap stops, and counts once."""
    store, when = _capped_store(timedelta(hours=1))
    number = seed_item(store, "New", "P1-High")
    _echo_loop(store, number)
    when[0] = datetime.now(UTC)

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.refine.refine"):
        rounds = [refine_round(store, git_repo), refine_round(store, git_repo)]
        store.as_actor("a-person").comment(number, "A reply from a person.")
        rounds.append(refine_round(store, git_repo))

    comments = store.comments_on(number)
    assert (
        [[(w.item.number, w.step) for w in plan.waiting_items] for plan in rounds],
        [plan.has_writes for plan in rounds],
        model_fake.call_count,
        len(comments),
        otlp.points(ROADMAP_REFINE_COMMENTS_CAPPED_TOTAL.name),
        _refine_warnings(caplog),
        require_item(store, number).job_record.get(RefineRecordKey.CAPPED_AFTER),
    ) == (
        [[(number, "person")]] * 3,
        [True, False, True],
        0,
        2 * _CAP + 1,
        [({}, 2.0)],
        [_cap_warning(number)] * 2,
        comments[-1].created_at.isoformat(),
    )


def test_item_refines_an_item_at_the_comment_cap_since_a_person_asked_for_it(
    git_repo: Path, model_fake: ModelFake, otlp: FakeCollector
) -> None:
    """`--item` refines the item it names at the cap and posts its comment, since a person
    asked for it, and counts no stopped comment."""
    store, when = _capped_store(timedelta(hours=1))
    number = seed_item(store, "New", "P1-High")
    _echo_loop(store, number)
    when[0] = datetime.now(UTC)
    model_fake.answer(READY)

    plan = plan_refine(store, repo=REPO, source=git_repo, item_number=number)
    apply_refine(store, plan)

    assert (
        [r.item.number for r in plan.refined_items],
        len(store.comments_on(number)),
        otlp.points(ROADMAP_REFINE_COMMENTS_CAPPED_TOTAL.name),
    ) == ([number], 2 * _CAP + 1, [])
