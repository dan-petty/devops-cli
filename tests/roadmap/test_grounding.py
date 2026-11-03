"""The rules of a plan pull request: it plans an item and delivers none (#3280)."""

from __future__ import annotations

import pytest

from devops_cli.github.client import PullRequestFile
from devops_cli.roadmap.grounding import plan_blockers, plan_issue

_TITLE = "docs(openspec): plan #3183 add plan-check"
_BODY = "Plans #3183\n\nWhy and what.\n\nChange: `openspec/changes/3183-add-plan-check/`"
_FOLDER = PullRequestFile(
    filename="openspec/changes/3183-add-plan-check/proposal.md", status="added"
)


def _blockers(body: str = _BODY, *files: PullRequestFile) -> list[str]:
    return plan_blockers(335, 3183, body, list(files) or [_FOLDER])


def test_a_plan_title_names_its_issue() -> None:
    assert plan_issue(_TITLE) == 3183


@pytest.mark.parametrize(
    "title",
    [
        "feat(roadmap): add plan-check",
        "docs(openspec): archive 3183-x",
        "docs(openspec): plan #x y",
    ],
)
def test_a_title_that_is_no_plan_names_no_issue(title: str) -> None:
    assert plan_issue(title) is None


def test_a_valid_plan_has_no_blocker() -> None:
    assert _blockers() == []


def test_a_plan_without_a_plans_line_has_one_blocker() -> None:
    found = _blockers("Why and what.")
    assert len(found) == 1
    assert "Plans #3183" in found[0]


def test_a_plan_that_names_another_issue_has_one_blocker() -> None:
    found = _blockers("Plans #9\n\nWhy.")
    assert len(found) == 1
    assert "Plans #3183" in found[0]


def test_a_plan_with_two_plans_lines_has_one_blocker() -> None:
    assert len(_blockers("Plans #3183\nPlans #3183\n")) == 1


def test_a_plan_body_with_a_closing_keyword_has_one_blocker() -> None:
    found = _blockers("Plans #3183\n\nCloses #3183")
    assert len(found) == 1
    assert "closes" in found[0].lower()


def test_a_plan_that_adds_no_change_folder_has_one_blocker() -> None:
    found = _blockers(_BODY, PullRequestFile(filename="docs/notes.md", status="added"))
    assert len(found) == 1
    assert "openspec/changes/3183-" in found[0]


def test_a_plan_that_changes_a_living_spec_has_one_blocker() -> None:
    spec = PullRequestFile(filename="openspec/specs/pr-grounding/spec.md", status="modified")
    found = _blockers(_BODY, _FOLDER, spec)
    assert len(found) == 1
    assert "openspec/specs/pr-grounding/spec.md" in found[0]
