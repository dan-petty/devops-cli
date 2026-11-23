"""`devops roadmap stage`: check plan numbers against staged constants (#3308)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from devops_cli.roadmap.stage.stage_change import (
    StageProposal,
    content_problems,
)
from devops_cli.roadmap.stage.stage_constants import (
    candidate_names,
    claimed_names,
    constant_problems,
    parse_constants,
    staged_constants,
)
from tests.support.builders import make_stage_proposal
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


def test_the_stage_reply_holds_constant_claims() -> None:
    plan = make_stage_proposal(constant_claims=[{"name": "SUMMARY_MAX_CHARS", "value": 60}])
    assert len(plan.constant_claims) == 1
    assert plan.constant_claims[0].name == "SUMMARY_MAX_CHARS"
    assert plan.constant_claims[0].value == 60

    empty_plan = make_stage_proposal()
    assert empty_plan.constant_claims == []

    with pytest.raises(ValidationError, match="is not a Python identifier"):
        StageProposal.model_validate(
            {**PLAN_OF_THIS_CHANGE, "constant_claims": [{"name": "SUMMARY-MAX", "value": 60}]}
        )


PLAN_OF_THIS_CHANGE: dict[str, Any] = {
    "summary": "The stage plan states constant claims",
    "pull_request_body": (
        "The plan check reads constant claims from prose, so it skips a sentence with two "
        "numbers and a new name for an existing bound, and a wrong bound passes (#3388)."
    ),
    "why": (
        "Issue #3388: the plan check reads constant claims from prose, so it skips a sentence "
        "with two numbers and a new name for an existing bound, and a wrong bound passes."
    ),
    "what_changes": [
        "Add `StageConstantClaim` with `name` and `value`, and the `constant_claims` list with an empty default, to `StageProposal` in `src/devops_cli/roadmap/stage/stage_change.py`.",
        "Refuse a claim whose value differs from the staged value, and a claim whose name the staged values do not hold, in `check_proposal`.",
        "Run the prose scan of constant claims only when `constant_claims` is empty.",
        "Add `stage_problem_constant_undefined` to `src/devops_cli/lang/en/messages.py` for a claim that names no module-level integer of the staged tree.",
        "List `constant_claims` among the reply keys of `src/devops_cli/ai/tasks/roadmap_stage_change.md`.",
        "Add `claimed_names` to `src/devops_cli/roadmap/stage/stage_constants.py` and call it in `src/devops_cli/roadmap/stage/stage.py`.",
        "Describe the claim list in `docs/roadmap/stage.md`.",
    ],
    "skip_specs": False,
    "feasibility": [
        "`src/devops_cli/roadmap/stage/stage_change.py:3094:        ProposalGate.CONSTANTS: constant_problems(plan_texts(proposal), constants or {}),` is the prose scan that the plan keeps as the fallback.",
        "`staged_constants` needs a checkout of the repository at the staged commit, because it runs `git grep` and `git show` (`src/devops_cli/roadmap/stage/stage_constants.py:229:def staged_constants(source: Path, sha: str, names: Iterable[str]) -> dict[str, int]:`).",
        "`constant_problems` needs no checkout, no client and no network: the caller gives the staged values as a mapping (`src/devops_cli/roadmap/stage/stage_constants.py:257:def constant_problems(texts: Iterable[str], constants: Mapping[str, int]) -> list[str]:`).",
    ],
    "existing_tool": (
        "No open tool covers the check: about 12k tokens to build, 3k tokens a month to keep "
        "and fix, and 1 to 2 days of elapsed time."
    ),
    "decisions": [
        {
            "decision": "constant_claims is a field of StageProposal with an empty default",
            "reason": "A reply with no structured claim has no value to compare, and the prose scan is the only reading of it.",
        }
    ],
    "rejected": [
        {
            "alternative": "Parse the claims from the prose with a second reader",
            "evidence": "src/devops_cli/roadmap/stage/stage_constants.py:257: constant_problems skips a sentence with two numbers.",
        }
    ],
    "specs": [
        {
            "capability": "roadmap-stage/claims",
            "purpose": None,
            "added": [
                {
                    "name": "The stage reply holds structured constant claims",
                    "text": "The stage reply SHALL hold structured constant claims.",
                    "scenarios": [
                        {
                            "name": "A reply with one claim",
                            "when": "A reply gives constant_claims with the name SUMMARY_MAX_CHARS and the value 60",
                            "then": "The validated proposal holds one entry",
                        }
                    ],
                }
            ],
            "modified": [],
            "renamed": [],
            "removed": [],
        }
    ],
    "groups": [
        {
            "title": "Add the constant-claim field to the stage reply and the prompt",
            "kind": "behavior",
            "reads": [
                "src/devops_cli/roadmap/stage/stage_change.py",
                "src/devops_cli/ai/tasks/roadmap_stage_change.md",
                "tests/roadmap/stage/test_roadmap_stage_prompt_rules.py",
                "tests/roadmap/stage/test_roadmap_stage_constants.py",
            ],
            "changes": [
                "src/devops_cli/roadmap/stage/stage_change.py",
                "src/devops_cli/ai/tasks/roadmap_stage_change.md",
                "tests/roadmap/stage/test_roadmap_stage_constants.py",
                "tests/roadmap/stage/test_roadmap_stage_prompt_rules.py",
            ],
            "creates": [],
            "creates_lines": {},
            "test": (
                "Write `test_the_stage_reply_holds_constant_claims` in "
                "`tests/roadmap/stage/test_roadmap_stage_constants.py` and "
                "`test_the_plan_check_accepts_the_plan_of_this_change`, which builds the plan's "
                "own `StageProposal` and asserts that `content_problems` returns no problem for it, "
                "and verify that `src/devops_cli/roadmap/stage/stage_change.py` fails on the base"
            ),
            "implementation": (
                "Add `StageConstantClaim` and `constant_claims` to `StageProposal` in `stage_change.py`"
            ),
            "documentation": None,
            "verify": "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_constants.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py",
        },
        {
            "title": "Judge each structured claim in the plan check",
            "kind": "behavior",
            "reads": [
                "src/devops_cli/roadmap/stage/stage_change.py",
                "src/devops_cli/roadmap/stage/stage_constants.py",
                "src/devops_cli/lang/en/messages.py",
                "tests/roadmap/stage/test_roadmap_stage_plan.py",
            ],
            "changes": [
                "src/devops_cli/roadmap/stage/stage_change.py",
                "src/devops_cli/lang/en/messages.py",
                "tests/roadmap/stage/test_roadmap_stage_plan.py",
            ],
            "creates": [],
            "creates_lines": {},
            "test": (
                "Write `test_check_proposal_refuses_a_wrong_constant_claim` and "
                "`test_check_proposal_refuses_a_claim_the_tree_does_not_define` in "
                "`tests/roadmap/stage/test_roadmap_stage_plan.py`; it fails on the base, where "
                "`src/devops_cli/roadmap/stage/stage_change.py:3094:        ProposalGate.CONSTANTS: constant_problems(plan_texts(proposal), constants or {}),` "
                "judges only the prose"
            ),
            "implementation": "Add `claim_problems` to `stage_change.py`",
            "documentation": None,
            "verify": "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py tests/roadmap/stage/test_roadmap_stage_constants.py",
        },
        {
            "title": "Read the staged value of each claimed name",
            "kind": "behavior",
            "reads": [
                "src/devops_cli/roadmap/stage/stage_constants.py",
                "src/devops_cli/roadmap/stage/stage.py",
                "tests/roadmap/stage/test_roadmap_stage_apply.py",
            ],
            "changes": [
                "src/devops_cli/roadmap/stage/stage_constants.py",
                "src/devops_cli/roadmap/stage/stage.py",
                "tests/roadmap/stage/test_roadmap_stage_constants.py",
            ],
            "creates": [],
            "creates_lines": {},
            "test": (
                "Write `test_claimed_names_adds_the_names_of_the_claims` in "
                "`tests/roadmap/stage/test_roadmap_stage_constants.py`"
            ),
            "implementation": "Add `claimed_names` to `stage_constants.py`",
            "documentation": None,
            "verify": "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_constants.py tests/roadmap/stage/test_roadmap_stage_apply.py",
        },
        {
            "title": "Describe the claim list in the stage guide",
            "kind": "other",
            "reads": [
                "docs/roadmap/stage.md",
                "src/devops_cli/ai/tasks/roadmap_stage_change.md",
            ],
            "changes": ["docs/roadmap/stage.md"],
            "creates": [],
            "creates_lines": {},
            "test": None,
            "implementation": "Describe the constant_claims key in `docs/roadmap/stage.md`",
            "documentation": "Edit `docs/roadmap/stage.md`",
            "verify": "uv run devops ci docs",
        },
    ],
    "constant_claims": [{"name": "SUMMARY_MAX_CHARS", "value": 60}],
}


def test_the_plan_check_accepts_the_plan_of_this_change() -> None:
    assert content_problems(StageProposal.model_validate(PLAN_OF_THIS_CHANGE)) == []


def test_claimed_names_adds_the_names_of_the_claims() -> None:
    texts = ["A plan mentions SUMMARY_MAX_CHARS."]
    claimed = ["BODY_MAX_CHARS", "OTHER_BOUND"]
    assert claimed_names(texts, claimed) == {
        "SUMMARY_MAX_CHARS",
        "BODY_MAX_CHARS",
        "OTHER_BOUND",
    }
