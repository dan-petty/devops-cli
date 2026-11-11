"""`check_proposal` refuses a requirement text that the strict OpenSpec validation of the merged
spec refuses after `openspec archive` (#4524)."""

from __future__ import annotations

from devops_cli.roadmap.stage.stage_change import (
    REQUIREMENT_MAX_CHARS,
    ProposalGate,
    StageProposal,
    StageSpec,
    check_gates,
    check_proposal,
)
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal

TREE = StagedTree(["src/devops_cli/sample.py"])
CAPABILITY = "comment-thread"
NAME = "The job keeps every comment"
# The text of the MODIFIED requirement of the #3462 plan (PR #4435): 543 characters.
TEXT_3462 = (
    "The stage plan SHALL refuse an other task group that changes only test modules under tests "
    "and whose implementation names no test function in a code span. The stage plan SHALL accept "
    "an other group with one changed path that is no test module under tests. A test module under "
    "tests is a path under `tests/` whose base name starts with `test_` and ends with `.py`. A code "
    "span names a test function when its last segment starts with `test_`, with optional "
    "parentheses. The last segment of a span that holds `::` is the text after the last `::`."
)
LENGTH_3462 = 543
LEAD = "The job SHALL keep every comment of a thread "


def _text(length: int) -> str:
    """A requirement text of `length` characters that says SHALL."""
    return LEAD + "a" * (length - len(LEAD))


def _spec(text: str, *, modified: bool = False) -> StageSpec:
    """The stock spec delta with its one requirement given `text`, as ADDED or as MODIFIED."""
    spec = make_stage_proposal().specs[0]
    requirement = spec.added[0].model_copy(update={"text": text})
    if modified:
        return spec.model_copy(update={"purpose": None, "added": [], "modified": [requirement]})
    return spec.model_copy(update={"added": [requirement]})


def _plan(text: str, *, modified: bool = False) -> StageProposal:
    return make_stage_proposal(specs=[_spec(text, modified=modified)])


def _long(length: int, name: str = NAME) -> str:
    return (
        f"The text of the requirement {name} has {length} characters, and the most is "
        f"{REQUIREMENT_MAX_CHARS}. Move the details into a scenario, or split the requirement."
    )


def test_the_limit_is_the_limit_of_openspec() -> None:
    assert REQUIREMENT_MAX_CHARS == 500


def test_an_added_requirement_over_the_limit_is_refused_with_its_name_and_length() -> None:
    problems = check_proposal(_plan(_text(LENGTH_3462)), [], TREE)

    assert problems == [_long(LENGTH_3462)]


def test_the_modified_requirement_of_the_3462_plan_is_refused_with_its_name_and_length() -> None:
    assert len(TEXT_3462) == LENGTH_3462

    problems = check_proposal(_plan(TEXT_3462, modified=True), [CAPABILITY], TREE)

    assert problems == [_long(LENGTH_3462)]


def test_a_requirement_at_the_limit_passes() -> None:
    assert check_proposal(_plan(_text(REQUIREMENT_MAX_CHARS)), [], TREE) == []
    assert (
        check_proposal(_plan(_text(REQUIREMENT_MAX_CHARS), modified=True), [CAPABILITY], TREE) == []
    )


def test_the_length_counts_utf16_units_as_openspec_does() -> None:
    """OpenSpec measures a JavaScript string, so a character outside the Basic Multilingual Plane
    counts two."""
    text = _text(REQUIREMENT_MAX_CHARS - 1) + "\N{GRINNING FACE}"

    assert check_proposal(_plan(text), [], TREE) == [_long(REQUIREMENT_MAX_CHARS + 1)]


def test_the_length_problem_is_a_problem_of_the_gate_spec_delta() -> None:
    found = check_gates(_plan(_text(LENGTH_3462)), [], TREE)

    assert found[ProposalGate.SPEC_DELTA] == [_long(LENGTH_3462)]
    assert [gate for gate, problems in found.items() if problems] == [ProposalGate.SPEC_DELTA]
