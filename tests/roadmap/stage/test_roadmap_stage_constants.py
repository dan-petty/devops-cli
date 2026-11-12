"""`devops roadmap stage`: check plan numbers against staged constants (#3308)."""

from __future__ import annotations

import pytest

from devops_cli.roadmap.stage.stage_constants import (
    candidate_names,
    constant_problems,
    parse_constants,
    staged_constants,
)
from tests.support.paths import REPO_ROOT


def test_parse_constants_reads_annotated_assignment() -> None:
    source = "SUMMARY_MAX_CHARS: Final[int] = 60\n"
    assert parse_constants({"src/devops_cli/roadmap/pull_form.py": source}) == {
        "SUMMARY_MAX_CHARS": 60
    }


def test_parse_constants_resolves_alias_across_modules() -> None:
    sources = {
        "src/devops_cli/roadmap/pull_form.py": (
            "BODY_MAX_CHARS = CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS\n"
        ),
        "src/devops_cli/config/constants.py": "CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS = 1000\n",
    }
    assert parse_constants(sources) == {
        "BODY_MAX_CHARS": 1000,
        "CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS": 1000,
    }


def test_parse_constants_leaves_out_call_value() -> None:
    source = "SUMMARY_MAX_CHARS = int('60')\n"
    assert parse_constants({"src/devops_cli/roadmap/pull_form.py": source}) == {}


def test_parse_constants_leaves_out_ambiguous_definition() -> None:
    sources = {
        "src/devops_cli/module_a.py": "SUMMARY_MAX_CHARS = 40\n",
        "src/devops_cli/module_b.py": "SUMMARY_MAX_CHARS = 60\n",
    }
    assert parse_constants(sources) == {}


def test_candidate_names_extracts_constant_identifiers() -> None:
    texts = [
        "A requirement says `SUMMARY_MAX_CHARS` is 40.",
        "WHEN `BODY_MAX_CHARS` is 1000.",
    ]
    assert candidate_names(texts) == {"SUMMARY_MAX_CHARS", "BODY_MAX_CHARS"}


@pytest.mark.parametrize(
    "text",
    [
        "A spec scenario says `SUMMARY_MAX_CHARS` is 40.",
        "The design keeps `SUMMARY_MAX_CHARS = 40` in `pull_form.py`.",
        "`pull_form.py:12:SUMMARY_MAX_CHARS: Final[int] = 40` gives the bound.",
    ],
    ids=["is", "assignment", "annotated-assignment"],
)
def test_constant_problems_yields_problem_on_mismatch(text: str) -> None:
    constants = {"SUMMARY_MAX_CHARS": 60}
    assert constant_problems([text], constants) == [
        "SUMMARY_MAX_CHARS is 60 in the staged tree, but the plan says 40."
    ]


@pytest.mark.parametrize(
    ("text", "constants"),
    [
        (
            "`read_file` of `src/devops_cli/commands/ci.py` lines 1790-2000 showed the rule at "
            "`src/devops_cli/commands/ci.py:1830:if len(targets) <= DEFAULT_CI_TEST_SERIAL_MAX_FILES:`.",
            {"DEFAULT_CI_TEST_SERIAL_MAX_FILES": 12},
        ),
        (
            "`tests/commands/test_test_selection.py:577:modules = _test_modules(project, "
            "DEFAULT_CI_TEST_SERIAL_MAX_FILES + 1)` is the existing file-count test.",
            {"DEFAULT_CI_TEST_SERIAL_MAX_FILES": 12},
        ),
        (
            "It SHALL run pytest with `-n 0` when the count is no more than "
            "`DEFAULT_CI_TEST_SERIAL_MAX_TESTS`, and with `-n DEFAULT_CI_TEST_NARROWED_WORKERS` above it.",
            {"DEFAULT_CI_TEST_NARROWED_WORKERS": 4},
        ),
        (
            "Add `DEFAULT_CI_TEST_SERIAL_MAX_TESTS: Final[int] = 50` to "
            "`src/devops_cli/config/defaults.py` after `DEFAULT_CI_TEST_NARROWED_WORKERS`.",
            {"DEFAULT_CI_TEST_NARROWED_WORKERS": 4},
        ),
        (
            "Edit the sentence of `docs/ROADMAP_WORKFLOW.md` at line 266 that names "
            "`CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS`.",
            {"CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS": 30},
        ),
        (
            "Add `CONST_ROADMAP_IMPLEMENT_MAX_CONSECUTIVE_REFUSALS` of 3 beside "
            "`CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS`.",
            {"CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS": 30},
        ),
        (
            "Raise `SUMMARY_MAX_CHARS` to 80 in `pull_form.py`.",
            {"SUMMARY_MAX_CHARS": 60},
        ),
        (
            "The test patches `SUMMARY_MAX_CHARS` to 1, so that each summary is too long.",
            {"SUMMARY_MAX_CHARS": 60},
        ),
    ],
    ids=[
        "line-range",
        "operand",
        "option-value",
        "new-constant-value",
        "line-number",
        "new-constant-of",
        "new-value-to",
        "patch-to",
    ],
)
def test_constant_problems_ignores_number_that_is_no_value_of_the_constant(
    text: str, constants: dict[str, int]
) -> None:
    assert constant_problems([text], constants) == []


@pytest.mark.parametrize(
    ("number", "problems"),
    [
        ("6_500", []),
        (
            "6_400",
            ["CONST_AGENTS_MD_MAX_CHARS is 6500 in the staged tree, but the plan says 6400."],
        ),
    ],
    ids=["same-value", "other-value"],
)
def test_constant_problems_reads_number_with_digit_separators(
    number: str, problems: list[str]
) -> None:
    texts = [
        "`src/devops_cli/config/constants.py:195:CONST_AGENTS_MD_MAX_CHARS: Final[int] = "
        f"{number}` gives the bound."
    ]
    constants = {"CONST_AGENTS_MD_MAX_CHARS": 6500}
    assert constant_problems(texts, constants) == problems


def test_constant_problems_accepts_matching_number() -> None:
    texts = ["A plan text says `SUMMARY_MAX_CHARS` is 60."]
    constants = {"SUMMARY_MAX_CHARS": 60}
    assert constant_problems(texts, constants) == []


def test_constant_problems_ignores_note_reference() -> None:
    texts = ["A requirement says `SUMMARY_MAX_CHARS` is 60 (#2714)."]
    constants = {"SUMMARY_MAX_CHARS": 60}
    assert constant_problems(texts, constants) == []


def test_constant_problems_ignores_line_location() -> None:
    texts = ["See pull_form.py:12 where `SUMMARY_MAX_CHARS` is 60."]
    constants = {"SUMMARY_MAX_CHARS": 60}
    assert constant_problems(texts, constants) == []


def test_constant_problems_skips_sentence_with_two_candidate_numbers() -> None:
    texts = [
        "A design decision says `SUMMARY_MAX_CHARS` is 40, while the staged tree sets it to 60."
    ]
    constants = {"SUMMARY_MAX_CHARS": 60}
    assert constant_problems(texts, constants) == []


def test_staged_constants_reads_repository() -> None:
    # `src/devops_cli/roadmap/pull_form.py` defines `SUMMARY_MAX_CHARS: Final[int] = 60`
    constants = staged_constants(REPO_ROOT, "HEAD", ["SUMMARY_MAX_CHARS"])
    assert constants.get("SUMMARY_MAX_CHARS") == 60
