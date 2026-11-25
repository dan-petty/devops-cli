"""The acceptance criteria of an issue against the criteria list of a plan (#3019)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
)
from devops_cli.roadmap.stage.stage_criteria import (
    StageCriterion,
    acceptance_criteria,
    criterion_problems,
    refine_decisions,
    requirement_lines,
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


def test_a_criteria_entry_from_the_refine_block_is_refused() -> None:
    body = "Text.\n" + REFINE_BLOCK
    copied = "Criterion 1: The refine form. Verification: a test."
    entry = _entry(copied)

    problems = criterion_problems([entry], body, 1)

    assert problems == [
        f'The entry of `criteria` for "{copied}" is no acceptance criterion that a person wrote '
        "in the issue body. Copy the text of a top-level item under the heading `Acceptance criteria` "
        "or give an empty list."
    ]


def test_an_empty_criteria_list_for_a_body_with_only_a_refine_block_is_accepted() -> None:
    body = "Text.\n" + REFINE_BLOCK

    assert criterion_problems([], body, 1) == []


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


def test_a_struck_through_unchecked_item_is_no_criterion() -> None:
    body = "## Acceptance criteria\n\n- ~~[ ] Dropped criterion~~\n"

    assert acceptance_criteria(body) == []


def test_a_struck_through_checked_item_is_no_criterion() -> None:
    body = "## Acceptance criteria\n\n- ~~[x] Dropped criterion~~\n"

    assert acceptance_criteria(body) == []


def test_active_items_beside_a_struck_item_keep_their_order() -> None:
    body = "## Acceptance criteria\n\n- ~~[ ] Dropped~~\n- [ ] Kept one\n- [x] Kept two\n"

    assert acceptance_criteria(body) == ["Kept one", "Kept two"]


def test_an_inline_strikethrough_in_an_active_item_keeps_the_item() -> None:
    body = "## Acceptance criteria\n\n- [ ] Keep ~~this~~ text\n"

    assert acceptance_criteria(body) == ["Keep ~~this~~ text"]


def test_refine_decisions_extracts_chosen_and_rejected_lines() -> None:
    body = (
        "## Problem\n\nSome text.\n\n"
        "<!-- devops-roadmap-refine:start -->\n"
        "### Key questions\n"
        "- **Which parser?**: Use the library.\n"
        "  - Chosen: Use the library. It is maintained.\n"
        "  - Rejected: Write a parser. It adds code to keep.\n"
        "- **Which cache?**: Valkey.\n"
        "  - Chosen: Use Valkey. It is fast.\n"
        "<!-- devops-roadmap-refine:end -->\n"
    )
    chosen, rejected = refine_decisions(body)

    assert chosen == ["Use the library. It is maintained.", "Use Valkey. It is fast."]
    assert rejected == ["Write a parser. It adds code to keep."]


def test_refine_decisions_returns_empty_when_no_refine_block() -> None:
    body = "## Problem\n\nSome text with no refine block.\n"
    chosen, rejected = refine_decisions(body)

    assert chosen == []
    assert rejected == []


def test_a_quoted_marker_pair_keeps_the_criteria_and_gives_no_refine_block() -> None:
    quoted = (
        f"A person writes `{CONST_ROADMAP_REFINE_START_MARKER}` here.\n\n"
        "### Acceptance criteria\n\n"
        "- [ ] A criterion between the quoted markers.\n\n"
        "### Files\n\n"
        "- [ ] A bullet that names `src/devops_cli/roadmap/body_hash.py`.\n\n"
        f"and `{CONST_ROADMAP_REFINE_END_MARKER}` here.\n"
    )

    assert acceptance_criteria(quoted) == ["A criterion between the quoted markers."]
    assert refine_decisions(quoted) == ([], [])
    assert [line.text for line in requirement_lines(quoted)] == [
        "src/devops_cli/roadmap/body_hash.py"
    ]

    real = (
        "## Problem\n\nSome text.\n\n"
        f"{CONST_ROADMAP_REFINE_START_MARKER}\n"
        "### Key questions\n"
        "- **Which parser?**: Use the library.\n"
        "  - Chosen: Use the library. It is maintained.\n"
        f"{CONST_ROADMAP_REFINE_END_MARKER}\n"
    )
    chosen, rejected = refine_decisions(real)

    assert chosen == ["Use the library. It is maintained."]
    assert rejected == []


def test_a_start_marker_with_no_end_marker_gives_no_refine_block() -> None:
    """A real start marker of refine on a line of its own, with no end marker, bounds no block: the
    job reads no decision from the text after it, and reads its criteria as text of the person
    (#6627)."""
    body = (
        "## Problem\n\nSome text.\n\n"
        f"{CONST_ROADMAP_REFINE_START_MARKER}\n\n"
        "### Key questions\n"
        "- **Which parser?**: Use the library.\n"
        "  - Chosen: Use the library. It is maintained.\n\n"
        "### Acceptance criteria\n\n"
        "- [ ] A criterion after the start marker.\n"
    )

    assert (refine_decisions(body), acceptance_criteria(body)) == (
        ([], []),
        ["A criterion after the start marker."],
    )


def test_acceptance_criteria_stops_at_alternatives_block() -> None:
    """acceptance_criteria stops an open heading at a job block marker so Covers/Lacks do not leak (#6626)."""
    from devops_cli.config.constants import (
        CONST_ROADMAP_ALTERNATIVES_END_MARKER,
        CONST_ROADMAP_ALTERNATIVES_START_MARKER,
    )

    body = (
        "## Acceptance criteria\n\n"
        "- [ ] First criterion\n"
        "- [x] Second criterion\n\n"
        f"{CONST_ROADMAP_ALTERNATIVES_START_MARKER}\n"
        "Alternatives check of 2026-11-21: none.\n"
        "Tool: none found.\n\n"
        "Lacks:\n"
        "- No awareness of job block markers\n"
        f"{CONST_ROADMAP_ALTERNATIVES_END_MARKER}\n"
    )

    assert acceptance_criteria(body) == ["First criterion", "Second criterion"]


def test_criterion_problems_ignores_lacks_items_from_alternatives_block() -> None:
    """criterion_problems does not require mapping Lacks items inside an alternatives block (#6626)."""
    from devops_cli.config.constants import (
        CONST_ROADMAP_ALTERNATIVES_END_MARKER,
        CONST_ROADMAP_ALTERNATIVES_START_MARKER,
    )

    body = (
        "## Acceptance criteria\n\n"
        "- First criterion\n\n"
        f"{CONST_ROADMAP_ALTERNATIVES_START_MARKER}\n"
        "Lacks:\n"
        "- Unrelated tool gap\n"
        f"{CONST_ROADMAP_ALTERNATIVES_END_MARKER}\n"
    )

    assert criterion_problems([_entry("First criterion")], body, 1) == []
