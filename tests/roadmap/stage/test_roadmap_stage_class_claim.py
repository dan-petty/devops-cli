"""`check_proposal`: a design claim about an internal class quotes the class at the staged commit
(#3407)."""

from __future__ import annotations

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stage.stage_change import (
    StageDecision,
    StageProposal,
    check_proposal,
    content_problems,
)
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal
from tests.support.paths import REPO_ROOT

TREE = StagedTree(["src/devops_cli/sample.py"])
# The text of `StagedTree` as a design line quotes it: the class keeps the tracked paths and no
# file text.
STAGED_TREE_SOURCE = (
    "class StagedTree:\n"
    "    @classmethod\n"
    "    def read(cls, source: Path, *, operation: str) -> Self:\n"
    '        listing = git(source, "ls-files", "-z", operation=operation)\n'
    '        return cls((path for path in listing.split("\\0") if path), source=source)\n'
)
CLASSES = {"StagedTree": STAGED_TREE_SOURCE}
PLAN_CHECK_FILE = "src/devops_cli/roadmap/stage/stage_change.py"
MESSAGES_FILE = "src/devops_cli/lang/en/messages.py"
MODELS_FILE = "src/devops_cli/roadmap/stage/stage_models.py"
STEP_FILES_FILE = "src/devops_cli/roadmap/step_files.py"
TEST_FILE = "tests/roadmap/stage/test_roadmap_stage_class_claim.py"
SELF_ACCEPTANCE_TEST = (
    "Write a test that builds the plan's own `StageProposal` and asserts that `content_problems` "
    "returns no problem for it, and that quotes `ls-files`; it fails on the base"
)


def _plan(decision: str) -> StageProposal:
    """The sample plan with one design decision."""
    return make_stage_proposal(
        decisions=[StageDecision(decision=decision, reason="It is the simplest fix.")]
    )


def _problems(decision: str, *, classes: dict[str, str] | None = None) -> list[str]:
    return check_proposal(
        _plan(decision),
        ["comment-thread"],
        TREE,
        classes=CLASSES if classes is None else classes,
        registry=(),
    )


def test_class_sources_reads_a_class_with_no_base() -> None:
    from devops_cli.roadmap.stage.stage_models import class_sources

    sources = class_sources(REPO_ROOT, "HEAD", ["StagedTree"])

    assert "ls-files" in sources["StagedTree"]


def test_a_decision_that_names_a_class_with_no_quote_is_refused() -> None:
    problems = _problems("`StagedTree` holds the file text of the staged commit.")

    assert len(problems) == 1
    assert "StagedTree" in problems[0]


def test_a_decision_that_quotes_the_class_passes() -> None:
    problems = _problems("`StagedTree.read` keeps the tracked paths with `ls-files`.")

    assert problems == []


def test_a_quote_the_class_lacks_is_refused() -> None:
    problems = _problems("`StagedTree` holds the `file text` of the commit.")

    assert len(problems) == 1
    assert "StagedTree" in problems[0]


def test_a_name_that_no_class_under_src_defines_is_no_claim() -> None:
    from devops_cli.roadmap.stage.stage_models import class_sources

    assert class_sources(REPO_ROOT, "HEAD", ["ConfigDict"]) == {}

    assert _problems("`ConfigDict` refuses an unknown field.") == []


def test_a_quote_of_two_characters_is_refused() -> None:
    problems = _problems("`StagedTree` holds `ls` in its reader.")

    assert len(problems) == 1
    assert "StagedTree" in problems[0]


def test_the_problem_names_the_class_and_the_section() -> None:
    problems = _problems("`StagedTree` holds the file text of the staged commit.")

    assert problems == [
        MESSAGES.roadmap.stage_problem_class_claim.format(
            name="StagedTree", section="design decision"
        )
    ]


def _task_group_classes() -> dict[str, str]:
    """The source of `TaskGroup` at the staged commit, as the stage job reads it."""
    from devops_cli.roadmap.stage.stage_models import class_sources

    return class_sources(REPO_ROOT, "HEAD", ["TaskGroup"])


def test_a_member_claim_the_staged_class_lacks_is_refused() -> None:
    problems = _problems(
        "`TaskGroup.kind` carries the kind of the group, and `class TaskGroup:` shows no such "
        "member.",
        classes=_task_group_classes(),
    )

    assert problems == [
        MESSAGES.roadmap.stage_problem_class_member.format(
            name="TaskGroup", member="kind", section="design decision"
        )
    ]


