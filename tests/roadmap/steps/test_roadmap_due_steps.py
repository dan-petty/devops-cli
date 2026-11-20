"""Table tests for the pure function `due_steps(state)` (#5024).

Covers each verdict for a bot pull request and for a person's pull request.
"""

from __future__ import annotations

import pytest

from devops_cli.github.check_verdict import CheckBucket, PRCheckItem
from devops_cli.roadmap.steps.watch import (
    DueStep,
    PRVerdict,
    WatchState,
    WatchVerdict,
    due_steps,
    fix_checks_check,
    verdict,
)


def _passing_checks() -> list[PRCheckItem]:
    return [
        PRCheckItem(name="Tests & Coverage", bucket=CheckBucket.PASS, state="success"),
        PRCheckItem(name="Lint", bucket=CheckBucket.PASS, state="success"),
    ]


def _failing_checks(name: str = "Tests & Coverage") -> list[PRCheckItem]:
    return [
        PRCheckItem(name=name, bucket=CheckBucket.FAIL, state="failure"),
    ]


def _pending_checks() -> list[PRCheckItem]:
    return [
        PRCheckItem(name="Tests & Coverage", bucket=CheckBucket.PENDING, state="pending"),
    ]


@pytest.mark.parametrize(
    ("is_bot", "is_plan", "expected_steps"),
    [
        (True, False, (DueStep.READY,)),
        (True, True, (DueStep.READY,)),
        (False, False, ()),
        (False, True, ()),
    ],
)
def test_due_steps_ready(is_bot: bool, is_plan: bool, expected_steps: tuple[DueStep, ...]) -> None:
    """A READY verdict gives the ready step for bot PRs and nothing for person PRs."""
    state = WatchState(
        pull=101,
        head_sha="a" * 40,
        checks=_passing_checks(),
        is_bot=is_bot,
        is_plan=is_plan,
    )
    assert verdict(state) == WatchVerdict(verdict=PRVerdict.READY, reason="PR #101 is ready.")
    assert due_steps(state) == expected_steps


@pytest.mark.parametrize(
    ("is_bot", "delivery", "expected_steps"),
    [
        (True, True, (DueStep.STOP,)),
        (True, False, ()),
        (False, False, (DueStep.COMMENT_CONFLICT,)),
    ],
    ids=["delivery-draft", "bot", "person"],
)
def test_due_steps_conflict(
    is_bot: bool, delivery: bool, expected_steps: tuple[DueStep, ...]
) -> None:
    """A CONFLICT verdict gives one comment per head for person PRs, the stop of the item for a
    delivery draft, which no actor repairs (#6559), and nothing for another bot PR."""
    state = WatchState(
        pull=102,
        head_sha="b" * 40,
        mergeable=False,
        mergeable_state="dirty",
        checks=_passing_checks(),
        is_bot=is_bot,
        delivery=delivery,
    )
    assert verdict(state) == WatchVerdict(
        verdict=PRVerdict.CONFLICT,
        reason="PR #102 has merge conflicts with base branch 'main'.",
    )
    assert due_steps(state) == expected_steps


@pytest.mark.parametrize(
    ("is_bot", "check_name", "expected_steps"),
    [
        (True, "Tests & Coverage", (DueStep.FIX_CHECKS,)),
        (True, "Static Analysis", (DueStep.FIX_CHECKS,)),
        (True, "ci-infra-check", ()),
        (True, "Semantic PR title", ()),
        (False, "Tests & Coverage", ()),
        (False, "ci-infra-check", ()),
    ],
)
def test_due_steps_failed(
    is_bot: bool, check_name: str, expected_steps: tuple[DueStep, ...]
) -> None:
    """FAILED verdict gives fix_checks for a bot PR whose check failed with the class test, lint,
    types or plan check (#5027), and nothing for a CI_INFRA failure or a person's PR."""
    state = WatchState(
        pull=103,
        head_sha="c" * 40,
        checks=_failing_checks(check_name),
        is_bot=is_bot,
    )
    v = verdict(state)
    assert v is not None
    assert v.verdict == PRVerdict.FAILED
    assert due_steps(state) == expected_steps


