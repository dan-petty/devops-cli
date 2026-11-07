"""The milestones that the GitHub roadmap store finds, orders, edits and closes (#1335)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from devops_cli.exceptions.git import (
    GitHubOperationError,
)
from devops_cli.roadmap.stores.store import (
    GitHubState,
)
from tests.support.roadmap_github_store import MILESTONES, REPO, recorded_store


def created_milestone(number: int, title: str, **changes: Any) -> dict[str, Any]:
    """The recorded milestone #43, as GitHub would return it after a write."""
    milestone = next(m for m in MILESTONES if m["title"] == "v0.2.25")
    return {**milestone, "number": number, "title": title, **changes}


# ── Milestones ────────────────────────────────────────────────────────────────


def test_a_milestone_is_found_by_its_exact_title_or_by_its_number() -> None:
    """No title is read as a version: `0.2.25` names no milestone, `v0.2.25` and `43` name #43."""
    store, _ = recorded_store({"milestones?state=all": MILESTONES})
    found = (store.milestone("v0.2.25"), store.milestone("43"), store.milestone("0.2.25"))
    assert [milestone.number if milestone else None for milestone in found] == [43, 43, None]


def test_milestones_sort_by_due_date_then_by_number_whatever_their_titles() -> None:
    """Every recorded milestone is read, whatever its title; the one with a due date comes
    first, and the others follow by number."""
    store, _ = recorded_store({"milestones?state=all": MILESTONES})
    milestones = store.milestones()
    numbers = [milestone.number for milestone in milestones]
    assert (
        (milestones[0].title, milestones[0].due_on),
        numbers[1:] == sorted(numbers[1:]),
        "Q4 hardening" in [milestone.title for milestone in milestones],
        len(milestones),
    ) == (("2026-10-29", date(2026, 10, 29)), True, True, len(MILESTONES))


def test_edit_milestone_sends_only_the_fields_it_is_given() -> None:
    store, runner = recorded_store(
        {"milestones?state=all": MILESTONES, "-X PATCH": created_milestone(43, "2026-12-24")}
    )
    store.edit_milestone("v0.2.25", title="2026-12-24", due_on=date(2026, 12, 24))
    assert runner.writes == [
        [
            "api",
            "-X",
            "PATCH",
            f"repos/{REPO}/milestones/43",
            "-f",
            "title=2026-12-24",
            "-f",
            "due_on=2026-12-24T00:00:00Z",
        ]
    ]


def test_renaming_a_milestone_onto_another_milestones_title_raises_without_writing() -> None:
    store, runner = recorded_store({"milestones?state=all": MILESTONES})
    with pytest.raises(GitHubOperationError, match="already has the title 'Q4 hardening'"):
        store.edit_milestone("43", title="Q4 hardening")
    assert runner.writes == []


def test_an_edit_that_names_no_state_sends_no_state() -> None:
    store, runner = recorded_store(
        {"milestones?state=all": MILESTONES, "-X PATCH": created_milestone(43, "v0.2.25")}
    )
    edited = store.edit_milestone("43", description="new text")
    assert (runner.writes, edited.state) == (
        [["api", "-X", "PATCH", f"repos/{REPO}/milestones/43", "-f", "description=new text"]],
        GitHubState.OPEN,
    )


def test_an_edit_with_nothing_to_change_writes_nothing() -> None:
    store, runner = recorded_store({"milestones?state=all": MILESTONES})
    assert (store.edit_milestone("43").number, runner.writes) == (43, [])


def test_close_milestone_patches_only_its_state() -> None:
    store, runner = recorded_store(
        {
            "milestones?state=all": MILESTONES,
            "-X PATCH": created_milestone(48, "Q4 hardening", state="closed"),
        }
    )
    closed = store.close_milestone("Q4 hardening")
    assert (runner.writes, closed.state) == (
        [["api", "-X", "PATCH", f"repos/{REPO}/milestones/48", "-f", "state=closed"]],
        GitHubState.CLOSED,
    )


def test_editing_an_unknown_milestone_raises_without_writing() -> None:
    store, runner = recorded_store({"milestones?state=all": MILESTONES})
    with pytest.raises(GitHubOperationError, match="No milestone has the title or number"):
        store.close_milestone("Q5")
    assert runner.writes == []
