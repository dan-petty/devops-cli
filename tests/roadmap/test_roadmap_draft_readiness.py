"""The one function that decides when any draft pull request is ready (#2916).

A stage plan is complete when opened. An implement pull request is complete when every task group
is ticked and the change is archived. An agent's or a person's pull request is complete when the
author declares it. Then the check runs decide: a failed or unread check refuses, a running check
waits. Then each extra check runs.
"""

from __future__ import annotations

import pytest

from devops_cli.github.check_verdict import CheckBucket, CheckVerdictSummary, PRCheckItem
from devops_cli.github.client import PullStatus
from devops_cli.roadmap.implement_pull import (
    Answer,
    ChangeFacts,
    Draft,
    DraftKind,
    Readiness,
    draft_readiness,
    kind_of,
)
from devops_cli.roadmap.store import ImplementRecordKey, Item, StageRecordKey

_PASSING = CheckVerdictSummary(items=[PRCheckItem(name="Lint", bucket=CheckBucket.PASS)])
_FAILING = CheckVerdictSummary(items=[PRCheckItem(name="Lint", bucket=CheckBucket.FAIL)])
_RUNNING = CheckVerdictSummary(items=[PRCheckItem(name="Lint", bucket=CheckBucket.PENDING)])

_PULL = PullStatus(state="open", draft=True)

_COMPLETE_TASKS = """\
# Tasks

## 1. Group one
- [x] 1.1 Done

## 2. Group two
- [x] 2.1 Done
"""

_UNTICKED_GROUP_2_TASKS = """\
# Tasks

## 1. Group one
- [x] 1.1 Done

## 2. Group two
- [ ] 2.1 Not done
"""


@pytest.mark.parametrize(
    ("kind", "declared", "change", "checks", "expected_answer"),
    [
        (DraftKind.STAGE_PLAN, False, None, _PASSING, Answer.READY),
        (DraftKind.STAGE_PLAN, False, None, _FAILING, Answer.REFUSE),
        (
            DraftKind.IMPLEMENT,
            False,
            ChangeFacts(archived=True, tasks_text=_COMPLETE_TASKS),
            _PASSING,
            Answer.READY,
        ),
        (
            DraftKind.IMPLEMENT,
            False,
            ChangeFacts(archived=True, tasks_text=_UNTICKED_GROUP_2_TASKS),
            _PASSING,
            Answer.REFUSE,
        ),
        (DraftKind.AGENT, True, None, _PASSING, Answer.READY),
        (DraftKind.AGENT, False, None, _PASSING, Answer.WAIT),
        (DraftKind.PERSON, True, None, _PASSING, Answer.READY),
        (DraftKind.PERSON, False, None, _PASSING, Answer.WAIT),
    ],
)
def test_draft_readiness_table_covers_four_kinds_complete_and_incomplete(
    kind: DraftKind,
    declared: bool,
    change: ChangeFacts | None,
    checks: CheckVerdictSummary,
    expected_answer: Answer,
) -> None:
    draft = Draft(
        kind=kind,
        pull=_PULL,
        declared=declared,
        change=change,
        checks=checks,
    )
    result = draft_readiness(draft)
    assert result.answer is expected_answer
    if kind is DraftKind.IMPLEMENT and change is not None and "Not done" in change.tasks_text:
        assert "Group two" in result.reason
        assert "2" in result.reason


def test_draft_readiness_waits_when_a_check_runs() -> None:
    draft = Draft(kind=DraftKind.STAGE_PLAN, pull=_PULL, checks=_RUNNING)
    result = draft_readiness(draft)
    assert result.answer is Answer.WAIT


def test_draft_readiness_skips_checks_rule_when_checks_is_none() -> None:
    draft = Draft(
        kind=DraftKind.IMPLEMENT,
        pull=_PULL,
        change=ChangeFacts(archived=True, tasks_text=_COMPLETE_TASKS),
        checks=None,
    )
    result = draft_readiness(draft)
    assert result.answer is Answer.READY


def test_draft_readiness_refuses_unarchived_change_with_every_group_ticked() -> None:
    draft = Draft(
        kind=DraftKind.IMPLEMENT,
        pull=_PULL,
        change=ChangeFacts(archived=False, tasks_text=_COMPLETE_TASKS),
        checks=_PASSING,
    )
    result = draft_readiness(draft)
    assert result.answer is Answer.REFUSE


def test_draft_readiness_refuses_missing_change_for_implement_kind() -> None:
    draft = Draft(
        kind=DraftKind.IMPLEMENT,
        pull=_PULL,
        change=None,
        checks=_PASSING,
    )
    result = draft_readiness(draft)
    assert result.answer is Answer.REFUSE


def test_draft_readiness_extra_check_refuses_complete_draft() -> None:
    draft = Draft(kind=DraftKind.STAGE_PLAN, pull=_PULL, checks=_PASSING)

    def extra(_d: Draft) -> Readiness:
        return Readiness(Answer.REFUSE, "evaluated alignment failed")

    result = draft_readiness(draft, extra_checks=(extra,))
    assert result.answer is Answer.REFUSE
    assert result.reason == "evaluated alignment failed"


def test_kind_of_resolves_the_four_kinds_from_records_and_claims() -> None:
    item_implement = Item(
        number=1,
        title="one",
        url="u1",
        job_record={ImplementRecordKey.PR: "335"},
    )
    item_agent = Item(
        number=2,
        title="two",
        url="u2",
        owner="agent",
    )
    item_stage = Item(
        number=3,
        title="three",
        url="u3",
        job_record={StageRecordKey.PR: "335"},
    )
    item_none = Item(
        number=4,
        title="four",
        url="u4",
    )

    assert kind_of(item_implement, 335) is DraftKind.IMPLEMENT
    assert kind_of(item_agent, 335) is DraftKind.AGENT
    assert kind_of(item_stage, 335) is DraftKind.STAGE_PLAN
    assert kind_of(item_none, 335) is DraftKind.PERSON


def test_kind_of_claim_beats_record() -> None:
    item = Item(
        number=5,
        title="five",
        url="u5",
        owner="agent",
        job_record={StageRecordKey.PR: "335"},
    )
    assert kind_of(item, 335) is DraftKind.AGENT


def test_kind_of_no_item_gives_person() -> None:
    assert kind_of(None, 335) is DraftKind.PERSON