@pytest.mark.parametrize(
    ("check_name", "repairs", "ended", "expected_steps"),
    [
        ("Tests & Coverage", True, (), (DueStep.FIX_CHECKS,)),
        ("Tests & Coverage", False, (), (DueStep.STOP,)),
        ("Tests & Coverage", True, ("Tests & Coverage",), (DueStep.STOP,)),
        ("Tests & Coverage", True, ("Static Analysis",), (DueStep.FIX_CHECKS,)),
        ("Semantic PR title", True, (), (DueStep.STOP,)),
    ],
    ids=["owner", "mode-not-on", "unit-ended", "other-unit-ended", "ci-infra"],
)
def test_a_failed_check_of_a_delivery_draft_has_a_repair_owner_or_stops_the_item(
    check_name: str, repairs: bool, ended: tuple[str, ...], expected_steps: tuple[DueStep, ...]
) -> None:
    """A delivery draft has a repair owner only when mode `on` lets a unit repair, the class of
    the check is one of FIX_CHECK_CLASSES, and the unit of the head and the check has not ended
    with no repair. In each other case the item stops (#6559)."""
    state = WatchState(
        pull=108,
        head_sha="a" * 40,
        checks=_failing_checks(check_name),
        is_bot=True,
        delivery=True,
        repairs=repairs,
        ended_checks=frozenset(ended),
    )
    assert due_steps(state) == expected_steps


@pytest.mark.parametrize(
    ("delivery", "expected_steps"),
    [(True, (DueStep.STOP,)), (False, ())],
    ids=["delivery-draft", "bot"],
)
def test_due_steps_a_cancelled_check_of_a_delivery_draft_stops_the_item(
    delivery: bool, expected_steps: tuple[DueStep, ...]
) -> None:
    """A cancelled check gets no fix-checks unit, so the item of a delivery draft stops (#6559)."""
    state = WatchState(
        pull=106,
        head_sha="f" * 40,
        checks=[PRCheckItem(name="Tests & Coverage", bucket=CheckBucket.CANCEL, state="cancelled")],
        is_bot=True,
        delivery=delivery,
        repairs=True,
    )
    assert due_steps(state) == expected_steps


def test_due_steps_a_check_that_cannot_be_read_stops_nothing() -> None:
    """A check with no readable conclusion may read next round, so it stops no item."""
    state = WatchState(
        pull=107,
        head_sha="0" * 40,
        checks=[PRCheckItem(name="Semantic PR title", bucket=CheckBucket.UNREAD)],
        is_bot=True,
    )
    assert due_steps(state) == ()


@pytest.mark.parametrize("is_bot", [True, False])
def test_due_steps_pending(is_bot: bool) -> None:
    """PENDING verdict yields no due steps for bot or person PRs."""
    state = WatchState(
        pull=104,
        head_sha="d" * 40,
        checks=_pending_checks(),
        is_bot=is_bot,
    )
    assert due_steps(state) == ()


@pytest.mark.parametrize("is_bot", [True, False])
def test_due_steps_behind(is_bot: bool) -> None:
    """BEHIND verdict yields no due steps for bot or person PRs."""
    state = WatchState(
        pull=105,
        head_sha="e" * 40,
        mergeable=True,
        mergeable_state="behind",
        checks=_passing_checks(),
        is_bot=is_bot,
    )
    assert due_steps(state) == ()


@pytest.mark.parametrize("is_bot", [True, False])
def test_due_steps_threads(is_bot: bool) -> None:
    """THREADS verdict yields no due steps."""
    state = WatchState(
        pull=106,
        head_sha="f" * 40,
        checks=_passing_checks(),
        unresolved_threads=2,
        is_bot=is_bot,
    )
    assert due_steps(state) == ()