def test_a_member_claim_the_staged_class_defines_passes() -> None:
    problems = _problems(
        "`TaskGroup.tasks` holds the tasks of the group, as `tasks: tuple[GroupTask, ...]` shows.",
        classes=_task_group_classes(),
    )

    assert problems == []


def test_the_member_rule_accepts_the_plan_of_this_change() -> None:
    """The plan's own acceptance test (#3404): the plan extends the plan check, so it builds its
    own `StageProposal` and asserts that `content_problems` returns no problem for it."""
    group = (
        make_stage_proposal()
        .groups[0]
        .model_copy(
            update={
                "title": "Refuse a member that the staged class lacks",
                "reads": [MODELS_FILE, STEP_FILES_FILE],
                "changes": [PLAN_CHECK_FILE, MODELS_FILE, MESSAGES_FILE, TEST_FILE],
                "creates": [TEST_FILE],
                "creates_lines": {TEST_FILE: 90},
                "test": (
                    "Write `test_the_member_rule_accepts_the_plan_of_this_change` in "
                    f"`{TEST_FILE}` first, build the plan's own `StageProposal`, assert that "
                    "`content_problems` returns no problem for it, and add "
                    "`parse_class_members`; it fails on the base"
                ),
                "implementation": (
                    "Add `parse_class_members` to "
                    "`src/devops_cli/roadmap/stage/stage_models.py` and refuse a member that the "
                    "class body lacks in `src/devops_cli/roadmap/stage/stage_change.py`"
                ),
                "verify": f"uv run devops ci test {TEST_FILE}",
            }
        )
    )
    plan = make_stage_proposal(
        summary="Refuse a member that the staged class lacks",
        why=(
            "Issue #3458: the plan of #3417 claimed that `TaskGroup` carries its kind, and the "
            "class body holds no such member."
        ),
        what_changes=[
            f"`{PLAN_CHECK_FILE}` refuses a `Class.member` claim that the class body lacks.",
            f"`{MODELS_FILE}` gives the members of a class body.",
            f"`{MESSAGES_FILE}` gains the message of the member-claim problem.",
            f"`{TEST_FILE}` pins the rule.",
        ],
        feasibility=[
            "`read_file` of `src/devops_cli/roadmap/step_files.py` showed `class TaskGroup:` and "
            "`tasks: tuple[GroupTask, ...]`, and the body holds no `kind` member, so the change "
            "adds `parse_class_members`."
        ],
        existing_tool=(
            "No open tool covers the check, so the change builds it: about 2,000 tokens to build, "
            "1,000 tokens for each later fix, and about 30 minutes of elapsed time."
        ),
        groups=[group],
        builds_own=True,
    )

    assert content_problems(plan) == []


def test_the_plan_check_accepts_the_plan_of_this_change() -> None:
    group = (
        make_stage_proposal()
        .groups[0]
        .model_copy(
            update={
                "reads": [MODELS_FILE],
                "changes": [PLAN_CHECK_FILE, MODELS_FILE, MESSAGES_FILE, TEST_FILE],
                "creates": [TEST_FILE],
                "creates_lines": {TEST_FILE: 60},
                "test": SELF_ACCEPTANCE_TEST,
                "implementation": (
                    "Add `class_claim_problems` to `src/devops_cli/roadmap/stage/stage_change.py`"
                ),
                "verify": f"uv run devops ci test {TEST_FILE}",
            }
        )
    )
    plan = make_stage_proposal(
        summary="Refuse a class claim that the source lacks",
        why=(
            "Issue #3407: a plan names `StagedTree` and claims that the class holds the file text, "
            "and the class keeps the tracked paths only."
        ),
        what_changes=[
            f"`{PLAN_CHECK_FILE}` refuses a class claim with no quote of the class.",
            f"`{MODELS_FILE}` reads the source of a class at the staged commit.",
            f"`{MESSAGES_FILE}` gains the message of the class-claim problem.",
            f"`{TEST_FILE}` pins the rule.",
        ],
        feasibility=[
            "`read_file` of `src/devops_cli/roadmap/stage/stage_paths.py` showed "
            "`class StagedTree:` and `ls-files`, so the class keeps the tracked paths and no file "
            "text."
        ],
        existing_tool=(
            "No open tool covers the check, so the change builds it: about 8,000 tokens to build, "
            "2,000 tokens for each later fix, and about 1 day of elapsed time."
        ),
        groups=[group],
        builds_own=True,
    )

    assert content_problems(plan) == []
