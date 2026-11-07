"""`devops roadmap stage`: check plan numbers against staged constants (#3308)."""

from __future__ import annotations

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


def test_constant_problems_yields_problem_on_mismatch() -> None:
    texts = ["A plan text with `SUMMARY_MAX_CHARS` and 40 in one sentence."]
    constants = {"SUMMARY_MAX_CHARS": 60}
    assert constant_problems(texts, constants) == [
        "SUMMARY_MAX_CHARS is 60 in the staged tree, but the plan says 40."
    ]


def test_constant_problems_accepts_matching_number() -> None:
    texts = ["A plan text with `SUMMARY_MAX_CHARS` and 60 in one sentence."]
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