@pytest.mark.parametrize("is_bot", [True, False])
def test_due_steps_head_moved(is_bot: bool) -> None:
    """HEAD_MOVED verdict yields no due steps."""
    state = WatchState(
        pull=107,
        head_sha="1" * 40,
        expected_head="2" * 40,
        checks=_passing_checks(),
        is_bot=is_bot,
    )
    assert due_steps(state) == ()


@pytest.mark.parametrize(
    ("is_bot", "is_plan", "expected_steps"),
    [
        (True, False, (DueStep.STATUS_SYNC,)),
        (True, True, (DueStep.STATUS_SYNC, DueStep.CLEANUP)),
        (False, False, (DueStep.STATUS_SYNC,)),
        (False, True, (DueStep.STATUS_SYNC,)),
    ],
)
def test_due_steps_merged_or_closed(
    is_bot: bool, is_plan: bool, expected_steps: tuple[DueStep, ...]
) -> None:
    """MERGED or CLOSED gives status_sync (and cleanup for bot plan PRs)."""
    merged_state = WatchState(
        pull=108,
        head_sha="3" * 40,
        merged=True,
        is_bot=is_bot,
        is_plan=is_plan,
    )
    assert due_steps(merged_state) == expected_steps

    closed_state = WatchState(
        pull=109,
        head_sha="4" * 40,
        state="closed",
        is_bot=is_bot,
        is_plan=is_plan,
    )
    assert due_steps(closed_state) == expected_steps


def test_due_steps_skip_ci() -> None:
    """Commit message with [skip ci] produces no verdict and no due steps."""
    state = WatchState(
        pull=110,
        head_sha="5" * 40,
        commit_message="docs: update readme [skip ci]",
        is_bot=True,
    )
    assert verdict(state) is None
    assert due_steps(state) == ()


def test_due_steps_skips_live_unit() -> None:
    """A pull request whose item has a live unit is skipped."""
    state = WatchState(
        pull=111,
        head_sha="6" * 40,
        checks=_passing_checks(),
        is_bot=True,
        has_live_unit=True,
    )
    assert due_steps(state) == ()


def test_the_fix_unit_takes_the_failed_shard_and_no_cancelled_check() -> None:
    """The check of the unit is the failed check whose log holds the cause: a shard of
    `Tests & Coverage` before the join check, and never a cancelled check (#5027). A cancelled
    check of a delivery draft stops its item instead (#6559)."""
    shard = "Tests & Coverage (shard 2)"
    failed = WatchState(
        pull=104,
        head_sha="d" * 40,
        checks=[
            PRCheckItem(name="Tests & Coverage", bucket=CheckBucket.FAIL, state="failure"),
            PRCheckItem(name=shard, bucket=CheckBucket.FAIL, state="failure"),
        ],
        is_bot=True,
    )
    cancelled = WatchState(
        pull=105,
        head_sha="e" * 40,
        checks=[PRCheckItem(name="Tests & Coverage", bucket=CheckBucket.CANCEL, state="cancelled")],
        is_bot=True,
        delivery=True,
    )

    assert (fix_checks_check(failed), fix_checks_check(cancelled), due_steps(cancelled)) == (
        shard,
        None,
        (DueStep.STOP,),
    )


@pytest.mark.parametrize(
    ("labels", "expected_steps"),
    [
        ((), (DueStep.READY,)),
        (("verdict/mergeable",), (DueStep.READY,)),
        (("verdict/fix-plan",), ()),
        (("type/feature", "verdict/issue-changed"), ()),
        (("verdict/fix-implementation",), ()),
    ],
)
def test_a_verdict_label_that_sends_the_work_back_holds_the_ready_step(
    labels: tuple[str, ...], expected_steps: tuple[DueStep, ...]
) -> None:
    """The watch row does not mark ready a green bot pull request that a verdict sent back (#6024)."""
    state = WatchState(
        pull=101,
        head_sha="a" * 40,
        checks=_passing_checks(),
        is_bot=True,
        is_plan=True,
        labels=labels,
    )

    assert due_steps(state) == expected_steps
