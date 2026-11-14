"""`devops roadmap retitle` corrects a title type that `CONST_BRANCH_TYPES` does not list (#4508).

The stage job leaves out an item with such a type for ever, because its branch has no type. The
retitle job selects the item also when its summary is short, writes the listed type of the
correction table of `commit_title.py` (`security(<scope>)` becomes `fix(security)`), and
shortens a long summary in the same round. An item with a type that has no correction is left
with one comment and one log line. Intake does not refuse a new candidate with such a type."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from devops_cli.config.constants import CONST_BRANCH_TYPES, CONST_ROADMAP_RETITLE_COMMENT_MARKER
from devops_cli.roadmap.commit_title import commit_type
from devops_cli.roadmap.intake.intake import NewCandidate
from devops_cli.roadmap.pull_form import SUMMARY_MAX_CHARS, summary_length, title_problems
from devops_cli.roadmap.retitle import (
    RetitleReply,
    apply_retitle,
    plan_retitle,
    render_retitle_plan,
    retitle_items,
)
from devops_cli.roadmap.run import MODEL_LANE_ROWS
from devops_cli.roadmap.stores.store import ItemField
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

REPO = "example/roadmap"
SHORT = "security(ssh): verify node host keys"
LONG_SUMMARY = (
    "source aliases.zsh from the dotfiles checkout, not from the directory a shell starts in"
)
LONG = f"security(zsh): {LONG_SUMMARY}"
NEW_SUMMARY = "source aliases.zsh from the dotfiles checkout"
UNKNOWN = "wip(cli): finish the half-done work"
JOB_COMMENT = "<!-- devops roadmap intake: reason -->\nPlaced."


class Clock:
    """A clock that a test moves, so that the order of events is exact."""

    def __init__(self) -> None:
        self.now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(minutes=1)
        return self.now


class FakeModel:
    """Records each request and answers from a list of summaries, the last one repeated."""

    def __init__(self, *summaries: str) -> None:
        self.requests: list[str] = []
        self._summaries = list(summaries) or [NEW_SUMMARY]

    def summarize(self, request: str) -> RetitleReply:
        self.requests.append(request)
        index = min(len(self.requests), len(self._summaries)) - 1
        return RetitleReply(summary=self._summaries[index])


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=REPO, clock=Clock())


def _item(store: InMemoryRoadmapStore, title: str) -> int:
    return store.seed_issue(
        title,
        body="It asks for one change.",
        fields={ItemField.PRIORITY: "P1-High", ItemField.STATUS: "Ready"},
    )


def _title(store: InMemoryRoadmapStore, number: int) -> str:
    item = store.item(number)
    assert item is not None
    return item.title


def _round(store: InMemoryRoadmapStore, model: FakeModel) -> Any:
    plan = plan_retitle(store, repo=REPO, model=model)
    apply_retitle(store, plan)
    return plan


def _job_comments(store: InMemoryRoadmapStore, number: int) -> list[str]:
    return [
        c.body for c in store.comments_on(number) if CONST_ROADMAP_RETITLE_COMMENT_MARKER in c.body
    ]


def test_a_security_title_with_a_short_summary_is_selected(store: InMemoryRoadmapStore) -> None:
    number = _item(store, SHORT)

    assert [item.number for item in retitle_items(store)] == [number]


def test_a_security_title_becomes_a_fix_with_the_security_scope_and_no_model_call(
    store: InMemoryRoadmapStore,
) -> None:
    number = _item(store, SHORT)
    model = FakeModel()

    plan = _round(store, model)

    assert _title(store, number) == "fix(security): verify node host keys"
    assert (commit_type(_title(store, number)), title_problems(_title(store, number))) == (
        "fix",
        [],
    )
    assert model.requests == []
    assert f"`{SHORT}` becomes `fix(security): verify node host keys`" in render_retitle_plan(plan)
    (comment,) = _job_comments(store, number)
    assert SHORT in comment
    assert "fix(security): verify node host keys" in comment
    assert "`security`" in comment
    # The next round selects the item no more.
    assert plan_retitle(store, repo=REPO, model=model).changes == ()


def test_a_long_security_title_gets_the_listed_type_and_a_short_summary_in_one_round(
    store: InMemoryRoadmapStore,
) -> None:
    number = _item(store, LONG)
    model = FakeModel()

    _round(store, model)

    assert _title(store, number) == f"fix(security): {NEW_SUMMARY}"
    assert len(model.requests) == 1
    assert "fix(security)" in model.requests[0]
    assert len(_job_comments(store, number)) == 1


def test_a_long_security_title_that_the_model_cannot_shorten_still_gets_the_listed_type(
    store: InMemoryRoadmapStore,
) -> None:
    number = _item(store, LONG)
    model = FakeModel(LONG_SUMMARY)

    _round(store, model)

    assert _title(store, number) == f"fix(security): {LONG_SUMMARY}"
    assert summary_length(LONG_SUMMARY) > SUMMARY_MAX_CHARS
    # The next round selects the item for its long summary, as for any listed type.
    assert [item.number for item in retitle_items(store)] == [number]


def test_a_type_with_no_correction_is_left_with_one_comment_and_one_log_line(
    store: InMemoryRoadmapStore, caplog: pytest.LogCaptureFixture
) -> None:
    number = _item(store, UNKNOWN)
    model = FakeModel()

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.retitle"):
        _round(store, model)
        _round(store, model)

    assert _title(store, number) == UNKNOWN
    assert model.requests == []
    (comment,) = _job_comments(store, number)
    assert "`wip`" in comment
    assert all(kind in comment for kind in CONST_BRANCH_TYPES)
    lines = [r.getMessage() for r in caplog.records if f"#{number}" in r.getMessage()]
    assert len(lines) == 1
    assert "invalid-title-type" in lines[0]


def test_a_security_title_that_a_person_set_is_kept_with_a_comment_that_names_the_type(
    store: InMemoryRoadmapStore,
) -> None:
    number = _item(store, "fix(ssh): verify node host keys")
    store.comment(number, JOB_COMMENT)
    store.rename_by_hand(number, SHORT)

    _round(store, FakeModel())
    _round(store, FakeModel())

    assert _title(store, number) == SHORT
    (comment,) = _job_comments(store, number)
    assert "`security`" in comment
    assert "fix(security): verify node host keys" in comment


def test_the_service_row_corrects_a_security_title_before_the_stage_row(
    store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("devops_cli.roadmap.run.build_retitle_model", FakeModel)
    number = _item(store, SHORT)
    row = next(row for row in MODEL_LANE_ROWS if row.name == "retitle")

    row.runner(store=store, repo=REPO)

    assert commit_type(_title(store, number)) == "fix"


# Intake keeps the early return of its summary check: retitle corrects the type (#4508).


@pytest.mark.parametrize("title", [SHORT, LONG, UNKNOWN])
def test_intake_keeps_a_new_candidate_with_an_unlisted_title_type(title: str) -> None:
    """The retitle job corrects the type and shortens the summary of the new issue, so intake
    does not refuse a candidate that the job can correct."""
    assert NewCandidate(title=title, body="Body.").refuse_long_summary() is None


def test_a_person_title_survives_a_body_edit_after_the_skip_comment(
    store: InMemoryRoadmapStore,
) -> None:
    """The skip comment of the person's unlisted title does not bound the rename, so a body edit
    that selects the item again keeps the title (#4620)."""
    number = _item(store, "fix(ssh): verify node host keys")
    store.comment(number, JOB_COMMENT)
    store.rename_by_hand(number, SHORT)
    _round(store, FakeModel())
    store.edit_body_by_hand(number, "It asks for one more change.")

    _round(store, FakeModel())

    assert _title(store, number) == SHORT
    assert len(_job_comments(store, number)) == 1
