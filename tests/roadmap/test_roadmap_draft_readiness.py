"""The one function that decides when any draft pull request is ready (#2916).

A stage plan is complete when opened. An implement pull request is complete when every task group
is ticked and the change is archived. An agent's or a person's pull request is complete when the
author declares it. Then the check runs decide: a failed or unread check refuses, a running check
waits. Then each extra check runs.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from devops_cli.github.check_verdict import CheckBucket, CheckVerdictSummary, PRCheckItem
from devops_cli.github.client import PullRequestFile, PullStatus
from devops_cli.roadmap.implement.implement_pull import (
    Answer,
    ChangeFacts,
    Draft,
    DraftKind,
    Readiness,
    _check_failure_reason,
    draft_readiness,
    kind_of,
    read_draft,
)
from devops_cli.roadmap.stores.store import ImplementRecordKey, Item, ItemField, StageRecordKey
from tests.support.fakes.roadmap_store import (
    InMemoryRoadmapStore,
    encode_job_record,
    with_record,
)

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

_STAGE_ITEM = Item(number=3321, title="a plan", url="u")


def _stage_draft(title: str, body: str) -> Draft:
    return Draft(
        kind=DraftKind.STAGE_PLAN,
        pull=PullStatus(state="open", draft=True, title=title, body=body),
        item=_STAGE_ITEM,
        checks=_PASSING,
    )


def test_draft_readiness_refuses_a_stage_plan_whose_title_summary_is_a_placeholder() -> None:
    draft = _stage_draft("docs(openspec): plan #3321 x", "A real body.")

    result = draft_readiness(draft)

    assert (result.answer, "placeholder" in result.reason) == (Answer.REFUSE, True)


def test_draft_readiness_refuses_a_stage_plan_whose_body_is_a_placeholder() -> None:
    draft = _stage_draft("docs(openspec): plan #3321 Refuse a placeholder summary", "x")

    result = draft_readiness(draft)

    assert (result.answer, "placeholder" in result.reason) == (Answer.REFUSE, True)


def test_draft_readiness_marks_a_complete_stage_plan_ready() -> None:
    draft = _stage_draft(
        "docs(openspec): plan #3321 Refuse a placeholder summary",
        "Plans #3321",
    )

    result = draft_readiness(draft)

    assert result.answer is Answer.READY


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


def test_kind_of_resolves_human_owner_and_label() -> None:
    item_human = Item(number=1, title="one", url="u1", owner="human")
    item_human_label = Item(number=2, title="two", url="u2", labels=("owner/human",))
    assert kind_of(item_human, 335) is DraftKind.PERSON
    assert kind_of(item_human_label, 335) is DraftKind.PERSON


def test_check_failure_reason_cancelled_check() -> None:
    checks = CheckVerdictSummary(
        exit_code=1,
        items=[PRCheckItem(name="Build", bucket=CheckBucket.CANCEL)],
    )
    draft = Draft(kind=DraftKind.STAGE_PLAN, pull=_PULL, checks=checks)
    res = draft_readiness(draft)
    assert res.answer is Answer.REFUSE
    assert "Build" in res.reason


def test_check_failure_reason_fallthrough() -> None:
    checks = CheckVerdictSummary(exit_code=1, items=[])
    reason = _check_failure_reason(checks)
    assert "could not say whether the checks passed" in reason.lower()


def test_read_draft_with_active_change_and_no_pull_arg() -> None:
    store = InMemoryRoadmapStore()
    issue_num = store.seed_issue(
        "Issue 1",
        body=with_record("", encode_job_record({}, {ImplementRecordKey.PR: "335"})),
        fields={ItemField.PRIORITY: "P2-Medium"},
    )
    client = MagicMock()
    client.get_pull_status.return_value = PullStatus(
        state="open",
        draft=True,
        head_ref=f"fix/{issue_num}-feature",
        head_sha="sha123",
    )
    client.get_pull_files.return_value = [
        PullRequestFile(filename=f"openspec/changes/{issue_num}-feature/tasks.md", status="added"),
    ]
    client.get_file_at.return_value = _COMPLETE_TASKS

    draft = read_draft("dan-petty/devops-cli", 335, store=store, client=client)

    client.get_pull_status.assert_called_once_with("dan-petty/devops-cli", 335)
    assert draft.kind is DraftKind.IMPLEMENT
    assert draft.change is not None
    assert draft.change.archived is False
    assert draft.change.tasks_text == _COMPLETE_TASKS


def test_read_draft_non_implement_kind_returns_early_without_reading_files() -> None:
    store = InMemoryRoadmapStore()
    issue_num = store.seed_issue(
        "Issue 1",
        labels=("owner/agent",),
        fields={ItemField.PRIORITY: "P2-Medium"},
        body="",
    )
    client = MagicMock()
    pull = PullStatus(
        state="open",
        draft=True,
        head_ref=f"fix/{issue_num}-agent-task",
        head_sha="sha123",
    )

    draft = read_draft("dan-petty/devops-cli", 335, pull=pull, store=store, client=client)

    assert draft.kind is DraftKind.AGENT
    assert draft.change is None
    client.get_pull_files.assert_not_called()


def test_read_draft_implement_kind_with_no_change_folder_in_files() -> None:
    store = InMemoryRoadmapStore()
    issue_num = store.seed_issue(
        "Issue 1",
        body=with_record("", encode_job_record({}, {ImplementRecordKey.PR: "335"})),
        fields={ItemField.PRIORITY: "P2-Medium"},
    )
    client = MagicMock()
    pull = PullStatus(
        state="open",
        draft=True,
        head_ref=f"fix/{issue_num}-feature",
        head_sha="sha123",
    )
    client.get_pull_files.return_value = [
        PullRequestFile(filename="src/main.py", status="modified"),
    ]

    draft = read_draft("dan-petty/devops-cli", 335, pull=pull, store=store, client=client)

    assert draft.kind is DraftKind.IMPLEMENT
    assert draft.change is None


def test_read_draft_keeps_the_title_and_the_body_of_the_stage_plan_pull() -> None:
    store = InMemoryRoadmapStore()
    issue_num = store.seed_issue(
        "Issue 1",
        body=with_record("", encode_job_record({}, {StageRecordKey.PR: "335"})),
        fields={ItemField.PRIORITY: "P2-Medium"},
    )
    client = MagicMock()
    pull = PullStatus(
        state="open",
        draft=True,
        title="docs(openspec): plan #3321 Refuse a placeholder summary",
        body="Plans #3321",
        head_ref=f"fix/{issue_num}-refuse-a-placeholder-summary",
        head_sha="sha123",
    )

    draft = read_draft("dan-petty/devops-cli", 335, pull=pull, store=store, client=client)

    assert draft.kind is DraftKind.STAGE_PLAN
    assert (draft.pull.title, draft.pull.body) == (pull.title, pull.body)
