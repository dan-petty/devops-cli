"""The acceptance criteria of an issue against the criteria list of a plan (#3019)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from devops_cli.roadmap.stage.stage_criteria import (
    StageCriterion,
    acceptance_criteria,
    criterion_problems,
)

HUMAN_LIST = """### What happened

A plan drops a criterion.

### Acceptance criteria

- [ ] A test with an issue of three criteria is refused.
- [x] The `tasks.md` shows
  which group delivers it.
  - a nested note, no criterion
- A bullet with no box, see [the docs](docs/x.md).

### Source

- [ ] not a criterion, other section
"""
REFINE_BLOCK = """
<!-- devops-roadmap-refine:start -->
## Proposed design

### Acceptance criteria

- Criterion 1: The refine form. Verification: a test.
### Requirement: x
<!-- devops-roadmap-refine:end -->
"""
EXPECTED = [
    "A test with an issue of three criteria is refused.",
    "The `tasks.md` shows which group delivers it.",
    "A bullet with no box, see [the docs](docs/x.md).",
]


def _entry(criterion: str, group: int | str = 1, reason: str | None = None) -> StageCriterion:
    return StageCriterion.model_validate({"criterion": criterion, "group": group, "reason": reason})


def test_the_criteria_are_the_top_level_items_under_the_heading_of_the_human_list() -> None:
    assert acceptance_criteria(HUMAN_LIST) == EXPECTED


def test_the_list_of_the_refine_block_is_not_read() -> None:
    assert acceptance_criteria(HUMAN_LIST + REFINE_BLOCK) == EXPECTED
    assert acceptance_criteria("Text.\n" + REFINE_BLOCK) == []


@pytest.mark.parametrize("body", ["", "No list here.", "### Steps\n\n- [ ] one\n- [ ] two\n"])
def test_a_body_with_no_acceptance_list_has_no_criterion(body: str) -> None:
    assert acceptance_criteria(body) == []
    assert criterion_problems([], body, 1) == []


def test_a_reply_that_maps_two_of_three_criteria_is_refused_with_the_text_to_copy() -> None:
    mapped = [_entry(EXPECTED[0]), _entry(EXPECTED[1], "pending-person", "A person decides.")]

    problems = criterion_problems(mapped, HUMAN_LIST, 2)

    assert problems == [
        f'The issue lists the acceptance criterion "{EXPECTED[2]}", and `criteria` has no entry '
        "with this text. Add an entry that copies the text, with the number of the group that "
        "delivers it or pending-person and a reason."
    ]


def test_a_reply_that_maps_every_criterion_has_no_problem_whatever_its_spacing() -> None:
    mapped = [_entry(f"  {text.replace(' ', '  ')}\n") for text in EXPECTED]

    assert criterion_problems(mapped, HUMAN_LIST, 1) == []


def test_an_entry_for_a_group_the_plan_does_not_have_is_refused() -> None:
    mapped = [_entry(text, 3) for text in EXPECTED]

    problems = criterion_problems(mapped, HUMAN_LIST, 2)

    assert len(problems) == 3
    assert problems[0].endswith("names group 3, and the plan has 2 groups.")


def test_a_pending_person_entry_needs_a_reason() -> None:
    with pytest.raises(ValidationError, match="is pending-person and has no reason"):
        _entry("A criterion.", "pending-person", "  ")
    assert _entry("A criterion.", "pending-person", "A person decides.").group == "pending-person"


def test_a_group_number_starts_at_one() -> None:
    with pytest.raises(ValidationError, match="A criterion group is a number from 1, not 0"):
        _entry("A criterion.", 0)


def test_a_pending_person_criterion_with_a_comma_keeps_its_whole_text() -> None:
    """The reader splits at the first comma, and the issue's own criterion restores the whole
    text (#4023)."""
    body = "## Acceptance criteria\n\n- Add the label, keep the title\n"
    entry = _entry(
        "Add the label", "pending-person", "keep the title, because the label is missing"
    )

    assert criterion_problems([entry], body, 1) == []


def test_a_pending_person_reason_with_a_comma_keeps_its_whole_text() -> None:
    body = "## Acceptance criteria\n\n- Add the label\n"
    entry = _entry(
        "Add the label", "pending-person", "because the label is missing, and the title is short"
    )

    assert criterion_problems([entry], body, 1) == []


def test_the_longest_pending_person_criterion_wins() -> None:
    from devops_cli.roadmap.stage.stage_criteria import _resolved

    entry = _entry(
        "Add the label", "pending-person", "keep the title, because the label is missing"
    )

    (resolved,) = _resolved([entry], ["Add the label", "Add the label, keep the title"])

    assert resolved.criterion == "Add the label, keep the title"


def test_a_pending_person_criterion_that_the_issue_does_not_list_is_reported() -> None:
    body = "## Acceptance criteria\n\n- Add the label\n"
    entry = _entry("Unknown text", "pending-person", "because the text is absent")

    problems = criterion_problems([entry], body, 1)

    assert "Add the label" in " ".join(problems)
