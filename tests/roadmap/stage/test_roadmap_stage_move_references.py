"""The move-reference gate judges a move and the files that a person edits.

A group moves a module when it creates the module in another place. A group that edits a module
and creates a test moves nothing. The release tool writes `CHANGELOG.md`, and the change folders
are records, so no task group of a plan edits them to follow a move (#3373).
"""

from __future__ import annotations

import pytest

from devops_cli.roadmap.stage.stage_change import StageGroup, check_proposal, moved_modules
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal

OLD = "src/devops_cli/roadmap/stage_probe.py"
TREE = StagedTree(["src/devops_cli/sample.py"])


def _group(changes: list[str], creates: list[str]) -> StageGroup:
    return StageGroup.model_validate(
        {
            "title": "Change a module",
            "kind": "behavior",
            "reads": [],
            "changes": [*changes, *creates],
            "creates": creates,
            "creates_lines": dict.fromkeys(creates, 50),
            "test": "Write a test for the module",
            "implementation": "Change the module",
            "verify": "uv run devops ci test tests/roadmap/test_stage_probe.py",
        }
    )


@pytest.mark.parametrize(
    "creates",
    [
        ["tests/roadmap/test_stage_probe.py"],
        ["src/devops_cli/roadmap/stage_probe_helper.py"],
        ["tests/roadmap/test_new.py", "docs/new.md"],
    ],
)
def test_a_group_that_edits_a_module_and_creates_other_files_moves_nothing(
    creates: list[str],
) -> None:
    assert moved_modules([_group([OLD], creates)]) == []


@pytest.mark.parametrize(
    "created",
    [
        "src/devops_cli/roadmap/stage/stage_probe.py",
        "src/devops_cli/roadmap/stage/probe.py",
        "src/devops_cli/roadmap/other/stage_probe.py",
    ],
)
def test_a_group_that_creates_the_module_in_another_place_moves_it(created: str) -> None:
    moved = moved_modules([_group([OLD], [created, "tests/roadmap/test_new.py"])])

    assert moved == [(OLD, "devops_cli.roadmap.stage_probe")]


@pytest.mark.parametrize(
    "path",
    [
        "CHANGELOG.md",
        "openspec/changes/3253-map-all-issue-requirements-to-a/proposal.md",
        "openspec/changes/archive/2026-11-08-3373-a-move-plan-covers/tasks.md",
        "docs/adr/0001-record.md",
    ],
)
def test_the_files_of_a_tool_or_a_record_need_no_task_group(path: str) -> None:
    assert (
        check_proposal(
            make_stage_proposal(), ["comment-thread"], TREE, references=[path], registry=()
        )
        == []
    )


@pytest.mark.parametrize(
    "path",
    ["docs/ROADMAP_WORKFLOW.md", "tests/roadmap/test_x.py", "src/devops_cli/roadmap/caller.py"],
)
def test_any_other_file_that_names_a_moved_module_still_needs_a_task_group(path: str) -> None:
    problems = check_proposal(
        make_stage_proposal(), ["comment-thread"], TREE, references=[path], registry=()
    )

    assert any(path in problem for problem in problems)
