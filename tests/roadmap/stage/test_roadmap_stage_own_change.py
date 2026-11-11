"""`devops roadmap stage`: refuse paths under the plan's own change folder (#3321)."""

from __future__ import annotations

from devops_cli.roadmap.stage.stage_change import StageGroup, check_proposal
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal

TREE = StagedTree(
    [
        "src/devops_cli/sample.py",
        "tests/test_sample.py",
        "openspec/changes/3307-other/proposal.md",
    ]
)


def _construct(**update: object) -> StageGroup:
    base = {
        "title": "A group",
        "kind": "behavior",
        "reads": ["src/devops_cli/sample.py"],
        "changes": ["src/devops_cli/sample.py"],
        "creates": [],
        "creates_lines": {},
        "test": "Write `test_x` in `tests/test_sample.py`",
        "implementation": "Do x in `src/devops_cli/sample.py`",
        "documentation": None,
        "verify": "uv run devops ci test tests/test_sample.py",
    }
    return StageGroup.model_construct(**{**base, **update})


def test_a_group_that_changes_the_own_change_folder_is_refused() -> None:
    path = "openspec/changes/3321-plan-check/proposal.md"
    group = _construct(changes=[path, "src/devops_cli/sample.py"])
    proposal = make_stage_proposal().model_copy(update={"groups": [group]})

    problems = check_proposal(
        proposal, ["comment-thread"], TREE, change="3321-plan-check", registry=()
    )

    matching = [p for p in problems if path in p and "3321-plan-check" in p]
    assert len(matching) == 1


def test_a_task_code_span_that_names_the_own_change_folder_is_refused() -> None:
    path = "openspec/changes/3321-plan-check/tasks.md"
    group = _construct(implementation=f"Write `{path}`.")
    proposal = make_stage_proposal(groups=[group])

    problems = check_proposal(
        proposal, ["comment-thread"], TREE, change="3321-plan-check", registry=()
    )

    matching = [p for p in problems if "Group 1" in p and path in p]
    assert len(matching) == 1


def test_a_group_that_names_another_change_folder_has_no_own_change_problem() -> None:
    path = "openspec/changes/3307-other/proposal.md"
    group = _construct(implementation=f"Read `{path}`.")
    proposal = make_stage_proposal(groups=[group])

    problems = check_proposal(
        proposal, ["comment-thread"], TREE, change="3321-plan-check", registry=()
    )

    assert not any("own change" in p.lower() or "3321-plan-check" in p for p in problems)
